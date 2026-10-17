"""Tests for H3: Single batch Action per run with BASED_ON links to active suspicious findings."""

import pytest
from luna.orchestrator.actions import (
    Action,
    propose_actions,
)


@pytest.mark.integration
def test_single_batch_action_with_finding_links_not_decision(live_store, tmp_graph: str) -> None:
    """Verify one Action per run with target_cids, linked to active suspicious findings and never to Decision."""
    try:
        # 1. Setup Customer 1 (corroborated by 2 distinct skills at 0.65)
        # 2. Setup Customer 2 (corroborated by 1 skill with confidence 0.85)
        # 3. Setup Customer 3 (lone 0.65 finding - NOT corroborated)
        # 4. Include a Decision in the graph to verify Action is NEVER linked to Decision
        live_store.query(
            tmp_graph,
            "CREATE (c1:Customer {cid: 'cust-batch-01'}) "
            "CREATE (c2:Customer {cid: 'cust-batch-02'}) "
            "CREATE (c3:Customer {cid: 'cust-uncorroborated'}) "
            "CREATE (f1:Finding {id: 'f-c1-1', target_cid: 'cust-batch-01', verdict: 'suspicious', skill_id: 'skill-A', confidence: 0.65}) "
            "CREATE (f2:Finding {id: 'f-c1-2', target_cid: 'cust-batch-01', verdict: 'suspicious', skill_id: 'skill-B', confidence: 0.65}) "
            "CREATE (f3:Finding {id: 'f-c2-1', target_cid: 'cust-batch-02', verdict: 'suspicious', skill_id: 'skill-A', confidence: 0.85}) "
            "CREATE (f4:Finding {id: 'f-c3-1', target_cid: 'cust-uncorroborated', verdict: 'suspicious', skill_id: 'skill-A', confidence: 0.65}) "
            "CREATE (f_old:Finding {id: 'f-c1-old', target_cid: 'cust-batch-01', verdict: 'suspicious', skill_id: 'skill-C', confidence: 0.90, status: 'superseded'}) "
            "CREATE (d:Decision {id: 'dec-c1', target_cid: 'cust-batch-01', chosen_verdict: 'suspicious', confidence: 0.85}) "
            "CREATE (f1)-[:ASSESSES]->(c1) "
            "CREATE (f2)-[:ASSESSES]->(c1) "
            "CREATE (f_old)-[:ASSESSES]->(c1) "
            "CREATE (f3)-[:ASSESSES]->(c2) "
            "CREATE (f4)-[:ASSESSES]->(c3) "
            "CREATE (d)-[:UPHELD]->(f1)",
        )

        actions = propose_actions(live_store, tmp_graph)

        # H3: Exactly ONE Action per run
        assert len(actions) == 1
        action = actions[0]
        assert isinstance(action, Action)
        assert action.kind == "flag_for_review"
        assert action.status == "PENDING"
        assert sorted(action.target_cids) == ["cust-batch-01", "cust-batch-02"]

        # Action node in graph
        nodes = live_store.query(
            tmp_graph,
            "MATCH (a:Action {id: $aid}) "
            "RETURN a.kind AS kind, a.status AS status, a.target_cids AS target_cids",
            {"aid": action.id},
        )
        assert len(nodes) == 1
        assert nodes[0]["kind"] == "flag_for_review"
        assert nodes[0]["status"] == "PENDING"
        assert sorted(nodes[0]["target_cids"]) == ["cust-batch-01", "cust-batch-02"]

        # H3: Action-[:BASED_ON]->every active suspicious Finding on the targets
        finding_links = live_store.query(
            tmp_graph,
            "MATCH (a:Action {id: $aid})-[:BASED_ON]->(f:Finding) "
            "RETURN f.id AS fid",
            {"aid": action.id},
        )
        linked_fids = {r["fid"] for r in finding_links}
        # f1, f2 (on c1) and f3 (on c2) must be linked.
        # f_old (superseded) must NOT be linked.
        # f4 (on uncorroborated c3) must NOT be linked.
        assert linked_fids == {"f-c1-1", "f-c1-2", "f-c2-1"}

        # H3: NEVER link Action to Decision
        dec_links = live_store.query(
            tmp_graph,
            "MATCH (a:Action {id: $aid})-[:BASED_ON]->(d:Decision) "
            "RETURN d.id AS did",
            {"aid": action.id},
        )
        assert len(dec_links) == 0

    finally:
        pass


@pytest.mark.integration
def test_propose_actions_empty_when_no_corroborated_targets(live_store, tmp_graph: str) -> None:
    """Verify propose_actions returns empty list when no targets meet corroboration."""
    try:
        live_store.query(
            tmp_graph,
            "CREATE (c:Customer {cid: 'cust-lone'}) "
            "CREATE (f:Finding {id: 'f-lone', target_cid: 'cust-lone', verdict: 'suspicious', skill_id: 's1', confidence: 0.60}) "
            "CREATE (f)-[:ASSESSES]->(c)",
        )
        actions = propose_actions(live_store, tmp_graph)
        assert actions == []
    finally:
        pass
