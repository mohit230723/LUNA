"""Automated contradiction detection between promoted findings in shared run memory."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from luna.graph.store import GraphStore
from luna.graph.schema import (
    LABEL_FINDING,
    LABEL_CUSTOMER,
    REL_ASSESSES,
    REL_CONFLICTS_WITH,
)


class Contradiction(BaseModel):
    """Represents a detected contradiction between two promoted findings assessing the same target."""

    finding1_id: str
    finding2_id: str
    target_cid: str
    verdict1: str
    verdict2: str
    detected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def detect_contradictions(
    store: GraphStore,
    run_graph_name: str,
    detected_at: Optional[str] = None,
) -> list[Contradiction]:
    """Identify opposing verdicts on the same customer in run memory and create CONFLICTS_WITH edges.

    Args:
        store: GraphStore connection
        run_graph_name: Target run memory graph
        detected_at: Optional ISO timestamp override

    Returns:
        List of Contradiction objects representing detected conflicting finding pairs.
    """
    ts = detected_at or datetime.now(timezone.utc).isoformat()

    # Match pairs of findings assessing the same customer entity where verdicts differ
    # f1.id < f2.id ensures deterministic canonical pairing without duplicate mirror edges
    query = (
        f"MATCH (f1:{LABEL_FINDING})-[:{REL_ASSESSES}]->(c:{LABEL_CUSTOMER})<-[:{REL_ASSESSES}]-(f2:{LABEL_FINDING}) "
        "WHERE f1.id < f2.id AND f1.verdict <> f2.verdict "
        f"MERGE (f1)-[r:{REL_CONFLICTS_WITH}]->(f2) "
        "ON CREATE SET r.detected_at = $detected_at "
        "RETURN f1.id AS f1_id, f2.id AS f2_id, c.cid AS target_cid, "
        "f1.verdict AS v1, f2.verdict AS v2, coalesce(r.detected_at, $detected_at) AS detected_at"
    )

    records = store.query(run_graph_name, query, {"detected_at": ts})

    contradictions = []
    for rec in records:
        contradictions.append(
            Contradiction(
                finding1_id=rec["f1_id"],
                finding2_id=rec["f2_id"],
                target_cid=rec["target_cid"],
                verdict1=rec["v1"],
                verdict2=rec["v2"],
                detected_at=rec["detected_at"],
            )
        )

    return contradictions
