"""Integration test verifying the run memory schema naming contract on live FalkorDB."""

import pytest
from luna.agents.models import Finding
from luna.graph.schema import run_graph_name, agent_graph_name
from luna.graph.store import GraphStore
from luna.orchestrator.promote import promote_findings


@pytest.mark.integration
def test_promoted_run_graph_schema_contract() -> None:
    """Assert that promoting a finding produces exactly the contracted labels and relationship types."""
    store = GraphStore()
    run_id = "test_contract_run"
    agent_id = "test_agent"

    agent_slice = agent_graph_name(run_id, agent_id)
    run_graph = run_graph_name(run_id)

    # Clean any leftover probe graphs
    store.delete_graph(agent_slice)
    store.delete_graph(run_graph)

    try:
        # Seed evidence node in agent slice so promotion passes anti-hallucination check
        store.query(
            agent_slice,
            "CREATE (:Customer {cid: $target_cid})-[:HAS_ACCOUNT]->(:BankAccount {cid: $ev_cid})",
            {"target_cid": "cust-test-01", "ev_cid": "ba-test-01"},
        )

        finding = Finding(
            agent_id=agent_id,
            skill_id="entity-linker",
            target_cid="cust-test-01",
            verdict="suspicious",
            confidence=0.90,
            reasoning="Contract verification finding",
            evidence_cids=["ba-test-01"],
        )

        result = promote_findings(
            store=store,
            agent_graph_name=agent_slice,
            run_graph_name=run_graph,
            findings=[finding],
        )

        assert result.total_promoted == 1
        assert result.total_rejected == 0

        # Query live graph labels
        raw_labels = store.query(run_graph, "CALL db.labels()")
        # db.labels() returns list of rows with label
        labels = {row.get("label") or list(row.values())[0] for row in raw_labels}

        # Query live relationship types
        raw_rels = store.query(run_graph, "CALL db.relationshipTypes()")
        rels = {row.get("relationshipType") or list(row.values())[0] for row in raw_rels}

        expected_labels = {"Finding", "Agent", "Customer", "Entity"}
        expected_rels = {"PROMOTED_FROM", "ASSESSES", "SUPPORTED_BY"}

        assert labels == expected_labels, f"Labels mismatch: {labels} != {expected_labels}"
        assert rels == expected_rels, f"Relationships mismatch: {rels} != {expected_rels}"

    finally:
        store.delete_graph(agent_slice)
        store.delete_graph(run_graph)
