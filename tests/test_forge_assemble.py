"""Integration tests for Forge run assembly and skill learning."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from luna.forge.assemble import assemble_run
from luna.forge.models import CheckReport
from luna.forge.planner import build_plan
from luna.forge.runs import claim_task, create_run, get_run, submit_task
from luna.forge.skill_import import import_repo_skills
from luna.forge.vocab import seed_forge_vocabulary
from luna.graph.schema import GRAPH_FORGE_INDEX, TASK_TYPE_SOFTWARE_BUILD, run_graph_name

pytestmark = pytest.mark.integration

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
T0 = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)
PROMPT = "build me a portfolio website with React"


@pytest.fixture
def atlas(live_store, tmp_graph):
    seed_forge_vocabulary(live_store, tmp_graph)
    import_repo_skills(live_store, SKILLS_ROOT, tmp_graph)
    return tmp_graph


@pytest.fixture
def run_ids(live_store):
    ids: list[str] = []
    yield ids
    for rid in ids:
        live_store.delete_graph(run_graph_name(rid))
        live_store.query(
            GRAPH_FORGE_INDEX, "MATCH (f:ForgeRun {run_id: $id}) DELETE f", {"id": rid}
        )


@pytest.fixture
def rid(live_store, atlas, run_ids):
    run_id = f"test_{uuid.uuid4().hex[:10]}"
    run_ids.append(run_id)
    draft = build_plan(live_store, PROMPT, atlas_graph=atlas)
    create_run(live_store, draft, PROMPT, "s0", run_id=run_id, now=T0)
    return run_id


def do_task(store, atlas, rid, task_id, files, checks):
    claim_task(store, rid, task_id, "s1", now=T0)
    res = submit_task(
        store, rid, task_id, "s1", f"did {task_id}", files,
        [CheckReport(id=c, passed=ok) for c, ok in checks.items()], atlas_graph=atlas, now=T0,
    )
    assert res.accepted, res.errors


def submit_all(store, atlas, rid):
    do_task(store, atlas, rid, "scaffold_project", ["package.json", "src/main.tsx"],
            {"runs": True, "readme": True})
    do_task(store, atlas, rid, "implement_frontend", ["src/main.tsx", "src/App.tsx"],
            {"routes": True, "responsive": True, "a11y": False})
    do_task(store, atlas, rid, "verify_contracts", [],
            {"build": True, "smoke": True, "contracts": True})


def score(store, atlas, skill_id):
    return store.query(
        atlas,
        "MATCH (:Skill {id: $id})-[r:SUCCEEDED_ON]->(:TaskType {name: $tt}) RETURN r.score AS s",
        {"id": skill_id, "tt": TASK_TYPE_SOFTWARE_BUILD},
    )[0]["s"]


class RaisingLLM:
    def info(self):
        return {"reachable": True}

    def complete_text(self, system, user, **kw):
        raise RuntimeError("boom")


class FakeLLM:
    def info(self):
        return {"reachable": True}

    def complete_text(self, system, user, **kw):
        return "LLM summary"


def test_assemble_incomplete_lists_missing(live_store, atlas, rid):
    rep = assemble_run(live_store, rid, atlas_graph=atlas)
    assert rep.status == "incomplete"
    assert rep.missing == ["implement_frontend", "scaffold_project", "verify_contracts"]
    assert {"task_id": "scaffold_project", "kind": "missing"} in rep.gaps
    assert get_run(live_store, rid)["run"]["status"] != "assembled"


def test_assemble_complete_overlaps_and_gaps(live_store, atlas, rid):
    submit_all(live_store, atlas, rid)
    rep = assemble_run(live_store, rid, atlas_graph=atlas)
    assert rep.status == "complete"
    assert rep.overlaps == {"src/main.tsx": ["implement_frontend", "scaffold_project"]}
    assert {"task_id": "implement_frontend", "kind": "failed_checks", "failed": ["a11y"]} in rep.gaps
    assert rep.summary.startswith("3/3 tasks complete across 3 waves")
    assert [t["task_id"] for t in rep.tasks] == [
        "scaffold_project", "implement_frontend", "verify_contracts",
    ]
    fe = rep.tasks[1]
    assert fe["checks_passed"] == 2 and fe["checks_total"] == 3 and fe["wave"] == 1
    view = get_run(live_store, rid)
    assert view["run"]["status"] == "assembled"
    assert view["report"]["status"] == "complete"
    idx = live_store.query(
        GRAPH_FORGE_INDEX, "MATCH (f:ForgeRun {run_id: $id}) RETURN f.status AS s", {"id": rid}
    )
    assert idx[0]["s"] == "assembled"


def test_assemble_learning_applies_once(live_store, atlas, rid):
    submit_all(live_store, atlas, rid)
    before = score(live_store, atlas, "react-vite-pages")
    assemble_run(live_store, rid, atlas_graph=atlas)
    mid = score(live_store, atlas, "react-vite-pages")
    assemble_run(live_store, rid, atlas_graph=atlas)
    after = score(live_store, atlas, "react-vite-pages")
    assert mid == pytest.approx(0.8 * before + 0.2 * (2 / 3))
    assert after == mid


def test_assemble_llm_failure_falls_back_to_template(live_store, atlas, rid):
    submit_all(live_store, atlas, rid)
    rep = assemble_run(live_store, rid, llm=RaisingLLM(), atlas_graph=atlas)
    assert rep.summary.startswith("3/3 tasks complete across 3 waves")


def test_assemble_uses_llm_summary(live_store, atlas, rid):
    submit_all(live_store, atlas, rid)
    rep = assemble_run(live_store, rid, llm=FakeLLM(), atlas_graph=atlas)
    assert rep.summary == "LLM summary"


def test_assemble_learning_failure_releases_claim_and_retries(live_store, atlas, rid, monkeypatch):
    import luna.forge.assemble as asm

    submit_all(live_store, atlas, rid)
    before = score(live_store, atlas, "react-vite-pages")

    def boom(*a, **k):
        raise RuntimeError("learner down")

    monkeypatch.setattr(asm, "update_skill_score", boom)
    with pytest.raises(RuntimeError):
        assemble_run(live_store, rid, atlas_graph=atlas)
    rows = live_store.query(
        run_graph_name(rid), "MATCH (r:Run) WHERE r.learned_at IS NULL RETURN r.id AS id"
    )
    assert rows
    assert get_run(live_store, rid)["run"]["status"] != "assembled"
    monkeypatch.undo()

    assemble_run(live_store, rid, atlas_graph=atlas)
    assert get_run(live_store, rid)["run"]["status"] == "assembled"
    assert score(live_store, atlas, "react-vite-pages") == pytest.approx(
        0.8 * before + 0.2 * (2 / 3)
    )
    assemble_run(live_store, rid, atlas_graph=atlas)
    assert score(live_store, atlas, "react-vite-pages") == pytest.approx(
        0.8 * before + 0.2 * (2 / 3)
    )


def test_assemble_zero_checks_reward_one(live_store, atlas, rid):
    live_store.query(
        atlas,
        "MATCH (:Skill {id: 'project-scaffold'})-[:HAS_CHECK]->(c:ChecklistItem) DETACH DELETE c",
    )
    do_task(live_store, atlas, rid, "scaffold_project", ["package.json"], {})
    do_task(live_store, atlas, rid, "implement_frontend", [],
            {"routes": True, "responsive": True, "a11y": True})
    do_task(live_store, atlas, rid, "verify_contracts", [],
            {"build": True, "smoke": True, "contracts": True})
    before = score(live_store, atlas, "project-scaffold")
    rep = assemble_run(live_store, rid, atlas_graph=atlas)
    assert rep.tasks[0]["checks_total"] == 0
    assert score(live_store, atlas, "project-scaffold") == pytest.approx(0.8 * before + 0.2)
