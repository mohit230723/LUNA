"""Integration tests for finding promotion engine and anti-hallucination barrier."""

import pytest
from luna.agents.models import Finding
from luna.orchestrator.promote import promote_findings


@pytest.mark.integration
def test_promote_valid_findings(live_store, tmp_graph: str) -> None:
    """Verify that findings with verified evidence in the agent slice are promoted to the live run graph."""
    run_graph = f"{tmp_graph}_run"
    try:
        # Populate agent slice in tmp_graph with verified entities
        live_store.query(
            tmp_graph,
            "CREATE (c:Customer {cid: 'cust-000'}), "
            "       (b:BankAccount {cid: 'ba-ring-01'}), "
            "       (a:Customer {cid: 'cust-001'})"
        )

        finding = Finding(
            id="find-valid-01",
            agent_id="agent-01",
            skill_id="entity-linker",
            target_cid="cust-000",
            verdict="suspicious",
            confidence=0.92,
            reasoning="Shared high-risk bank account with associate",
            evidence_cids=["ba-ring-01", "cust-001"],
        )

        res = promote_findings(
            store=live_store,
            agent_graph_name=tmp_graph,
            run_graph_name=run_graph,
            findings=[finding],
        )

        assert res.total_promoted == 1
        assert res.total_rejected == 0
        assert len(res.promoted) == 1
        assert res.promoted[0].id == "find-valid-01"

        # Verify Finding node and relationships exist in live run graph
        findings = live_store.query(run_graph, "MATCH (f:Finding {id: 'find-valid-01'}) RETURN f.id AS id")
        assert len(findings) == 1

        promoted_from = live_store.query(run_graph, "MATCH (:Finding)-[:PROMOTED_FROM]->(:Agent) RETURN count(*) AS cnt")
        assert promoted_from[0]["cnt"] == 1

        assesses = live_store.query(run_graph, "MATCH (:Finding)-[:ASSESSES]->(:Customer) RETURN count(*) AS cnt")
        assert assesses[0]["cnt"] == 1

        supported_by = live_store.query(run_graph, "MATCH (:Finding)-[:SUPPORTED_BY]->(:Entity) RETURN count(*) AS cnt")
        assert supported_by[0]["cnt"] == 2
    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_reject_hallucinated_evidence(live_store, tmp_graph: str) -> None:
    """Verify that findings citing non-existent evidence CIDs are rejected by live barrier."""
    run_graph = f"{tmp_graph}_run"
    try:
        # Populate agent slice with only one valid node
        live_store.query(
            tmp_graph,
            "CREATE (c:Customer {cid: 'cust-000'}), (b:BankAccount {cid: 'ba-ring-01'})"
        )

        hallucinated_finding = Finding(
            id="find-hallucinated-02",
            agent_id="agent-01",
            skill_id="entity-linker",
            target_cid="cust-000",
            verdict="suspicious",
            confidence=0.95,
            reasoning="Hallucinated evidence connection",
            evidence_cids=["ba-ring-01", "cust-fake-999"],
        )

        res = promote_findings(
            store=live_store,
            agent_graph_name=tmp_graph,
            run_graph_name=run_graph,
            findings=[hallucinated_finding],
        )

        assert res.total_promoted == 0
        assert res.total_rejected == 1
        assert len(res.rejected) == 1
        assert res.rejected[0].finding.id == "find-hallucinated-02"
        assert "cust-fake-999" in res.rejected[0].reason
        assert "anti-hallucination barrier" in res.rejected[0].reason

        # Verify no writes occurred on run graph
        findings = live_store.query(run_graph, "MATCH (f:Finding) RETURN count(f) AS cnt")
        assert findings == [] or findings[0]["cnt"] == 0
    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_partial_batch_promotion(live_store, tmp_graph: str) -> None:
    """Verify mixed batch with 1 valid and 1 invalid finding."""
    run_graph = f"{tmp_graph}_run"
    try:
        live_store.query(
            tmp_graph,
            "CREATE (c1:Customer {cid: 'cust-000'}), (c2:Customer {cid: 'cust-001'}), (e:Entity {cid: 'valid-evidence-cid'})"
        )

        f1 = Finding(
            id="find-good",
            agent_id="agent-01",
            skill_id="entity-linker",
            target_cid="cust-000",
            verdict="suspicious",
            confidence=0.9,
            reasoning="Genuine evidence",
            evidence_cids=["valid-evidence-cid"],
        )
        f2 = Finding(
            id="find-bad",
            agent_id="agent-01",
            skill_id="entity-linker",
            target_cid="cust-001",
            verdict="suspicious",
            confidence=0.8,
            reasoning="Fake evidence",
            evidence_cids=["ghost-cid"],
        )

        res = promote_findings(
            store=live_store,
            agent_graph_name=tmp_graph,
            run_graph_name=run_graph,
            findings=[f1, f2],
        )

        assert res.total_promoted == 1
        assert res.total_rejected == 1
        assert res.promoted[0].id == "find-good"
        assert res.rejected[0].finding.id == "find-bad"
    finally:
        live_store.delete_graph(run_graph)
