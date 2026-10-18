"""Integration tests for the Forge REST and SSE routes (live FalkorDB, TestClient)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from luna.api.app import create_app
from luna.forge.events import RUN_CREATED
from luna.forge.planner import build_plan
from luna.forge.runs import create_run
from luna.graph.schema import GRAPH_FORGE_INDEX, run_graph_name

pytestmark = pytest.mark.integration

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
PROMPT = "build me a portfolio website with React"
SKILL_MD = """---
name: Upload Probe
description: A probe skill uploaded in tests.
capabilities: [implement_frontend]
checklist:
  - id: one
    text: Do the thing.
---
Body text.

## Steps
Do it.
"""


def make_app(live_store, tmp_graph):
    return create_app(
        store=live_store,
        config={
            "atlas_graph": tmp_graph,
            "forge_llm_factory": lambda: None,
            "forge_skills_dir": str(SKILLS_ROOT),
        },
    )


@pytest.fixture
def client(live_store, tmp_graph):
    with TestClient(make_app(live_store, tmp_graph)) as c:
        yield c


@pytest.fixture
def client_with_token(live_store, tmp_graph, monkeypatch):
    monkeypatch.setenv("LUNA_MCP_TOKEN", "s3cret")
    with TestClient(make_app(live_store, tmp_graph)) as c:
        yield c


@pytest.fixture
def run_ids(live_store):
    ids: list[str] = []
    yield ids
    for rid in ids:
        live_store.delete_graph(run_graph_name(rid))
        live_store.query(GRAPH_FORGE_INDEX, "MATCH (f:ForgeRun {run_id: $id}) DELETE f", {"id": rid})


def upload(client, text=SKILL_MD, refs=()):
    files = [("skill", ("SKILL.md", text.encode(), "text/markdown"))]
    files += [("references", (n, c.encode(), "text/markdown")) for n, c in refs]
    return client.post("/api/forge/skills/upload", files=files)


def test_connect_snippets_without_token(client, monkeypatch):
    body = client.get("/api/forge/connect").json()
    assert body["token_required"] is False
    assert body["mcp_url"].endswith("/mcp")
    assert body["snippets"]["claude_code"] == f"claude mcp add --transport http luna {body['mcp_url']}"
    assert json.loads(body["snippets"]["antigravity"]) == {
        "mcpServers": {"luna": {"serverUrl": body["mcp_url"]}}
    }
    assert body["snippets"]["claude_code_token"] == (
        f'claude mcp add --transport http luna {body["mcp_url"]} --header "Authorization: Bearer <token>"'
    )
    assert json.loads(body["snippets"]["antigravity_token"]) == {
        "mcpServers": {
            "luna": {"serverUrl": body["mcp_url"], "headers": {"Authorization": "Bearer <token>"}}
        }
    }


def test_connect_never_leaks_token(client_with_token):
    resp = client_with_token.get("/api/forge/connect")
    assert resp.json()["token_required"] is True
    assert "s3cret" not in resp.text and "<token>" in resp.text


def test_agents_lists_sessions(client):
    client.app.state.forge_sessions.touch("sess-1", "claude-code", "1.0")
    agents = client.get("/api/forge/agents").json()
    assert any(a["session_id"] == "sess-1" for a in agents)


def test_upload_approve_flow(client):
    resp = upload(client)
    assert resp.status_code == 200
    assert resp.json()["skill_id"] == "upload-probe"
    assert resp.json()["status"] == "pending_review"

    detail = client.get("/api/forge/skills/upload-probe").json()
    assert detail["source"] == "upload" and detail["status"] == "pending_review"

    assert client.post("/api/forge/skills/upload-probe/approve").status_code == 204
    assert client.get("/api/forge/skills/upload-probe").json()["status"] == "approved"
    assert client.post("/api/forge/skills/upload-probe/reject").status_code == 204
    assert client.get("/api/forge/skills/upload-probe").json()["status"] == "rejected"
    assert client.post("/api/forge/skills/nope/reject").status_code == 404
    assert client.post("/api/forge/skills/nope/approve").status_code == 404

    types = [e["type"] for e in client.app.state.forge_bus.wait_after(0, 0)]
    assert types.count("skill_imported") == 3

    listed = {s["id"]: s for s in client.get("/api/forge/skills").json()}
    assert listed["upload-probe"]["capabilities"] == ["implement_frontend"]
    assert listed["react-vite-pages"]["source"] == "repo"


def test_skill_warnings_in_detail_and_list(client):
    extra = "capabilities: [implement_frontend]\ntechnologies: [Cobol]"
    text = SKILL_MD.replace("capabilities: [implement_frontend]", extra).replace("Upload Probe", "Warn Probe")
    assert upload(client, text).status_code == 200
    detail = client.get("/api/forge/skills/warn-probe").json()
    assert detail["warnings"] == ["unknown technology 'Cobol'"]
    listed = {s["id"]: s for s in client.get("/api/forge/skills").json()}
    assert listed["warn-probe"]["warnings_count"] == 1


def test_upload_parse_error_422(client):
    resp = upload(client, "no frontmatter here")
    assert resp.status_code == 422
    assert "frontmatter" in resp.json()["detail"]


def test_upload_too_large_413(client):
    assert upload(client, SKILL_MD + "x" * 110_000).status_code == 413
    refs = [(f"r{i}.md", "# R\n") for i in range(21)]
    assert upload(client, refs=refs).status_code == 413
    assert upload(client, refs=[("big.md", "y" * 110_000)]).status_code == 413


def test_reimport_returns_results(client):
    results = client.post("/api/forge/skills/reimport").json()
    assert {r["skill_id"] for r in results} >= {"react-vite-pages", "project-scaffold"}


def test_runs_list_and_detail_404(client, live_store, tmp_graph, run_ids):
    rid = f"test_{uuid.uuid4().hex[:10]}"
    run_ids.append(rid)
    draft = build_plan(live_store, PROMPT, atlas_graph=tmp_graph)
    create_run(live_store, draft, PROMPT, "s0", run_id=rid)

    assert rid in [r["run_id"] for r in client.get("/api/forge/runs").json()]
    detail = client.get(f"/api/forge/runs/{rid}")
    assert detail.status_code == 200 and detail.json()["run"]["run_id"] == rid
    assert client.get("/api/forge/runs/test_missing").status_code == 404


def test_skill_detail_neighbourhood(client):
    detail = client.get("/api/forge/skills/react-vite-pages").json()
    assert detail["requires"] == ["project-scaffold"]
    assert any(c["id"] == "routes" for c in detail["checklist"])
    assert detail["sections"]
    edges = {(e["source"], e["target"]) for e in detail["neighbourhood"]["edges"]}
    assert ("react-vite-pages", "implement_frontend") in edges
    assert ("react-vite-pages", "project-scaffold") in edges
    node_ids = {n["id"] for n in detail["neighbourhood"]["nodes"]}
    assert {"react-vite-pages", "implement_frontend", "project-scaffold"} <= node_ids
    assert "react-vite-pages" in client.get("/api/forge/skills/project-scaffold").json()["required_by"]
    assert client.get("/api/forge/skills/missing").status_code == 404


def test_events_stream_replays_after(client):
    bus = client.app.state.forge_bus
    first = bus.publish(RUN_CREATED, {"run_id": "a"})["seq"]
    second = bus.publish(RUN_CREATED, {"run_id": "b"})["seq"]
    with client.stream("GET", f"/api/forge/events?after={first}&max_events=1") as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
        text = "".join(resp.iter_text())
    assert f"id: {second}\n" in text and f"id: {first}\n" not in text
    assert "event: run_created\n" in text
    data = json.loads(text.split("data: ", 1)[1].split("\n", 1)[0])
    assert data["data"] == {"run_id": "b"}

    # Last-Event-ID wins over ?after
    with client.stream(
        "GET", "/api/forge/events?after=0&max_events=1", headers={"Last-Event-ID": str(first)}
    ) as resp:
        text = "".join(resp.iter_text())
    assert f"id: {second}\n" in text


def test_upload_content_length_guard_413(client):
    resp = client.post(
        "/api/forge/skills/upload",
        content=b"x",
        headers={
            "Content-Type": "multipart/form-data; boundary=zzz",
            "Content-Length": str(21 * 102_400 + 65_536 + 1),
        },
    )
    assert resp.status_code == 413
    assert "exceeds" in resp.json()["detail"]


def test_upload_too_many_files_413(client):
    refs = [(f"r{i}.md", "# R\n") for i in range(30)]
    assert upload(client, refs=refs).status_code == 413


class _FakeLLM:
    def info(self):
        return {"reachable": True}

    def complete_json(self, system, user, schema):
        return {"capabilities": ["implement_frontend"], "technologies": []}


def test_upload_uses_llm_suggestions(live_store, tmp_graph):
    app = create_app(
        store=live_store,
        config={
            "atlas_graph": tmp_graph,
            "forge_llm_factory": lambda: _FakeLLM(),
            "forge_skills_dir": str(SKILLS_ROOT),
        },
    )
    md = "---\nname: No Caps\ndescription: nothing declared\n---\nBody.\n"
    with TestClient(app) as c:
        body = upload(c, md).json()
    assert any("suggested capability 'implement_frontend'" in w for w in body["warnings"])
