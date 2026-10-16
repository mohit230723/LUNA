"""Finding promotion engine validating private graph slice evidence into shared run memory."""

from typing import Optional
from pydantic import BaseModel, Field
from luna.agents.models import Finding
from luna.graph.store import GraphStore
from luna.graph.schema import (
    REL_PROMOTED_FROM,
    REL_ASSESSES,
    REL_SUPPORTED_BY,
)


class RejectedFinding(BaseModel):
    """Encapsulates a finding that failed evidence verification with the rejection reason."""

    finding: Finding
    reason: str


class PromotionResult(BaseModel):
    """Outcome of a finding promotion batch execution."""

    promoted: list[Finding] = Field(default_factory=list)
    rejected: list[RejectedFinding] = Field(default_factory=list)
    total_promoted: int = 0
    total_rejected: int = 0


def promote_findings(
    store: GraphStore,
    agent_graph_name: str,
    run_graph_name: str,
    findings: list[Finding],
    *,
    observed: Optional[set[str]] = None,
    require_observed: bool = False,
    max_hops: Optional[int] = None,
) -> PromotionResult:
    """Validate evidence CIDs against the agent's private slice and promote verified findings.

    ANTI-HALLUCINATION & PROVENANCE BARRIER:
    1. Every CID in finding.evidence_cids MUST exist as a node in `agent_graph_name`.
       Failure reason contains "evidence_not_in_slice" and "anti-hallucination barrier rejection".
    2. If require_observed=True, every evidence CID must be in `observed` (target_cid exempt).
       Failure reason contains "evidence_not_observed".
    3. If max_hops is not None, every evidence CID must be within max_hops of target_cid in slice.
       Failure reason contains "evidence_not_connected".
    Verified findings are merged into `run_graph_name` with provenance links. Zero writes on rejection.
    """
    result = PromotionResult()

    for finding in findings:
        # Check 1: Evidence CIDs must exist in the agent slice
        missing_cids: list[str] = []
        for cid in finding.evidence_cids:
            query = "MATCH (n) WHERE n.cid = $cid RETURN count(n) AS cnt"
            rows = store.query(agent_graph_name, query, {"cid": cid})
            cnt = rows[0].get("cnt", 0) if rows else 0
            if cnt == 0:
                missing_cids.append(cid)

        if missing_cids:
            result.rejected.append(
                RejectedFinding(
                    finding=finding,
                    reason=(
                        f"Evidence CID(s) {missing_cids} not found in agent graph "
                        f"slice '{agent_graph_name}': evidence_not_in_slice (anti-hallucination barrier rejection)"
                    ),
                )
            )
            continue

        # Check 2: If require_observed, every evidence CID must be observed in tool outputs (target_cid is exempt)
        if require_observed:
            observed_set = observed or set()
            unobserved_cids = [
                cid for cid in finding.evidence_cids
                if cid != finding.target_cid and cid not in observed_set
            ]
            if unobserved_cids:
                result.rejected.append(
                    RejectedFinding(
                        finding=finding,
                        reason=(
                            f"Evidence CID(s) {unobserved_cids} not observed in tool outputs: "
                            f"evidence_not_observed"
                        ),
                    )
                )
                continue

        # Check 3: If max_hops is not None, each evidence CID must be connected within max_hops of target_cid
        if max_hops is not None:
            unconnected_cids = []
            for cid in finding.evidence_cids:
                if cid == finding.target_cid:
                    continue
                sp_query = (
                    "MATCH (a {cid: $source_cid}), (b {cid: $target_cid}) "
                    "WITH shortestPath((a)-[*]-(b)) AS p "
                    "RETURN length(p) AS len"
                )
                rows = store.query(
                    agent_graph_name,
                    sp_query,
                    {"source_cid": finding.target_cid, "target_cid": cid},
                )
                if not rows or rows[0].get("len") is None or rows[0].get("len") > max_hops:
                    unconnected_cids.append(cid)

            if unconnected_cids:
                result.rejected.append(
                    RejectedFinding(
                        finding=finding,
                        reason=(
                            f"Evidence CID(s) {unconnected_cids} not within {max_hops} hops "
                            f"of target '{finding.target_cid}': evidence_not_connected"
                        ),
                    )
                )
                continue

        # Step 2: Persist verified finding and provenance edges into shared run graph
        create_finding_query = (
            "CREATE (f:Finding { "
            "    id: $id, "
            "    target_cid: $target_cid, "
            "    verdict: $verdict, "
            "    confidence: $confidence, "
            "    reasoning: $reasoning, "
            "    skill_id: $skill_id, "
            "    agent_id: $agent_id, "
            "    status: 'promoted', "
            "    timestamp: $timestamp, "
            "    backend: $backend, "
            "    fallback_reason: $fallback_reason "
            "}) "
            "MERGE (a:Agent {id: $agent_id}) "
            f"CREATE (f)-[:{REL_PROMOTED_FROM}]->(a) "
            "MERGE (c:Customer {cid: $target_cid}) "
            f"CREATE (f)-[:{REL_ASSESSES}]->(c)"
        )
        finding_params = {
            "id": finding.id,
            "target_cid": finding.target_cid,
            "verdict": finding.verdict,
            "confidence": finding.confidence,
            "reasoning": finding.reasoning,
            "skill_id": finding.skill_id,
            "agent_id": finding.agent_id,
            "timestamp": finding.timestamp,
            "backend": finding.backend,
            "fallback_reason": finding.fallback_reason,
        }
        store.query(run_graph_name, create_finding_query, finding_params)

        # Step 3: Link verified evidence entity CIDs in run graph
        for ev_cid in finding.evidence_cids:
            evidence_query = (
                "MATCH (f:Finding {id: $finding_id}) "
                "MERGE (e:Entity {cid: $ev_cid}) "
                f"CREATE (f)-[:{REL_SUPPORTED_BY}]->(e)"
            )
            store.query(
                run_graph_name,
                evidence_query,
                {"finding_id": finding.id, "ev_cid": ev_cid},
            )

        result.promoted.append(finding)

    result.total_promoted = len(result.promoted)
    result.total_rejected = len(result.rejected)
    return result
