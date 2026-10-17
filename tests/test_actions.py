"""Tests for Action lifecycle, approval gate, domain execution, and evaluation (Plan 3.3)."""

import pytest
from luna.orchestrator.actions import (
    Action,
    Outcome,
    EvaluationMetrics,
    propose_actions,
    approve_action,
    reject_action,
    execute_action,
    evaluate_outcomes,
)
from luna.domain.seed import GroundTruth


@pytest.mark.integration
def test_propose_actions_from_decisions(live_store, tmp_graph: str) -> None:
    """Verify actions are proposed for suspicious decisions with PENDING status."""
    # Seed decision in tmp_graph
    live_store.query(
        tmp_graph,
        "CREATE (d:Decision {id: 'dec-01', target_cid: 'cust-ring-01', chosen_verdict: 'suspicious', confidence: 0.95})",
    )

    actions = propose_actions(live_store, tmp_graph)
    assert len(actions) == 1
    act = actions[0]
    assert isinstance(act, Action)
    assert act.target_cid == "cust-ring-01"
    assert act.status == "PENDING"
    assert act.action_type == "FLAG_CUSTOMER"
    assert act.recommended_by_id == "dec-01"

    # Check graph edge
    links = live_store.query(
        tmp_graph,
        "MATCH (a:Action {id: $aid})-[:BASED_ON]->(d:Decision {id: 'dec-01'}) RETURN a.status AS status",
        {"aid": act.id},
    )
    assert len(links) == 1
    assert links[0]["status"] == "PENDING"


@pytest.mark.integration
def test_execute_action_refuses_when_not_approved(live_store, tmp_graph: str) -> None:
    """Verify execute_action strictly refuses unless status is APPROVED (Phase 3 mandatory rule)."""
    # 1. PENDING action
    live_store.query(
        tmp_graph,
        "CREATE (a:Action {id: 'act-pending', status: 'PENDING', target_cid: 'cust-01', action_type: 'FLAG_CUSTOMER'})",
    )
    with pytest.raises(PermissionError, match="requires 'APPROVED'"):
        execute_action(live_store, tmp_graph, "domain", "act-pending")

    # 2. REJECTED action
    live_store.query(
        tmp_graph,
        "CREATE (a:Action {id: 'act-rejected', status: 'REJECTED', target_cid: 'cust-01', action_type: 'FLAG_CUSTOMER'})",
    )
    with pytest.raises(PermissionError, match="requires 'APPROVED'"):
        execute_action(live_store, tmp_graph, "domain", "act-rejected")


@pytest.mark.integration
def test_approve_and_execute_action(live_store, tmp_graph: str) -> None:
    """Verify approval gate with explicit approver enables domain mutation and Outcome record."""
    run_graph = tmp_graph
    domain_graph = f"{tmp_graph}_domain"

    try:
        # Create domain customer
        live_store.query(domain_graph, "CREATE (c:Customer {cid: 'cust-target-99', flagged: false})")

        # Create pending action in run graph
        live_store.query(
            run_graph,
            "CREATE (a:Action {id: 'act-99', status: 'PENDING', target_cid: 'cust-target-99', action_type: 'FLAG_CUSTOMER'})",
        )

        # Approve action explicitly (headless demo mode passes approver="auto")
        approved_act = approve_action(live_store, run_graph, "act-99", approver="auto")
        assert approved_act.status == "APPROVED"
        assert approved_act.approver == "auto"
        assert approved_act.approved_at is not None

        # Execute approved action
        outcome = execute_action(live_store, run_graph, domain_graph, "act-99")
        assert isinstance(outcome, Outcome)
        assert outcome.success is True
        assert outcome.target_cid == "cust-target-99"

        # Verify domain customer mutated
        cust = live_store.query(
            domain_graph,
            "MATCH (c:Customer {cid: 'cust-target-99'}) RETURN c.flagged AS flagged, c.flagged_at AS flagged_at",
        )
        assert len(cust) == 1
        assert cust[0]["flagged"] is True
        assert cust[0]["flagged_at"] is not None

        # Verify Outcome node and RESULTED_IN edge in run graph
        out_edges = live_store.query(
            run_graph,
            "MATCH (a:Action {id: 'act-99'})-[:RESULTED_IN]->(o:Outcome) RETURN a.status AS act_status, o.success AS success",
        )
        assert len(out_edges) == 1
        assert out_edges[0]["act_status"] == "EXECUTED"
        assert out_edges[0]["success"] is True

    finally:
        live_store.delete_graph(domain_graph)


def test_evaluate_outcomes_metrics_logic() -> None:
    """Unit test for evaluation precision, recall, and F1 calculation."""
    gt = GroundTruth(
        ring_cids={"cust-00", "cust-01", "cust-02", "cust-03"},
        decoy_cids={"cust-10", "cust-11", "cust-12", "cust-13"},
    )

    mock_store = pytest.importorskip("unittest.mock").MagicMock()
    # Mock flagged customers in domain: cust-00, cust-01 (TP=2), cust-10 (FP=1)
    # Ring customers cust-02, cust-03 unflagged (FN=2)
    # Decoy customers cust-11, cust-12, cust-13 unflagged (TN=3)
    mock_store.query.return_value = [
        {"cid": "cust-00"},
        {"cid": "cust-01"},
        {"cid": "cust-10"},
    ]

    metrics = evaluate_outcomes(mock_store, "domain", gt)
    assert metrics.true_positives == 2
    assert metrics.false_positives == 1
    assert metrics.true_negatives == 3
    assert metrics.false_negatives == 2
    assert round(metrics.precision, 2) == 0.67  # 2 / (2 + 1)
    assert round(metrics.recall, 2) == 0.50     # 2 / (2 + 2)
    assert round(metrics.f1, 2) == 0.57         # 2 * (0.67 * 0.5) / (0.67 + 0.5)


@pytest.mark.integration
def test_execute_action_idempotent(live_store, tmp_graph: str) -> None:
    """Verify executing action multiple times is safe and maintains consistent state."""
    run_graph = tmp_graph
    domain_graph = f"{tmp_graph}_dom"

    try:
        live_store.query(domain_graph, "CREATE (c:Customer {cid: 'cust-idem-01', flagged: false})")
        live_store.query(
            run_graph,
            "CREATE (a:Action {id: 'act-idem', status: 'PENDING', target_cid: 'cust-idem-01', action_type: 'FLAG_CUSTOMER'})",
        )

        approve_action(live_store, run_graph, "act-idem", approver="auto")
        out1 = execute_action(live_store, run_graph, domain_graph, "act-idem")
        assert out1.success is True

        # Re-execute: action is now EXECUTED; approve again or re-executing should be safe
        approve_action(live_store, run_graph, "act-idem", approver="auto")
        out2 = execute_action(live_store, run_graph, domain_graph, "act-idem")
        assert out2.success is True

        cust = live_store.query(
            domain_graph,
            "MATCH (c:Customer {cid: 'cust-idem-01'}) RETURN c.flagged AS flagged",
        )
        assert cust[0]["flagged"] is True
    finally:
        live_store.delete_graph(domain_graph)

