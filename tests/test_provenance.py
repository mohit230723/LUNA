"""Unit and integration tests for provenance logging and promotion connectivity checks."""

import pytest
from luna.agents.models import Finding
from luna.agents.provenance import ToolCallLog
from luna.orchestrator.promote import promote_findings


def test_tool_call_log_collects_nested_strings():
    """Verify ToolCallLog recursively extracts strings from deeply nested structures."""
    log = ToolCallLog()
    log.record(
        tool_name="test_tool",
        args={"cid": "root_cid"},
        result={
            "outer_key": "val1",
            "nested_list": [
                {"inner_id": "inner_cid_01"},
                ("tuple_val", {"deep_id": "deep_cid_02"}),
            ],
            "number": 12345,
            "boolean": True,
        },
    )

    observed = log.observed_strings()
    assert "val1" in observed
    assert "inner_cid_01" in observed
    assert "tuple_val" in observed
    assert "deep_cid_02" in observed


@pytest.mark.integration
def test_rejects_evidence_never_observed(live_store, tmp_graph):
    """Evidence exists in slice but was not in any tool output -> rejected with evidence_not_observed."""
    run_graph = f"{tmp_graph}_run"
    try:
        # Create nodes in slice
        live_store.query(
            tmp_graph,
            "CREATE (c:Customer {cid: 'cust_target'}), "
            "       (b:BankAccount {cid: 'ba_unobserved'}), "
            "       (c)-[:PAYS_FROM]->(b)"
        )

        finding = Finding(
            agent_id="agent_01",
            skill_id="entity-linker",
            target_cid="cust_target",
            verdict="suspicious",
            confidence=0.9,
            reasoning="Testing unobserved evidence",
            evidence_cids=["ba_unobserved"],
        )

        res = promote_findings(
            store=live_store,
            agent_graph_name=tmp_graph,
            run_graph_name=run_graph,
            findings=[finding],
            observed={"some_other_cid"},
            require_observed=True,
            max_hops=3,
        )

        assert res.total_promoted == 0
        assert res.total_rejected == 1
        assert "evidence_not_observed" in res.rejected[0].reason
    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_rejects_evidence_not_connected(live_store, tmp_graph):
    """Real node in slice, but 5+ hops from the target -> rejected with evidence_not_connected."""
    run_graph = f"{tmp_graph}_run"
    try:
        # Create a linear path of 5 hops: n0 -> n1 -> n2 -> n3 -> n4 -> n5
        live_store.query(
            tmp_graph,
            "CREATE (n0:Entity {cid: 'n0'}), "
            "       (n1:Entity {cid: 'n1'}), "
            "       (n2:Entity {cid: 'n2'}), "
            "       (n3:Entity {cid: 'n3'}), "
            "       (n4:Entity {cid: 'n4'}), "
            "       (n5:Entity {cid: 'n5'}), "
            "       (n0)-[:REL]->(n1), "
            "       (n1)-[:REL]->(n2), "
            "       (n2)-[:REL]->(n3), "
            "       (n3)-[:REL]->(n4), "
            "       (n4)-[:REL]->(n5)"
        )

        finding = Finding(
            agent_id="agent_01",
            skill_id="entity-linker",
            target_cid="n0",
            verdict="suspicious",
            confidence=0.9,
            reasoning="Testing distant node",
            evidence_cids=["n5"],
        )

        res = promote_findings(
            store=live_store,
            agent_graph_name=tmp_graph,
            run_graph_name=run_graph,
            findings=[finding],
            observed={"n5"},
            require_observed=True,
            max_hops=3,
        )

        assert res.total_promoted == 0
        assert res.total_rejected == 1
        assert "evidence_not_connected" in res.rejected[0].reason
    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_accepts_evidence_observed_and_connected(live_store, tmp_graph):
    """Evidence in slice, observed, and <= 3 hops from target is promoted."""
    run_graph = f"{tmp_graph}_run"
    try:
        live_store.query(
            tmp_graph,
            "CREATE (c:Customer {cid: 'cust_01'}), "
            "       (b:BankAccount {cid: 'ba_01'}), "
            "       (c)-[:PAYS_FROM]->(b)"
        )

        finding = Finding(
            agent_id="agent_01",
            skill_id="entity-linker",
            target_cid="cust_01",
            verdict="suspicious",
            confidence=0.9,
            reasoning="Testing connected and observed evidence",
            evidence_cids=["ba_01"],
        )

        res = promote_findings(
            store=live_store,
            agent_graph_name=tmp_graph,
            run_graph_name=run_graph,
            findings=[finding],
            observed={"ba_01"},
            require_observed=True,
            max_hops=3,
        )

        assert res.total_promoted == 1
        assert res.total_rejected == 0
        assert res.promoted[0].id == finding.id
    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_target_cid_exempt_from_observed(live_store, tmp_graph):
    """Target CID itself is exempt from observed set check."""
    run_graph = f"{tmp_graph}_run"
    try:
        live_store.query(
            tmp_graph,
            "CREATE (c:Customer {cid: 'cust_solo'})"
        )

        finding = Finding(
            agent_id="agent_01",
            skill_id="entity-linker",
            target_cid="cust_solo",
            verdict="benign",
            confidence=0.9,
            reasoning="Solo target CID evidence",
            evidence_cids=["cust_solo"],
        )

        res = promote_findings(
            store=live_store,
            agent_graph_name=tmp_graph,
            run_graph_name=run_graph,
            findings=[finding],
            observed=set(),  # empty observed set
            require_observed=True,
            max_hops=3,
        )

        assert res.total_promoted == 1
        assert res.total_rejected == 0
    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_no_writes_on_rejection(live_store, tmp_graph):
    """When a finding is rejected, run graph node count remains unchanged."""
    run_graph = f"{tmp_graph}_run"
    try:
        live_store.query(
            tmp_graph,
            "CREATE (c:Customer {cid: 'cust_01'})"
        )

        finding = Finding(
            agent_id="agent_01",
            skill_id="entity-linker",
            target_cid="cust_01",
            verdict="suspicious",
            confidence=0.9,
            reasoning="Testing rejection zero writes",
            evidence_cids=["ghost_cid"],
        )

        res = promote_findings(
            store=live_store,
            agent_graph_name=tmp_graph,
            run_graph_name=run_graph,
            findings=[finding],
            observed={"ghost_cid"},
            require_observed=True,
            max_hops=3,
        )

        assert res.total_promoted == 0
        assert res.total_rejected == 1

        nodes = live_store.query(run_graph, "MATCH (n) RETURN count(n) AS cnt")
        assert nodes == [] or nodes[0]["cnt"] == 0
    finally:
        live_store.delete_graph(run_graph)
