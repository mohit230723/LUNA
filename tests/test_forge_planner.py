"""Integration tests for the starter skill library and the graph-native planner."""

from pathlib import Path

import pytest

from luna.forge.planner import build_plan
from luna.forge.skill_import import import_repo_skills, import_skill
from luna.forge.skill_parse import parse_skill_md
from luna.forge.vocab import seed_forge_vocabulary

pytestmark = pytest.mark.integration

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"

better_frontend_doc = parse_skill_md(
    """---
name: Better Frontend
description: An uploaded frontend skill that targets everything.
capabilities: [implement_frontend]
technologies: [React, Vite, TypeScript, TailwindCSS, Next.js]
---
Do frontend things.

## One
a

## Two
b
""",
    default_id="better-frontend",
)


class FakeLLM:
    def __init__(self, reachable=True, fail=False, picks=None):
        self.reachable, self.fail = reachable, fail
        self.picks = picks or {"capabilities": ["implement_backend", "teleport"], "technologies": ["Express", "Cobol"]}

    def info(self):
        return {"reachable": self.reachable}

    def complete_json(self, system, user, schema):
        if self.fail:
            raise RuntimeError("boom")
        return self.picks


@pytest.fixture
def atlas(live_store, tmp_graph):
    seed_forge_vocabulary(live_store, tmp_graph)
    import_repo_skills(live_store, SKILLS_ROOT, tmp_graph)
    return tmp_graph


def task(d, task_id):
    return next(t for t in d.tasks if t.task_id == task_id)


def restrict(store, g, skill_id):
    store.query(g, "MATCH (s:Skill {id: $id}) SET s.restricted = true", {"id": skill_id})


def test_repo_skills_import_clean(live_store, atlas):
    results = import_repo_skills(live_store, SKILLS_ROOT, atlas)
    assert len(results) == 6 and all(r.status == "approved" and r.warnings == [] for r in results)
    rows = live_store.query(atlas, "MATCH (a:Skill)-[:REQUIRES]->(b:Skill) RETURN a.id AS a, b.id AS b")
    assert sorted((r["a"], r["b"]) for r in rows) == [
        ("backend-api", "project-scaffold"), ("react-vite-pages", "project-scaffold"), ("ui-styling", "project-scaffold")]
    checks = live_store.query(
        atlas, "MATCH (:Skill {id: $id})-[:HAS_CHECK]->(c:ChecklistItem) RETURN c.check_id AS c", {"id": "qa-verification"})
    assert sorted(r["c"] for r in checks) == ["build", "contracts", "smoke"]


def test_repo_skills_retry_requires_in_fresh_graph(live_store, tmp_graph):
    seed_forge_vocabulary(live_store, tmp_graph)
    results = import_repo_skills(live_store, SKILLS_ROOT, tmp_graph)
    assert [r.skill_id for r in results] == sorted(r.skill_id for r in results)
    assert all(r.warnings == [] and r.changed for r in results)


def test_repo_skill_bodies_are_substantial():
    for d in sorted(p for p in SKILLS_ROOT.iterdir() if (p / "SKILL.md").is_file()):
        text = (d / "SKILL.md").read_text(encoding="utf-8")
        doc = parse_skill_md(text, default_id=d.name)
        body_lines = len(text.split("\n---", 1)[1].strip().splitlines())
        assert 30 <= body_lines <= 80, (d.name, body_lines)
        assert len(doc.sections) >= 2, d.name


def test_plan_portfolio_website(live_store, atlas):
    d = build_plan(live_store, "build me a portfolio website with React", atlas_graph=atlas)
    assert d.status == "planned"
    assert d.waves == [["scaffold_project"], ["implement_frontend"], ["verify_contracts"]]
    assert {t.task_id: t.skill_id for t in d.tasks} == {
        "scaffold_project": "project-scaffold", "implement_frontend": "react-vite-pages", "verify_contracts": "qa-verification"}
    assert task(d, "implement_frontend").depends_on == ["scaffold_project"]
    assert task(d, "verify_contracts").depends_on == ["implement_frontend", "scaffold_project"]
    assert task(d, "implement_frontend").title == "Implement frontend"
    assert [t.wave for t in d.tasks] == [0, 1, 2]
    assert d.matched_capabilities == ["implement_frontend"] and d.matched_technologies == ["React"]


def test_plan_styling_runs_parallel_to_pages(live_store, atlas):
    d = build_plan(live_store, "build a website with tailwind styling", atlas_graph=atlas)
    assert d.waves[1] == ["implement_frontend", "style_ui"]
    assert task(d, "style_ui").skill_id == "ui-styling"


def test_plan_fullstack_orders_db_backend_frontend(live_store, atlas):
    d = build_plan(live_store, "build a todo web app with a FastAPI backend and sqlite database", atlas_graph=atlas)
    assert d.waves == [["scaffold_project"], ["implement_database"], ["implement_backend"], ["implement_frontend"], ["verify_contracts"]]
    assert task(d, "implement_backend").skill_id == "backend-api"
    assert task(d, "implement_database").skill_id == "database-schema"


def test_plan_with_react_adds_no_backend(live_store, atlas):
    d = build_plan(live_store, "a web app with React", atlas_graph=atlas)
    assert {t.task_id for t in d.tasks} == {"scaffold_project", "implement_frontend", "verify_contracts"}


def test_plan_stack_hints_match(live_store, atlas):
    assert build_plan(live_store, "make something", ["nextjs", "website"], atlas_graph=atlas).status == "planned"


def test_plan_technology_only_fallback(live_store, atlas):
    d = build_plan(live_store, "use fastapi", atlas_graph=atlas)
    assert d.status == "planned"
    assert d.matched_capabilities == ["implement_backend"]
    assert task(d, "implement_backend").skill_id == "backend-api"


def test_plan_unknown_stack_needs_input(live_store, atlas):
    d = build_plan(live_store, "build me a Flutter mobile app", atlas_graph=atlas)
    assert d.status == "needs_input" and "implement_frontend" in d.question and d.tasks == []
    assert d.question.startswith("I couldn't map that request to LUNA's skills. Which of these should I plan for: ")


def test_plan_excludes_pending_and_restricted(live_store, atlas):
    import_skill(live_store, better_frontend_doc, "upload", atlas)  # pending_review, higher overlap
    d = build_plan(live_store, "website with React", atlas_graph=atlas)
    assert task(d, "implement_frontend").skill_id == "react-vite-pages"
    assert any(c.rejected_reason == "pending_review" for c in d.candidates["implement_frontend"])


def test_plan_higher_overlap_wins_and_ties_break_by_id(live_store, atlas):
    import_skill(live_store, better_frontend_doc, "repo", atlas)  # approved, more tech overlap
    d = build_plan(live_store, "website with React, Vite and tailwind", atlas_graph=atlas)
    assert task(d, "implement_frontend").skill_id == "better-frontend"
    recs = {c.skill_id: c for c in d.candidates["implement_frontend"]}
    assert recs["better-frontend"].rejected_reason == "" and recs["react-vite-pages"].rejected_reason == "lower score"
    # Equal overlap and score: lexicographically smallest id wins.
    d2 = build_plan(live_store, "website with React", atlas_graph=atlas)
    assert task(d2, "implement_frontend").skill_id == "better-frontend"


def test_plan_succeeded_on_score_breaks_overlap_tie(live_store, atlas):
    import_skill(live_store, better_frontend_doc, "repo", atlas)
    live_store.query(atlas, "MATCH (:Skill {id: 'better-frontend'})-[r:SUCCEEDED_ON]->() SET r.score = 0.2")
    d = build_plan(live_store, "website with React", atlas_graph=atlas)
    assert task(d, "implement_frontend").skill_id == "react-vite-pages"


def test_plan_unskilled_task(live_store, atlas):
    restrict(live_store, atlas, "qa-verification")
    d = build_plan(live_store, "website with React", atlas_graph=atlas)
    assert "verify_contracts" not in {t.task_id for t in d.tasks}
    restrict(live_store, atlas, "react-vite-pages")
    d = build_plan(live_store, "website with React", atlas_graph=atlas)
    assert task(d, "implement_frontend").skill_id == ""
    assert [c.rejected_reason for c in d.candidates["implement_frontend"]] == ["restricted"]


def test_plan_required_skill_adds_capability(live_store, atlas):
    # Remove the foundation role so scaffold_project is only added via REQUIRES.
    live_store.query(atlas, "MATCH (c:Capability {name: 'scaffold_project'}) SET c.role = 'normal'")
    d = build_plan(live_store, "an api server", atlas_graph=atlas)
    assert task(d, "scaffold_project").skill_id == "project-scaffold"
    assert task(d, "implement_backend").depends_on == ["scaffold_project"]
    assert d.candidates["scaffold_project"][0].rejected_reason == "required by backend-api"


def test_plan_llm_picks_are_unioned(live_store, atlas):
    d = build_plan(live_store, "website with React", llm=FakeLLM(), atlas_graph=atlas)
    assert "implement_backend" in d.matched_capabilities and "Express" in d.matched_technologies
    assert "teleport" not in d.matched_capabilities


def test_plan_llm_failure_is_swallowed(live_store, atlas):
    a = build_plan(live_store, "website with React", llm=FakeLLM(fail=True), atlas_graph=atlas)
    b = build_plan(live_store, "website with React", llm=FakeLLM(reachable=False), atlas_graph=atlas)
    assert a.model_dump() == b.model_dump() and a.status == "planned"


def test_plan_is_deterministic(live_store, atlas):
    a = build_plan(live_store, "website with React", atlas_graph=atlas)
    b = build_plan(live_store, "website with React", atlas_graph=atlas)
    assert a.model_dump() == b.model_dump()
