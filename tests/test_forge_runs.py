"""Integration tests for Forge run persistence, task lifecycle and briefings."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from luna.forge.briefing import RULES, build_briefing, get_section
from luna.forge.models import CheckReport, ForgeError, PlanDraft, PlanTask
from luna.forge.planner import build_plan
from luna.forge.runs import (
    claim_task,
    create_run,
    expire_leases,
    get_run,
    list_runs,
    set_run_status,
    submit_task,
)
from luna.forge.skill_import import import_repo_skills
from luna.forge.vocab import seed_forge_vocabulary
from luna.graph.schema import GRAPH_FORGE_INDEX, run_graph_name

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
    """Collect run ids created by a test and remove their graphs and index rows afterwards."""
    ids: list[str] = []
    yield ids
    for rid in ids:
        live_store.delete_graph(run_graph_name(rid))
        live_store.query(
            GRAPH_FORGE_INDEX, "MATCH (f:ForgeRun {run_id: $id}) DELETE f", {"id": rid}
        )


@pytest.fixture
def new_run(live_store, atlas, run_ids):
    def make(prompt=PROMPT, now=T0):
        rid = f"test_{uuid.uuid4().hex[:10]}"
        run_ids.append(rid)
        draft = build_plan(live_store, prompt, atlas_graph=atlas)
        return create_run(live_store, draft, prompt, "s0", run_id=rid, now=now)

    return make


@pytest.fixture
def rid(new_run):
    return new_run().run_id


def tasks_by_id(store, rid, now=T0):
    return {t["task_id"]: t for t in get_run(store, rid, now=now)["tasks"]}


def results_count(store, rid):
    return store.query(run_graph_name(rid), "MATCH (r:Result) RETURN count(r) AS n")[0]["n"]


def test_create_run_initial_states(live_store, new_run):
    plan = new_run()
    rid = plan.run_id
    assert plan.status == "planned" and plan.waves[0] == ["scaffold_project"]
    tasks = tasks_by_id(live_store, rid)
    assert tasks["scaffold_project"]["status"] == "ready"
    assert tasks["implement_frontend"]["status"] == "pending"
    assert tasks["verify_contracts"]["status"] == "pending"
    assert [t.status for t in plan.tasks] == ["ready", "pending", "pending"]
    idx = live_store.query(
        GRAPH_FORGE_INDEX, "MATCH (f:ForgeRun {run_id: $id}) RETURN f", {"id": rid}
    )
    assert len(idx) == 1
    row = idx[0]["f"]
    assert row["prompt"] == PROMPT and row["status"] == "planned" and row["task_count"] == 3
    assert row["created_at"] == T0.isoformat()
    deps = live_store.query(
        run_graph_name(rid),
        "MATCH (a:Task)-[:DEPENDS_ON]->(b:Task) RETURN a.id AS a, b.id AS b",
    )
    assert sorted((d["a"], d["b"]) for d in deps) == [
        ("implement_frontend", "scaffold_project"),
        ("verify_contracts", "implement_frontend"),
        ("verify_contracts", "scaffold_project"),
    ]


def test_create_run_records_assignment_and_candidates(live_store, new_run):
    rid = new_run().run_id
    t = tasks_by_id(live_store, rid)["implement_frontend"]
    assert t["assignment"]["skill_id"] == "react-vite-pages"
    assert t["assignment"]["reason"] == "best match"
    assert t["candidates"] == []


def test_create_run_required_reason_on_assignment(live_store, atlas, run_ids):
    live_store.query(atlas, "MATCH (c:Capability {name: 'scaffold_project'}) SET c.role = 'normal'")
    draft = build_plan(live_store, "an api server", atlas_graph=atlas)
    rid = f"test_{uuid.uuid4().hex[:10]}"
    run_ids.append(rid)
    create_run(live_store, draft, "an api server", "s0", run_id=rid, now=T0)
    t = tasks_by_id(live_store, rid)["scaffold_project"]
    assert t["assignment"]["reason"] == "required by backend-api"


def test_create_run_needs_input(live_store, atlas, run_ids):
    draft = build_plan(live_store, "build me a Flutter mobile app", atlas_graph=atlas)
    rid = f"test_{uuid.uuid4().hex[:10]}"
    run_ids.append(rid)
    plan = create_run(live_store, draft, "flutter", "s0", run_id=rid, now=T0)
    assert plan.status == "needs_input" and plan.question and plan.tasks == []
    assert get_run(live_store, rid, now=T0)["run"]["status"] == "needs_input"


def test_create_run_duplicate_id_rejected(live_store, atlas, rid):
    draft = build_plan(live_store, PROMPT, atlas_graph=atlas)
    with pytest.raises(ForgeError) as e:
        create_run(live_store, draft, PROMPT, "s0", run_id=rid, now=T0)
    assert e.value.code == "invalid"


def test_claim_returns_task_and_renews_for_same_session(live_store, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    t = claim_task(live_store, rid, "scaffold_project", "s1", agent_label="sub-1", now=T0 + timedelta(minutes=10))
    assert t.status == "claimed" and t.task_id == "scaffold_project"
    row = tasks_by_id(live_store, rid, now=T0 + timedelta(minutes=11))["scaffold_project"]
    assert row["lease_expires_at"] == (T0 + timedelta(minutes=25)).isoformat()
    assert row["claimed_by"] == "s1" and row["agent_label"] == "sub-1"


def test_claim_lease_minutes_from_env(live_store, rid, monkeypatch):
    monkeypatch.setenv("LUNA_FORGE_LEASE_MIN", "5")
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    row = tasks_by_id(live_store, rid, now=T0)["scaffold_project"]
    assert row["lease_expires_at"] == (T0 + timedelta(minutes=5)).isoformat()


def test_claim_conflict_reports_expiry(live_store, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    with pytest.raises(ForgeError) as e:
        claim_task(live_store, rid, "scaffold_project", "s2", now=T0 + timedelta(minutes=1))
    assert e.value.code == "claim_conflict"
    assert str(e.value) == (
        f"task 'scaffold_project' is claimed by another session until {(T0 + timedelta(minutes=15)).isoformat()}"
    )
    assert claim_task(live_store, rid, "scaffold_project", "s2", now=T0 + timedelta(minutes=16)).status == "claimed"


def test_claim_not_ready_names_blockers(live_store, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    with pytest.raises(ForgeError, match=r"waiting on: scaffold_project \(claimed\)") as e:
        claim_task(live_store, rid, "implement_frontend", "s1", now=T0)
    assert e.value.code == "not_ready"
    assert str(e.value) == "task 'implement_frontend' is waiting on: scaffold_project (claimed)"


def test_unknown_run_and_task(live_store, rid):
    with pytest.raises(ForgeError) as e:
        claim_task(live_store, "nope_" + uuid.uuid4().hex[:6], "x", "s1", now=T0)
    assert e.value.code == "not_found" and "not found" in str(e.value)
    with pytest.raises(ForgeError) as e:
        claim_task(live_store, rid, "teleport", "s1", now=T0)
    assert e.value.code == "not_found"
    assert str(e.value) == f"task 'teleport' not found in run '{rid}'"
    with pytest.raises(ForgeError) as e:
        get_run(live_store, "nope_" + uuid.uuid4().hex[:6])
    assert e.value.code == "not_found"


def test_submit_unlocks_dependents(live_store, atlas, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    r = submit_task(
        live_store, rid, "scaffold_project", "s1", "done", ["package.json"],
        [CheckReport(id="runs", passed=True)], atlas, now=T0,
    )
    assert r.accepted and r.errors == [] and r.unlocked_tasks == ["implement_frontend"]
    tasks = tasks_by_id(live_store, rid)
    assert tasks["scaffold_project"]["status"] == "done"
    assert tasks["implement_frontend"]["status"] == "ready"
    assert tasks["verify_contracts"]["status"] == "pending"
    res = tasks["scaffold_project"]["result"]
    assert res["summary"] == "done" and res["files"] == ["package.json"]
    assert res["submitted_at"] == T0.isoformat()


def test_submit_missing_checks_count_as_failed(live_store, atlas, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    r = submit_task(
        live_store, rid, "scaffold_project", "s1", "done", ["package.json"],
        [CheckReport(id="runs", passed=True, note="npm run dev ok")], atlas, now=T0,
    )
    assert r.accepted
    rows = live_store.query(run_graph_name(rid), "MATCH (r:Result) RETURN r.checks_json AS c")
    checks = json.loads(rows[0]["c"])
    assert checks == [
        {"id": "runs", "passed": True, "note": "npm run dev ok"},
        {"id": "readme", "passed": False, "note": "not reported"},
    ]
    assert tasks_by_id(live_store, rid)["scaffold_project"]["result"]["checks"] == checks


@pytest.mark.parametrize(
    "files,checks,err",
    [
        (["../../etc/passwd"], [], "invalid path"),
        (["C:\\x"], [], "invalid path"),
        (["/abs"], [], "invalid path"),
        (["src\\..\\..\\x"], [], "invalid path"),
        ([""], [], "invalid path"),
        (["a" * 301], [], "exceeds 300 characters"),
        ([f"f{i}" for i in range(501)], [], "at most 500 files"),
        (["a"], [CheckReport(id="bogus", passed=True)], "unknown check 'bogus'"),
    ],
)
def test_submit_rejects_bad_paths_and_limits(live_store, atlas, rid, files, checks, err):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    r = submit_task(live_store, rid, "scaffold_project", "s1", "done", files, checks, atlas, now=T0)
    assert not r.accepted and any(err in e for e in r.errors), r.errors
    assert r.unlocked_tasks == []
    assert tasks_by_id(live_store, rid)["scaffold_project"]["status"] == "claimed"
    assert results_count(live_store, rid) == 0


def test_submit_accepts_path_at_limit(live_store, atlas, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    assert submit_task(live_store, rid, "scaffold_project", "s1", "ok", ["a" * 300], [], atlas, now=T0).accepted


DIAMOND = PlanDraft(
    status="planned",
    tasks=[
        PlanTask(task_id="a", title="A", capability="a", wave=0),
        PlanTask(task_id="b", title="B", capability="b", wave=0),
        PlanTask(task_id="c", title="C", capability="c", depends_on=["a", "b"], wave=1),
    ],
    waves=[["a", "b"], ["c"]],
)


@pytest.fixture
def diamond(live_store, run_ids):
    rid = f"test_{uuid.uuid4().hex[:10]}"
    run_ids.append(rid)
    create_run(live_store, DIAMOND, "diamond", "s0", run_id=rid, now=T0)
    return rid


class RacingStore:
    """Store proxy that runs ``before_write`` just before submit's Result write,
    i.e. after submit_task has read its task snapshot."""

    def __init__(self, store, before_write):
        self.store, self.before_write, self.fired = store, before_write, False

    def query(self, graph, cypher, params=None):
        if not self.fired and "HAS_RESULT" in cypher and "CREATE" in cypher:
            self.fired = True
            self.before_write()
        return self.store.query(graph, cypher, params)

    def __getattr__(self, name):
        return getattr(self.store, name)


def test_concurrent_sibling_submit_still_unlocks_dependent(live_store, atlas, diamond):
    rid = diamond
    claim_task(live_store, rid, "a", "s1", now=T0)
    claim_task(live_store, rid, "b", "s2", now=T0)

    def sibling_done_without_unlock():
        # The concurrent submit of b read a stale snapshot (a still claimed) and so did not unlock c.
        live_store.query(
            run_graph_name(rid),
            "MATCH (t:Task {id: 'b'}) SET t.status = 'done', t.claimed_by = '', t.lease_expires_at = ''",
        )

    racing = RacingStore(live_store, sibling_done_without_unlock)
    r = submit_task(racing, rid, "a", "s1", "done", ["a.txt"], [], atlas, now=T0)
    assert racing.fired and r.accepted and r.unlocked_tasks == ["c"]
    assert tasks_by_id(live_store, rid)["c"]["status"] == "ready"


def test_claim_pending_task_with_all_deps_done_promotes(live_store, atlas, diamond):
    rid = diamond
    live_store.query(run_graph_name(rid), "MATCH (t:Task) WHERE t.id IN ['a', 'b'] SET t.status = 'done'")
    assert tasks_by_id(live_store, rid)["c"]["status"] == "pending"
    t = claim_task(live_store, rid, "c", "s1", now=T0)
    assert t.status == "claimed"
    assert tasks_by_id(live_store, rid)["c"]["claimed_by"] == "s1"


def test_submit_rejects_long_summary(live_store, atlas, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    r = submit_task(live_store, rid, "scaffold_project", "s1", "x" * 20_001, ["a"], [], atlas, now=T0)
    assert not r.accepted and "summary exceeds 20000 characters" in r.errors
    assert results_count(live_store, rid) == 0


def test_submit_by_other_session_raises(live_store, atlas, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    with pytest.raises(ForgeError) as e:
        submit_task(live_store, rid, "scaffold_project", "s2", "done", ["a"], [], atlas, now=T0)
    assert e.value.code == "invalid"
    assert str(e.value) == "task 'scaffold_project' is not claimed by this session"
    with pytest.raises(ForgeError) as e:
        submit_task(live_store, rid, "implement_frontend", "s1", "done", ["a"], [], atlas, now=T0)
    assert e.value.code == "invalid"


def test_submit_twice_raises(live_store, atlas, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    assert submit_task(live_store, rid, "scaffold_project", "s1", "done", ["a"], [], atlas, now=T0).accepted
    with pytest.raises(ForgeError) as e:
        submit_task(live_store, rid, "scaffold_project", "s1", "again", ["a"], [], atlas, now=T0)
    assert e.value.code == "invalid"
    assert results_count(live_store, rid) == 1


def test_briefing_contains_skill_checklist_upstream_and_truncation(live_store, atlas, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    submit_task(
        live_store, rid, "scaffold_project", "s1", "scaffolded vite app", ["package.json", "src/main.tsx"],
        [CheckReport(id="runs", passed=True)], atlas, now=T0,
    )
    claim_task(live_store, rid, "implement_frontend", "s2", now=T0)
    b = build_briefing(live_store, rid, "implement_frontend", atlas)
    assert b.run_id == rid and b.task_id == "implement_frontend"
    assert b.task.status == "claimed" and b.task.skill_id == "react-vite-pages"
    assert b.skill["id"] == "react-vite-pages" and b.skill["name"] and b.skill["description"]
    assert len(b.skill["body"]) <= 12000 and not b.truncated
    assert b.upstream == [
        {"task_id": "scaffold_project", "summary": "scaffolded vite app", "files": ["package.json", "src/main.tsx"]}
    ]
    assert [c.id for c in b.checklist] == ["routes", "responsive", "a11y"]
    assert b.sections_index and all({"slug", "title", "chars"} <= set(s) for s in b.sections_index)
    assert b.rules == RULES and len(RULES) == 3
    first = b.sections_index[0]
    sec = get_section(live_store, "react-vite-pages", first["slug"], atlas)
    assert sec["title"] == first["title"] and len(sec["content"]) == first["chars"]


def test_briefing_truncates_long_body(live_store, atlas, rid):
    live_store.query(
        atlas, "MATCH (s:Skill {id: 'project-scaffold'}) SET s.body = $b", {"b": "word " * 5000}
    )
    b = build_briefing(live_store, rid, "scaffold_project", atlas)
    assert b.truncated and len(b.skill["body"]) <= 12000
    assert "luna_get_skill" in b.skill["body"]


def test_unskilled_briefing(live_store, atlas, run_ids):
    live_store.query(atlas, "MATCH (s:Skill {id: 'react-vite-pages'}) SET s.restricted = true")
    draft = build_plan(live_store, PROMPT, atlas_graph=atlas)
    rid = f"test_{uuid.uuid4().hex[:10]}"
    run_ids.append(rid)
    create_run(live_store, draft, PROMPT, "s0", run_id=rid, now=T0)
    t = tasks_by_id(live_store, rid)["implement_frontend"]
    assert t["skill_id"] == "" and t["assignment"] is None
    assert [c["rejected_reason"] for c in t["candidates"]] == ["restricted"]
    b = build_briefing(live_store, rid, "implement_frontend", atlas)
    desc = live_store.query(
        atlas, "MATCH (c:Capability {name: 'implement_frontend'}) RETURN c.description AS d"
    )[0]["d"]
    assert b.skill == {
        "id": "",
        "name": "Generic Implement frontend",
        "description": desc,
        "body": "No skill in the library covers this capability. Work from the capability description and the upstream results.",
    }
    assert b.checklist == [] and b.sections_index == [] and b.rules == RULES


def test_get_section_unknown_slug_not_found(live_store, atlas):
    with pytest.raises(ForgeError) as e:
        get_section(live_store, "react-vite-pages", "no-such-section", atlas)
    assert e.value.code == "not_found"


def test_get_run_lazily_expires_leases(live_store, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    assert tasks_by_id(live_store, rid, now=T0 + timedelta(minutes=14))["scaffold_project"]["status"] == "claimed"
    run = get_run(live_store, rid, now=T0 + timedelta(minutes=16))
    t = {x["task_id"]: x for x in run["tasks"]}["scaffold_project"]
    assert t["status"] == "ready" and t["claimed_by"] == "" and t["lease_expires_at"] == ""
    assert run["run"]["run_id"] == rid and run["run"]["prompt"] == PROMPT
    assert run["report"] is None
    assert [x["task_id"] for x in run["tasks"]] == ["scaffold_project", "implement_frontend", "verify_contracts"]


def test_expire_leases_returns_ids(live_store, rid):
    claim_task(live_store, rid, "scaffold_project", "s1", now=T0)
    assert expire_leases(live_store, rid, now=T0 + timedelta(minutes=5)) == []
    assert expire_leases(live_store, rid, now=T0 + timedelta(minutes=15, seconds=1)) == ["scaffold_project"]
    assert expire_leases(live_store, rid, now=T0 + timedelta(minutes=20)) == []


def test_list_runs_newest_first_and_set_status(live_store, new_run):
    old = new_run(now=datetime(2099, 1, 1, tzinfo=timezone.utc)).run_id
    new = new_run(now=datetime(2099, 1, 2, tzinfo=timezone.utc)).run_id
    runs = list_runs(live_store, limit=2)
    assert [r["run_id"] for r in runs] == [new, old]
    assert runs[0]["task_count"] == 3 and runs[0]["prompt"] == PROMPT
    set_run_status(live_store, old, "assembled")
    assert get_run(live_store, old)["run"]["status"] == "assembled"
    assert {r["run_id"]: r["status"] for r in list_runs(live_store, limit=2)}[old] == "assembled"
    with pytest.raises(ForgeError) as e:
        set_run_status(live_store, "nope_" + uuid.uuid4().hex[:6], "assembled")
    assert e.value.code == "not_found"
