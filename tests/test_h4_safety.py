"""Tests for H4: Execution safety, NotApprovedError, atomic conditional status, domain flag_run, and idempotent outcomes."""

import pytest
from unittest.mock import MagicMock
from luna.orchestrator.actions import (
    Action,
    Outcome,
    NotApprovedError,
    approve_action,
    execute_action,
)


@pytest.mark.integration
def test_not_approved_raises_not_approved_error(live_store, tmp_graph: str) -> None:
    """Verify executing an action that is not APPROVED raises NotApprovedError (inheriting from PermissionError)."""
    run_graph = tmp_graph
    domain_graph = f"{tmp_graph}_dom"

    try:
        live_store.query(
            run_graph,
            "CREATE (a1:Action {id: 'act-pending', status: 'PENDING', target_cids: ['c1']}) "
            "CREATE (a2:Action {id: 'act-rejected', status: 'REJECTED', target_cids: ['c2']})",
        )

        with pytest.raises(NotApprovedError) as exc_info1:
            execute_action(live_store, run_graph, domain_graph, "act-pending")
        assert issubclass(NotApprovedError, PermissionError)
        assert isinstance(exc_info1.value, PermissionError)
        assert "requires 'APPROVED'" in str(exc_info1.value)

        with pytest.raises(NotApprovedError) as exc_info2:
            execute_action(live_store, run_graph, domain_graph, "act-rejected")
        assert isinstance(exc_info2.value, PermissionError)
        assert "requires 'APPROVED'" in str(exc_info2.value)

    finally:
        pass


@pytest.mark.integration
def test_execute_sets_flag_run_and_timestamp(live_store, tmp_graph: str) -> None:
    """Verify execute sets flagged=true, flag_run=$run_id, and flagged_at on target customers."""
    run_graph = tmp_graph
    domain_graph = f"{tmp_graph}_dom"

    try:
        live_store.query(
            domain_graph,
            "CREATE (c1:Customer {cid: 'cust-tgt-01', flagged: false}) "
            "CREATE (c2:Customer {cid: 'cust-tgt-02', flagged: false})",
        )
        live_store.query(
            run_graph,
            "CREATE (a:Action {id: 'act-batch-run', status: 'PENDING', target_cids: ['cust-tgt-01', 'cust-tgt-02']})",
        )

        approve_action(live_store, run_graph, "act-batch-run", approver="investigator-01")
        outcome = execute_action(live_store, run_graph, domain_graph, "act-batch-run", run_id="run-exp-777")

        assert isinstance(outcome, Outcome)
        assert outcome.success is True

        custs = live_store.query(
            domain_graph,
            "MATCH (c:Customer) WHERE c.cid IN ['cust-tgt-01', 'cust-tgt-02'] "
            "RETURN c.cid AS cid, c.flagged AS flagged, c.flag_run AS flag_run, c.flagged_at AS flagged_at",
        )
        assert len(custs) == 2
        for c in custs:
            assert c["flagged"] is True
            assert c["flag_run"] == "run-exp-777"
            assert c["flagged_at"] is not None

    finally:
        live_store.delete_graph(domain_graph)


@pytest.mark.integration
def test_double_execute_returns_same_outcome_id(live_store, tmp_graph: str) -> None:
    """Verify calling execute_action twice returns the exact same outcome id without re-running."""
    run_graph = tmp_graph
    domain_graph = f"{tmp_graph}_dom"

    try:
        live_store.query(domain_graph, "CREATE (c:Customer {cid: 'cust-double', flagged: false})")
        live_store.query(
            run_graph,
            "CREATE (a:Action {id: 'act-double', status: 'PENDING', target_cids: ['cust-double']})",
        )

        approve_action(live_store, run_graph, "act-double", approver="auto")

        out1 = execute_action(live_store, run_graph, domain_graph, "act-double", run_id="run-42")
        out2 = execute_action(live_store, run_graph, domain_graph, "act-double", run_id="run-42")

        assert out1.id == out2.id
        assert out1.target_cid == out2.target_cid

        # Verify only one Outcome node exists in run graph
        outcomes = live_store.query(
            run_graph,
            "MATCH (a:Action {id: 'act-double'})-[:RESULTED_IN]->(o:Outcome) RETURN o.id AS id",
        )
        assert len(outcomes) == 1
        assert outcomes[0]["id"] == out1.id

    finally:
        live_store.delete_graph(domain_graph)


def test_conditional_status_update_failure_sets_failed() -> None:
    """Verify on exception during execution, action status is transitioned to FAILED with reason."""
    mock_store = MagicMock()
    # 1. Action query -> APPROVED
    # 2. Conditional status update -> EXECUTING
    # 3. Domain mutation raises exception
    mock_store.query.side_effect = [
        # 1. Existing outcome check -> None
        [],
        # 2. Check action -> APPROVED
        [{"id": "act-fail", "status": "APPROVED", "target_cids": ["c1"], "kind": "flag_for_review"}],
        # 3. Conditional status update -> EXECUTING
        [{"id": "act-fail", "target_cids": ["c1"], "kind": "flag_for_review"}],
        # 4. Domain query raises
        RuntimeError("Database connection lost"),
        # 5. Setting status to FAILED
        [],
    ]

    with pytest.raises(RuntimeError, match="Database connection lost"):
        execute_action(mock_store, "run_graph", "domain_graph", "act-fail")

    # Verify FAILED status query was called
    failed_calls = [
        c for c in mock_store.query.call_args_list
        if "SET a.status = 'FAILED'" in str(c)
    ]
    assert len(failed_calls) == 1
