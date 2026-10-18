"""Case storage backed by the FalkorDB conversations graph."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from luna.graph.schema import GRAPH_CONVERSATIONS
from luna.graph.store import GraphStore

LABEL_CONVERSATION = "Conversation"
LABEL_SOURCE = "Source"
LABEL_TURN = "Turn"

REL_HAS_SOURCE = "HAS_SOURCE"
REL_HAS_TURN = "HAS_TURN"

CASE_DATA_ROOT = Path("data/cases")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to basename only with allowlist characters [A-Za-z0-9._ -]."""
    base = os.path.basename(filename)
    sanitized = re.sub(r"[^A-Za-z0-9._ -]", "_", base)
    return sanitized if sanitized else "source_file"


class CaseStore:
    """Manages Case metadata, sources, and turns in the conversations FalkorDB graph."""

    def __init__(self, store: Optional[GraphStore] = None, graph_name: str = GRAPH_CONVERSATIONS) -> None:
        self.store = store or GraphStore()
        self.graph_name = graph_name
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Create indices on Conversation and Source nodes if supported."""
        try:
            self.store.query(self.graph_name, f"CREATE INDEX ON :{LABEL_CONVERSATION}(id)")
            self.store.query(self.graph_name, f"CREATE INDEX ON :{LABEL_SOURCE}(id)")
            self.store.query(self.graph_name, f"CREATE INDEX ON :{LABEL_TURN}(id)")
        except Exception:
            pass

    def create_case(self, title: str = "New case") -> dict[str, Any]:
        """Create a new case in 'draft' status."""
        case_id = uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        ctx_graph = f"ctx_{case_id}"

        self.store.query(
            self.graph_name,
            f"CREATE (c:{LABEL_CONVERSATION} {{"
            f"  id: $id, title: $title, status: 'draft', created_at: $now, "
            f"  updated_at: $now, context_graph: $ctx_graph, build_error: ''"
            f"}})",
            {"id": case_id, "title": title, "now": now, "ctx_graph": ctx_graph},
        )

        case_dir = CASE_DATA_ROOT / case_id / "sources"
        case_dir.mkdir(parents=True, exist_ok=True)

        return {
            "id": case_id,
            "title": title,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
            "context_graph": ctx_graph,
        }

    def list_cases(self) -> list[dict[str, Any]]:
        """List all cases ordered by updated_at desc."""
        rows = self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION}) "
            f"RETURN c.id AS id, c.title AS title, c.status AS status, c.updated_at AS updated_at "
            f"ORDER BY c.updated_at DESC",
        )
        cases: list[dict[str, Any]] = []
        for r in rows:
            cases.append({
                "id": r.get("id"),
                "title": r.get("title") or "Untitled Case",
                "status": r.get("status") or "draft",
                "updated_at": r.get("updated_at") or "",
            })
        return cases

    def get_case(self, case_id: str) -> Optional[dict[str, Any]]:
        """Retrieve complete case details including sources, turns, and stats."""
        rows = self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $id}}) "
            f"RETURN c.id AS id, c.title AS title, c.status AS status, "
            f"       c.created_at AS created_at, c.updated_at AS updated_at, "
            f"       c.context_graph AS context_graph, c.build_error AS build_error, "
            f"       c.stats_json AS stats_json",
            {"id": case_id},
        )
        if not rows:
            return None

        c_row = rows[0]
        stats = None
        stats_raw = c_row.get("stats_json")
        if stats_raw:
            try:
                stats = json.loads(stats_raw)
            except Exception:
                pass

        # Load sources
        src_rows = self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $id}})-[:{REL_HAS_SOURCE}]->(s:{LABEL_SOURCE}) "
            f"RETURN s.id AS id, s.name AS name, s.kind AS kind, s.bytes AS bytes, "
            f"       s.status AS status, s.error AS error, s.stats_json AS stats_json, s.path AS path",
            {"id": case_id},
        )
        sources: list[dict[str, Any]] = []
        for sr in src_rows:
            s_stats = None
            if sr.get("stats_json"):
                try:
                    s_stats = json.loads(sr.get("stats_json"))
                except Exception:
                    pass
            sources.append({
                "id": sr.get("id"),
                "name": sr.get("name"),
                "kind": sr.get("kind"),
                "bytes": int(sr.get("bytes") or 0),
                "status": sr.get("status") or "pending",
                "error": sr.get("error") or None,
                "stats": s_stats,
                "path": sr.get("path") or "",
            })

        # Load turns
        turn_rows = self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $id}})-[:{REL_HAS_TURN}]->(t:{LABEL_TURN}) "
            f"RETURN t.id AS id, t.idx AS idx, t.role AS role, t.blocks_json AS blocks_json, "
            f"       t.run_id AS run_id, t.created_at AS created_at "
            f"ORDER BY t.idx ASC, t.created_at ASC",
            {"id": case_id},
        )
        messages: list[dict[str, Any]] = []
        for tr in turn_rows:
            blocks = []
            if tr.get("blocks_json"):
                try:
                    blocks = json.loads(tr.get("blocks_json"))
                except Exception:
                    pass
            messages.append({
                "id": tr.get("id"),
                "role": tr.get("role") or "assistant",
                "created_at": tr.get("created_at") or "",
                "run_id": tr.get("run_id") or None,
                "blocks": blocks,
            })

        return {
            "id": c_row.get("id"),
            "title": c_row.get("title") or "New case",
            "status": c_row.get("status") or "draft",
            "created_at": c_row.get("created_at"),
            "updated_at": c_row.get("updated_at"),
            "context_graph": c_row.get("context_graph") or f"ctx_{case_id}",
            "build_error": c_row.get("build_error") or "",
            "stats": stats,
            "sources": sources,
            "messages": messages,
        }

    def delete_case(self, case_id: str) -> bool:
        """Drop case record, its context graph, its run graphs, and on-disk files."""
        # 1. Fetch case info to locate graphs
        c = self.get_case(case_id)
        if not c:
            return False

        ctx_graph = c.get("context_graph") or f"ctx_{case_id}"

        # 2. Drop context graph
        try:
            self.store.delete_graph(ctx_graph)
        except Exception:
            pass

        # 3. Find and drop all associated run graphs
        run_ids = {m.get("run_id") for m in c.get("messages", []) if m.get("run_id")}
        for r_id in run_ids:
            try:
                self.store.delete_graph(f"run_{r_id}")
            except Exception:
                pass

        # 4. Delete graph nodes from conversations graph
        self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $id}}) "
            f"OPTIONAL MATCH (c)-[:{REL_HAS_SOURCE}]->(s:{LABEL_SOURCE}) "
            f"OPTIONAL MATCH (c)-[:{REL_HAS_TURN}]->(t:{LABEL_TURN}) "
            f"DETACH DELETE s, t, c",
            {"id": case_id},
        )

        # 5. Clean up data directory
        case_dir = CASE_DATA_ROOT / case_id
        if case_dir.exists():
            shutil.rmtree(case_dir, ignore_errors=True)

        return True

    def add_source(
        self,
        case_id: str,
        name: str,
        kind: str,
        content_bytes: bytes,
        stats: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Save a source to disk and persist its Source node in the graph."""
        case = self.get_case(case_id)
        if not case:
            raise KeyError(f"Case {case_id} not found")

        # Limits verification
        current_sources = case.get("sources", [])
        if len(current_sources) >= 20:
            raise ValueError("Limit exceeded: maximum 20 files per case")

        total_bytes = sum(s.get("bytes", 0) for s in current_sources) + len(content_bytes)
        if total_bytes > 100 * 1024 * 1024:
            raise ValueError("Limit exceeded: maximum 100 MB per case")

        if len(content_bytes) > 20 * 1024 * 1024:
            raise ValueError("Limit exceeded: file exceeds 20 MB limit")

        source_id = uuid4().hex[:12]
        sanitized_name = sanitize_filename(name)
        source_dir = CASE_DATA_ROOT / case_id / "sources" / source_id
        source_dir.mkdir(parents=True, exist_ok=True)
        file_path = source_dir / sanitized_name

        with open(file_path, "wb") as f:
            f.write(content_bytes)

        stats_json = json.dumps(stats or {})
        now = datetime.now(timezone.utc).isoformat()

        # If previous status was ready, adding source marks case stale
        next_status = "stale" if case.get("status") == "ready" else case.get("status", "draft")

        self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $case_id}}) "
            f"CREATE (s:{LABEL_SOURCE} {{"
            f"  id: $source_id, name: $name, kind: $kind, bytes: $bytes, "
            f"  status: 'pending', error: '', stats_json: $stats_json, path: $path"
            f"}}) "
            f"CREATE (c)-[:{REL_HAS_SOURCE}]->(s) "
            f"SET c.status = $next_status, c.updated_at = $now",
            {
                "case_id": case_id,
                "source_id": source_id,
                "name": sanitized_name,
                "kind": kind,
                "bytes": len(content_bytes),
                "stats_json": stats_json,
                "path": str(file_path.resolve()),
                "next_status": next_status,
                "now": now,
            },
        )

        return {
            "id": source_id,
            "name": sanitized_name,
            "kind": kind,
            "bytes": len(content_bytes),
            "status": "pending",
            "stats": stats,
            "path": str(file_path.resolve()),
        }

    def remove_source(self, case_id: str, source_id: str) -> bool:
        """Remove a source file and update case status to stale if ready."""
        case = self.get_case(case_id)
        if not case:
            return False

        # Find source path
        source = next((s for s in case.get("sources", []) if s.get("id") == source_id), None)
        if source and source.get("path"):
            p = Path(source["path"])
            if p.exists():
                p.unlink(missing_ok=True)
            if p.parent.exists():
                shutil.rmtree(p.parent, ignore_errors=True)

        now = datetime.now(timezone.utc).isoformat()
        next_status = "stale" if case.get("status") == "ready" else case.get("status", "draft")

        self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $case_id}})-[r:{REL_HAS_SOURCE}]->(s:{LABEL_SOURCE} {{id: $source_id}}) "
            f"DELETE r, s "
            f"SET c.status = $next_status, c.updated_at = $now",
            {"case_id": case_id, "source_id": source_id, "next_status": next_status, "now": now},
        )
        return True

    def update_source_status(
        self,
        source_id: str,
        status: str,
        error: str = "",
        stats: Optional[dict[str, Any]] = None,
    ) -> None:
        """Update individual source parsing status."""
        stats_json = json.dumps(stats or {})
        self.store.query(
            self.graph_name,
            f"MATCH (s:{LABEL_SOURCE} {{id: $source_id}}) "
            f"SET s.status = $status, s.error = $error, s.stats_json = $stats_json",
            {"source_id": source_id, "status": status, "error": error, "stats_json": stats_json},
        )

    def set_case_status(
        self,
        case_id: str,
        status: str,
        build_error: str = "",
        stats: Optional[dict[str, Any]] = None,
        title: Optional[str] = None,
    ) -> None:
        """Update case lifecycle status (draft, building, ready, failed, stale)."""
        now = datetime.now(timezone.utc).isoformat()
        params: dict[str, Any] = {
            "case_id": case_id,
            "status": status,
            "build_error": build_error,
            "now": now,
        }
        set_clauses = ["c.status = $status", "c.build_error = $build_error", "c.updated_at = $now"]
        if stats is not None:
            params["stats_json"] = json.dumps(stats)
            set_clauses.append("c.stats_json = $stats_json")
        if title:
            params["title"] = title
            set_clauses.append("c.title = $title")

        self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $case_id}}) "
            f"SET {', '.join(set_clauses)}",
            params,
        )

    def add_turn(
        self,
        case_id: str,
        role: str,
        blocks: list[dict[str, Any]],
        run_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Append a message turn to the case."""
        turn_id = uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()

        # Count existing turns for idx
        rows = self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $id}})-[:{REL_HAS_TURN}]->(t:{LABEL_TURN}) "
            f"RETURN count(t) AS cnt",
            {"id": case_id},
        )
        idx = int(rows[0].get("cnt", 0)) if rows else 0

        self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $case_id}}) "
            f"CREATE (t:{LABEL_TURN} {{"
            f"  id: $turn_id, idx: $idx, role: $role, blocks_json: $blocks_json, "
            f"  run_id: $run_id, created_at: $now"
            f"}}) "
            f"CREATE (c)-[:{REL_HAS_TURN}]->(t) "
            f"SET c.updated_at = $now",
            {
                "case_id": case_id,
                "turn_id": turn_id,
                "idx": idx,
                "role": role,
                "blocks_json": json.dumps(blocks),
                "run_id": run_id or "",
                "now": now,
            },
        )

        return {
            "id": turn_id,
            "role": role,
            "created_at": now,
            "run_id": run_id,
            "blocks": blocks,
        }
