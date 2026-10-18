"""Thread-safe TraversalRecorder and edge descriptor for investigation steps."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from luna.graph.store import GraphStore

LABEL_TRAVERSAL_STEP = "TraversalStep"
REL_HAS_STEP = "HAS_STEP"


@dataclass
class TraversalStep:
    seq: int
    tool: str
    agent_id: str
    from_cid: str
    to_cid: str
    rel: str
    direction: str = "out"
    note: str = ""
    edge_source_id: str = ""
    edge_locator: str = ""
    edge_quote: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def describe_edge(
    from_name: str,
    to_name: str,
    rel: str,
    quote: str = "",
    locator: str = "",
    source_name: str = "",
) -> str:
    """Build a human-readable description of a graph hop."""
    if quote:
        loc = f" ({locator})" if locator else ""
        return f'{from_name} —[{rel}]→ {to_name}: "{quote}"{loc}'
    if source_name or locator:
        src = f"appears in {source_name}" if source_name else "recorded in source"
        loc = f" ({locator})" if locator else ""
        return f"{from_name} —[{rel}]→ {to_name}; {src}{loc}"
    return f"{from_name} —[{rel}]→ {to_name}"


class TraversalRecorder:
    """Thread-safe recorder accumulating traversal hops and writing to FalkorDB."""

    def __init__(self, store: Optional[GraphStore] = None) -> None:
        self.store = store or GraphStore()
        self._lock = threading.Lock()
        self._seq = 0
        self._steps: list[TraversalStep] = []

    def record_step(
        self,
        agent_id: str,
        tool: str,
        from_cid: str,
        to_cid: str,
        rel: str,
        direction: str = "out",
        note: str = "",
        edge_source_id: str = "",
        edge_locator: str = "",
        edge_quote: str = "",
        agent_graph_name: Optional[str] = None,
    ) -> TraversalStep:
        """Record a single traversed hop."""
        with self._lock:
            self._seq += 1
            step = TraversalStep(
                seq=self._seq,
                tool=tool,
                agent_id=agent_id,
                from_cid=from_cid,
                to_cid=to_cid,
                rel=rel,
                direction=direction,
                note=note,
                edge_source_id=edge_source_id,
                edge_locator=edge_locator,
                edge_quote=edge_quote,
            )
            self._steps.append(step)

        if agent_graph_name:
            try:
                self.store.query(
                    agent_graph_name,
                    f"CREATE (s:{LABEL_TRAVERSAL_STEP} {{"
                    f"  seq: $seq, tool: $tool, agent_id: $agent_id, "
                    f"  from_cid: $from_cid, to_cid: $to_cid, rel: $rel, "
                    f"  direction: $direction, note: $note, quote: $quote, locator: $locator"
                    f"}})",
                    {
                        "seq": step.seq,
                        "tool": step.tool,
                        "agent_id": step.agent_id,
                        "from_cid": step.from_cid,
                        "to_cid": step.to_cid,
                        "rel": step.rel,
                        "direction": step.direction,
                        "note": step.note[:500],
                        "quote": step.edge_quote[:200],
                        "locator": step.edge_locator[:200],
                    },
                )
            except Exception:
                pass

        return step

    def get_steps(self) -> list[TraversalStep]:
        with self._lock:
            return list(self._steps)

    def promote_to_run_graph(self, run_graph_name: str, task_id: str, verified_cids: set[str]) -> int:
        """Copy recorded steps that touch verified CIDs into the shared run graph."""
        count = 0
        with self._lock:
            for s in self._steps:
                if s.from_cid in verified_cids and s.to_cid in verified_cids:
                    try:
                        self.store.query(
                            run_graph_name,
                            f"MATCH (t:Task {{id: $task_id}}) "
                            f"CREATE (s:{LABEL_TRAVERSAL_STEP} {{"
                            f"  seq: $seq, tool: $tool, agent_id: $agent_id, "
                            f"  from_cid: $from_cid, to_cid: $to_cid, rel: $rel, "
                            f"  note: $note, quote: $quote, locator: $locator"
                            f"}}) "
                            f"CREATE (t)-[:{REL_HAS_STEP}]->(s)",
                            {
                                "task_id": task_id,
                                "seq": s.seq,
                                "tool": s.tool,
                                "agent_id": s.agent_id,
                                "from_cid": s.from_cid,
                                "to_cid": s.to_cid,
                                "rel": s.rel,
                                "note": s.note[:500],
                                "quote": s.edge_quote[:200],
                                "locator": s.edge_locator[:200],
                            },
                        )
                        count += 1
                    except Exception:
                        pass
        return count
