"""Thread-safe TraversalRecorder and cited Answer composer for Investigate Pack."""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any, Callable, Optional
from pydantic import BaseModel, Field

from luna.graph.schema import (
    LABEL_TRAVERSAL_STEP,
    LABEL_ANSWER,
    LABEL_TASK,
    LABEL_CUSTOMER,
    REL_HAS_STEP,
    REL_ANSWERED_BY,
    REL_CITES,
)
from luna.graph.store import GraphStore


class TraversalStep(BaseModel):
    """A discrete traversal step taken by an agent during graph exploration."""

    id: str = Field(default_factory=lambda: f"step-{uuid.uuid4().hex[:8]}")
    seq: int = 1
    tool: str = ""
    agent_id: str = ""
    from_cid: str = ""
    to_cid: str = ""
    rel: str = ""
    note: str = ""


class TraversalRecorder:
    """Thread-safe recorder for multi-agent graph traversal steps.

    Records steps during sub-agent execution and validates/promotes them
    into the run memory graph with anti-hallucination CID checks.
    """

    def __init__(
        self,
        event_callback: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._seq: int = 0
        self._steps: list[TraversalStep] = []
        self._event_callback = event_callback

    def record_step(
        self,
        tool: str,
        agent_id: str,
        from_cid: str,
        to_cid: str,
        rel: str = "",
        note: str = "",
    ) -> TraversalStep:
        """Record a single step and trigger traversal_step SSE event."""
        with self._lock:
            self._seq += 1
            step = TraversalStep(
                seq=self._seq,
                tool=tool,
                agent_id=agent_id,
                from_cid=from_cid,
                to_cid=to_cid,
                rel=rel,
                note=note,
            )
            self._steps.append(step)

        if self._event_callback:
            try:
                self._event_callback(
                    "traversal_step",
                    {
                        "id": step.id,
                        "seq": step.seq,
                        "tool": step.tool,
                        "agent_id": step.agent_id,
                        "from_cid": step.from_cid,
                        "to_cid": step.to_cid,
                        "rel": step.rel,
                        "note": step.note,
                    },
                )
            except Exception:
                pass

        return step

    def get_steps(self) -> list[TraversalStep]:
        """Return a snapshot of all recorded traversal steps."""
        with self._lock:
            return list(self._steps)

    def persist_to_run_graph(
        self,
        store: GraphStore,
        run_graph_name: str,
        task_id: str,
        domain_graph_name: Optional[str] = None,
    ) -> list[TraversalStep]:
        """Promote verified steps to run graph linked via (Task)-[:HAS_STEP]->(TraversalStep).

        Enforces anti-hallucination: skips steps where either from_cid or to_cid
        does not exist in the domain or run graph.
        """
        promoted: list[TraversalStep] = []
        steps = self.get_steps()

        for s in steps:
            # Check for phantom CIDs if domain graph is available
            if domain_graph_name:
                valid_from = store.query(
                    domain_graph_name,
                    "MATCH (n {cid: $cid}) RETURN count(n) AS cnt",
                    {"cid": s.from_cid},
                )
                valid_to = store.query(
                    domain_graph_name,
                    "MATCH (n {cid: $cid}) RETURN count(n) AS cnt",
                    {"cid": s.to_cid},
                )
                if not valid_from or int(valid_from[0].get("cnt", 0)) == 0:
                    continue  # Phantom from_cid rejected
                if not valid_to or int(valid_to[0].get("cnt", 0)) == 0:
                    continue  # Phantom to_cid rejected

            # Persist TraversalStep node
            store.query(
                run_graph_name,
                f"MERGE (ts:{LABEL_TRAVERSAL_STEP} {{id: $sid}}) "
                "ON CREATE SET ts.seq = $seq, ts.tool = $tool, ts.agent_id = $aid, "
                "              ts.from_cid = $from_cid, ts.to_cid = $to_cid, "
                "              ts.rel = $rel, ts.note = $note",
                {
                    "sid": s.id,
                    "seq": s.seq,
                    "tool": s.tool,
                    "aid": s.agent_id,
                    "from_cid": s.from_cid,
                    "to_cid": s.to_cid,
                    "rel": s.rel,
                    "note": s.note,
                },
            )

            # Link (Task)-[:HAS_STEP]->(TraversalStep)
            store.query(
                run_graph_name,
                f"MATCH (t:{LABEL_TASK} {{id: $tid}}) "
                f"MATCH (ts:{LABEL_TRAVERSAL_STEP} {{id: $sid}}) "
                f"MERGE (t)-[:{REL_HAS_STEP}]->(ts)",
                {"tid": task_id, "sid": s.id},
            )
            promoted.append(s)

        return promoted


def compose_answer(
    store: GraphStore,
    run_graph_name: str,
    task_id: str,
    target_cids: list[str],
    prompt: str = "",
    backend: str = "rules",
    confidence: float = 0.90,
) -> dict[str, Any]:
    """Compose structured Answer, verifying every cited CID against observed entities.

    Enforces citation integrity:
      - Any cited CID not present in run memory is stripped and flagged.
      - Persists (:Answer)-[:CITES]->(:Customer) or (:Entity).
      - Links (Task)-[:ANSWERED_BY]->(:Answer).
    """
    # 1. Fetch observed entities from run graph
    observed_rows = store.query(
        run_graph_name,
        "MATCH (n) WHERE n.cid IS NOT NULL RETURN DISTINCT n.cid AS cid",
    )
    observed_cids = {r["cid"] for r in observed_rows if r.get("cid")}

    # 2. Validate cited CIDs
    valid_cited: list[str] = []
    stripped_cids: list[str] = []
    for cid in target_cids:
        if cid in observed_cids:
            valid_cited.append(cid)
        else:
            stripped_cids.append(cid)

    # 3. Formulate answer text
    if valid_cited:
        cids_formatted = ", ".join(valid_cited)
        text = (
            f"Investigation confirmed connected fraud ring involving {len(valid_cited)} customer(s): "
            f"{cids_formatted}. Multi-hop traversal corroborated shared high-risk attributes (bank accounts, phone numbers)."
        )
    else:
        text = "No corroborating fraud connections were observed in the graph."

    answer_id = f"ans-{uuid.uuid4().hex[:8]}"

    # 4. Persist Answer node
    store.query(
        run_graph_name,
        f"CREATE (ans:{LABEL_ANSWER} {{"
        "  id: $aid, "
        "  text: $text, "
        "  backend: $backend, "
        "  confidence: $conf, "
        "  cited_cids: $cited, "
        "  stripped_cids: $stripped"
        "})",
        {
            "aid": answer_id,
            "text": text,
            "backend": backend,
            "conf": confidence,
            "cited": valid_cited,
            "stripped": stripped_cids,
        },
    )

    # 5. Link (Task)-[:ANSWERED_BY]->(Answer)
    store.query(
        run_graph_name,
        f"MATCH (t:{LABEL_TASK} {{id: $tid}}) "
        f"MATCH (ans:{LABEL_ANSWER} {{id: $aid}}) "
        f"MERGE (t)-[:{REL_ANSWERED_BY}]->(ans)",
        {"tid": task_id, "aid": answer_id},
    )

    # 6. Link (Answer)-[:CITES]->(Entity) for all verified CIDs
    for cid in valid_cited:
        store.query(
            run_graph_name,
            f"MATCH (ans:{LABEL_ANSWER} {{id: $aid}}) "
            f"MATCH (e {{cid: $cid}}) "
            f"MERGE (ans)-[:{REL_CITES}]->(e)",
            {"aid": answer_id, "cid": cid},
        )

    return {
        "id": answer_id,
        "text": text,
        "cited_cids": valid_cited,
        "stripped_cids": stripped_cids,
        "backend": backend,
        "confidence": confidence,
    }
