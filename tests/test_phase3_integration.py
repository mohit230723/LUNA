"""End-to-end integration test verifying the complete Phase 3 pipeline on live FalkorDB.

Pipeline flow:
1. Seed atlas skill catalog and synthetic domain graph with ground truth.
2. Simulate promoted findings in run memory containing:
   - True positive suspicious finding on fraud ring member (cust-000).
   - Conflicting findings on decoy customer (cust-010):
     * Suspicious finding by entity-linker (confidence 0.62).
     * Benign finding by community-analyzer (confidence 0.85).
3. Contradiction Detection Engine:
   - Detects opposing verdicts on decoy customer and links with [:CONFLICTS_WITH].
4. Main-Agent Conflict Resolution:
   - Evaluates weighted evidence, upholds benign finding, and marks suspicious finding 'superseded'.
   - Verifies explainability contract: zero deletions (all findings preserved).
5. Action Proposal:
   - Proposes PENDING FLAG_CUSTOMER action for ring member; zero actions for cleared decoy.
6. Human Approval Barrier:
   - Unapproved execution strictly rejected with PermissionError.
   - Headless demo / analyst approval transitions status to APPROVED.
7. Domain Execution & Outcome Evaluation:
   - Mutates domain graph customer (flagged=True).
   - Records Outcome node with [:RESULTED_IN] edge in run graph.
   - Evaluates precision, recall, and F1 metrics against GroundTruth.
8. Cross-Run Learner:
   - Inspects decisions and updates SUCCEEDED_ON scores in atlas via EMA (alpha=0.2).
"""

import pytest
from luna.atlas.seed import seed_atlas
from luna.domain.seed import seed_domain, GroundTruth
from luna.orchestrator.conflicts import detect_contradictions, Contradiction
from luna.orchestrator.resolve import resolve_conflicts, Decision
from luna.orchestrator.actions import (
    Action,
    Outcome,
    EvaluationMetrics,
    propose_actions,
    approve_action,
    execute_action,
    evaluate_outcomes,
)
from luna.atlas.learner import learn_from_run
from luna.graph.schema import (
    GRAPH_ATLAS,
    GRAPH_DOMAIN,
    LABEL_CUSTOMER,
    LABEL_FINDING,
    LABEL_ACTION,
    LABEL_OUTCOME,
    REL_CONFLICTS_WITH,
    REL_UPHELD,
    REL_SUPERSEDES,
    REL_RESULTED_IN,
)


@pytest.mark.integration
def test_complete_phase3_end_to_end_pipeline(live_store, tmp_graph: str) -> None:
    """Execute complete Phase 3 Conflict Resolution, Action Execution, and Learning pipeline."""
    # 1. Seed atlas and domain graphs
    seed_atlas(live_store)
    gt = seed_domain(live_store, seed=42)

    ring_cids = sorted(list(gt.ring_cids))
    decoy_cids = sorted(list(gt.decoy_cids))
    target_ring_cid = ring_cids[0]
    target_decoy_cid = decoy_cids[0]

    run_graph = f"{tmp_graph}_run"

    try:
        # 2. Seed run memory with findings from multi-agent exploration
        # A: True positive finding on ring member
        live_store.query(
            run_graph,
            "CREATE (c:Customer {cid: $cid}) "
            "CREATE (f:Finding {"
            "  id: 'find-ring-tp', "
            "  skill_id: 'entity-linker', "
            "  target_cid: $cid, "
            "  verdict: 'suspicious', "
            "  confidence: 0.92, "
            "  reasoning: 'Shared bank account with verified syndicate member', "
            "  evidence_cids: ['bank-01']"
            "}) "
            "CREATE (f)-[:ASSESSES]->(c)",
            {"cid": target_ring_cid},
        )

        # B: Conflicting findings on decoy customer (entity-linker false alarm vs ring-detector benign)
        live_store.query(
            run_graph,
            "CREATE (c:Customer {cid: $cid}) "
            "CREATE (f1:Finding {"
            "  id: 'find-decoy-sus', "
            "  skill_id: 'entity-linker', "
            "  target_cid: $cid, "
            "  verdict: 'suspicious', "
            "  confidence: 0.62, "
            "  reasoning: 'Shares residential address attribute', "
            "  evidence_cids: ['addr-01']"
            "}) "
            "CREATE (f2:Finding {"
            "  id: 'find-decoy-benign', "
            "  skill_id: 'ring-detector', "
            "  target_cid: $cid, "
            "  verdict: 'benign', "
            "  confidence: 0.85, "
            "  reasoning: 'Legitimate family household cluster with clean transaction history', "
            "  evidence_cids: ['addr-01', 'cust-011']"
            "}) "
            "CREATE (f1)-[:ASSESSES]->(c) "
            "CREATE (f2)-[:ASSESSES]->(c)",
            {"cid": target_decoy_cid},
        )

        # Verify initial state: 3 findings in run graph
        initial_f_cnt = live_store.query(run_graph, "MATCH (f:Finding) RETURN count(f) AS cnt")
        assert initial_f_cnt[0]["cnt"] == 3

        # 3. Step 1: Detect Contradictions (REQ-13)
        conflicts = detect_contradictions(live_store, run_graph)
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert isinstance(conflict, Contradiction)
        assert conflict.target_cid == target_decoy_cid
        assert {conflict.verdict1, conflict.verdict2} == {"suspicious", "benign"}

        # Verify graph edge
        conflict_edges = live_store.query(
            run_graph,
            "MATCH (f1:Finding {id: 'find-decoy-sus'})-[r:CONFLICTS_WITH]-(f2:Finding {id: 'find-decoy-benign'}) "
            "RETURN r.detected_at AS detected_at",
        )
        assert len(conflict_edges) == 1
        assert conflict_edges[0]["detected_at"] is not None

        # 4. Step 2: Main-Agent Conflict Resolution (REQ-14)
        decisions = resolve_conflicts(live_store, run_graph, atlas_graph_name=GRAPH_ATLAS)
        assert len(decisions) == 1
        decision = decisions[0]
        assert isinstance(decision, Decision)
        assert decision.target_cid == target_decoy_cid
        assert decision.chosen_verdict == "benign"
        assert decision.winning_finding_id == "find-decoy-benign"
        assert decision.superseded_finding_ids == ["find-decoy-sus"]

        # Verify explainability invariant: ZERO findings deleted
        f_cnt_after = live_store.query(run_graph, "MATCH (f:Finding) RETURN count(f) AS cnt")
        assert f_cnt_after[0]["cnt"] == 3

        # Verify loser finding marked superseded
        loser_status = live_store.query(
            run_graph,
            "MATCH (f:Finding {id: 'find-decoy-sus'}) RETURN f.status AS status",
        )
        assert loser_status[0]["status"] == "superseded"

        # 5. Step 3: Action Proposal (REQ-15)
        actions = propose_actions(live_store, run_graph)
        assert len(actions) == 1
        action = actions[0]
        assert isinstance(action, Action)
        assert action.target_cid == target_ring_cid
        assert action.action_type == "FLAG_CUSTOMER"
        assert action.status == "PENDING"
        assert action.recommended_by_id is None or action.recommended_by_id == "find-ring-tp"

        # 6. Step 4: Human Approval Barrier (REQ-15)
        # Attempt execution before approval MUST raise PermissionError
        with pytest.raises(PermissionError, match="requires 'APPROVED'"):
            execute_action(live_store, run_graph, GRAPH_DOMAIN, action.id)

        # Transition action via approval gate
        approved_act = approve_action(live_store, run_graph, action.id, approver="auto")
        assert approved_act.status == "APPROVED"
        assert approved_act.approver == "auto"
        assert approved_act.approved_at is not None

        # 7. Step 5: Domain Execution & Outcome Evaluation (REQ-15)
        outcome = execute_action(live_store, run_graph, GRAPH_DOMAIN, action.id)
        assert isinstance(outcome, Outcome)
        assert outcome.success is True
        assert outcome.target_cid == target_ring_cid

        # Check domain graph mutation
        domain_cust = live_store.query(
            GRAPH_DOMAIN,
            "MATCH (c:Customer {cid: $cid}) RETURN c.flagged AS flagged, c.flagged_at AS flagged_at",
            {"cid": target_ring_cid},
        )
        assert len(domain_cust) == 1
        assert domain_cust[0]["flagged"] is True
        assert domain_cust[0]["flagged_at"] is not None

        # Verify Outcome node and RESULTED_IN edge
        out_edges = live_store.query(
            run_graph,
            "MATCH (a:Action {id: $aid})-[:RESULTED_IN]->(o:Outcome) RETURN a.status AS a_status, o.success AS success",
            {"aid": action.id},
        )
        assert len(out_edges) == 1
        assert out_edges[0]["a_status"] == "EXECUTED"
        assert out_edges[0]["success"] is True

        # Evaluate performance against GroundTruth
        metrics = evaluate_outcomes(live_store, GRAPH_DOMAIN, gt)
        assert isinstance(metrics, EvaluationMetrics)
        assert metrics.true_positives == 1
        assert metrics.false_positives == 0
        assert metrics.precision == 1.0

        # 8. Step 6: Cross-Run Learner in Atlas (REQ-16)
        # Check initial scores in atlas
        linker_before = live_store.query(
            GRAPH_ATLAS,
            "MATCH (s:Skill {id: 'entity-linker'})-[r:SUCCEEDED_ON]->(:TaskType {name: 'fraud_ring_investigation'}) "
            "RETURN r.score AS score, r.runs AS runs",
        )
        assert len(linker_before) == 1
        initial_linker_runs = int(linker_before[0]["runs"])

        detector_before = live_store.query(
            GRAPH_ATLAS,
            "MATCH (s:Skill {id: 'ring-detector'})-[r:SUCCEEDED_ON]->(:TaskType {name: 'fraud_ring_investigation'}) "
            "RETURN r.score AS score, r.runs AS runs",
        )
        assert len(detector_before) == 1
        initial_detector_runs = int(detector_before[0]["runs"])

        # Learn from run
        learning_updates = learn_from_run(
            live_store,
            run_graph_name=run_graph,
            ground_truth=gt,
            atlas_graph=GRAPH_ATLAS,
            alpha=0.2,
        )
        assert len(learning_updates) == 2

        # Verify atlas edge updated for entity-linker
        linker_after = live_store.query(
            GRAPH_ATLAS,
            "MATCH (s:Skill {id: 'entity-linker'})-[r:SUCCEEDED_ON]->(:TaskType {name: 'fraud_ring_investigation'}) "
            "RETURN r.score AS score, r.runs AS runs, r.last_updated AS last_updated",
        )
        assert len(linker_after) == 1
        assert int(linker_after[0]["runs"]) == initial_linker_runs + 1
        assert linker_after[0]["last_updated"] is not None

        # Verify atlas edge updated for ring-detector
        detector_after = live_store.query(
            GRAPH_ATLAS,
            "MATCH (s:Skill {id: 'ring-detector'})-[r:SUCCEEDED_ON]->(:TaskType {name: 'fraud_ring_investigation'}) "
            "RETURN r.score AS score, r.runs AS runs, r.last_updated AS last_updated",
        )
        assert len(detector_after) == 1
        assert int(detector_after[0]["runs"]) == initial_detector_runs + 1
        assert detector_after[0]["last_updated"] is not None

    finally:
        live_store.delete_graph(run_graph)
