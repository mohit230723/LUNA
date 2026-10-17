"""Main-agent conflict resolution logic creating immutable Decision provenance records."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from luna.graph.store import GraphStore
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_FINDING,
    LABEL_DECISION,
    LABEL_CUSTOMER,
    LABEL_SKILL,
    REL_ASSESSES,
    REL_CONFLICTS_WITH,
    REL_UPHELD,
    REL_SUPERSEDES,
    REL_SUCCEEDED_ON,
)
from luna.llm.client import LLMClient


class Decision(BaseModel):
    """Represents an arbitration decision resolving conflicting findings."""

    id: str = Field(default_factory=lambda: f"dec-{uuid.uuid4().hex[:8]}")
    target_cid: str
    chosen_verdict: str  # "suspicious" | "benign"
    confidence: float
    reasoning: str
    winning_finding_id: str
    superseded_finding_ids: list[str] = Field(default_factory=list)
    resolved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _get_skill_score(store: GraphStore, atlas_graph: str, skill_id: str) -> float:
    """Fetch the historical success score for a skill from the atlas graph."""
    try:
        recs = store.query(
            atlas_graph,
            f"MATCH (s:{LABEL_SKILL} {{id: $skill_id}})-[r:{REL_SUCCEEDED_ON}]->() "
            "RETURN r.score AS score LIMIT 1",
            {"skill_id": skill_id},
        )
        if recs and recs[0].get("score") is not None:
            return float(recs[0]["score"])
    except Exception:
        pass
    return 0.70  # Default neutral/good prior


def resolve_conflicts(
    store: GraphStore,
    run_graph_name: str,
    atlas_graph_name: str = GRAPH_ATLAS,
    llm_client: Optional[LLMClient] = None,
) -> list[Decision]:
    """Evaluate active conflicting findings, arbitrate winner, and persist Decision nodes.

    Zero Deletion Contract: Losing findings are NEVER deleted. They are marked
    status = 'superseded' and linked via [:SUPERSEDES], while the winning finding
    is linked via [:UPHELD].

    Args:
        store: GraphStore connection
        run_graph_name: Target run memory graph
        atlas_graph_name: Name of atlas catalog graph
        llm_client: Optional LLMClient for qualitative arbitration

    Returns:
        List of created Decision objects.
    """
    # 1. Identify distinct target customers with active (non-superseded) conflicting findings
    find_conflicts_query = (
        f"MATCH (f1:{LABEL_FINDING})-[:{REL_CONFLICTS_WITH}]-(f2:{LABEL_FINDING}), "
        f"(f1)-[:{REL_ASSESSES}]->(c:{LABEL_CUSTOMER}) "
        "WHERE (f1.status IS NULL OR f1.status <> 'superseded') "
        "  AND (f2.status IS NULL OR f2.status <> 'superseded') "
        "RETURN DISTINCT c.cid AS target_cid"
    )

    targets = store.query(run_graph_name, find_conflicts_query)
    if not targets:
        return []

    decisions: list[Decision] = []

    for target in targets:
        cid = target["target_cid"]

        # Fetch all active findings assessing this customer
        findings_query = (
            f"MATCH (f:{LABEL_FINDING})-[:{REL_ASSESSES}]->(c:{LABEL_CUSTOMER} {{cid: $cid}}) "
            "WHERE (f.status IS NULL OR f.status <> 'superseded') "
            "RETURN f.id AS id, f.verdict AS verdict, f.confidence AS confidence, "
            "       f.reasoning AS reasoning, f.skill_id AS skill_id, "
            "       coalesce(f.evidence_cids, []) AS evidence_cids"
        )
        active_findings = store.query(run_graph_name, findings_query, {"cid": cid})
        if len(active_findings) < 2:
            continue

        # Check if there is a genuine verdict discrepancy among active findings
        verdicts = {f["verdict"] for f in active_findings}
        if len(verdicts) < 2:
            continue

        # Calculate arbitration score for each finding
        scored_findings = []
        for f in active_findings:
            conf = float(f.get("confidence", 0.5))
            ev_count = len(f.get("evidence_cids") or [])
            skill_id = f.get("skill_id", "")
            atlas_score = _get_skill_score(store, atlas_graph_name, skill_id)

            # Weighted arbitration score:
            # - Finding Confidence (50%)
            # - Structural Evidence Presence (30%)
            # - Equipped Skill Reputation / Historical Score (20%)
            weighted_score = (conf * 0.50) + (0.30 if ev_count > 0 else 0.0) + (atlas_score * 0.20)
            scored_findings.append({
                "finding": f,
                "weighted_score": weighted_score,
                "confidence": conf,
                "ev_count": ev_count,
                "atlas_score": atlas_score,
            })

        # Sort descending: primary by weighted_score, secondary by confidence, tertiary by ev_count
        scored_findings.sort(
            key=lambda item: (item["weighted_score"], item["confidence"], item["ev_count"]),
            reverse=True,
        )

        winner_item = scored_findings[0]
        winner = winner_item["finding"]
        loser_items = scored_findings[1:]
        loser_ids = [l["finding"]["id"] for l in loser_items]

        # Synthesize rationalization
        reasoning = (
            f"Arbitrated conflict on {cid} in favor of finding {winner['id']} ({winner['verdict']}) "
            f"produced by skill '{winner['skill_id']}' (confidence: {winner['confidence']:.2f}, "
            f"evidence count: {len(winner.get('evidence_cids', []))}, atlas reputation: {winner_item['atlas_score']:.2f}). "
            f"Superseded contradictory findings: {', '.join(loser_ids)}."
        )

        decision = Decision(
            target_cid=cid,
            chosen_verdict=winner["verdict"],
            confidence=winner["confidence"],
            reasoning=reasoning,
            winning_finding_id=winner["id"],
            superseded_finding_ids=loser_ids,
        )

        # Write Decision node to run graph
        create_decision_cypher = (
            f"CREATE (d:{LABEL_DECISION} {{"
            f"  id: $id, "
            f"  target_cid: $target_cid, "
            f"  chosen_verdict: $chosen_verdict, "
            f"  confidence: $confidence, "
            f"  reasoning: $reasoning, "
            f"  winning_finding_id: $winning_finding_id, "
            f"  resolved_at: $resolved_at"
            f"}})"
        )
        store.query(
            run_graph_name,
            create_decision_cypher,
            {
                "id": decision.id,
                "target_cid": decision.target_cid,
                "chosen_verdict": decision.chosen_verdict,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "winning_finding_id": decision.winning_finding_id,
                "resolved_at": decision.resolved_at,
            },
        )

        # Link UPHELD edge to winning finding
        store.query(
            run_graph_name,
            f"MATCH (d:{LABEL_DECISION} {{id: $dec_id}}), (w:{LABEL_FINDING} {{id: $winner_id}}) "
            f"CREATE (d)-[:{REL_UPHELD}]->(w)",
            {"dec_id": decision.id, "winner_id": winner["id"]},
        )

        # Mark losing findings as superseded and link SUPERSEDES edge
        for loser_id in loser_ids:
            store.query(
                run_graph_name,
                f"MATCH (d:{LABEL_DECISION} {{id: $dec_id}}), (l:{LABEL_FINDING} {{id: $loser_id}}) "
                f"SET l.status = 'superseded' "
                f"CREATE (d)-[:{REL_SUPERSEDES}]->(l)",
                {"dec_id": decision.id, "loser_id": loser_id},
            )

        decisions.append(decision)

    return decisions
