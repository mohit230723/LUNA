"""Integration tests: Forge MCP server over Streamable HTTP at /mcp (live FalkorDB)."""

from __future__ import annotations

import json
import re
import socket
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Implementation

from luna.api.app import create_app
from luna.forge.events import RUN_CREATED
from luna.graph.schema import GRAPH_FORGE_INDEX, run_graph_name
from luna.graph.store import GraphStore

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

PROMPT = "build me a portfolio website with React"
TOKEN = "forge-test-token"
ERROR_PREFIX = re.compile(r"^(Error executing tool \w+: )?")
ALLOWED_TYPES = {"string", "integer", "boolean", "array", "object"}


@dataclass
class Server:
    app: object
    base: str

    @property
    def url(self) -> str:
        return f"{self.base}/mcp"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(app):
    port = _free_port()
    # Clients may leave an idle SSE stream open; bound the graceful wait.
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", lifespan="on", timeout_graceful_shutdown=2
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 60
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.05)
    return server, thread, f"http://127.0.0.1:{port}"


def _cleanup_runs(store, app) -> None:
    for ev in app.state.forge_bus.wait_after(0, 0):
        if ev["type"] != RUN_CREATED:
            continue
        rid = ev["data"]["run_id"]
        store.delete_graph(run_graph_name(rid))
        store.query(GRAPH_FORGE_INDEX, "MATCH (f:ForgeRun {run_id: $id}) DELETE f", {"id": rid})


def _llm_off():
    return None


@pytest.fixture
def make_server(live_store, tmp_graph):
    started = []

    def make(store=None, **extra):
        cfg = {"atlas_graph": tmp_graph, "forge_llm_factory": _llm_off, **extra}
        app = create_app(store=store or live_store, config=cfg)
        server, thread, base = _serve(app)
        started.append((server, thread, app, store is None))
        return Server(app=app, base=base)

    yield make
    for server, thread, app, live in started:
        server.should_exit = True
        thread.join(timeout=15)
        if live:
            _cleanup_runs(live_store, app)
    assert not any(thread.is_alive() for _, thread, _, _ in started), "uvicorn did not shut down"


@pytest.fixture
def forge_server(make_server, monkeypatch):
    monkeypatch.delenv("LUNA_MCP_TOKEN", raising=False)
    return make_server()


@pytest.fixture
def forge_server_with_token(make_server, monkeypatch):
    monkeypatch.setenv("LUNA_MCP_TOKEN", TOKEN)
    return make_server()


@asynccontextmanager
async def client(server: Server, headers: dict | None = None, name: str = "pytest", url: str | None = None):
    async with streamablehttp_client(url or server.url, headers=headers) as (read, write, _):
        async with ClientSession(read, write, client_info=Implementation(name=name, version="0.1")) as s:
            await s.initialize()
            yield s


def json_of(result) -> dict:
    assert not result.isError, result.content[0].text
    return json.loads(result.content[0].text)


def error_text(result) -> str:
    assert result.isError
    return ERROR_PREFIX.sub("", result.content[0].text, count=1)


async def test_mcp_lists_tools_and_prompt(forge_server):
    async with client(forge_server) as s:
        names = sorted(t.name for t in (await s.list_tools()).tools)
        assert names == [
            "luna_add_skill", "luna_assemble", "luna_get_skill",
            "luna_plan", "luna_search_skills", "luna_submit",
        ]
        assert "luna-build" in [p.name for p in (await s.list_prompts()).prompts]
        prompt = await s.get_prompt("luna-build", {"request": PROMPT})
        text = prompt.messages[0].content.text
        assert PROMPT in text
        assert "parallel" in text.lower() and "sequential" in text.lower()
        positions = [text.index(n) for n in ("luna_plan", "luna_get_skill", "luna_submit", "luna_assemble")]
        assert positions == sorted(positions)


async def test_mcp_trailing_slash_url_also_works(forge_server):
    async with client(forge_server, url=forge_server.url + "/") as s:
        assert len((await s.list_tools()).tools) == 6


async def test_mcp_exact_path_is_not_redirected(forge_server):
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "raw", "version": "1"},
    }}
    headers = {"Accept": "application/json, text/event-stream"}
    async with httpx.AsyncClient(follow_redirects=False) as h:
        r = await h.post(forge_server.url, json=body, headers=headers)
    assert r.status_code == 200 and r.headers.get("mcp-session-id")


async def test_lease_sweep_publishes_task_stalled(forge_server, live_store):
    from datetime import datetime, timedelta, timezone

    from luna.forge.mcp_server import sweep_leases_once
    from luna.forge.runs import claim_task

    async with client(forge_server) as s:
        plan = json_of(await s.call_tool("luna_plan", {"prompt": PROMPT}))
    tid = plan["waves"][0][0]
    claim_task(live_store, plan["run_id"], tid, "old-session", now=datetime.now(timezone.utc) - timedelta(hours=1))
    bus = forge_server.app.state.forge_bus
    expired = sweep_leases_once(live_store, bus)
    assert (plan["run_id"], tid) in expired
    stalled = [e["data"] for e in bus.wait_after(0, 0) if e["type"] == "task_stalled"]
    assert {"run_id": plan["run_id"], "task_id": tid, "status": "ready"} in stalled


async def test_tool_schemas_are_gemini_safe(forge_server):
    def walk(node, path):
        if isinstance(node, dict):
            for bad in ("anyOf", "oneOf", "allOf", "$ref", "$defs"):
                assert bad not in node, f"{bad} at {path}"
            for name, prop in (node.get("properties") or {}).items():
                assert prop.get("type") in ALLOWED_TYPES, f"{path}.{name}: {prop}"
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    async with client(forge_server) as s:
        for tool in (await s.list_tools()).tools:
            assert re.fullmatch(r"[a-z_]+", tool.name)
            walk(tool.inputSchema, tool.name)


async def test_mcp_end_to_end_build(forge_server):
    async with client(forge_server) as s:
        plan = json_of(await s.call_tool("luna_plan", {"prompt": PROMPT}))
        assert plan["status"] == "planned" and plan["run_id"]
        for wave in plan["waves"]:
            for tid in wave:
                b = json_of(await s.call_tool("luna_get_skill", {"run_id": plan["run_id"], "task_id": tid}))
                assert b["task_id"] == tid and b["rules"]
                checks = [{"id": c["id"], "passed": True, "note": ""} for c in b["checklist"]]
                r = json_of(await s.call_tool("luna_submit", {
                    "run_id": plan["run_id"], "task_id": tid, "summary": "ok",
                    "files": [f"{tid}.txt"], "checks": checks,
                }))
                assert r["accepted"], r["errors"]
        rep = json_of(await s.call_tool("luna_assemble", {"run_id": plan["run_id"]}))
        assert rep["status"] == "complete" and rep["gaps"] == []

    events = forge_server.app.state.forge_bus.wait_after(0, 0)
    types = [e["type"] for e in events]
    assert "run_created" in types and "run_assembled" in types
    statuses = {e["data"]["status"] for e in events if e["type"] == "task_updated"}
    assert {"claimed", "done", "ready"} <= statuses


async def test_mcp_section_requires_claim(forge_server):
    async with client(forge_server) as s:
        plan = json_of(await s.call_tool("luna_plan", {"prompt": PROMPT}))
        tid = plan["waves"][0][0]
        args = {"run_id": plan["run_id"], "task_id": tid, "section": "anything"}
        res = await s.call_tool("luna_get_skill", args)
        assert error_text(res).startswith("invalid:")
        b = json_of(await s.call_tool("luna_get_skill", {"run_id": plan["run_id"], "task_id": tid}))
        assert b["sections_index"], "starter skill should have sections"
        slug = b["sections_index"][0]["slug"]
        sec = json_of(await s.call_tool("luna_get_skill", {**args, "section": slug}))
        assert sec["content"]


async def test_mcp_errors_are_tool_errors(forge_server):
    async with client(forge_server) as s:
        plan = json_of(await s.call_tool("luna_plan", {"prompt": PROMPT}))
        pending = plan["waves"][1][0]
        res = await s.call_tool("luna_get_skill", {"run_id": plan["run_id"], "task_id": pending})
        assert error_text(res).startswith("not_ready:")
        res = await s.call_tool("luna_assemble", {"run_id": "no_such_run"})
        assert error_text(res).startswith("not_found:")


async def test_mcp_plan_needs_input_creates_no_run(forge_server):
    async with client(forge_server) as s:
        plan = json_of(await s.call_tool("luna_plan", {"prompt": "zzz qqq"}))
        assert plan["status"] == "needs_input" and plan["run_id"] == "" and plan["question"]


async def test_mcp_add_skill_is_pending(forge_server):
    md = (
        "---\nname: Forge MCP Test Skill\ndescription: Zebra-striped widgets for tests.\n"
        "capabilities: [style_ui]\n---\nDo the zebra thing.\n"
    )
    async with client(forge_server) as s:
        out = json_of(await s.call_tool("luna_add_skill", {
            "skill_md": md, "references": [{"name": "extra.md", "content": "# Extra\nmore"}],
        }))
        assert out["status"] == "pending_review" and out["skill_id"]
        found = json_of(await s.call_tool("luna_search_skills", {"query": "ZEBRA-striped"}))
        assert [k["id"] for k in found["skills"]] == [out["skill_id"]]
        assert found["skills"][0]["status"] == "pending_review"
        bad = await s.call_tool("luna_add_skill", {"skill_md": "no frontmatter here"})
        assert error_text(bad).startswith("invalid:")
        many = json_of(await s.call_tool("luna_search_skills", {"query": "", "limit": 2}))
        assert len(many["skills"]) == 2
    assert any(e["type"] == "skill_imported" for e in forge_server.app.state.forge_bus.wait_after(0, 0))


async def test_mcp_token_required(forge_server_with_token):
    async with httpx.AsyncClient() as h:
        r = await h.post(forge_server_with_token.url, json={})
        assert r.status_code == 401 and r.json() == {"error": "unauthorized"}
        r = await h.post(forge_server_with_token.url, json={}, headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401
    async with client(forge_server_with_token, headers={"Authorization": f"Bearer {TOKEN}"}) as s:
        assert len((await s.list_tools()).tools) == 6


async def test_mcp_rejects_foreign_host(forge_server):
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "evil", "version": "1"},
    }}
    headers = {"Host": "evil.example", "Accept": "application/json, text/event-stream"}
    async with httpx.AsyncClient() as h:
        r = await h.post(forge_server.url, json=body, headers=headers)
    assert r.status_code in (403, 421)


async def test_mcp_store_down_returns_tool_error(make_server, monkeypatch):
    monkeypatch.delenv("LUNA_MCP_TOKEN", raising=False)
    server = make_server(store=GraphStore(host="127.0.0.1", port=1))
    async with client(server) as s:
        res = await s.call_tool("luna_plan", {"prompt": PROMPT})
        assert res.isError and "LUNA graph store unavailable" in res.content[0].text


class _TimingOutStore(GraphStore):
    """A store whose queries fail like FalkorDB's per-query TIMEOUT."""

    def query(self, *a, **kw):
        import redis.exceptions

        raise redis.exceptions.ResponseError("Query timed out")


async def test_mcp_query_timeout_maps_to_store_unavailable(make_server, monkeypatch):
    monkeypatch.delenv("LUNA_MCP_TOKEN", raising=False)
    server = make_server(store=_TimingOutStore(host="localhost", port=6379))
    async with client(server) as s:
        res = await s.call_tool("luna_plan", {"prompt": PROMPT})
        assert res.isError and "store_unavailable" in res.content[0].text


async def test_sessions_record_client_name(forge_server):
    async with client(forge_server, name="pytest-agent") as s:
        await s.call_tool("luna_search_skills", {"query": "react"})
    sessions = forge_server.app.state.forge_sessions.list()
    assert sessions[0]["client_name"] == "pytest-agent"
    assert sessions[0]["session_id"]
