"""FastAPI REST API application with Server-Sent Events (SSE) streaming and Graph inspection."""

import os
import re
import json
import time
import uuid
import logging
import urllib.request
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from fastapi import FastAPI, HTTPException, Request, Response, Query, Header, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from luna.graph.store import GraphStore
from luna.graph.schema import GRAPH_DOMAIN, GRAPH_ATLAS, GRAPH_CONVERSATIONS, LABEL_CUSTOMER
from luna.domain.seed import GroundTruth
from luna.orchestrator.pipeline import LunaPipeline, PipelineConfig, PipelineEvent, PipelineRunResult
from luna.orchestrator.actions import approve_action, reject_action, NotApprovedError
from luna.orchestrator.explain import explain_customer, explain_action
from luna.llm import get_llm
from luna.llm.client import MockLLMClient, OllamaClient
from luna.conversation.store import ConversationStore
from luna.cases.store import CaseStore
from luna.ingest.builder import build_context_graph
from luna.investigate.pipeline import InvestigationPipeline
from luna.investigate.trace import build_trace_response, build_why_response, generate_suggestions
from luna.investigate.seed import seed_investigation_atlas
from luna.packs.registry import default_registry, PackRegistry
from luna.packs.router import route_prompt
from luna.packs.build.pipeline import BuildPipeline, BuildPipelineConfig
from luna.forge.events import ForgeEventBus
from luna.forge.sessions import SessionRegistry
from luna.forge.mcp_server import (
    allowed_hosts_from_env,
    create_forge_mcp,
    forge_asgi_app,
    start_lease_sweep,
)
from luna.forge.routes import register_forge_routes
from luna.forge.skill_import import import_repo_skills
from luna.forge.vocab import seed_forge_vocabulary

logger = logging.getLogger(__name__)


# Strict allowlist pattern for graph scope identifiers to prevent Cypher injection
SAFE_SCOPE_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


class CreateRunRequest(BaseModel):
    task: str = "Investigate suspected auto insurance fraud ring"
    k_hops: int = 2
    strict_llm: bool = False
    parallel: int = 3
    mode: str = "scripted"  # "scripted" or "live"


class ApproveActionRequest(BaseModel):
    approver: str = ""


class RejectActionRequest(BaseModel):
    approver: str = ""
    reason: str = ""


class CreateConversationRequest(BaseModel):
    title: str = "New case"


class SendMessageRequest(BaseModel):
    prompt: Optional[str] = None
    content: Optional[str] = None
    pack_override: Optional[str] = None
    options: Optional[dict[str, Any]] = None


class ProvideAnswerRequest(BaseModel):
    answer: Optional[str] = None
    choice: Optional[str] = None


class UploadTextRequest(BaseModel):
    name: Optional[str] = "Pasted text"
    text: str


class StartBuildRequest(BaseModel):
    acknowledge_remote: bool = False


class BuildState:
    """Thread-safe state container for a case context-graph build."""

    def __init__(self, build_id: str, case_id: str) -> None:
        self.build_id = build_id
        self.case_id = case_id
        self.events: list[dict[str, Any]] = []
        self.cancelled = False
        self.finished = False
        self.seq = 0
        self._lock = threading.Lock()
        self.condition = threading.Condition(self._lock)

    def add_event(self, event_type: str, data: dict[str, Any]) -> None:
        with self.condition:
            self.seq += 1
            ev = {
                "build_id": self.build_id,
                "seq": self.seq,
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": event_type,
                "data": data,
            }
            self.events.append(ev)
            if event_type in ("completed", "failed", "cancelled"):
                self.finished = True
            self.condition.notify_all()

    def cancel(self) -> None:
        with self.condition:
            self.cancelled = True
            self.condition.notify_all()


class InvestigationRunState:
    """Thread-safe state container for an investigation pipeline run."""

    def __init__(self, run_id: str, case_id: str, question: str) -> None:
        self.run_id = run_id
        self.case_id = case_id
        self.question = question
        self.events: list[dict[str, Any]] = []
        self.cancelled = False
        self.finished = False
        self.seq = 0
        self.pending_answer: Optional[str] = None
        self._lock = threading.Lock()
        self.condition = threading.Condition(self._lock)

    def add_event(self, event: dict[str, Any]) -> None:
        with self.condition:
            self.seq += 1
            event["seq"] = self.seq
            self.events.append(event)
            if event.get("type") in ("completed", "failed", "cancelled"):
                self.finished = True
            self.condition.notify_all()

    def cancel(self) -> None:
        with self.condition:
            self.cancelled = True
            self.condition.notify_all()

    def provide_answer(self, ans: str) -> None:
        with self.condition:
            self.pending_answer = ans
            self.condition.notify_all()



class RunState:
    """Thread-safe state container for an autonomous pipeline run."""

    def __init__(self, run_id: str, task: str, pipeline: Any, pack: str = "investigate") -> None:
        self.run_id = run_id
        self.task = task
        self.pipeline = pipeline
        self.pack = pack
        self.status: str = "initializing"  # initializing, running, pending_approval, executed, rejected, failed
        self.current_step: str = "init"
        self.events: list[PipelineEvent] = []
        self.action_id: Optional[str] = None
        self.outcome_id: Optional[str] = None
        self.metrics: Optional[dict[str, Any]] = None
        self.backend_counts: dict[str, int] = {"llm": 0, "rules": 0, "scripted": 0}
        self.finished: bool = False
        self.error: Optional[str] = None
        self.created_at: str = datetime.now(timezone.utc).isoformat()

        self._lock = threading.Lock()
        self.condition = threading.Condition(self._lock)

    def add_event(self, event: PipelineEvent) -> None:
        with self.condition:
            self.events.append(event)
            self.current_step = event.step
            self.condition.notify_all()

    def set_status(self, status: str, error: Optional[str] = None) -> None:
        with self.condition:
            self.status = status
            if error:
                self.error = error
            self.condition.notify_all()

    def mark_finished(self) -> None:
        with self.condition:
            self.finished = True
            self.condition.notify_all()


class RunRegistry:
    """Thread-safe registry of active and completed pipeline runs."""

    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = threading.Lock()

    def register(self, run_state: RunState) -> None:
        with self._lock:
            self._runs[run_state.run_id] = run_state

    def get(self, run_id: str) -> Optional[RunState]:
        with self._lock:
            return self._runs.get(run_id)

    def list_all(self) -> list[RunState]:
        with self._lock:
            return list(self._runs.values())


def create_app(
    store: Optional[GraphStore] = None,
    config: Optional[dict[str, Any]] = None,
) -> FastAPI:
    """FastAPI application factory supporting dependency injection for testing."""
    cfg = config or {}
    graph_store = store or GraphStore()
    domain_graph = cfg.get("domain_graph", GRAPH_DOMAIN)
    atlas_graph = cfg.get("atlas_graph", GRAPH_ATLAS)
    ground_truth: Optional[GroundTruth] = cfg.get("ground_truth")
    recording_file = cfg.get("recording_file", os.path.join("artifacts", "replay_recording.json"))

    # LUNA Forge: event bus, agent sessions and the MCP server mounted at /mcp
    forge_enabled = bool(cfg.get("forge_enabled", True))
    forge_skills_dir = Path(cfg.get("forge_skills_dir", "skills"))
    forge_llm_factory = cfg.get("forge_llm_factory", get_llm)
    forge_bus = ForgeEventBus()
    forge_sessions = SessionRegistry(forge_bus)
    forge_mcp = (
        create_forge_mcp(
            graph_store,
            forge_bus,
            forge_sessions,
            forge_llm_factory,
            atlas_graph=atlas_graph,
            allowed_hosts=allowed_hosts_from_env(),
        )
        if forge_enabled
        else None
    )
    forge_endpoint = forge_asgi_app(forge_mcp, os.environ.get("LUNA_MCP_TOKEN") or None) if forge_mcp else None

    def _forge_startup_import() -> None:
        try:
            seed_forge_vocabulary(graph_store, atlas_graph)
            import_repo_skills(graph_store, forge_skills_dir, atlas_graph)
        except Exception as err:
            logger.warning("LUNA Forge startup skill import skipped: %s", err)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if forge_mcp is None:
            yield
            return
        import anyio

        await anyio.to_thread.run_sync(_forge_startup_import)
        sweep_thread, sweep_stop = start_lease_sweep(graph_store, forge_bus)
        try:
            async with forge_mcp.session_manager.run():
                yield
        finally:
            sweep_stop.set()
            sweep_thread.join(timeout=5)

    app = FastAPI(
        title="LUNA OS API",
        description="Autonomous Multi-Agent Graph Intelligence Engine API with SSE Streaming",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.forge_bus = forge_bus
    app.state.forge_sessions = forge_sessions
    app.state.forge_mcp = forge_mcp

    # Configure CORS
    cors_origins_env = os.environ.get("LUNA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    if "*" not in origins:
        origins.append("http://localhost:5173")
        origins.append("http://127.0.0.1:5173")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # In-memory registries & concurrency control
    registry = RunRegistry()
    run_semaphore = threading.Semaphore(5)
    build_registry: dict[str, BuildState] = {}
    investigation_registry: dict[str, InvestigationRunState] = {}

    # Case store & Conversation store
    conversations_graph = cfg.get("conversations_graph", GRAPH_CONVERSATIONS)
    conv_store = ConversationStore(graph_store, conversations_graph)
    case_store = CaseStore(graph_store, conversations_graph)
    try:
        conv_store.ensure_schema()
        case_store.ensure_schema()
    except Exception:
        pass

    # Pack registry & atlas seeds
    pack_reg: PackRegistry = cfg.get("pack_registry") or default_registry()
    try:
        pack_reg.seed_all_atlas(graph_store, atlas_graph)
    except Exception:
        pass
    try:
        seed_investigation_atlas(graph_store, atlas_graph)
    except Exception:
        pass

    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail if isinstance(exc.detail, str) else "HTTP Error", "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "detail": str(exc)},
        )

    @app.get("/api/health")
    @app.get("/health")
    def health_check():
        """Health check verifying FalkorDB and LLM reachability."""
        falkordb_ok = False
        try:
            graph_store.query(domain_graph, "RETURN 1 AS ping")
            falkordb_ok = True
        except Exception:
            pass

        llm = get_llm()
        llm_info = llm.info()

        return {
            "status": "ok" if (falkordb_ok and llm_info.get("reachable")) else "degraded",
            "falkordb": falkordb_ok,
            "llm": llm_info,
        }

    @app.post("/api/runs")
    def create_run(req: CreateRunRequest):
        """Initiate a new autonomous investigation pipeline run in the background."""
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        llm = OllamaClient() if req.mode == "live" else MockLLMClient()

        pipe_config = PipelineConfig(
            run_id=run_id,
            domain_graph=domain_graph,
            atlas_graph=atlas_graph,
            k_hops=req.k_hops,
            strict_llm=req.strict_llm,
            max_parallel_agents=req.parallel,
            llm_client=llm,
        )

        pipeline = LunaPipeline(graph_store, pipe_config)
        run_state = RunState(run_id=run_id, task=req.task, pipeline=pipeline)
        registry.register(run_state)

        def event_subscriber(ev: PipelineEvent):
            run_state.add_event(ev)

        pipeline.subscribe(event_subscriber)

        def run_worker():
            try:
                run_state.set_status("running")
                res = pipeline.start(req.task, ground_truth=ground_truth)
                run_state.action_id = res.action_id
                run_state.backend_counts = res.backend_counts
                if res.action_id:
                    run_state.set_status("pending_approval")
                else:
                    run_state.set_status("completed")
                    run_state.mark_finished()
            except Exception as err:
                run_state.set_status("failed", error=str(err))
                run_state.mark_finished()

        worker_thread = threading.Thread(target=run_worker, daemon=True)
        worker_thread.start()

        return {"run_id": run_id, "status": "started"}

    @app.get("/api/runs")
    def list_runs():
        """List all active and completed runs."""
        runs = registry.list_all()
        return [
            {
                "run_id": r.run_id,
                "status": r.status,
                "current_step": r.current_step,
                "task": r.task,
                "action_id": r.action_id,
                "created_at": r.created_at,
            }
            for r in runs
        ]

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        """Retrieve state, current step, action details, and metrics for a run."""
        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

        with state.condition:
            return {
                "run_id": state.run_id,
                "status": state.status,
                "current_step": state.current_step,
                "task": state.task,
                "action_id": state.action_id,
                "outcome_id": state.outcome_id,
                "metrics": state.metrics,
                "backend_counts": state.backend_counts,
                "events": [e.model_dump() for e in state.events],
                "error": state.error,
                "created_at": state.created_at,
            }

    @app.get("/api/runs/{run_id}/events")
    def stream_run_events(
        run_id: str,
        request: Request,
        last_event_id: Optional[int] = Query(None),
        header_last_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    ):
        """Server-Sent Events (SSE) streaming discrete PipelineEvent messages."""
        # Determine starting sequence from header or query
        start_seq = 0
        if header_last_id:
            try:
                start_seq = int(header_last_id)
            except ValueError:
                pass
        elif last_event_id is not None:
            start_seq = last_event_id

        # Check investigation registry first
        inv_state = investigation_registry.get(run_id)
        if inv_state:
            def inv_event_generator():
                cursor = 0
                while True:
                    events_to_send = []
                    with inv_state.condition:
                        while cursor < len(inv_state.events):
                            ev = inv_state.events[cursor]
                            cursor += 1
                            if ev.get("seq", 0) > start_seq:
                                events_to_send.append(ev)

                        if not events_to_send:
                            if inv_state.finished:
                                break
                            notified = inv_state.condition.wait(timeout=15.0)
                            if not notified:
                                yield ": keepalive\n\n"
                                continue

                    for ev in events_to_send:
                        seq_id = ev.get("seq", 1)
                        ev_type = ev.get("type", "update")
                        yield f"id: {seq_id}\nevent: {ev_type}\ndata: {json.dumps(ev)}\n\n"

            return StreamingResponse(
                inv_event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

        def event_generator():
            cursor = 0
            while True:
                events_to_send: list[PipelineEvent] = []
                with state.condition:
                    # Collect any events beyond current cursor and start_seq
                    while cursor < len(state.events):
                        ev = state.events[cursor]
                        cursor += 1
                        if ev.seq > start_seq:
                            events_to_send.append(ev)

                    if not events_to_send:
                        if state.finished or state.status in ("pending_approval", "executed", "rejected", "failed"):
                            # If no more events and finished, send any final events and close
                            break
                        # Wait for new events or emit keepalive after 15s
                        notified = state.condition.wait(timeout=15.0)
                        if not notified:
                            yield ": keepalive\n\n"
                            continue

                for ev in events_to_send:
                    data_json = ev.model_dump_json()
                    yield f"id: {ev.seq}\nevent: {ev.step}\ndata: {data_json}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def _resolve_action(
        run_id: str,
        action_id: str,
    ) -> tuple["RunState", str]:
        """Shared helper to validate a run+action before approve/reject."""
        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        return state, f"run_{run_id}" if not run_id.startswith("run_") else run_id

    @app.post("/api/runs/{run_id}/actions/{action_id}/approve")
    def approve_run_action(run_id: str, action_id: str, req: ApproveActionRequest):
        """Approve proposed action, triggering execution, evaluation, and learning."""
        # Q0.4: 422 if approver is empty string
        if not req.approver or not req.approver.strip():
            raise HTTPException(status_code=422, detail="Field 'approver' is required and must not be empty")

        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

        # Q0.4: 404 if action not found; 409 if not PENDING
        run_graph = f"run_{run_id}" if not run_id.startswith("run_") else run_id
        try:
            act_rows = graph_store.query(
                run_graph,
                "MATCH (a:Action {id: $aid}) RETURN a.status AS status",
                {"aid": action_id},
            )
        except Exception:
            act_rows = []
        if not act_rows:
            raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found in run '{run_id}'")
        if act_rows[0].get("status") != "PENDING":
            raise HTTPException(
                status_code=409,
                detail=f"Action '{action_id}' is not in PENDING status (current: {act_rows[0].get('status')})",
            )

        try:
            state.set_status("executing")
            res = state.pipeline.approve_and_finish(
                run_id=run_id,
                action_id=action_id,
                approver=req.approver.strip(),
                ground_truth=ground_truth,
            )
            state.outcome_id = res.outcome_id
            state.metrics = res.metrics.model_dump() if res.metrics else None
            state.set_status("executed")
            state.mark_finished()

            return {
                "status": "EXECUTED",
                "action_id": action_id,
                "outcome_id": res.outcome_id,
                "metrics": state.metrics,
            }
        except NotApprovedError as nae:
            state.set_status("failed", error=str(nae))
            raise HTTPException(status_code=403, detail=str(nae))
        except Exception as err:
            state.set_status("failed", error=str(err))
            raise HTTPException(status_code=500, detail=str(err))

    @app.post("/api/runs/{run_id}/actions/{action_id}/reject")
    def reject_run_action(run_id: str, action_id: str, req: RejectActionRequest):
        """Reject proposed action and update run status."""
        # Q0.4: 422 if approver empty
        if not req.approver or not req.approver.strip():
            raise HTTPException(status_code=422, detail="Field 'approver' is required and must not be empty")

        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

        run_graph = f"run_{run_id}" if not run_id.startswith("run_") else run_id
        # Q0.4: 404 if action not found; 409 if not PENDING
        try:
            act_rows = graph_store.query(
                run_graph,
                "MATCH (a:Action {id: $aid}) RETURN a.status AS status",
                {"aid": action_id},
            )
        except Exception:
            act_rows = []
        if not act_rows:
            raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found in run '{run_id}'")
        if act_rows[0].get("status") != "PENDING":
            raise HTTPException(
                status_code=409,
                detail=f"Action '{action_id}' is not in PENDING status (current: {act_rows[0].get('status')})",
            )

        try:
            act = reject_action(graph_store, run_graph, action_id, approver=req.approver.strip(), reason=req.reason)
            state.set_status("rejected")
            state.mark_finished()
            return {"status": "REJECTED", "action_id": action_id, "rejection_reason": req.reason}
        except Exception as err:
            raise HTTPException(status_code=500, detail=str(err))

    # Q0.4: alias for approve — single-action run where action_id is already in state
    @app.post("/api/runs/{run_id}/approve")
    def approve_run_action_alias(run_id: str, req: ApproveActionRequest):
        """Alias: approve the single pending action in a run (backward-compatible)."""
        if not req.approver or not req.approver.strip():
            raise HTTPException(status_code=422, detail="Field 'approver' is required and must not be empty")

        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        if not state.action_id:
            raise HTTPException(status_code=404, detail=f"No pending action found in run '{run_id}'")

        return approve_run_action(run_id, state.action_id, req)

    @app.get("/api/runs/{run_id}/why/{cid}")
    def explain_entity(run_id: str, cid: str):
        """Return 'Why?' explanation graph and narrative for a specific entity (Part 3.7)."""
        try:
            return build_why_response(graph_store, run_id, cid)
        except Exception:
            run_graph = f"run_{run_id}" if not run_id.startswith("run_") else run_id
            try:
                explanation = explain_customer(graph_store, run_graph, cid)
                return explanation.model_dump()
            except Exception as err:
                raise HTTPException(status_code=500, detail=f"Failed to explain customer '{cid}': {err}")

    @app.get("/api/runs/{run_id}/trace")
    def get_run_trace(run_id: str):
        """Return traversal trace graph, ordered steps, and path node IDs (Part 3.6)."""
        ctx_graph = None
        inv_state = investigation_registry.get(run_id)
        if inv_state:
            c = case_store.get_case(inv_state.case_id)
            if c:
                ctx_graph = c.get("context_graph")

        try:
            return build_trace_response(graph_store, run_id, ctx_graph=ctx_graph)
        except Exception as err:
            pass

        # Fallback to legacy structure
        state = registry.get(run_id)
        run_graph = f"run_{run_id}" if not run_id.startswith("run_") else run_id

        try:
            step_query = (
                "MATCH (ts:TraversalStep) "
                "RETURN ts.id AS id, ts.seq AS seq, ts.tool AS tool, ts.agent_id AS agent_id, "
                "       ts.from_cid AS from_cid, ts.to_cid AS to_cid, ts.rel AS rel, ts.note AS note "
                "ORDER BY ts.seq ASC"
            )
            step_rows = graph_store.query(run_graph, step_query)
            steps = [
                {
                    "seq": int(r.get("seq", 0)),
                    "tool": r.get("tool", ""),
                    "agent_id": r.get("agent_id", ""),
                    "from": r.get("from_cid", ""),
                    "to": r.get("to_cid", ""),
                    "rel": r.get("rel", ""),
                    "note": r.get("note", ""),
                    "focus": r.get("to_cid", ""),
                    "value": {"title": r.get("to_cid", ""), "subtitle": "ENTITY", "properties": []},
                }
                for r in step_rows
            ]

            path_node_ids: list[str] = []
            for s in steps:
                if s["from"] and s["from"] not in path_node_ids:
                    path_node_ids.append(s["from"])
                if s["to"] and s["to"] not in path_node_ids:
                    path_node_ids.append(s["to"])

            n_rows = graph_store.query(
                run_graph,
                "MATCH (n) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props LIMIT 401",
            )
            truncated = len(n_rows) > 400
            nodes = []
            for r in n_rows[:400]:
                props = r.get("props") or {}
                nid = props.get("id") or props.get("cid") or str(r.get("id"))
                nodes.append({
                    "id": str(nid),
                    "label": r.get("labels", ["Entity"])[0] if r.get("labels") else "Entity",
                    "props": props,
                    "context": str(nid) not in path_node_ids,
                })

            e_rows = graph_store.query(
                run_graph,
                "MATCH (a)-[r]->(b) "
                "RETURN id(r) AS id, coalesce(a.cid, a.id, str(id(a))) AS src, "
                "       coalesce(b.cid, b.id, str(id(b))) AS dst, type(r) AS rel "
                "LIMIT 1201",
            )
            edges = []
            for r in e_rows[:1200]:
                edges.append({
                    "id": f"e_{r.get('id')}",
                    "src": str(r.get("src")),
                    "dst": str(r.get("dst")),
                    "rel": r.get("rel") or "RELATED_TO",
                    "on_path": True,
                })

            return {
                "mode": "traversal",
                "nodes": nodes,
                "edges": edges,
                "steps": steps,
                "path_node_ids": path_node_ids,
                "summary": "Investigation trace traversal",
                "truncated": truncated,
                "explored_steps": len(steps),
            }
        except Exception as err:
            raise HTTPException(status_code=500, detail=f"Failed to query trace for run '{run_id}': {err}")

    @app.get("/api/atlas/graph")
    def get_atlas_graph():
        """Get atlas graph topology."""
        return get_graph_topology("atlas")

    @app.get("/api/graphs/{scope}")
    def get_graph_topology(
        scope: str,
        cid: Optional[str] = Query(None),
        hops: int = Query(1),
        conversation_id: Optional[str] = Query(None),
    ):
        """Query node and edge topology for Cytoscape.js visualization (500-node/1500-edge cap)."""
        if not SAFE_SCOPE_PATTERN.match(scope):
            raise HTTPException(status_code=400, detail=f"Invalid or unsafe graph scope identifier: '{scope}'")

        # Map semantic scope to actual FalkorDB graph name
        if scope == "domain":
            if conversation_id:
                graph_name = f"ctx_{conversation_id}"
            else:
                graph_name = domain_graph
        elif scope == "atlas":
            graph_name = atlas_graph
        elif scope == "run":
            runs = registry.list_all()
            if runs:
                graph_name = f"run_{runs[-1].run_id}" if not runs[-1].run_id.startswith("run_") else runs[-1].run_id
            else:
                return {"nodes": [], "edges": [], "truncated": False}
        else:
            graph_name = scope

        try:
            if cid:
                h = max(1, min(5, hops))
                n_query = (
                    f"MATCH (c {{cid: $cid}}) "
                    f"OPTIONAL MATCH (c)-[r*1..{h}]-(n) WHERE NOT n:Source "
                    f"WITH collect(DISTINCT n) + collect(DISTINCT c) AS all_nodes "
                    f"UNWIND all_nodes AS node "
                    f"RETURN DISTINCT id(node) AS id, labels(node) AS labels, properties(node) AS props "
                    f"LIMIT 501"
                )
                n_rows = graph_store.query(graph_name, n_query, {"cid": cid})
                truncated = len(n_rows) > 500
                nodes = []
                node_ids = set()
                for r in n_rows[:500]:
                    props = r.get("props") or {}
                    nid = props.get("id") or props.get("cid") or str(r.get("id"))
                    node_ids.add(str(nid))
                    nodes.append({
                        "data": {
                            "id": str(nid),
                            "label": r.get("labels", ["Entity"])[0] if r.get("labels") else "Entity",
                            **props,
                        }
                    })

                e_query = (
                    "MATCH (a)-[r]->(b) "
                    "WHERE (coalesce(a.cid, a.id, str(id(a))) IN $nids) AND (coalesce(b.cid, b.id, str(id(b))) IN $nids) "
                    "RETURN id(r) AS id, coalesce(a.cid, a.id, str(id(a))) AS src, "
                    "       coalesce(b.cid, b.id, str(id(b))) AS dst, type(r) AS rel, properties(r) AS props "
                    "LIMIT 1501"
                )
                e_rows = graph_store.query(graph_name, e_query, {"nids": list(node_ids)})
                if len(e_rows) > 1500:
                    truncated = True
                edges = []
                for r in e_rows[:1500]:
                    edges.append({
                        "data": {
                            "id": f"e_{r.get('id')}",
                            "source": str(r.get("src")),
                            "target": str(r.get("dst")),
                            "label": r.get("rel") or "RELATED_TO",
                            **(r.get("props") or {}),
                        }
                    })
                return {
                    "scope": scope,
                    "graph_name": graph_name,
                    "nodes": nodes,
                    "edges": edges,
                    "truncated": truncated,
                }

            # Check nodes (up to 501 to check truncation)
            node_query = "MATCH (n) WHERE NOT n:Source RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props LIMIT 501"
            n_rows = graph_store.query(graph_name, node_query)
            truncated = len(n_rows) > 500
            nodes = []
            for r in n_rows[:500]:
                props = r.get("props") or {}
                nid = props.get("id") or props.get("cid") or str(r.get("id"))
                nodes.append({
                    "data": {
                        "id": str(nid),
                        "label": r.get("labels", ["Entity"])[0] if r.get("labels") else "Entity",
                        **props,
                    }
                })

            # Check edges (up to 1501 to check truncation)
            edge_query = (
                "MATCH (a)-[r]->(b) WHERE type(r) <> 'MENTIONED_IN' "
                "RETURN id(r) AS id, coalesce(a.cid, a.id, str(id(a))) AS src, "
                "       coalesce(b.cid, b.id, str(id(b))) AS dst, type(r) AS rel, properties(r) AS props "
                "LIMIT 1501"
            )
            e_rows = graph_store.query(graph_name, edge_query)
            if len(e_rows) > 1500:
                truncated = True
            edges = []
            for r in e_rows[:1500]:
                edges.append({
                    "data": {
                        "id": f"e_{r.get('id')}",
                        "source": str(r.get("src")),
                        "target": str(r.get("dst")),
                        "label": r.get("rel") or "RELATED_TO",
                        **(r.get("props") or {}),
                    }
                })

            return {
                "scope": scope,
                "graph_name": graph_name,
                "nodes": nodes,
                "edges": edges,
                "truncated": truncated,
            }
        except Exception as err:
            return {"scope": scope, "nodes": [], "edges": [], "truncated": False, "note": str(err)}

    @app.get("/api/replay")
    def get_replay_recording():
        """Retrieve pre-recorded deterministic demo run data for instant frontend playback."""
        if os.path.exists(recording_file):
            with open(recording_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"runs": [], "error": "No replay recording file found"}

    @app.get("/api/runs/{run_id}/download")
    def download_run_zip(run_id: str):
        """Download complete workspace zip archive for a build run."""
        from fastapi.responses import FileResponse
        zip_path = Path("workspaces") / f"{run_id}.zip"
        if not zip_path.exists():
            raise HTTPException(status_code=404, detail=f"Zip archive for run '{run_id}' not found")
        return FileResponse(
            path=str(zip_path),
            filename=f"{run_id}.zip",
            media_type="application/zip",
        )

    @app.get("/api/runs/{run_id}/artifacts/{file_path:path}")
    def get_run_artifact(run_id: str, file_path: str):
        """Retrieve raw content of a specific artifact file."""
        from fastapi.responses import PlainTextResponse
        clean_path = Path("workspaces") / run_id / file_path
        try:
            clean_path.resolve().relative_to((Path("workspaces") / run_id).resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid artifact path")
        if not clean_path.exists() or not clean_path.is_file():
            raise HTTPException(status_code=404, detail=f"Artifact '{file_path}' not found")
        return PlainTextResponse(clean_path.read_text(encoding="utf-8"))

    # ---------------------------------------------------------
    # Q5: Chat Platform & Conversation Layer Endpoints
    # ---------------------------------------------------------

    # ---------------------------------------------------------
    # Case Workspace & Investigation Endpoints (Part 3.2)
    # ---------------------------------------------------------

    @app.post("/api/chat/conversations")
    def create_case(req: Optional[CreateConversationRequest] = None):
        """Create a new case in 'draft' status."""
        title = req.title if req and req.title else "New case"
        res = case_store.create_case(title=title)
        return {"id": res["id"]}

    @app.get("/api/chat/conversations")
    def list_cases():
        """List all cases ordered by recency."""
        return case_store.list_cases()

    @app.get("/api/chat/conversations/{conversation_id}")
    def get_case(conversation_id: str):
        """Retrieve complete case details, sources, stats, turns, and LLM info."""
        case = case_store.get_case(conversation_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{conversation_id}' not found")
        llm = get_llm()
        case["llm"] = llm.info()
        return case

    @app.delete("/api/chat/conversations/{conversation_id}", status_code=204)
    def delete_case(conversation_id: str):
        """Delete case, dropping its ctx_<id> graph, run graphs, and disk files."""
        deleted = case_store.delete_case(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Case '{conversation_id}' not found")
        return Response(status_code=204)

    @app.post("/api/chat/conversations/{conversation_id}/sources/text")
    def upload_source_text(conversation_id: str, req: UploadTextRequest):
        """Upload raw text or pasted scenario to the case."""
        case = case_store.get_case(conversation_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{conversation_id}' not found")

        if not req.text or not req.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        if len(req.text) > 200_000:
            raise HTTPException(status_code=413, detail="Text exceeds limit of 200,000 characters")

        name = f"{req.name or 'Pasted Note'}.txt"
        try:
            return case_store.add_source(
                case_id=conversation_id,
                name=name,
                kind="text",
                content_bytes=req.text.encode("utf-8"),
            )
        except ValueError as ve:
            raise HTTPException(status_code=413, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/chat/conversations/{conversation_id}/sources/files")
    async def upload_source_files(conversation_id: str, files: list[UploadFile] = File(...)):
        """Upload one or more source files to the case."""
        case = case_store.get_case(conversation_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{conversation_id}' not found")

        allowed_exts = {".csv", ".json", ".jsonl", ".xlsx", ".sqlite", ".db", ".txt", ".md"}
        results: list[dict[str, Any]] = []

        for f in files:
            fname = f.filename or "file"
            ext = os.path.splitext(fname)[1].lower()
            if ext not in allowed_exts:
                raise HTTPException(
                    status_code=415,
                    detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed_exts))}",
                )

            content = await f.read()
            if len(content) > 20 * 1024 * 1024:
                raise HTTPException(status_code=413, detail=f"File '{fname}' exceeds 20 MB limit")

            kind = "csv" if ext == ".csv" else (
                "xlsx" if ext == ".xlsx" else (
                    "sqlite" if ext in (".sqlite", ".db") else (
                        "jsonl" if ext == ".jsonl" else (
                            "json" if ext == ".json" else (
                                "md" if ext == ".md" else "txt"
                            )
                        )
                    )
                )
            )

            try:
                s_info = case_store.add_source(
                    case_id=conversation_id,
                    name=fname,
                    kind=kind,
                    content_bytes=content,
                )
                results.append(s_info)
            except ValueError as ve:
                raise HTTPException(status_code=413, detail=str(ve))
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        return results

    @app.delete("/api/chat/conversations/{conversation_id}/sources/{source_id}", status_code=204)
    def remove_source(conversation_id: str, source_id: str):
        """Remove a source from the case, marking it stale if ready."""
        case = case_store.get_case(conversation_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{conversation_id}' not found")
        removed = case_store.remove_source(conversation_id, source_id)
        if not removed:
            raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")
        return Response(status_code=204)

    @app.post("/api/chat/conversations/{conversation_id}/build")
    def start_build(conversation_id: str, req: StartBuildRequest):
        """Start context graph construction for the case."""
        case = case_store.get_case(conversation_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{conversation_id}' not found")
        if case.get("status") == "building":
            raise HTTPException(status_code=409, detail="A build is already in progress for this case")

        llm = get_llm()
        info = llm.info()
        if not info.get("reachable"):
            raise HTTPException(status_code=503, detail={"error": "llm_unavailable", "detail": "LLM is unreachable"})
        if info.get("remote") and not req.acknowledge_remote:
            raise HTTPException(status_code=422, detail="Remote model acknowledgement required before sending data")

        build_id = f"build_{uuid.uuid4().hex[:8]}"
        b_state = BuildState(build_id=build_id, case_id=conversation_id)
        build_registry[build_id] = b_state

        def run_build_worker():
            try:
                build_context_graph(
                    conversation_id=conversation_id,
                    case_store=case_store,
                    graph_store=graph_store,
                    llm=llm,
                    emit=lambda ev_type, data: b_state.add_event(ev_type, data),
                    is_cancelled=lambda: b_state.cancelled,
                )
            except Exception as err:
                b_state.add_event("failed", {"error": str(err)})

        threading.Thread(target=run_build_worker, daemon=True).start()
        return {"build_id": build_id}

    @app.get("/api/chat/conversations/{conversation_id}/build/{build_id}/events")
    def stream_build_events(
        conversation_id: str,
        build_id: str,
        last_event_id: Optional[int] = Query(None),
        header_last_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    ):
        """SSE stream for context graph build progress."""
        b_state = build_registry.get(build_id)
        if not b_state:
            raise HTTPException(status_code=404, detail=f"Build '{build_id}' not found")

        start_seq = 0
        if header_last_id:
            try:
                start_seq = int(header_last_id)
            except ValueError:
                pass
        elif last_event_id is not None:
            start_seq = last_event_id

        def event_stream():
            cursor = 0
            while True:
                events_to_send = []
                with b_state.condition:
                    while cursor < len(b_state.events):
                        ev = b_state.events[cursor]
                        cursor += 1
                        if ev["seq"] > start_seq:
                            events_to_send.append(ev)

                    if not events_to_send:
                        if b_state.finished:
                            break
                        notified = b_state.condition.wait(timeout=15.0)
                        if not notified:
                            yield ": keepalive\n\n"
                            continue

                for ev in events_to_send:
                    yield f"id: {ev['seq']}\nevent: build_event\ndata: {json.dumps(ev)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/chat/conversations/{conversation_id}/build/{build_id}/cancel")
    def cancel_build(conversation_id: str, build_id: str):
        """Cancel an in-progress build."""
        b_state = build_registry.get(build_id)
        if not b_state:
            raise HTTPException(status_code=404, detail=f"Build '{build_id}' not found")
        b_state.cancel()
        return {"status": "cancelled", "build_id": build_id}

    @app.get("/api/chat/conversations/{conversation_id}/suggestions")
    def get_suggestions(conversation_id: str):
        """Generate 3 to 4 dynamic suggestions from the context graph."""
        case = case_store.get_case(conversation_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{conversation_id}' not found")
        ctx_graph = case.get("context_graph") or f"ctx_{conversation_id}"
        return generate_suggestions(graph_store, ctx_graph)

    @app.post("/api/chat/conversations/{conversation_id}/messages")
    def send_investigation_message(conversation_id: str, req: SendMessageRequest):
        """Send question to case investigation pipeline."""
        case = case_store.get_case(conversation_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{conversation_id}' not found")
        if case.get("status") != "ready":
            raise HTTPException(
                status_code=409,
                detail=f"Case context graph is not ready (current status: {case.get('status')})",
            )

        question = (req.content or req.prompt or "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        if len(question) > 8000:
            raise HTTPException(status_code=413, detail=f"Question exceeds limit of 8,000 characters")

        # Concurrency limit: max 3 concurrent runs
        active_runs = sum(1 for r in investigation_registry.values() if not r.finished)
        if active_runs >= 3:
            raise HTTPException(status_code=429, detail="Maximum 3 concurrent investigation runs allowed")

        llm = get_llm()
        info = llm.info()
        if not info.get("reachable"):
            raise HTTPException(status_code=503, detail={"error": "llm_unavailable", "detail": "LLM is unreachable"})

        # Set title from first message
        turns = case.get("messages", [])
        if not turns:
            case_store.set_case_status(conversation_id, "ready", title=question[:48])

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        message_id = f"msg_{uuid.uuid4().hex[:8]}"

        # Add user turn
        case_store.add_turn(conversation_id, role="user", text=question)

        inv_state = InvestigationRunState(run_id=run_id, case_id=conversation_id, question=question)
        investigation_registry[run_id] = inv_state

        opts = req.options or {}
        pipeline = InvestigationPipeline(
            case_id=conversation_id,
            run_id=run_id,
            question=question,
            case_store=case_store,
            graph_store=graph_store,
            llm=llm,
            options=opts,
        )

        def worker():
            try:
                pipeline.execute(
                    emit_fn=lambda ev: inv_state.add_event(ev),
                    is_cancelled=lambda: inv_state.cancelled,
                    answer_receiver=lambda: inv_state.pending_answer,
                )
            except Exception as err:
                inv_state.add_event({
                    "run_id": run_id,
                    "seq": inv_state.seq + 1,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "failed",
                    "backend": "llm",
                    "data": {"error": str(err)},
                })

        threading.Thread(target=worker, daemon=True).start()
        return {"message_id": message_id, "run_id": run_id}

    @app.post("/api/runs/{run_id}/answer")
    def provide_run_answer(run_id: str, req: ProvideAnswerRequest):
        """Provide clarifying choice/answer to resume an investigation."""
        choice = req.choice or req.answer
        if not choice:
            raise HTTPException(status_code=400, detail="Answer or choice cannot be empty")

        inv_state = investigation_registry.get(run_id)
        if inv_state:
            inv_state.provide_answer(choice)
            return {"status": "resumed", "run_id": run_id, "answer": choice}

        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        if state.status != "needs_input":
            raise HTTPException(
                status_code=409,
                detail=f"Run '{run_id}' is not waiting for input (current status: {state.status})",
            )

        def resume_worker():
            try:
                state.set_status("running")
                res = state.pipeline.start(task=f"{state.task} (Answer: {choice})", ground_truth=ground_truth)
                if getattr(res, "action_id", None):
                    state.action_id = res.action_id
                    state.set_status("pending_approval")
                else:
                    state.set_status("completed")
                    state.mark_finished()
            except Exception as err:
                state.set_status("failed", error=str(err))
                state.mark_finished()

        threading.Thread(target=resume_worker, daemon=True).start()
        return {"status": "resumed", "run_id": run_id, "answer": choice}

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: str):
        """Cancel a running pipeline or investigation and mark finished."""
        inv_state = investigation_registry.get(run_id)
        if inv_state:
            inv_state.cancel()
            return {"status": "cancelled", "run_id": run_id}

        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        state.set_status("cancelled")
        state.mark_finished()
        return {"status": "cancelled", "run_id": run_id}

    @app.get("/api/atlas/skills")
    def list_atlas_skills():
        """Return catalog of all skills across investigate and build packs."""
        try:
            query = (
                "MATCH (s:Skill)-[:PROVIDES]->(c:Capability) "
                "OPTIONAL MATCH (s)-[:IN_PACK]->(p:Pack) "
                "OPTIONAL MATCH (s)-[:TARGETS]->(t:Technology) "
                "OPTIONAL MATCH (s)-[r:SUCCEEDED_ON]->(tt:TaskType) "
                "RETURN s.id AS id, s.name AS name, s.restricted AS restricted, "
                "       s.prompt_fragment AS prompt_fragment, c.name AS capability, "
                "       p.name AS pack, collect(DISTINCT t.name) AS technologies, "
                "       avg(r.score) AS track_record"
            )
            rows = graph_store.query(atlas_graph, query)
            skills = []
            for r in rows:
                skills.append({
                    "id": r["id"],
                    "name": r.get("name", r["id"]),
                    "restricted": bool(r.get("restricted", False)),
                    "prompt_fragment": r.get("prompt_fragment", ""),
                    "capability": r.get("capability", ""),
                    "pack": r.get("pack") or "investigate",
                    "technologies": [t for t in (r.get("technologies") or []) if t],
                    "track_record": round(float(r.get("track_record") or 0.8), 2),
                })
            return skills
        except Exception as err:
            return []

    if forge_endpoint is not None:
        # The endpoint ignores the path, so serve the exact "/mcp" (no 307 redirect
        # that could drop a POST) as well as "/mcp/..." via the mount.
        from starlette.routing import Route

        app.router.routes.append(Route("/mcp", endpoint=forge_endpoint))
        app.mount("/mcp", forge_endpoint, name="forge_mcp")

    if forge_enabled:
        register_forge_routes(app, graph_store, forge_bus, forge_sessions, atlas_graph, forge_skills_dir)

    ui_dist_dir = Path("ui/dist")
    if ui_dist_dir.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(ui_dist_dir), html=True), name="ui")

    return app


# Default singleton instance for uvicorn run
app = create_app()
