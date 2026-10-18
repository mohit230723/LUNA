"""REST and SSE routes feeding the Forge Platform page (Agents and Skills tabs)."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

import anyio
import redis.exceptions
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from luna.forge.events import SKILL_IMPORTED, ForgeEventBus
from luna.forge.models import ForgeError
from luna.forge.runs import get_run, list_runs
from luna.forge.sessions import SessionRegistry
from luna.forge.skill_import import import_repo_skills, import_skill, set_skill_status
from luna.forge.skill_parse import (
    MAX_REFERENCE_BYTES,
    MAX_REFERENCES,
    MAX_SKILL_BYTES,
    SkillParseError,
    parse_skill_md,
)
from luna.graph.schema import (
    LABEL_CAPABILITY,
    LABEL_CHECKLIST_ITEM,
    LABEL_SECTION,
    LABEL_SKILL,
    LABEL_TECHNOLOGY,
    REL_HAS_CHECK,
    REL_HAS_SECTION,
    REL_PROVIDES,
    REL_REQUIRES,
    REL_TARGETS,
)

__all__ = ["register_forge_routes"]

KEEP_ALIVE_S = 15.0
MAX_UPLOAD_BODY_BYTES = (MAX_REFERENCES + 1) * MAX_SKILL_BYTES + 65_536
_STORE_ERRORS = (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, ConnectionError, OSError)


@contextmanager
def _http_errors() -> Iterator[None]:
    """Map Forge and store errors to HTTP status codes."""
    try:
        yield
    except ForgeError as e:
        status = 404 if e.code == "not_found" else 422
        raise HTTPException(status_code=status, detail=str(e)) from e
    except _STORE_ERRORS as e:
        raise HTTPException(status_code=503, detail="LUNA graph store unavailable") from e


def _connect_snippets(mcp_url: str) -> dict[str, str]:
    def antigravity(headers: bool) -> str:
        server: dict[str, Any] = {"serverUrl": mcp_url}
        if headers:
            server["headers"] = {"Authorization": "Bearer <token>"}
        return json.dumps({"mcpServers": {"luna": server}})

    base = f"claude mcp add --transport http luna {mcp_url}"
    return {
        "claude_code": base,
        "antigravity": antigravity(False),
        "claude_code_token": f'{base} --header "Authorization: Bearer <token>"',
        "antigravity_token": antigravity(True),
    }


def _sse_frame(ev: dict[str, Any]) -> str:
    return f"id: {ev['seq']}\nevent: {ev['type']}\ndata: {json.dumps(ev)}\n\n"


def register_forge_routes(
    app: FastAPI,
    store,
    bus: ForgeEventBus,
    sessions: SessionRegistry,
    atlas_graph: str,
    skills_dir: Path,
    llm_factory: Callable[[], Any] | None = None,
) -> None:
    def _llm():
        if llm_factory is None:
            return None
        try:
            return llm_factory()
        except Exception:
            return None

    async def _blocking(fn):
        with _http_errors():
            return await anyio.to_thread.run_sync(fn)

    @app.get("/api/forge/connect")
    def forge_connect(request: Request) -> dict:
        mcp_url = f"{str(request.base_url)}mcp"
        return {
            "mcp_url": mcp_url,
            "token_required": bool(os.environ.get("LUNA_MCP_TOKEN")),
            "snippets": _connect_snippets(mcp_url),
        }

    @app.get("/api/forge/agents")
    def forge_agents() -> list[dict]:
        return sessions.list()

    @app.get("/api/forge/runs")
    def forge_runs() -> list[dict]:
        with _http_errors():
            return list_runs(store)

    @app.get("/api/forge/runs/{run_id}")
    def forge_run(run_id: str) -> dict:
        with _http_errors():
            return get_run(store, run_id)

    @app.get("/api/forge/events")
    async def forge_events(request: Request, after: int = 0, max_events: int = 0) -> StreamingResponse:
        seq = after
        last_id = request.headers.get("last-event-id")
        if last_id is not None:
            try:
                seq = int(last_id)
            except ValueError:
                pass
        seq = max(0, seq)
        limit = max(0, max_events)

        async def stream():
            cursor = seq
            sent = 0
            while True:
                events = await anyio.to_thread.run_sync(bus.wait_after, cursor, KEEP_ALIVE_S)
                if not events:
                    yield ": keep-alive\n\n"
                    continue
                for ev in events:
                    cursor = ev["seq"]
                    yield _sse_frame(ev)
                    sent += 1
                    if limit and sent >= limit:
                        return

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/forge/skills")
    async def forge_skills() -> list[dict]:
        def work() -> list[dict]:
            rows = store.query(
                atlas_graph,
                f"MATCH (s:{LABEL_SKILL}) "
                f"OPTIONAL MATCH (s)-[:{REL_PROVIDES}]->(c:{LABEL_CAPABILITY}) "
                f"OPTIONAL MATCH (s)-[:{REL_TARGETS}]->(t:{LABEL_TECHNOLOGY}) "
                "RETURN s.id AS id, s.name AS name, s.description AS description, "
                "s.status AS status, s.source AS source, "
                "collect(DISTINCT c.name) AS caps, collect(DISTINCT t.name) AS techs "
                "ORDER BY id",
            )
            return [
                {
                    "id": r["id"],
                    "name": r.get("name") or r["id"],
                    "description": r.get("description") or "",
                    "status": r.get("status") or "",
                    "source": r.get("source") or "",
                    "capabilities": sorted(c for c in r.get("caps") or [] if c),
                    "technologies": sorted(t for t in r.get("techs") or [] if t),
                    # Import warnings are not persisted on the Skill node.
                    "warnings_count": 0,
                }
                for r in rows
            ]

        return await _blocking(work)

    @app.get("/api/forge/skills/{skill_id}")
    async def forge_skill(skill_id: str) -> dict:
        def work() -> dict:
            params = {"id": skill_id}
            rows = store.query(
                atlas_graph,
                f"MATCH (s:{LABEL_SKILL} {{id: $id}}) RETURN s",
                params,
            )
            if not rows:
                raise ForgeError("not_found", f"skill '{skill_id}' not found")
            node = dict(rows[0]["s"])
            sections = [
                {"slug": r["slug"], "title": r["title"], "content": r["content"], "order": r["order"]}
                for r in store.query(
                    atlas_graph,
                    f"MATCH (:{LABEL_SKILL} {{id: $id}})-[:{REL_HAS_SECTION}]->(x:{LABEL_SECTION}) "
                    "RETURN x.slug AS slug, x.title AS title, x.content AS content, x.order AS order "
                    "ORDER BY order",
                    params,
                )
            ]
            checklist = [
                {"id": r["id"], "text": r["text"]}
                for r in store.query(
                    atlas_graph,
                    f"MATCH (:{LABEL_SKILL} {{id: $id}})-[:{REL_HAS_CHECK}]->(x:{LABEL_CHECKLIST_ITEM}) "
                    "RETURN x.check_id AS id, x.text AS text ORDER BY x.order",
                    params,
                )
            ]
            caps = [
                r["n"]
                for r in store.query(
                    atlas_graph,
                    f"MATCH (:{LABEL_SKILL} {{id: $id}})-[:{REL_PROVIDES}]->(c:{LABEL_CAPABILITY}) "
                    "RETURN c.name AS n ORDER BY n",
                    params,
                )
            ]
            techs = [
                r["n"]
                for r in store.query(
                    atlas_graph,
                    f"MATCH (:{LABEL_SKILL} {{id: $id}})-[:{REL_TARGETS}]->(t:{LABEL_TECHNOLOGY}) "
                    "RETURN t.name AS n ORDER BY n",
                    params,
                )
            ]
            requires = [
                r["n"]
                for r in store.query(
                    atlas_graph,
                    f"MATCH (:{LABEL_SKILL} {{id: $id}})-[:{REL_REQUIRES}]->(r:{LABEL_SKILL}) "
                    "RETURN r.id AS n ORDER BY n",
                    params,
                )
            ]
            required_by = [
                r["n"]
                for r in store.query(
                    atlas_graph,
                    f"MATCH (r:{LABEL_SKILL})-[:{REL_REQUIRES}]->(:{LABEL_SKILL} {{id: $id}}) "
                    "RETURN r.id AS n ORDER BY n",
                    params,
                )
            ]

            nodes = [{"id": skill_id, "label": node.get("name") or skill_id, "type": "skill"}]
            edges: list[dict[str, str]] = []
            for c in caps:
                nodes.append({"id": c, "label": c, "type": "capability"})
                edges.append({"source": skill_id, "target": c, "type": REL_PROVIDES})
            for t in techs:
                nodes.append({"id": t, "label": t, "type": "technology"})
                edges.append({"source": skill_id, "target": t, "type": REL_TARGETS})
            for r in requires:
                nodes.append({"id": r, "label": r, "type": "skill"})
                edges.append({"source": skill_id, "target": r, "type": REL_REQUIRES})
            for r in required_by:
                nodes.append({"id": r, "label": r, "type": "skill"})
                edges.append({"source": r, "target": skill_id, "type": REL_REQUIRES})

            return {
                "id": skill_id,
                "name": node.get("name") or skill_id,
                "description": node.get("description") or "",
                "status": node.get("status") or "",
                "source": node.get("source") or "",
                "body": node.get("body") or "",
                "capabilities": caps,
                "technologies": techs,
                "sections": sections,
                "checklist": checklist,
                "requires": requires,
                "required_by": required_by,
                "neighbourhood": {"nodes": nodes, "edges": edges},
            }

        return await _blocking(work)

    async def _read_limited(upload: UploadFile, limit: int, what: str) -> bytes:
        data = await upload.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(status_code=413, detail=f"{what} exceeds the {limit // 1024} KB limit")
        return data

    @app.post("/api/forge/skills/upload")
    async def forge_skill_upload(request: Request) -> dict:
        # Reject oversized bodies before Starlette parses or spools the multipart form.
        try:
            declared = int(request.headers.get("content-length") or 0)
        except ValueError:
            declared = 0
        if declared > MAX_UPLOAD_BODY_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"upload exceeds the {MAX_UPLOAD_BODY_BYTES // 1024} KB request limit",
            )
        try:
            form = await request.form(max_files=MAX_REFERENCES + 2, max_fields=MAX_REFERENCES + 8)
        except StarletteHTTPException as e:  # Starlette's file/field count limits
            raise HTTPException(status_code=413, detail=f"upload exceeds limits: {e.detail}") from e
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"invalid multipart upload: {e}") from e
        try:
            skill = form.get("skill")
            if not isinstance(skill, UploadFile):
                raise HTTPException(status_code=422, detail="missing 'skill' file field")
            refs = [r for r in form.getlist("references") if isinstance(r, UploadFile)]
            return await _handle_upload(skill, refs)
        finally:
            await form.close()

    async def _handle_upload(skill: UploadFile, refs: list[UploadFile]) -> dict:
        if len(refs) > MAX_REFERENCES:
            raise HTTPException(status_code=413, detail=f"too many references (max {MAX_REFERENCES})")
        skill_bytes = await _read_limited(skill, MAX_SKILL_BYTES, "SKILL.md")
        ref_bytes = [
            (r.filename or f"reference-{i + 1}.md", await _read_limited(r, MAX_REFERENCE_BYTES, f"reference '{r.filename}'"))
            for i, r in enumerate(refs)
        ]
        try:
            text = skill_bytes.decode("utf-8")
            ref_texts = [(name, raw.decode("utf-8")) for name, raw in ref_bytes]
            doc = parse_skill_md(text, ref_texts, default_id="")
        except UnicodeDecodeError as e:
            raise HTTPException(status_code=422, detail="files must be UTF-8 text") from e
        except SkillParseError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        result = await _blocking(lambda: import_skill(store, doc, "upload", atlas_graph, llm=_llm()))
        bus.publish(SKILL_IMPORTED, {"skill_id": result.skill_id, "status": result.status})
        return result.model_dump()

    @app.post("/api/forge/skills/reimport")
    async def forge_skill_reimport() -> list[dict]:
        results = await _blocking(lambda: import_repo_skills(store, skills_dir, atlas_graph))
        for r in results:
            if r.changed:
                bus.publish(SKILL_IMPORTED, {"skill_id": r.skill_id, "status": r.status})
        return [r.model_dump() for r in results]

    async def _set_status(skill_id: str, status: str) -> Response:
        await _blocking(lambda: set_skill_status(store, skill_id, status, atlas_graph))  # type: ignore[arg-type]
        bus.publish(SKILL_IMPORTED, {"skill_id": skill_id, "status": status})
        return Response(status_code=204)

    @app.post("/api/forge/skills/{skill_id}/approve", status_code=204)
    async def forge_skill_approve(skill_id: str) -> Response:
        return await _set_status(skill_id, "approved")

    @app.post("/api/forge/skills/{skill_id}/reject", status_code=204)
    async def forge_skill_reject(skill_id: str) -> Response:
        return await _set_status(skill_id, "rejected")
