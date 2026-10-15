"""Finding promotion engine validating private graph slice evidence into shared run memory."""

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
) -> PromotionResult:
    """Validate evidence CIDs against the agent's private slice and promote verified findings.

    ANTI-HALLUCINATION BARRIER:
    - Every CID in finding.evidence_cids MUST exist as a node in `agent_graph_name`.
    - If ANY evidence CID does not exist in the agent's slice, the finding is REJECTED.
    - Verified findings are merged into `run_graph_name` with provenance links.
    """
    result = PromotionResult()

    for finding in findings:
        missing_cids: list[str] = []

        # Step 1: Validate evidence CIDs in the agent's private slice
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
                        f"slice '{agent_graph_name}' (anti-hallucination barrier rejection)"
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
            "    timestamp: $timestamp "
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
