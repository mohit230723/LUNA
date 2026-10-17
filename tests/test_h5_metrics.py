"""Tests for H5: Run-scoped metrics evaluation, Outcome node property storage, and reset_flags."""

import pytest
from luna.orchestrator.actions import (
    evaluate_outcomes,
    reset_flags,
    EvaluationMetrics,
)
from luna.domain.seed import GroundTruth


@pytest.mark.integration
def test_evaluate_outcomes_run_scoped(live_store, tmp_graph: str) -> None:
    """Verify evaluate_outcomes only counts customers where flag_run == run_id."""
    domain_graph = f"{tmp_graph}_dom"
    run_graph = f"{tmp_graph}_run"

    gt = GroundTruth(
        ring_cids={"cust-ring-1", "cust-ring-2"},
        decoy_cids={"cust-decoy-1", "cust-decoy-2"},
    )

    try:
        # Create customers in domain graph
        live_store.query(
            domain_graph,
            "CREATE (c1:Customer {cid: 'cust-ring-1', flagged: true, flag_run: 'run-101'}) "
            "CREATE (c2:Customer {cid: 'cust-decoy-1', flagged: true, flag_run: 'run-101'}) "
            "CREATE (c3:Customer {cid: 'cust-ring-2', flagged: true, flag_run: 'run-202'}) "
            "CREATE (c4:Customer {cid: 'cust-decoy-2', flagged: false})",
        )

        # Create Outcome node in run_graph
        live_store.query(
            run_graph,
            "CREATE (o:Outcome {id: 'out-101', action_id: 'act-101', success: true})",
        )

        # Evaluate run-101
        metrics_101 = evaluate_outcomes(
            live_store,
            domain_graph,
            gt,
            run_id="run-101",
            run_graph_name=run_graph,
        )

        assert metrics_101 is not None
        assert metrics_101.true_positives == 1  # cust-ring-1
        assert metrics_101.false_positives == 1 # cust-decoy-1
        assert metrics_101.false_negatives == 1 # cust-ring-2 was NOT flagged in run-101
        assert round(metrics_101.precision, 2) == 0.50
        assert round(metrics_101.recall, 2) == 0.50

        # Check properties stored on Outcome node
        out_props = live_store.query(
            run_graph,
            "MATCH (o:Outcome {id: 'out-101'}) "
            "RETURN o.tp AS tp, o.fp AS fp, o.fn AS fn, "
            "       o.precision AS precision, o.recall AS recall, o.f1 AS f1",
        )
        assert len(out_props) == 1
        assert out_props[0]["tp"] == 1
        assert out_props[0]["fp"] == 1
        assert out_props[0]["fn"] == 1
        assert round(out_props[0]["precision"], 2) == 0.50

    finally:
        live_store.delete_graph(domain_graph)
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_evaluate_outcomes_null_without_truth(live_store, tmp_graph: str) -> None:
    """Verify that when no truth is supplied, metrics are null on the Outcome node."""
    domain_graph = f"{tmp_graph}_dom"
    run_graph = f"{tmp_graph}_run"

    try:
        live_store.query(
            domain_graph,
            "CREATE (c:Customer {cid: 'c1', flagged: true, flag_run: 'run-no-truth'})",
        )
        live_store.query(
            run_graph,
            "CREATE (o:Outcome {id: 'out-no-truth', action_id: 'act-1', success: true, tp: 99})",
        )

        res = evaluate_outcomes(
            live_store,
            domain_graph,
            ground_truth=None,
            run_id="run-no-truth",
            run_graph_name=run_graph,
        )
        assert res is None

        out_props = live_store.query(
            run_graph,
            "MATCH (o:Outcome {id: 'out-no-truth'}) "
            "RETURN o.tp AS tp, o.fp AS fp, o.fn AS fn, o.precision AS precision",
        )
        assert len(out_props) == 1
        assert out_props[0]["tp"] is None
        assert out_props[0]["precision"] is None

    finally:
        live_store.delete_graph(domain_graph)
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_reset_flags_scoped_and_global(live_store, tmp_graph: str) -> None:
    """Verify reset_flags clears flags by run_id or globally across all customers."""
    domain_graph = f"{tmp_graph}_dom"

    try:
        live_store.query(
            domain_graph,
            "CREATE (c1:Customer {cid: 'c1', flagged: true, flag_run: 'run-A', flagged_at: '2026-01-01'}) "
            "CREATE (c2:Customer {cid: 'c2', flagged: true, flag_run: 'run-B', flagged_at: '2026-01-01'}) "
            "CREATE (c3:Customer {cid: 'c3', flagged: false})",
        )

        # 1. Reset scoped to run-A
        count_a = reset_flags(live_store, domain_graph, run_id="run-A")
        assert count_a == 1

        c1 = live_store.query(domain_graph, "MATCH (c:Customer {cid: 'c1'}) RETURN c.flagged AS flagged, c.flag_run AS flag_run")
        assert c1[0]["flagged"] is False
        assert c1[0]["flag_run"] is None

        c2 = live_store.query(domain_graph, "MATCH (c:Customer {cid: 'c2'}) RETURN c.flagged AS flagged, c.flag_run AS flag_run")
        assert c2[0]["flagged"] is True
        assert c2[0]["flag_run"] == "run-B"

        # 2. Reset globally
        count_all = reset_flags(live_store, domain_graph)
        assert count_all >= 1

        c2_after = live_store.query(domain_graph, "MATCH (c:Customer {cid: 'c2'}) RETURN c.flagged AS flagged, c.flag_run AS flag_run")
        assert c2_after[0]["flagged"] is False
        assert c2_after[0]["flag_run"] is None

    finally:
        live_store.delete_graph(domain_graph)
