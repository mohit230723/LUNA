"""Integration test verifying the run memory schema naming contract on live FalkorDB."""

import pytest
from luna.agents.models import Finding
from luna.graph.schema import (
    LABEL_FINDING,
    LABEL_AGENT,
    LABEL_CUSTOMER,
    LABEL_DECISION,
    LABEL_ACTION,
    LABEL_OUTCOME,
    REL_PROMOTED_FROM,
    REL_ASSESSES,
    REL_SUPPORTED_BY,
    REL_CONFLICTS_WITH,
    REL_UPHELD,
    REL_SUPERSEDES,
    REL_ABOUT,
    REL_BASED_ON,
    REL_RESULTED_IN,
    agent_graph_name,
)
from luna.orchestrator.promote import promote_findings
from luna.orchestrator.resolve import Decision
from luna.orchestrator.actions import Action, Outcome


@pytest.mark.integration
def test_promoted_run_graph_schema_contract(live_store, tmp_graph: str) -> None:
    """Assert that promoting a finding produces exactly the contracted labels and relationship types."""
    run_id = f"contract_{tmp_graph}"
    agent_id = "test_agent"

    agent_slice = agent_graph_name(run_id, agent_id)
    run_graph = f"{tmp_graph}_run"

    try:
        # Seed evidence node in agent slice so promotion passes anti-hallucination check
        live_store.query(
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
            store=live_store,
            agent_graph_name=agent_slice,
            run_graph_name=run_graph,
            findings=[finding],
        )

        assert result.total_promoted == 1
        assert result.total_rejected == 0

        # Query live graph labels
        raw_labels = live_store.query(run_graph, "CALL db.labels()")
        labels = {row.get("label") or list(row.values())[0] for row in raw_labels}

        # Query live relationship types
        raw_rels = live_store.query(run_graph, "CALL db.relationshipTypes()")
        rels = {row.get("relationshipType") or list(row.values())[0] for row in raw_rels}

        expected_labels = {LABEL_FINDING, LABEL_AGENT, LABEL_CUSTOMER, "Entity"}
        expected_rels = {REL_PROMOTED_FROM, REL_ASSESSES, REL_SUPPORTED_BY}

        assert labels == expected_labels, f"Labels mismatch: {labels} != {expected_labels}"
        assert rels == expected_rels, f"Relationships mismatch: {rels} != {expected_rels}"

    finally:
        live_store.delete_graph(agent_slice)
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_orchestrator_decision_action_outcome_schema_contract(live_store, tmp_graph: str) -> None:
    """Assert that Decision, Action, and Outcome adhere strictly to the frozen schema naming contract."""
    run_graph = f"{tmp_graph}_orch"

    try:
        # Create full lifecycle graph structure: Customer, Findings, Decision, Action, Outcome
        live_store.query(
            run_graph,
            f"CREATE (c:{LABEL_CUSTOMER} {{cid: 'c-contract-01'}}) "
            f"CREATE (f1:{LABEL_FINDING} {{id: 'f-win', verdict: 'suspicious'}}) "
            f"CREATE (f2:{LABEL_FINDING} {{id: 'f-lose', verdict: 'benign', status: 'superseded'}}) "
            f"CREATE (d:{LABEL_DECISION} {{"
            f"  id: 'd-01', "
            f"  target_cid: 'c-contract-01', "
            f"  chosen_verdict: 'suspicious', "
            f"  confidence: 0.90, "
            f"  backend: 'rule', "
            f"  component_scores: $comp, "
            f"  weights: $weights, "
            f"  skill_scores_json: $skills"
            f"}}) "
            f"CREATE (a:{LABEL_ACTION} {{"
            f"  id: 'act-01', "
            f"  kind: 'flag_for_review', "
            f"  status: 'EXECUTED', "
            f"  target_cids: ['c-contract-01']"
            f"}}) "
            f"CREATE (o:{LABEL_OUTCOME} {{"
            f"  id: 'out-01', "
            f"  action_id: 'act-01', "
            f"  target_cid: 'c-contract-01', "
            f"  success: true, "
            f"  tp: 1, fp: 0, fn: 0, "
            f"  precision: 1.0, recall: 1.0, f1: 1.0, "
            f"  learned: true"
            f"}}) "
            f"CREATE (f1)-[:{REL_ASSESSES}]->(c) "
            f"CREATE (f2)-[:{REL_ASSESSES}]->(c) "
            f"CREATE (d)-[:{REL_UPHELD}]->(f1) "
            f"CREATE (d)-[:{REL_SUPERSEDES}]->(f2) "
            f"CREATE (d)-[:{REL_ABOUT}]->(c) "
            f"CREATE (a)-[:{REL_BASED_ON}]->(f1) "
            f"CREATE (a)-[:{REL_RESULTED_IN}]->(o)",
            {"comp": "{}", "weights": "{}", "skills": "{}"},
        )

        raw_labels = live_store.query(run_graph, "CALL db.labels()")
        labels = {row.get("label") or list(row.values())[0] for row in raw_labels}

        raw_rels = live_store.query(run_graph, "CALL db.relationshipTypes()")
        rels = {row.get("relationshipType") or list(row.values())[0] for row in raw_rels}

        assert LABEL_DECISION in labels
        assert LABEL_ACTION in labels
        assert LABEL_OUTCOME in labels
        assert REL_UPHELD in rels
        assert REL_SUPERSEDES in rels
        assert REL_ABOUT in rels
        assert REL_BASED_ON in rels
        assert REL_RESULTED_IN in rels

        # Verify Action has no edge to Decision
        bad_action_dec_links = live_store.query(
            run_graph,
            f"MATCH (a:{LABEL_ACTION})-[:{REL_BASED_ON}]->(d:{LABEL_DECISION}) RETURN count(d) AS cnt",
        )
        assert bad_action_dec_links[0]["cnt"] == 0

    finally:
        live_store.delete_graph(run_graph)
