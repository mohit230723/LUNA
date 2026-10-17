"""Tests for H7: Comprehensive verification suite covering all Phase 3 hardening requirements."""

import pytest
from luna.domain.seed import seed_domain, GroundTruth
from luna.atlas.seed import seed_atlas
from luna.orchestrator.conflicts import detect_contradictions
from luna.orchestrator.resolve import resolve_conflicts
from luna.orchestrator.actions import (
    propose_actions,
    approve_action,
    execute_action,
    evaluate_outcomes,
    NotApprovedError,
)
from luna.atlas.learner import learn_from_run


@pytest.mark.integration
def test_benign_wins_results_in_no_action_flag(live_store, tmp_graph: str) -> None:
    """Verify that when conflict resolution resolves in favor of benign, the customer is NOT flagged."""
    run_graph = f"{tmp_graph}_run"
    atlas_graph = f"{tmp_graph}_atlas"

    try:
        # Atlas: ring-detector has high score 0.85, entity-linker has 0.60
        live_store.query(
            atlas_graph,
            "CREATE (s1:Skill {id: 'entity-linker'}) "
            "CREATE (s2:Skill {id: 'ring-detector'}) "
            "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
            "CREATE (s1)-[:SUCCEEDED_ON {score: 0.60, runs: 5}]->(t) "
            "CREATE (s2)-[:SUCCEEDED_ON {score: 0.85, runs: 5}]->(t)",
        )

        # Customer with 1 weak suspicious finding and 1 strong benign finding
        live_store.query(
            run_graph,
            "CREATE (c:Customer {cid: 'cust-cleared-01'}) "
            "CREATE (f_sus:Finding {id: 'f-sus', target_cid: 'cust-cleared-01', skill_id: 'entity-linker', verdict: 'suspicious', confidence: 0.60, evidence_cids: ['p1']}) "
            "CREATE (f_ben:Finding {id: 'f-ben', target_cid: 'cust-cleared-01', skill_id: 'ring-detector', verdict: 'benign', confidence: 0.90, evidence_cids: ['a1', 'c2']}) "
            "CREATE (f_sus)-[:ASSESSES]->(c) "
            "CREATE (f_ben)-[:ASSESSES]->(c) "
            "CREATE (f_sus)-[:CONFLICTS_WITH]->(f_ben)",
        )

        # Resolve conflicts: benign must win
        decisions = resolve_conflicts(live_store, run_graph, atlas_graph_name=atlas_graph)
        assert len(decisions) == 1
        assert decisions[0].chosen_verdict == "benign"

        # Propose actions: customer MUST NOT be targeted
        actions = propose_actions(live_store, run_graph)
        assert actions == []

    finally:
        live_store.delete_graph(run_graph)
        live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_demo_profile_flagged_set_equals_ring_members(live_store, tmp_graph: str) -> None:
    """Verify that end-to-end pipeline on demo profile flags ring members accurately."""
    domain_graph = f"{tmp_graph}_dom"
    run_graph = f"{tmp_graph}_run"
    atlas_graph = f"{tmp_graph}_atlas"

    # Seed isolated domain and atlas
    seed_atlas(live_store, atlas_graph=atlas_graph)
    gt = seed_domain(live_store, domain_graph=domain_graph, seed=42)

    ring_cids = sorted(list(gt.ring_cids))
    decoy_cids = sorted(list(gt.decoy_cids))

    try:
        # Seed run memory with findings:
        # All ring members receive 2 distinct skill findings at 0.70 (corroborated)
        for i, r_cid in enumerate(ring_cids):
            live_store.query(
                run_graph,
                f"CREATE (c:Customer {{cid: '{r_cid}'}}) "
                f"CREATE (f1:Finding {{id: 'f-r-{i}-1', target_cid: '{r_cid}', skill_id: 'entity-linker', verdict: 'suspicious', confidence: 0.75, evidence_cids: ['bank-01']}}) "
                f"CREATE (f2:Finding {{id: 'f-r-{i}-2', target_cid: '{r_cid}', skill_id: 'ring-detector', verdict: 'suspicious', confidence: 0.75, evidence_cids: ['phone-01']}}) "
                f"CREATE (f1)-[:ASSESSES]->(c) "
                f"CREATE (f2)-[:ASSESSES]->(c)",
            )

        # Decoy members receive conflicting findings (suspicious vs benign)
        for i, d_cid in enumerate(decoy_cids):
            live_store.query(
                run_graph,
                f"CREATE (c:Customer {{cid: '{d_cid}'}}) "
                f"CREATE (f_sus:Finding {{id: 'f-d-{i}-sus', target_cid: '{d_cid}', skill_id: 'entity-linker', verdict: 'suspicious', confidence: 0.60, evidence_cids: ['addr-01']}}) "
                f"CREATE (f_ben:Finding {{id: 'f-d-{i}-ben', target_cid: '{d_cid}', skill_id: 'ring-detector', verdict: 'benign', confidence: 0.90, evidence_cids: ['addr-01', 'cust-fam']}}) "
                f"CREATE (f_sus)-[:ASSESSES]->(c) "
                f"CREATE (f_ben)-[:ASSESSES]->(c) "
                f"CREATE (f_sus)-[:CONFLICTS_WITH]->(f_ben)",
            )

        # 1. Detect conflicts & Resolve
        detect_contradictions(live_store, run_graph)
        decisions = resolve_conflicts(live_store, run_graph, atlas_graph_name=atlas_graph)
        assert len(decisions) == len(decoy_cids)
        for d in decisions:
            assert d.chosen_verdict == "benign"

        # 2. Propose actions
        actions = propose_actions(live_store, run_graph)
        assert len(actions) == 1
        action = actions[0]
        assert action.kind == "flag_for_review"
        assert sorted(action.target_cids) == ring_cids

        # 3. Execution barrier: unapproved raises NotApprovedError
        with pytest.raises(NotApprovedError):
            execute_action(live_store, run_graph, domain_graph, action.id)

        # 4. Approve and execute
        approve_action(live_store, run_graph, action.id, approver="auto")
        outcome = execute_action(live_store, run_graph, domain_graph, action.id, run_id="demo_run_1")
        assert outcome.success is True

        # 5. Verify domain flagged customers strictly equals ring members
        flagged_nodes = live_store.query(
            domain_graph,
            "MATCH (c:Customer {flagged: true}) RETURN c.cid AS cid",
        )
        flagged_cids = sorted([r["cid"] for r in flagged_nodes])
        assert flagged_cids == ring_cids

        # 6. Evaluate metrics: Precision = 1.0, Recall = 1.0, F1 = 1.0
        metrics = evaluate_outcomes(live_store, domain_graph, gt, run_id="demo_run_1", run_graph_name=run_graph)
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    finally:
        live_store.delete_graph(domain_graph)
        live_store.delete_graph(run_graph)
        live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_learner_updates_winner_and_loser_reputation(live_store, tmp_graph: str) -> None:
    """Verify that cross-run learner elevates winning skill and degrades losing skill."""
    run_graph = f"{tmp_graph}_run"
    atlas_graph = f"{tmp_graph}_atlas"

    gt = GroundTruth(ring_cids={"cust-ring-alpha"})

    try:
        live_store.query(
            atlas_graph,
            "CREATE (s1:Skill {id: 'skill-alpha'}) "
            "CREATE (s2:Skill {id: 'skill-beta'}) "
            "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
            "CREATE (s1)-[:SUCCEEDED_ON {score: 0.70, runs: 1}]->(t) "
            "CREATE (s2)-[:SUCCEEDED_ON {score: 0.70, runs: 1}]->(t)",
        )

        live_store.query(
            run_graph,
            "CREATE (a:Action {id: 'act-1', status: 'EXECUTED'}) "
            "CREATE (o:Outcome {id: 'out-1', action_id: 'act-1', success: true, learned: false}) "
            "CREATE (a)-[:RESULTED_IN]->(o) "
            "CREATE (c:Customer {cid: 'cust-ring-alpha'}) "
            "CREATE (f1:Finding {id: 'f1', target_cid: 'cust-ring-alpha', skill_id: 'skill-alpha', verdict: 'suspicious'}) "
            "CREATE (f2:Finding {id: 'f2', target_cid: 'cust-ring-alpha', skill_id: 'skill-beta', verdict: 'benign', status: 'superseded'}) "
            "CREATE (f1)-[:ASSESSES]->(c) "
            "CREATE (f2)-[:ASSESSES]->(c)",
        )

        updates = learn_from_run(live_store, run_graph, gt, atlas_graph=atlas_graph, alpha=0.2)
        upd_map = {u["skill_id"]: u for u in updates}

        # Winner (skill-alpha): reward = 1.0 -> 0.8 * 0.70 + 0.2 * 1.0 = 0.56 + 0.20 = 0.76
        assert round(upd_map["skill-alpha"]["new_score"], 2) == 0.76

        # Loser (skill-beta): reward = 0.0 -> 0.8 * 0.70 + 0.2 * 0.0 = 0.56
        assert round(upd_map["skill-beta"]["new_score"], 2) == 0.56

    finally:
        live_store.delete_graph(run_graph)
        live_store.delete_graph(atlas_graph)
