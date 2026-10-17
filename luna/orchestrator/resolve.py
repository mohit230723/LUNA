"""Main-agent conflict resolution logic creating immutable Decision provenance records."""

import json
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
    LABEL_TASK_TYPE,
    REL_ASSESSES,
    REL_UPHELD,
    REL_SUPERSEDES,
    REL_SUCCEEDED_ON,
    REL_ABOUT,
)
from luna.llm.client import LLMClient

# Scoring weight constants for per-customer side resolution
W_CONF: float = 0.5
W_EVID: float = 0.2
W_SKILL: float = 0.3


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
    backend: str = "rule"
    component_scores: Optional[str] = None
    weights: Optional[str] = None
    skill_scores_json: Optional[str] = None


def _get_skill_score(
    store: GraphStore,
    atlas_graph: str,
    skill_id: str,
    task_type: Optional[str] = None,
) -> float:
    """Fetch the historical success score for a skill from the atlas graph.
    
    Checks SUCCEEDED_ON for the specified task_type first, then falls back to any
    SUCCEEDED_ON relationship, or defaults to 0.50.
    """
    if task_type:
        try:
            recs = store.query(
                atlas_graph,
                f"MATCH (s:{LABEL_SKILL} {{id: $skill_id}})-[r:{REL_SUCCEEDED_ON}]->(t:{LABEL_TASK_TYPE} {{name: $task_type}}) "
                "RETURN r.score AS score LIMIT 1",
                {"skill_id": skill_id, "task_type": task_type},
            )
            if recs and recs[0].get("score") is not None:
                return float(recs[0]["score"])
        except Exception:
            pass

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

    return 0.50  # Neutral prior default


def resolve_conflicts(
    store: GraphStore,
    run_graph_name: str,
    atlas_graph_name: str = GRAPH_ATLAS,
    task_type: Optional[str] = None,
    w_conf: float = W_CONF,
    w_evid: float = W_EVID,
    w_skill: float = W_SKILL,
    llm_client: Optional[LLMClient] = None,
) -> list[Decision]:
    """Evaluate active conflicting findings, arbitrate winner per side, and persist Decision nodes.

    Zero Deletion Contract: Losing findings are NEVER deleted. They are marked
    status = 'superseded' and linked via [:SUPERSEDES], while the winning finding
    is linked via [:UPHELD]. Decision is linked via [:ABOUT]->Customer.

    Args:
        store: GraphStore connection
        run_graph_name: Target run memory graph
        atlas_graph_name: Name of atlas catalog graph
        task_type: Optional task type name for atlas skill lookup
        w_conf: Weight for confidence
        w_evid: Weight for evidence presence
        w_skill: Weight for skill reputation
        llm_client: Optional LLMClient for qualitative arbitration

    Returns:
        List of created Decision objects.
    """
    # 1. Identify distinct target customers with active findings
    find_targets_query = (
        f"MATCH (f:{LABEL_FINDING})-[:{REL_ASSESSES}]->(c:{LABEL_CUSTOMER}) "
        "WHERE (f.status IS NULL OR f.status <> 'superseded') "
        "RETURN DISTINCT c.cid AS target_cid"
    )

    targets = store.query(run_graph_name, find_targets_query)
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

        # Check if there is both suspicious and benign among active findings
        sus_findings = [f for f in active_findings if f.get("verdict") == "suspicious"]
        ben_findings = [f for f in active_findings if f.get("verdict") == "benign"]

        if not sus_findings or not ben_findings:
            continue

        # Snapshot skill scores BEFORE arbitration / learning
        skill_scores_snapshot: dict[str, float] = {}
        for f in active_findings:
            sk_id = f.get("skill_id", "")
            if sk_id and sk_id not in skill_scores_snapshot:
                skill_scores_snapshot[sk_id] = _get_skill_score(
                    store, atlas_graph_name, sk_id, task_type=task_type
                )

        # Helper to score an individual finding:
        # S = W_CONF * conf + W_EVID * min(evidence_count, 5)/5 + W_SKILL * skill_score
        def score_finding(f: dict) -> dict:
            conf = float(f.get("confidence") or 0.0)
            ev_count = len(f.get("evidence_cids") or [])
            ev_factor = min(ev_count, 5) / 5.0
            sk_id = f.get("skill_id", "")
            sk_score = skill_scores_snapshot.get(sk_id, 0.50)
            total = (w_conf * conf) + (w_evid * ev_factor) + (w_skill * sk_score)
            return {
                "finding": f,
                "confidence": conf,
                "evidence_count": ev_count,
                "evidence_factor": ev_factor,
                "skill_id": sk_id,
                "skill_score": sk_score,
                "score": total,
            }

        sus_scored = [score_finding(f) for f in sus_findings]
        ben_scored = [score_finding(f) for f in ben_findings]

        # Score each side by its best finding
        best_sus = max(
            sus_scored,
            key=lambda x: (x["score"], x["confidence"], x["evidence_count"]),
        )
        best_ben = max(
            ben_scored,
            key=lambda x: (x["score"], x["confidence"], x["evidence_count"]),
        )

        # Arbitration with conservative tie-break:
        # If best_sus["score"] > best_ben["score"], suspicious wins.
        # Otherwise (including ties), benign wins.
        if best_sus["score"] > best_ben["score"]:
            winning_verdict = "suspicious"
            winner_item = best_sus
            winning_findings = sus_findings
            losing_findings = ben_findings
        else:
            winning_verdict = "benign"
            winner_item = best_ben
            winning_findings = ben_findings
            losing_findings = sus_findings

        winner_finding = winner_item["finding"]
        loser_ids = [l["id"] for l in losing_findings]

        component_scores_dict = {
            "suspicious": {
                "best_finding_id": best_sus["finding"]["id"],
                "score": best_sus["score"],
                "confidence": best_sus["confidence"],
                "evidence_factor": best_sus["evidence_factor"],
                "skill_score": best_sus["skill_score"],
            },
            "benign": {
                "best_finding_id": best_ben["finding"]["id"],
                "score": best_ben["score"],
                "confidence": best_ben["confidence"],
                "evidence_factor": best_ben["evidence_factor"],
                "skill_score": best_ben["skill_score"],
            },
        }

        weights_dict = {
            "w_conf": w_conf,
            "w_evid": w_evid,
            "w_skill": w_skill,
        }

        reasoning = (
            f"Arbitrated conflict on {cid} in favor of side '{winning_verdict}' "
            f"(best finding: {winner_finding['id']}, score: {winner_item['score']:.4f}, "
            f"confidence: {winner_item['confidence']:.2f}, evidence: {winner_item['evidence_count']}, "
            f"skill: '{winner_item['skill_id']}' reputation: {winner_item['skill_score']:.2f}). "
            f"Superseded contradictory findings: {', '.join(loser_ids)}."
        )

        decision = Decision(
            target_cid=cid,
            chosen_verdict=winning_verdict,
            confidence=winner_item["confidence"],
            reasoning=reasoning,
            winning_finding_id=winner_finding["id"],
            superseded_finding_ids=loser_ids,
            backend="rule",
            component_scores=json.dumps(component_scores_dict),
            weights=json.dumps(weights_dict),
            skill_scores_json=json.dumps(skill_scores_snapshot),
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
            f"  resolved_at: $resolved_at, "
            f"  backend: $backend, "
            f"  component_scores: $component_scores, "
            f"  weights: $weights, "
            f"  skill_scores_json: $skill_scores_json"
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
                "backend": decision.backend,
                "component_scores": decision.component_scores,
                "weights": decision.weights,
                "skill_scores_json": decision.skill_scores_json,
            },
        )

        # Link UPHELD edge to best winning finding
        store.query(
            run_graph_name,
            f"MATCH (d:{LABEL_DECISION} {{id: $dec_id}}), (w:{LABEL_FINDING} {{id: $winner_id}}) "
            f"CREATE (d)-[:{REL_UPHELD}]->(w)",
            {"dec_id": decision.id, "winner_id": winner_finding["id"]},
        )

        # Link ABOUT edge to Customer node
        store.query(
            run_graph_name,
            f"MATCH (d:{LABEL_DECISION} {{id: $dec_id}}), (c:{LABEL_CUSTOMER} {{cid: $cid}}) "
            f"CREATE (d)-[:{REL_ABOUT}]->(c)",
            {"dec_id": decision.id, "cid": cid},
        )

        # Mark ALL losing findings as superseded and link SUPERSEDES edge
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
