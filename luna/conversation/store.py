"""ConversationStore backed by FalkorDB conversations graph."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from luna.graph.schema import (
    GRAPH_CONVERSATIONS,
    LABEL_CONVERSATION,
    LABEL_TURN,
    LABEL_RUN_REF,
    REL_HAS_TURN,
    REL_TRIGGERED,
    REL_FOLLOWS,
)
from luna.graph.store import GraphStore


class ConversationStore:
    """Manages conversations and multi-turn message history in FalkorDB."""

    def __init__(self, store: GraphStore, graph_name: str = GRAPH_CONVERSATIONS) -> None:
        self.store = store
        self.graph_name = graph_name

    def ensure_schema(self) -> None:
        """Create indices on Conversation and Turn nodes if supported."""
        try:
            self.store.query(self.graph_name, f"CREATE INDEX ON :{LABEL_CONVERSATION}(id)")
            self.store.query(self.graph_name, f"CREATE INDEX ON :{LABEL_TURN}(id)")
        except Exception:
            pass

    def create_conversation(
        self,
        title: str = "New Investigation",
        conversation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new conversation node."""
        cid = conversation_id or f"conv-{uuid.uuid4().hex[:8]}"
        now = time.time()
        self.store.query(
            self.graph_name,
            f"MERGE (c:{LABEL_CONVERSATION} {{id: $cid}}) "
            "ON CREATE SET c.title = $title, c.created_at = $now, c.updated_at = $now "
            "ON MATCH SET c.updated_at = $now",
            {"cid": cid, "title": title, "now": now},
        )
        return {
            "id": cid,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "turns": [],
        }

    def list_conversations(self) -> list[dict[str, Any]]:
        """List all conversations ordered by updated_at descending."""
        rows = self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION}) "
            "RETURN c.id AS id, c.title AS title, c.created_at AS created_at, c.updated_at AS updated_at "
            "ORDER BY c.updated_at DESC",
        )
        return [
            {
                "id": r["id"],
                "title": r.get("title", "Untitled Conversation"),
                "created_at": float(r.get("created_at", 0)),
                "updated_at": float(r.get("updated_at", 0)),
            }
            for r in rows
        ]

    def get_conversation(self, conv_id: str) -> Optional[dict[str, Any]]:
        """Fetch conversation metadata and ordered turns with typed blocks."""
        rows = self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $cid}}) "
            "RETURN c.id AS id, c.title AS title, c.created_at AS created_at, c.updated_at AS updated_at",
            {"cid": conv_id},
        )
        if not rows:
            return None

        conv_data = dict(rows[0])

        turn_rows = self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $cid}})-[:{REL_HAS_TURN}]->(t:{LABEL_TURN}) "
            "OPTIONAL MATCH (t)-[:{REL_TRIGGERED}]->(r:RunRef) "
            "RETURN t.id AS id, t.role AS role, t.text AS text, t.created_at AS created_at, "
            "       t.blocks_json AS blocks_json, r.run_id AS run_id, r.pack AS pack "
            "ORDER BY t.created_at ASC",
            {"cid": conv_id},
        )

        turns = []
        for tr in turn_rows:
            blocks = []
            if tr.get("blocks_json"):
                try:
                    blocks = json.loads(tr["blocks_json"])
                except Exception:
                    blocks = []
            turns.append({
                "id": tr["id"],
                "role": tr["role"],
                "text": tr["text"],
                "created_at": float(tr.get("created_at", 0)),
                "blocks": blocks,
                "run_id": tr.get("run_id"),
                "pack": tr.get("pack"),
            })

        conv_data["turns"] = turns
        return conv_data

    def add_turn(
        self,
        conv_id: str,
        role: str,
        text: str,
        blocks: list[dict[str, Any]] = [],
        run_id: Optional[str] = None,
        pack: Optional[str] = None,
    ) -> dict[str, Any]:
        """Append a Turn to the conversation, linking to previous turn and optional RunRef."""
        turn_id = f"turn-{uuid.uuid4().hex[:8]}"
        now = time.time()
        blocks_json = json.dumps(blocks)

        # 1. Create Turn
        self.store.query(
            self.graph_name,
            f"MERGE (c:{LABEL_CONVERSATION} {{id: $cid}}) "
            f"CREATE (t:{LABEL_TURN} {{id: $tid, role: $role, text: $text, created_at: $now, blocks_json: $bjson}}) "
            f"CREATE (c)-[:{REL_HAS_TURN}]->(t) "
            "SET c.updated_at = $now",
            {
                "cid": conv_id,
                "tid": turn_id,
                "role": role,
                "text": text,
                "now": now,
                "bjson": blocks_json,
            },
        )

        # 2. Link previous turn via FOLLOWS
        prev_rows = self.store.query(
            self.graph_name,
            f"MATCH (c:{LABEL_CONVERSATION} {{id: $cid}})-[:{REL_HAS_TURN}]->(t:{LABEL_TURN}) "
            "WHERE t.id <> $tid "
            "RETURN t.id AS id ORDER BY t.created_at DESC LIMIT 1",
            {"cid": conv_id, "tid": turn_id},
        )
        if prev_rows:
            prev_id = prev_rows[0]["id"]
            self.store.query(
                self.graph_name,
                f"MATCH (t_prev:{LABEL_TURN} {{id: $prev_id}}) "
                f"MATCH (t_cur:{LABEL_TURN} {{id: $tid}}) "
                f"MERGE (t_cur)-[:{REL_FOLLOWS}]->(t_prev)",
                {"prev_id": prev_id, "tid": turn_id},
            )

        # 3. Link RunRef if run_id provided
        if run_id:
            ref_id = f"ref-{uuid.uuid4().hex[:8]}"
            self.store.query(
                self.graph_name,
                f"MATCH (t:{LABEL_TURN} {{id: $tid}}) "
                f"CREATE (r:{LABEL_RUN_REF} {{id: $ref_id, run_id: $run_id, pack: $pack}}) "
                f"CREATE (t)-[:{REL_TRIGGERED}]->(r)",
                {"tid": turn_id, "ref_id": ref_id, "run_id": run_id, "pack": pack or ""},
            )

        return {
            "id": turn_id,
            "role": role,
            "text": text,
            "created_at": now,
            "blocks": blocks,
            "run_id": run_id,
            "pack": pack,
        }

    def update_turn_blocks(self, turn_id: str, blocks: list[dict[str, Any]]) -> None:
        """Update blocks_json for an existing Turn."""
        self.store.query(
            self.graph_name,
            f"MATCH (t:{LABEL_TURN} {{id: $tid}}) SET t.blocks_json = $bjson",
            {"tid": turn_id, "bjson": json.dumps(blocks)},
        )

    def get_context(self, conv_id: str) -> dict[str, Any]:
        """Retrieve conversation history context for follow-up prompts (e.g. Scenario D3)."""
        conv = self.get_conversation(conv_id)
        if not conv:
            return {"conversation_id": conv_id, "entities": [], "pack": None, "run_id": None}

        # Extract entities mentioned in past turns (e.g. cust-* identifiers)
        import re
        entities: list[str] = []
        prior_pack: Optional[str] = None
        prior_run_id: Optional[str] = None

        for turn in conv.get("turns", []):
            found = re.findall(r"cust(?:[-_][a-z0-9]+)+", turn.get("text", ""), re.IGNORECASE)
            for f in found:
                if f not in entities:
                    entities.append(f)
            if turn.get("pack"):
                prior_pack = turn.get("pack")
            if turn.get("run_id"):
                prior_run_id = turn.get("run_id")

        return {
            "conversation_id": conv_id,
            "entities": entities,
            "pack": prior_pack,
            "run_id": prior_run_id,
            "turns_count": len(conv.get("turns", [])),
        }
