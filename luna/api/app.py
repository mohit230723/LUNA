"""FastAPI REST API application with Server-Sent Events (SSE) streaming and Graph inspection."""

import os
import re
import json
import time
import uuid
import urllib.request
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from fastapi import FastAPI, HTTPException, Request, Response, Query, Header
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from luna.graph.store import GraphStore
from luna.graph.schema import GRAPH_DOMAIN, GRAPH_ATLAS, LABEL_CUSTOMER
from luna.domain.seed import GroundTruth
from luna.orchestrator.pipeline import LunaPipeline, PipelineConfig, PipelineEvent, PipelineRunResult
from luna.orchestrator.actions import approve_action, reject_action, NotApprovedError
from luna.orchestrator.explain import explain_customer, explain_action
from luna.llm.client import MockLLMClient, OllamaClient


# Strict allowlist pattern for graph scope identifiers to prevent Cypher injection
SAFE_SCOPE_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


class CreateRunRequest(BaseModel):
    task: str = "Investigate suspected auto insurance fraud ring"
    k_hops: int = 2
    strict_llm: bool = False
    parallel: int = 3
    mode: str = "scripted"  # "scripted" or "live"


class ApproveActionRequest(BaseModel):
    approver: str = "human"


class RejectActionRequest(BaseModel):
    approver: str = "human"
    reason: str = ""


class RunState:
    """Thread-safe state container for an autonomous investigation run."""

    def __init__(self, run_id: str, task: str, pipeline: LunaPipeline) -> None:
        self.run_id = run_id
        self.task = task
        self.pipeline = pipeline
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

    app = FastAPI(
        title="LUNA OS API",
        description="Autonomous Multi-Agent Graph Intelligence Engine API with SSE Streaming",
        version="1.0.0",
    )

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

    # In-memory run registry
    registry = RunRegistry()

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

    @app.get("/health")
    def health_check():
        """Health check verifying FalkorDB and Ollama reachability."""
        falkordb_status = "connected"
        try:
            graph_store.query(domain_graph, "RETURN 1 AS ping")
        except Exception as e:
            falkordb_status = f"unreachable: {e}"

        ollama_status = "unreachable"
        try:
            req = urllib.request.Request("http://localhost:11434/api/version", method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    ollama_status = "reachable"
        except Exception:
            pass

        return {
            "status": "ok" if falkordb_status == "connected" else "degraded",
            "falkordb": falkordb_status,
            "ollama": ollama_status,
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
        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

        # Determine starting sequence from header or query
        start_seq = 0
        if header_last_id:
            try:
                start_seq = int(header_last_id)
            except ValueError:
                pass
        elif last_event_id is not None:
            start_seq = last_event_id

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

    @app.post("/api/runs/{run_id}/actions/{action_id}/approve")
    def approve_run_action(run_id: str, action_id: str, req: ApproveActionRequest):
        """Approve proposed action, triggering execution, evaluation, and learning."""
        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

        try:
            state.set_status("executing")
            res = state.pipeline.approve_and_finish(
                run_id=run_id,
                action_id=action_id,
                approver=req.approver,
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
        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

        try:
            run_graph = f"run_{run_id}" if not run_id.startswith("run_") else run_id
            act = reject_action(graph_store, run_graph, action_id, approver=req.approver, reason=req.reason)
            state.set_status("rejected")
            state.mark_finished()
            return {"status": "REJECTED", "action_id": action_id, "rejection_reason": req.reason}
        except Exception as err:
            raise HTTPException(status_code=500, detail=str(err))

    @app.get("/api/runs/{run_id}/why/{cid}")
    def explain_entity(run_id: str, cid: str):
        """Return 'Why?' explanation graph and narrative for a specific entity."""
        state = registry.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

        run_graph = f"run_{run_id}" if not run_id.startswith("run_") else run_id
        try:
            explanation = explain_customer(graph_store, run_graph, cid)
            return explanation.model_dump()
        except Exception as err:
            raise HTTPException(status_code=500, detail=f"Failed to explain customer '{cid}': {err}")

    @app.get("/api/graphs/{scope}")
    def get_graph_topology(scope: str):
        """Query node and edge topology for Cytoscape.js visualization (500-node/1500-edge cap)."""
        if not SAFE_SCOPE_PATTERN.match(scope):
            raise HTTPException(status_code=400, detail=f"Invalid or unsafe graph scope identifier: '{scope}'")

        # Map semantic scope to actual FalkorDB graph name
        if scope == "domain":
            graph_name = domain_graph
        elif scope == "atlas":
            graph_name = atlas_graph
        elif scope == "run":
            # Return most recent run if available
            runs = registry.list_all()
            if runs:
                graph_name = f"run_{runs[-1].run_id}" if not runs[-1].run_id.startswith("run_") else runs[-1].run_id
            else:
                return {"nodes": [], "edges": [], "truncated": False}
        else:
            graph_name = scope

        try:
            # Check nodes (up to 501 to check truncation)
            node_query = "MATCH (n) RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props LIMIT 501"
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
                "MATCH (a)-[r]->(b) "
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

    ui_dist_dir = Path("ui/dist")
    if ui_dist_dir.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(ui_dist_dir), html=True), name="ui")

    return app


# Default singleton instance for uvicorn run
app = create_app()
