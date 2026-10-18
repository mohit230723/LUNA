"""Integration tests for the Forge vocabulary seed and skill importer."""

import pytest

from luna.forge.models import ForgeError
from luna.forge.skill_import import import_skill, import_skill_dir, set_skill_status
from luna.forge.skill_parse import parse_skill_md
from luna.forge.vocab import seed_forge_vocabulary

pytestmark = pytest.mark.integration

SAMPLE_FRONTEND = """---
name: React Vite Pages
description: Build pages for a React + Vite site.
capabilities: [implement_frontend]
technologies: [React, Vite]
checklist:
  - id: routes
    text: Every page has a route.
---
Core instructions.

## Routing
Use react-router.

## Layout
Mobile first.
"""


class FakeLLM:
    def __init__(self, reachable=True, fail=False):
        self.reachable, self.fail = reachable, fail

    def info(self):
        return {"reachable": self.reachable}

    def complete_json(self, system, user, schema):
        if self.fail:
            raise RuntimeError("boom")
        return {"capabilities": ["implement_backend", "nope"], "technologies": ["Express"]}


@pytest.fixture
def atlas(live_store, tmp_graph):
    seed_forge_vocabulary(live_store, tmp_graph)
    return tmp_graph


def doc_with(id="s1", capabilities=(), technologies=(), requires=(), body="Body.", sections=None):
    md = (
        f"---\nname: Skill {id}\ndescription: d\ncapabilities: {list(capabilities)}\n"
        f"technologies: {list(technologies)}\nrequires: {list(requires)}\n---\n{body}\n"
    )
    for s in sections or []:
        md += f"\n## {s}\ncontent of {s}\n"
    return parse_skill_md(md, default_id=id)


def q(store, g, cypher, params=None):
    return store.query(g, cypher, params)


def test_vocab_seed_is_idempotent(live_store, atlas):
    seed_forge_vocabulary(live_store, atlas)
    rows = q(live_store, atlas, "MATCH (c:Capability) RETURN count(c) AS n")
    assert rows[0]["n"] == 6
    roles = q(live_store, atlas, "MATCH (c:Capability {name: $n}) RETURN c.role AS r", {"n": "scaffold_project"})
    assert roles[0]["r"] == "foundation"
    edges = q(live_store, atlas, "MATCH (:Capability)-[r:BEFORE]->(:Capability) RETURN count(r) AS n")
    assert edges[0]["n"] == 6
    al = q(live_store, atlas, "MATCH (t:Technology {name: $n}) RETURN t.aliases AS a", {"n": "Next.js"})
    assert al[0]["a"] == ["next", "nextjs", "next.js"]


def test_import_creates_skill_sections_checks_and_links(live_store, atlas):
    res = import_skill(live_store, parse_skill_md(SAMPLE_FRONTEND, default_id="react-vite-pages"), "repo", atlas)
    assert res.status == "approved" and res.changed and res.warnings == []
    p = {"i": "react-vite-pages"}
    cap = q(live_store, atlas, "MATCH (:Skill {id: $i})-[:PROVIDES]->(c:Capability) RETURN c.name AS n", p)
    assert [r["n"] for r in cap] == ["implement_frontend"]
    t = q(live_store, atlas, "MATCH (:Skill {id: $i})-[:TARGETS]->(t:Technology) RETURN t.name AS n", p)
    assert sorted(r["n"] for r in t) == ["React", "Vite"]
    s = q(live_store, atlas, "MATCH (:Skill {id: $i})-[:HAS_SECTION]->(x:Section) RETURN x.id AS id ORDER BY x.order", p)
    assert [r["id"] for r in s] == ["react-vite-pages#routing", "react-vite-pages#layout"]
    c = q(live_store, atlas, "MATCH (:Skill {id: $i})-[:HAS_CHECK]->(x:ChecklistItem) RETURN count(x) AS n", p)
    assert c[0]["n"] == 1


def test_import_unknown_names_warn_without_edges(live_store, atlas):
    res = import_skill(live_store, doc_with(capabilities=["fly"], technologies=["Cobol"], requires=["ghost"]), "repo", atlas)
    assert sorted(res.warnings) == ["unknown capability 'fly'", "unknown required skill 'ghost'", "unknown technology 'Cobol'"]
    n = q(live_store, atlas, "MATCH (:Skill {id: 's1'})-[r:PROVIDES|TARGETS|REQUIRES]->() RETURN count(r) AS n")
    assert n[0]["n"] == 0


def test_import_same_hash_is_noop_and_keeps_score(live_store, atlas):
    doc = doc_with(capabilities=["implement_backend"])
    import_skill(live_store, doc, "repo", atlas)
    q(live_store, atlas, "MATCH (:Skill {id: 's1'})-[r:SUCCEEDED_ON]->() SET r.score = 0.33, r.runs = 4")
    res = import_skill(live_store, doc, "repo", atlas)
    assert res.changed is False
    r = q(live_store, atlas, "MATCH (:Skill {id: 's1'})-[r:SUCCEEDED_ON]->() RETURN r.score AS s, r.runs AS n")
    assert r[0]["s"] == 0.33 and r[0]["n"] == 4


def test_import_new_skill_initial_score(live_store, atlas):
    import_skill(live_store, doc_with(), "repo", atlas)
    r = q(live_store, atlas, "MATCH (:Skill {id: 's1'})-[r:SUCCEEDED_ON]->(t:TaskType) RETURN r.score AS s, r.runs AS n, t.name AS t")
    assert r[0]["s"] == 0.7 and r[0]["n"] == 0 and r[0]["t"] == "software_build"


def test_import_changed_hash_replaces_sections(live_store, atlas):
    import_skill(live_store, doc_with(sections=["Old"]), "repo", atlas)
    q(live_store, atlas, "MATCH (:Skill {id: 's1'})-[r:SUCCEEDED_ON]->() SET r.score = 0.4")
    res = import_skill(live_store, doc_with(sections=["Fresh"]), "repo", atlas)
    assert res.changed
    rows = q(live_store, atlas, "MATCH (:Skill {id: 's1'})-[:HAS_SECTION]->(x:Section) RETURN x.slug AS s")
    assert [r["s"] for r in rows] == ["fresh"]
    gone = q(live_store, atlas, "MATCH (x:Section {id: 's1#old'}) RETURN count(x) AS n")
    assert gone[0]["n"] == 0
    sc = q(live_store, atlas, "MATCH (:Skill {id: 's1'})-[r:SUCCEEDED_ON]->() RETURN r.score AS s")
    assert sc[0]["s"] == 0.4


def test_import_rejects_requires_cycle(live_store, atlas):
    import_skill(live_store, doc_with(id="a", requires=[]), "repo", atlas)
    import_skill(live_store, doc_with(id="b", requires=["a"]), "repo", atlas)
    with pytest.raises(ForgeError) as e:
        import_skill(live_store, doc_with(id="a", requires=["b"]), "repo", atlas)
    assert e.value.code == "invalid" and "cycle" in str(e.value)
    n = q(live_store, atlas, "MATCH (:Skill {id: 'a'})-[r:REQUIRES]->() RETURN count(r) AS n")
    assert n[0]["n"] == 0


@pytest.mark.parametrize("source,status", [("repo", "approved"), ("upload", "pending_review"), ("mcp", "pending_review")])
def test_import_status_by_source(live_store, atlas, source, status):
    assert import_skill(live_store, doc_with(), source, atlas).status == status


def test_reimport_keeps_status_until_hash_changes(live_store, atlas):
    import_skill(live_store, doc_with(), "upload", atlas)
    set_skill_status(live_store, "s1", "approved", atlas)
    assert import_skill(live_store, doc_with(), "upload", atlas).status == "approved"
    assert import_skill(live_store, doc_with(body="Different."), "upload", atlas).status == "pending_review"


def test_set_skill_status_and_missing(live_store, atlas):
    import_skill(live_store, doc_with(), "mcp", atlas)
    set_skill_status(live_store, "s1", "approved", atlas)
    st = q(live_store, atlas, "MATCH (s:Skill {id: 's1'}) RETURN s.status AS s")
    assert st[0]["s"] == "approved"
    with pytest.raises(ForgeError) as e:
        set_skill_status(live_store, "ghost", "rejected", atlas)
    assert e.value.code == "not_found"


def test_llm_suggestions_are_warnings_only(live_store, atlas):
    res = import_skill(live_store, doc_with(), "repo", atlas, llm=FakeLLM())
    assert sorted(res.warnings) == ["suggested capability 'implement_backend'", "suggested technology 'Express'"]
    n = q(live_store, atlas, "MATCH (:Skill {id: 's1'})-[r:PROVIDES|TARGETS]->() RETURN count(r) AS n")
    assert n[0]["n"] == 0


def test_llm_failure_adds_warning(live_store, atlas):
    res = import_skill(live_store, doc_with(), "repo", atlas, llm=FakeLLM(fail=True))
    assert res.warnings == ["llm suggestion unavailable"]


def test_import_skill_dir(live_store, atlas, tmp_path):
    d = tmp_path / "my-skill"
    (d / "references").mkdir(parents=True)
    (d / "SKILL.md").write_text(SAMPLE_FRONTEND, encoding="utf-8")
    (d / "references" / "forms.md").write_text("# Forms\nUse zod.", encoding="utf-8")
    res = import_skill_dir(live_store, d, atlas_graph=atlas)
    assert res.skill_id == "my-skill" and res.status == "approved"
    n = q(live_store, atlas, "MATCH (:Skill {id: 'my-skill'})-[:HAS_SECTION]->(x:Section) RETURN count(x) AS n")
    assert n[0]["n"] == 3
