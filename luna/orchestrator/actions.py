"""Action proposal, human approval barrier, idempotent execution, and evaluation (Plan 3.3)."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field

from luna.graph.store import GraphStore
from luna.graph.schema import (
    LABEL_ACTION,
    LABEL_OUTCOME,
    LABEL_DECISION,
    LABEL_FINDING,
    LABEL_CUSTOMER,
    REL_BASED_ON,
    REL_RESULTED_IN,
    REL_CONFLICTS_WITH,
    REL_UPHELD,
    REL_ASSESSES,
)
from luna.domain.seed import GroundTruth

CORROBORATION_MIN_SKILLS: int = 2
CORROBORATION_CONF: float = 0.8


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
    action_type: str = "FLAG_CUSTOMER"  # "FLAG_CUSTOMER" | "CLEAR_CUSTOMER" | "ESCALATE_CLAIM"
    target_cid: str
    status: str = "PENDING"  # "PENDING" | "APPROVED" | "REJECTED" | "EXECUTED"
    recommended_by_id: Optional[str] = None
    approver: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_at: Optional[str] = None
    executed_at: Optional[str] = None
    rejection_reason: Optional[str] = None


class Outcome(BaseModel):
    """Represents the recorded result of an executed domain action."""

    id: str = Field(default_factory=lambda: f"out-{uuid.uuid4().hex[:8]}")
    action_id: str
    target_cid: str
    success: bool
    details: str
    recorded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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
    """Scan run memory for suspicious decisions and uncontested findings, creating PENDING Actions.

    Args:
        store: GraphStore connection
        run_graph_name: Target run memory graph

    Returns:
        List of newly created Action objects with status='PENDING'.
    """
    actions: list[Action] = []
    now = datetime.now(timezone.utc).isoformat()

    # Query all active suspicious findings grouped by customer to check corroboration
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

    corroborated_cids = {
        cid for cid, f_list in findings_by_cid.items()
        if check_corroboration(f_list)
    }

    # 1. Propose actions based on suspicious Decisions
    dec_query = (
        f"MATCH (d:{LABEL_DECISION} {{chosen_verdict: 'suspicious'}}) "
        f"WHERE NOT (d)<-[:{REL_BASED_ON}]-(:{LABEL_ACTION}) "
        "RETURN d.id AS id, d.target_cid AS cid, d.confidence AS confidence"
    )
    suspicious_decisions = store.query(run_graph_name, dec_query)

    for row in suspicious_decisions:
        cid = row["cid"]
        conf = float(row.get("confidence") or 0.0)
        if cid not in corroborated_cids and conf < CORROBORATION_CONF:
            continue
        action = Action(
            target_cid=cid,
            action_type="FLAG_CUSTOMER",
            status="PENDING",
            recommended_by_id=row["id"],
            created_at=now,
        )
        # Create Action node and BASED_ON relationship
        cypher = (
            f"CREATE (a:{LABEL_ACTION} {{"
            f"  id: $id, "
            f"  action_type: $action_type, "
            f"  target_cid: $target_cid, "
            f"  status: 'PENDING', "
            f"  recommended_by_id: $rec_id, "
            f"  created_at: $created_at"
            f"}}) "
            f"WITH a "
            f"MATCH (d:{LABEL_DECISION} {{id: $rec_id}}) "
            f"CREATE (a)-[:{REL_BASED_ON}]->(d)"
        )
        store.query(
            run_graph_name,
            cypher,
            {
                "id": action.id,
                "action_type": action.action_type,
                "target_cid": action.target_cid,
                "rec_id": action.recommended_by_id,
                "created_at": action.created_at,
            },
        )
        actions.append(action)

    # 2. Propose actions based on uncontested, non-superseded suspicious Findings without Decisions
    find_query = (
        f"MATCH (f:{LABEL_FINDING} {{verdict: 'suspicious'}}) "
        "WHERE (f.status IS NULL OR f.status <> 'superseded') "
        f"  AND NOT (f)-[:{REL_CONFLICTS_WITH}]-() "
        f"  AND NOT (f)<-[:{REL_UPHELD}]-(:{LABEL_DECISION}) "
        f"  AND NOT (f)<-[:{REL_BASED_ON}]-(:{LABEL_ACTION}) "
        f"OPTIONAL MATCH (f)-[:{REL_ASSESSES}]->(c:{LABEL_CUSTOMER}) "
        "RETURN f.id AS id, coalesce(f.target_cid, c.cid) AS cid"
    )
    uncontested_findings = store.query(run_graph_name, find_query)

    for row in uncontested_findings:
        cid = row["cid"]
        if cid not in corroborated_cids:
            continue
        action = Action(
            target_cid=row["cid"],
            action_type="FLAG_CUSTOMER",
            status="PENDING",
            recommended_by_id=row["id"],
            created_at=now,
        )
        cypher = (
            f"CREATE (a:{LABEL_ACTION} {{"
            f"  id: $id, "
            f"  action_type: $action_type, "
            f"  target_cid: $target_cid, "
            f"  status: 'PENDING', "
            f"  recommended_by_id: $rec_id, "
            f"  created_at: $created_at"
            f"}}) "
            f"WITH a "
            f"MATCH (f:{LABEL_FINDING} {{id: $rec_id}}) "
            f"CREATE (a)-[:{REL_BASED_ON}]->(f)"
        )
        store.query(
            run_graph_name,
            cypher,
            {
                "id": action.id,
                "action_type": action.action_type,
                "target_cid": action.target_cid,
                "rec_id": action.recommended_by_id,
                "created_at": action.created_at,
            },
        )
        actions.append(action)

    return actions


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
        "RETURN a.id AS id, a.action_type AS action_type, a.target_cid AS target_cid, "
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
        action_type=r["action_type"],
        target_cid=r["target_cid"],
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
        "RETURN a.id AS id, a.action_type AS action_type, a.target_cid AS target_cid, "
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
        action_type=r["action_type"],
        target_cid=r["target_cid"],
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
) -> Outcome:
    """Execute an approved action against the domain graph and record the outcome in run memory.

    CRITICAL APPROVAL RULE:
    execute_action MUST refuse execution unless action.status is 'APPROVED'.
    There is no bypass flag.

    Args:
        store: GraphStore connection
        run_graph_name: Target run memory graph
        domain_graph_name: Operational domain graph
        action_id: Action identifier to execute

    Returns:
        Outcome object recording execution results.
    """
    # 1. Inspect Action in run memory
    check_cypher = (
        f"MATCH (a:{LABEL_ACTION} {{id: $action_id}}) "
        "RETURN a.id AS id, a.status AS status, a.target_cid AS target_cid, a.action_type AS action_type"
    )
    recs = store.query(run_graph_name, check_cypher, {"action_id": action_id})
    if not recs:
        raise ValueError(f"Action '{action_id}' not found in run graph '{run_graph_name}'.")

    act_data = recs[0]
    status = act_data["status"]
    cid = act_data["target_cid"]
    action_type = act_data["action_type"]

    # 2. INVIOLABLE APPROVAL BARRIER
    if status != "APPROVED":
        raise PermissionError(
            f"Action '{action_id}' cannot be executed: status is '{status}', requires 'APPROVED'."
        )

    now = datetime.now(timezone.utc).isoformat()

    # 3. Apply Idempotent Domain Graph Mutation
    if action_type == "FLAG_CUSTOMER":
        mutate_cypher = (
            f"MATCH (c:{LABEL_CUSTOMER} {{cid: $cid}}) "
            "SET c.flagged = true, c.flagged_at = $timestamp "
            "RETURN c.cid AS cid"
        )
        store.query(domain_graph_name, mutate_cypher, {"cid": cid, "timestamp": now})
        details = f"Flagged customer {cid} in operational domain graph."
    elif action_type == "CLEAR_CUSTOMER":
        mutate_cypher = (
            f"MATCH (c:{LABEL_CUSTOMER} {{cid: $cid}}) "
            "SET c.flagged = false, c.cleared_at = $timestamp "
            "RETURN c.cid AS cid"
        )
        store.query(domain_graph_name, mutate_cypher, {"cid": cid, "timestamp": now})
        details = f"Cleared customer {cid} in operational domain graph."
    else:
        details = f"Executed generic action '{action_type}' for {cid}."

    # 4. Record Outcome in Run Memory and update Action status to EXECUTED
    outcome = Outcome(
        action_id=action_id,
        target_cid=cid,
        success=True,
        details=details,
        recorded_at=now,
    )

    create_outcome_cypher = (
        f"CREATE (o:{LABEL_OUTCOME} {{"
        f"  id: $out_id, "
        f"  action_id: $action_id, "
        f"  target_cid: $cid, "
        f"  success: true, "
        f"  details: $details, "
        f"  recorded_at: $timestamp"
        f"}}) "
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
            "cid": cid,
            "details": details,
            "timestamp": now,
        },
    )

    return outcome


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

    # True Positives: ring members flagged
    tp = len(flagged_cids & ring_cids)

    # False Positives: flagged customers that are not in the fraud ring
    fp = len(flagged_cids - ring_cids)

    # True Negatives: decoy family members that were NOT flagged
    tn = len(decoy_cids - flagged_cids)

    # False Negatives: ring members that were NOT flagged
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
