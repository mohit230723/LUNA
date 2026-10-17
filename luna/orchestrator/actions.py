"""Action proposal, human approval barrier, idempotent execution, and evaluation (Plan 3.3)."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field

from luna.graph.store import GraphStore
from luna.graph.schema import (
    LABEL_ACTION,
    LABEL_OUTCOME,
    LABEL_FINDING,
    LABEL_CUSTOMER,
    REL_BASED_ON,
    REL_RESULTED_IN,
    REL_ASSESSES,
)
from luna.domain.seed import GroundTruth

CORROBORATION_MIN_SKILLS: int = 2
CORROBORATION_CONF: float = 0.8

ACTION_FLAG_FOR_REVIEW = "flag_for_review"
ACTION_FLAG_CUSTOMER = "flag_for_review"  # Backward-compatible alias
STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_EXECUTING = "EXECUTING"
STATUS_EXECUTED = "EXECUTED"
STATUS_FAILED = "FAILED"


class NotApprovedError(PermissionError):
    """Raised when an attempt is made to execute an action that is not in APPROVED status."""
    pass


def check_corroboration(
    findings: list[dict[str, Any]],
    min_skills: int = CORROBORATION_MIN_SKILLS,
    min_conf: float = CORROBORATION_CONF,
) -> bool:
    """Check if active suspicious findings meet corroboration criteria."""
    if not findings:
        return False
    distinct_skills = {f["skill_id"] for f in findings if f.get("skill_id")}
    best_conf = max((float(f.get("confidence") or 0.0) for f in findings), default=0.0)
    return len(distinct_skills) >= min_skills or best_conf >= min_conf


class Action(BaseModel):
    """Represents a proposed or executed remediation/investigation action."""

    id: str = Field(default_factory=lambda: f"act-{uuid.uuid4().hex[:8]}")
    kind: str = ACTION_FLAG_FOR_REVIEW
    action_type: str = ACTION_FLAG_FOR_REVIEW
    target_cids: list[str] = Field(default_factory=list)
    target_cid: Optional[str] = None
    status: str = STATUS_PENDING
    reasoning: str = ""
    finding_ids: list[str] = Field(default_factory=list)
    recommended_by_id: Optional[str] = None
    approver: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_at: Optional[str] = None
    executed_at: Optional[str] = None
    rejection_reason: Optional[str] = None

    def __init__(self, **data: Any):
        if "kind" in data and "action_type" not in data:
            data["action_type"] = data["kind"]
        elif "action_type" in data and "kind" not in data:
            data["kind"] = data["action_type"]
        if "target_cids" in data and not data.get("target_cid"):
            cids = data["target_cids"]
            if cids:
                data["target_cid"] = cids[0]
        elif "target_cid" in data and not data.get("target_cids"):
            cid = data["target_cid"]
            if cid:
                data["target_cids"] = [cid]
        super().__init__(**data)


class Outcome(BaseModel):
    """Represents the recorded result of an executed domain action."""

    id: str = Field(default_factory=lambda: f"out-{uuid.uuid4().hex[:8]}")
    action_id: str
    target_cid: str
    success: bool
    details: str
    recorded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    learned: bool = False


class EvaluationMetrics(BaseModel):
    """Precision, recall, and F1 performance metrics against ground truth."""

    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


def propose_actions(store: GraphStore, run_graph_name: str) -> list[Action]:
    """Scan run memory for active findings, creating a single batch PENDING Action if targets are corroborated.

    Args:
        store: GraphStore connection
        run_graph_name: Target run memory graph

    Returns:
        List with at most one Action object with status='PENDING'.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Query all active suspicious findings
    active_sus_query = (
        f"MATCH (f:{LABEL_FINDING} {{verdict: 'suspicious'}}) "
        "WHERE (f.status IS NULL OR f.status <> 'superseded') "
        f"OPTIONAL MATCH (f)-[:{REL_ASSESSES}]->(c:{LABEL_CUSTOMER}) "
        "RETURN f.id AS id, coalesce(f.target_cid, c.cid) AS cid, f.skill_id AS skill_id, f.confidence AS confidence"
    )
    active_findings_rows = store.query(run_graph_name, active_sus_query)
    findings_by_cid: dict[str, list[dict[str, Any]]] = {}
    for r in active_findings_rows:
        cid = r.get("cid")
        if cid:
            findings_by_cid.setdefault(cid, []).append(r)

    # Filter for corroborated targets
    corroborated_cids = sorted([
        cid for cid, f_list in findings_by_cid.items()
        if check_corroboration(f_list)
    ])

    if not corroborated_cids:
        return []

    # Gather active suspicious finding IDs for corroborated targets
    target_finding_ids: set[str] = set()
    for cid in corroborated_cids:
        for f in findings_by_cid.get(cid, []):
            target_finding_ids.add(f["id"])

    action = Action(
        kind=ACTION_FLAG_FOR_REVIEW,
        action_type=ACTION_FLAG_FOR_REVIEW,
        status=STATUS_PENDING,
        target_cids=corroborated_cids,
        finding_ids=sorted(target_finding_ids),
        reasoning=f"Corroborated suspicious findings on {len(corroborated_cids)} customer(s): {', '.join(corroborated_cids)}.",
        created_at=now,
    )

    create_action_cypher = (
        f"CREATE (a:{LABEL_ACTION} {{"
        f"  id: $id, "
        f"  kind: $kind, "
        f"  action_type: $action_type, "
        f"  status: $status, "
        f"  target_cids: $target_cids, "
        f"  target_cid: $target_cid, "
        f"  reasoning: $reasoning, "
        f"  created_at: $created_at"
        f"}})"
    )
    store.query(
        run_graph_name,
        create_action_cypher,
        {
            "id": action.id,
            "kind": action.kind,
            "action_type": action.action_type,
            "status": action.status,
            "target_cids": action.target_cids,
            "target_cid": action.target_cid,
            "reasoning": action.reasoning,
            "created_at": action.created_at,
        },
    )

    # Action-[:BASED_ON]->every active suspicious Finding on the targets (never to Decision)
    for fid in sorted(target_finding_ids):
        store.query(
            run_graph_name,
            f"MATCH (a:{LABEL_ACTION} {{id: $aid}}), (f:{LABEL_FINDING} {{id: $fid}}) "
            f"CREATE (a)-[:{REL_BASED_ON}]->(f)",
            {"aid": action.id, "fid": fid},
        )

    return [action]


def approve_action(
    store: GraphStore,
    run_graph_name: str,
    action_id: str,
    approver: str = "human",
) -> Action:
    """Transition an Action to APPROVED status and record the approver identity.

    Args:
        store: GraphStore connection
        run_graph_name: Target run memory graph
        action_id: Unique Action identifier
        approver: Approver identifier (e.g. 'auto' for headless demo, or investigator ID)

    Returns:
        Updated Action object.
    """
    now = datetime.now(timezone.utc).isoformat()
    cypher = (
        f"MATCH (a:{LABEL_ACTION} {{id: $action_id}}) "
        "SET a.status = 'APPROVED', a.approver = $approver, a.approved_at = $approved_at "
        "RETURN a.id AS id, a.kind AS kind, a.action_type AS action_type, "
        "       coalesce(a.target_cids, []) AS target_cids, a.target_cid AS target_cid, "
        "       a.status AS status, a.recommended_by_id AS recommended_by_id, "
        "       a.approver AS approver, a.created_at AS created_at, a.approved_at AS approved_at"
    )
    records = store.query(
        run_graph_name,
        cypher,
        {"action_id": action_id, "approver": approver, "approved_at": now},
    )
    if not records:
        raise ValueError(f"Action '{action_id}' not found in graph '{run_graph_name}'.")

    r = records[0]
    return Action(
        id=r["id"],
        kind=r.get("kind") or ACTION_FLAG_FOR_REVIEW,
        action_type=r.get("action_type") or ACTION_FLAG_FOR_REVIEW,
        target_cids=r.get("target_cids") or [],
        target_cid=r.get("target_cid"),
        status=r["status"],
        recommended_by_id=r.get("recommended_by_id"),
        approver=r.get("approver"),
        created_at=r.get("created_at") or now,
        approved_at=r.get("approved_at"),
    )


def reject_action(
    store: GraphStore,
    run_graph_name: str,
    action_id: str,
    approver: str = "human",
    reason: str = "",
) -> Action:
    """Transition an Action to REJECTED status and record reason.

    Args:
        store: GraphStore connection
        run_graph_name: Target run memory graph
        action_id: Unique Action identifier
        approver: Approver identifier
        reason: Explanation for rejection

    Returns:
        Updated Action object.
    """
    now = datetime.now(timezone.utc).isoformat()
    cypher = (
        f"MATCH (a:{LABEL_ACTION} {{id: $action_id}}) "
        "SET a.status = 'REJECTED', a.approver = $approver, a.rejection_reason = $reason, a.rejected_at = $now "
        "RETURN a.id AS id, a.kind AS kind, a.action_type AS action_type, "
        "       coalesce(a.target_cids, []) AS target_cids, a.target_cid AS target_cid, "
        "       a.status AS status, a.recommended_by_id AS recommended_by_id, "
        "       a.approver AS approver, a.created_at AS created_at, a.rejection_reason AS rejection_reason"
    )
    records = store.query(
        run_graph_name,
        cypher,
        {"action_id": action_id, "approver": approver, "reason": reason, "now": now},
    )
    if not records:
        raise ValueError(f"Action '{action_id}' not found in graph '{run_graph_name}'.")

    r = records[0]
    return Action(
        id=r["id"],
        kind=r.get("kind") or ACTION_FLAG_FOR_REVIEW,
        action_type=r.get("action_type") or ACTION_FLAG_FOR_REVIEW,
        target_cids=r.get("target_cids") or [],
        target_cid=r.get("target_cid"),
        status=r["status"],
        recommended_by_id=r.get("recommended_by_id"),
        approver=r.get("approver"),
        created_at=r.get("created_at") or now,
        rejection_reason=r.get("rejection_reason"),
    )


def execute_action(
    store: GraphStore,
    run_graph_name: str,
    domain_graph_name: str,
    action_id: str,
    run_id: Optional[str] = None,
) -> Outcome:
    """Execute an approved action against the domain graph and record the outcome in run memory.

    Execution Safety (H4):
    - Raises NotApprovedError unless status is 'APPROVED'.
    - Uses an atomic conditional status update (APPROVED -> EXECUTING).
    - Sets c.flagged = true, c.flag_run = $run_id, and c.flagged_at on targets.
    - On exception, marks the Action as FAILED with failure_reason.
    - Idempotent: Subsequent calls return the existing Outcome node.
    """
    effective_run_id = run_id or (run_graph_name[4:] if run_graph_name.startswith("run_") else run_graph_name)

    # 1. Idempotency Check: Return existing Outcome if already executed
    existing_outcome_cypher = (
        f"MATCH (a:{LABEL_ACTION} {{id: $action_id}})-[:{REL_RESULTED_IN}]->(o:{LABEL_OUTCOME}) "
        "RETURN o.id AS id, o.action_id AS action_id, o.target_cid AS target_cid, "
        "       o.success AS success, o.details AS details, o.recorded_at AS recorded_at, "
        "       coalesce(o.learned, false) AS learned"
    )
    existing_recs = store.query(run_graph_name, existing_outcome_cypher, {"action_id": action_id})
    if existing_recs:
        r = existing_recs[0]
        return Outcome(
            id=r["id"],
            action_id=r["action_id"],
            target_cid=r.get("target_cid") or "",
            success=bool(r.get("success", True)),
            details=r.get("details") or "",
            recorded_at=r.get("recorded_at") or "",
            learned=bool(r.get("learned", False)),
        )

    # 2. Inspect Action in run memory
    check_cypher = (
        f"MATCH (a:{LABEL_ACTION} {{id: $action_id}}) "
        "RETURN a.id AS id, a.status AS status, a.target_cid AS target_cid, "
        "       coalesce(a.target_cids, []) AS target_cids, a.kind AS kind, a.action_type AS action_type"
    )
    recs = store.query(run_graph_name, check_cypher, {"action_id": action_id})
    if not recs:
        raise ValueError(f"Action '{action_id}' not found in run graph '{run_graph_name}'.")

    act_data = recs[0]
    status = act_data["status"]
    if status != STATUS_APPROVED:
        raise NotApprovedError(
            f"Action '{action_id}' cannot be executed: status is '{status}', requires 'APPROVED'."
        )

    # 3. Atomic Conditional Status Update: APPROVED -> EXECUTING
    conditional_cypher = (
        f"MATCH (a:{LABEL_ACTION} {{id: $action_id}}) "
        "WHERE a.status = 'APPROVED' "
        "SET a.status = 'EXECUTING' "
        "RETURN a.id AS id, a.kind AS kind, a.action_type AS action_type, "
        "       coalesce(a.target_cids, []) AS target_cids, a.target_cid AS target_cid"
    )
    locked_recs = store.query(run_graph_name, conditional_cypher, {"action_id": action_id})
    if not locked_recs:
        # Re-check if already executed concurrently
        existing_recs = store.query(run_graph_name, existing_outcome_cypher, {"action_id": action_id})
        if existing_recs:
            r = existing_recs[0]
            return Outcome(
                id=r["id"],
                action_id=r["action_id"],
                target_cid=r.get("target_cid") or "",
                success=bool(r.get("success", True)),
                details=r.get("details") or "",
                recorded_at=r.get("recorded_at") or "",
                learned=bool(r.get("learned", False)),
            )
        raise NotApprovedError(
            f"Action '{action_id}' cannot be executed: concurrent transition from 'APPROVED'."
        )

    target_cids = locked_recs[0].get("target_cids") or []
    if not target_cids and locked_recs[0].get("target_cid"):
        target_cids = [locked_recs[0]["target_cid"]]
    primary_cid = target_cids[0] if target_cids else ""

    now = datetime.now(timezone.utc).isoformat()

    try:
        # 4. Apply Domain Graph Mutation to all targets
        for cid in target_cids:
            mutate_cypher = (
                f"MATCH (c:{LABEL_CUSTOMER} {{cid: $cid}}) "
                "SET c.flagged = true, c.flag_run = $run_id, c.flagged_at = $timestamp "
                "RETURN c.cid AS cid"
            )
            store.query(
                domain_graph_name,
                mutate_cypher,
                {"cid": cid, "run_id": effective_run_id, "timestamp": now},
            )
        details = f"Flagged {len(target_cids)} customer(s) in operational domain graph (run {effective_run_id}): {', '.join(target_cids)}."

        # 5. Record Outcome in Run Memory and update Action status to EXECUTED
        outcome = Outcome(
            action_id=action_id,
            target_cid=primary_cid,
            success=True,
            details=details,
            recorded_at=now,
        )

        create_outcome_cypher = (
            f"CREATE (o:{LABEL_OUTCOME} {{"
            f"  id: $out_id, "
            f"  action_id: $action_id, "
            f"  target_cid: $cid, "
            f"  target_cids: $target_cids, "
            f"  success: true, "
            f"  details: $details, "
            f"  recorded_at: $timestamp, "
            f"  learned: false"
            f"}})"
            f"WITH o "
            f"MATCH (a:{LABEL_ACTION} {{id: $action_id}}) "
            f"CREATE (a)-[:{REL_RESULTED_IN}]->(o) "
            f"SET a.status = 'EXECUTED', a.executed_at = $timestamp"
        )
        store.query(
            run_graph_name,
            create_outcome_cypher,
            {
                "out_id": outcome.id,
                "action_id": action_id,
                "cid": primary_cid,
                "target_cids": target_cids,
                "details": details,
                "timestamp": now,
            },
        )
        return outcome

    except Exception as err:
        try:
            store.query(
                run_graph_name,
                f"MATCH (a:{LABEL_ACTION} {{id: $action_id}}) "
                "SET a.status = 'FAILED', a.failure_reason = $reason",
                {"action_id": action_id, "reason": str(err)},
            )
        except Exception:
            pass
        raise


def evaluate_outcomes(
    store: GraphStore,
    domain_graph_name: str,
    ground_truth: GroundTruth,
) -> EvaluationMetrics:
    """Evaluate domain customer flagging against ground truth ring and decoy sets.

    Args:
        store: GraphStore connection
        domain_graph_name: Operational domain graph
        ground_truth: GroundTruth containing known ring_cids and decoy_cids

    Returns:
        EvaluationMetrics with TP, FP, TN, FN, precision, recall, and F1.
    """
    flagged_query = (
        f"MATCH (c:{LABEL_CUSTOMER} {{flagged: true}}) "
        "RETURN c.cid AS cid"
    )
    records = store.query(domain_graph_name, flagged_query)
    flagged_cids = {r["cid"] for r in records}

    ring_cids = set(ground_truth.ring_cids)
    decoy_cids = set(ground_truth.decoy_cids)

    tp = len(flagged_cids & ring_cids)
    fp = len(flagged_cids - ring_cids)
    tn = len(decoy_cids - flagged_cids)
    fn = len(ring_cids - flagged_cids)

    precision = float(tp) / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = float(tp) / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2.0 * (precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return EvaluationMetrics(
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1=f1,
    )
