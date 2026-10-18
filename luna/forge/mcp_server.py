"""LUNA Forge MCP server: a thin Streamable HTTP layer over the Forge units.

Tools are async and push every blocking FalkorDB call onto a worker thread
(``anyio.to_thread.run_sync``); FastMCP 1.30 calls sync tools inline on the
event loop, so it does not offload them itself.
"""

from __future__ import annotations

import hmac
import logging
import os
import threading
from typing import Annotated, Any, Callable

import anyio
import redis.exceptions
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, WithJsonSchema
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from luna.forge.assemble import assemble_run
from luna.forge.briefing import build_briefing, get_section
from luna.forge.events import (
    RUN_ASSEMBLED,
    RUN_CREATED,
    SKILL_IMPORTED,
    TASK_STALLED,
    TASK_UPDATED,
    ForgeEventBus,
)
from luna.forge.models import CheckReport, ForgeError, Plan, is_store_unavailable
from luna.forge.planner import build_plan
from luna.forge.runs import (
    claim_task,
    create_run,
    expire_leases,
    get_run,
    list_runs,
    read_results,
    submit_task,
)
from luna.forge.sessions import SessionRegistry
from luna.forge.skill_import import import_skill
from luna.forge.skill_parse import SkillParseError, parse_skill_md
from luna.graph.schema import GRAPH_ATLAS, LABEL_CAPABILITY, LABEL_SKILL, LABEL_TECHNOLOGY, REL_PROVIDES, REL_TARGETS

__all__ = [
    "BUILD_PROMPT_NAME",
    "DEFAULT_ALLOWED_HOSTS",
    "create_forge_mcp",
    "forge_asgi_app",
    "start_lease_sweep",
    "sweep_leases_once",
]

logger = logging.getLogger(__name__)

BUILD_PROMPT_NAME = "luna-build"
SWEEP_INTERVAL_S = 60.0
MAX_SEARCH_LIMIT = 50
STORE_UNAVAILABLE = "store_unavailable: LUNA graph store unavailable"
DEFAULT_ALLOWED_HOSTS = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*", "[::1]", "[::1]:*"]
ALLOWED_ORIGINS = ["http://localhost:*", "http://127.0.0.1:*"]
_STORE_ERRORS = (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, ConnectionError, OSError)

PLAYBOOK = """\
You are driving a LUNA Forge build. Request: {request}

Follow these steps exactly.

1. Call `luna_plan` with the request as `prompt`. If the result's status is `needs_input`, ask the user the returned `question`, then call `luna_plan` again with the clarified request.
2. Work through `waves` in order. For each wave, take every task in it:
   - Parallel mode (you can spawn subagents): spawn one subagent per task. The subagent's only instruction is: "Call `luna_get_skill(run_id, task_id)` first and work only from its briefing; when finished call `luna_submit`."
   - Sequential mode (otherwise): handle each task yourself, in order. Call `luna_get_skill(run_id, task_id)`, treat its briefing as a fresh assignment and do not carry assumptions across tasks, then call `luna_submit` with a summary, every file you created or changed (relative paths), and a check for every checklist item.
3. Move to the next wave only after every task in the current wave is submitted and accepted.
4. Call `luna_assemble` with the run_id and present the report to the user.
"""

_CHECKS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "passed": {"type": "boolean"},
            "note": {"type": "string"},
        },
        "required": ["id", "passed"],
    },
}
_REFERENCES_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "content": {"type": "string"}},
        "required": ["name", "content"],
    },
}


class SkillReference(BaseModel):
    name: str
    content: str


ChecksParam = Annotated[list[CheckReport], WithJsonSchema(_CHECKS_SCHEMA)]
ReferencesParam = Annotated[list[SkillReference], WithJsonSchema(_REFERENCES_SCHEMA)]


def _session_info(ctx: Context) -> tuple[str, str, str]:
    session_id = ""
    try:
        request = ctx.request_context.request
        if request is not None:
            session_id = request.headers.get("mcp-session-id") or ""
    except (AttributeError, ValueError, LookupError):
        pass
    name = version = ""
    try:
        params = ctx.session.client_params
        info = params.clientInfo if params is not None else None
        if info is not None:
            name, version = info.name or "", info.version or ""
    except (AttributeError, ValueError, LookupError):
        pass
    return session_id, name, version


async def _blocking(fn: Callable[[], Any]) -> Any:
    """Run a blocking forge call on a worker thread and map its errors to ToolError."""
    try:
        return await anyio.to_thread.run_sync(fn)
    except ToolError:
        raise
    except ForgeError as e:
        raise ToolError(f"{e.code}: {e}") from e
    except _STORE_ERRORS as e:
        raise ToolError(STORE_UNAVAILABLE) from e
    except redis.exceptions.ResponseError as e:
        if is_store_unavailable(e):  # FalkorDB "Query timed out"
            raise ToolError(STORE_UNAVAILABLE) from e
        raise


def create_forge_mcp(
    store,
    bus: ForgeEventBus,
    sessions: SessionRegistry,
    llm_factory: Callable[[], Any],
    atlas_graph: str = GRAPH_ATLAS,
    allowed_hosts: list[str] | None = None,
) -> FastMCP:
    hosts = list(DEFAULT_ALLOWED_HOSTS)
    for h in allowed_hosts or []:
        if h and h not in hosts:
            hosts.append(h)
    mcp = FastMCP(
        "luna",
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=list(ALLOWED_ORIGINS),
        ),
    )

    def _llm():
        try:
            return llm_factory()
        except Exception:
            return None

    def touch(ctx: Context) -> str:
        session_id, name, version = _session_info(ctx)
        sessions.touch(session_id, name, version)
        return session_id

    @mcp.tool(name="luna_plan", description="Plan a build: turn a request into a run with a task DAG in waves.")
    async def luna_plan(prompt: str, ctx: Context, stack_hints: list[str] = []) -> dict:  # noqa: B006
        sid = touch(ctx)

        def work() -> Plan:
            draft = build_plan(store, prompt, list(stack_hints), llm=_llm(), atlas_graph=atlas_graph)
            if draft.status != "planned":
                return Plan(run_id="", status=draft.status, question=draft.question)
            return create_run(store, draft, prompt, sid)

        plan = await _blocking(work)
        if plan.run_id:
            bus.publish(RUN_CREATED, {"run_id": plan.run_id, "prompt": prompt})
        return plan.model_dump()

    @mcp.tool(
        name="luna_get_skill",
        description=(
            "Without section: claim the task and return its skill briefing. "
            "With section: return that skill section (task must be claimed by this session)."
        ),
    )
    async def luna_get_skill(
        run_id: str, task_id: str, ctx: Context, agent_label: str = "", section: str = ""
    ) -> dict:
        sid = touch(ctx)
        if section:
            def read_section() -> dict:
                view = get_run(store, run_id)
                task = next((t for t in view["tasks"] if t["task_id"] == task_id), None)
                if task is None:
                    raise ForgeError("not_found", f"task '{task_id}' not found in run '{run_id}'")
                if task["status"] != "claimed" or task["claimed_by"] != sid:
                    raise ForgeError(
                        "invalid",
                        f"task '{task_id}' is not claimed by this session; "
                        "call luna_get_skill without section first",
                    )
                return get_section(store, task["skill_id"], section, atlas_graph)

            return await _blocking(read_section)

        def claim():
            claimed = claim_task(store, run_id, task_id, sid, agent_label)
            return claimed, build_briefing(store, run_id, task_id, atlas_graph)

        _, briefing = await _blocking(claim)
        bus.publish(TASK_UPDATED, {
            "run_id": run_id, "task_id": task_id, "status": "claimed",
            "claimed_by": sid, "agent_label": agent_label,
        })
        return briefing.model_dump()

    @mcp.tool(name="luna_submit", description="Submit a claimed task's result: summary, files and checklist checks.")
    async def luna_submit(
        run_id: str, task_id: str, summary: str, files: list[str], checks: ChecksParam, ctx: Context
    ) -> dict:
        sid = touch(ctx)

        def work():
            res = submit_task(store, run_id, task_id, sid, summary, list(files), list(checks), atlas_graph)
            result = read_results(store, run_id).get(task_id) if res.accepted else None
            return res, result

        res, result = await _blocking(work)
        if res.accepted:
            bus.publish(TASK_UPDATED, {"run_id": run_id, "task_id": task_id, "status": "done", "result": result})
            for tid in res.unlocked_tasks:
                bus.publish(TASK_UPDATED, {"run_id": run_id, "task_id": tid, "status": "ready"})
        return res.model_dump()

    @mcp.tool(name="luna_assemble", description="Assemble a run's results into a report.")
    async def luna_assemble(run_id: str, ctx: Context) -> dict:
        touch(ctx)
        report = await _blocking(lambda: assemble_run(store, run_id, llm=_llm(), atlas_graph=atlas_graph))
        data = report.model_dump()
        bus.publish(RUN_ASSEMBLED, {"run_id": run_id, "report": data})
        return data

    @mcp.tool(name="luna_add_skill", description="Add a SKILL.md (plus reference files) for review.")
    async def luna_add_skill(skill_md: str, ctx: Context, references: ReferencesParam = []) -> dict:  # noqa: B006
        touch(ctx)
        try:
            doc = parse_skill_md(skill_md, [(r.name, r.content) for r in references], default_id="")
        except SkillParseError as e:
            raise ToolError(f"invalid: {e}") from e
        result = await _blocking(lambda: import_skill(store, doc, "mcp", atlas_graph, llm=_llm()))
        bus.publish(SKILL_IMPORTED, {"skill_id": result.skill_id, "status": result.status})
        return result.model_dump()

    @mcp.tool(
        name="luna_search_skills",
        description="Search the skill library by id, name or description (case-insensitive).",
    )
    async def luna_search_skills(query: str, ctx: Context, limit: int = 10) -> dict:
        touch(ctx)
        cap = max(0, min(int(limit), MAX_SEARCH_LIMIT))
        needle = query.lower()

        def work() -> list[dict]:
            rows = store.query(
                atlas_graph,
                f"MATCH (s:{LABEL_SKILL}) WHERE s.source IS NOT NULL "
                f"OPTIONAL MATCH (s)-[:{REL_PROVIDES}]->(c:{LABEL_CAPABILITY}) "
                f"OPTIONAL MATCH (s)-[:{REL_TARGETS}]->(t:{LABEL_TECHNOLOGY}) "
                "RETURN s.id AS id, s.name AS name, s.description AS description, s.status AS status, "
                "collect(DISTINCT c.name) AS caps, collect(DISTINCT t.name) AS techs "
                "ORDER BY id",
            )
            out = []
            for r in rows:
                sid, name, desc = r.get("id") or "", r.get("name") or "", r.get("description") or ""
                if needle in sid.lower() or needle in name.lower() or needle in desc.lower():
                    out.append({
                        "id": sid, "name": name or sid, "description": desc,
                        "capabilities": sorted(c for c in r.get("caps") or [] if c),
                        "technologies": sorted(t for t in r.get("techs") or [] if t),
                        "status": r.get("status") or "",
                    })
                    if len(out) >= cap:
                        break
            return out

        return {"skills": await _blocking(work)}

    @mcp.prompt(name=BUILD_PROMPT_NAME, description="Playbook for building a request with LUNA Forge.")
    def luna_build(request: str) -> str:
        return PLAYBOOK.format(request=request)

    return mcp


class _BearerASGI:
    """Streamable HTTP endpoint guarded by an optional bearer token.

    The inner app is path-agnostic, so the same instance serves ``/mcp`` and
    ``/mcp/`` without a redirect. It is a class (not a function) so Starlette's
    ``Route`` treats it as a raw ASGI app.
    """

    def __init__(self, inner: ASGIApp, token: str | None) -> None:
        self._inner = inner
        self._expected = f"Bearer {token}".encode() if token else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._expected is not None and scope["type"] == "http":
            got = b""
            for k, v in scope.get("headers") or []:
                if k.lower() == b"authorization":
                    got = v
                    break
            if not hmac.compare_digest(got, self._expected):
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self._inner(scope, receive, send)


def forge_asgi_app(mcp: FastMCP, token: str | None) -> ASGIApp:
    mcp.streamable_http_app()  # creates mcp.session_manager on first call
    return _BearerASGI(StreamableHTTPASGIApp(mcp.session_manager), token)


def allowed_hosts_from_env() -> list[str]:
    raw = os.environ.get("LUNA_MCP_ALLOWED_HOSTS", "")
    return [h.strip() for h in raw.split(",") if h.strip()]


def sweep_leases_once(store, bus: ForgeEventBus) -> list[tuple[str, str]]:
    """Expire stale leases on every non-assembled run; publish ``task_stalled`` per task."""
    expired: list[tuple[str, str]] = []
    for run in list_runs(store, limit=500):
        if run.get("status") == "assembled":
            continue
        rid = run["run_id"]
        try:
            ids = expire_leases(store, rid)
        except ForgeError:
            continue
        for tid in ids:
            bus.publish(TASK_STALLED, {"run_id": rid, "task_id": tid, "status": "ready"})
            expired.append((rid, tid))
    return expired


def start_lease_sweep(
    store, bus: ForgeEventBus, interval: float = SWEEP_INTERVAL_S
) -> tuple[threading.Thread, threading.Event]:
    stop = threading.Event()

    def loop() -> None:
        while not stop.wait(interval):
            try:
                sweep_leases_once(store, bus)
            except Exception as e:  # store down, etc. — try again next tick
                logger.warning("forge lease sweep failed: %s", e)

    thread = threading.Thread(target=loop, name="forge-lease-sweep", daemon=True)
    thread.start()
    return thread, stop
