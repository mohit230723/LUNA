"""Tests for P1: Explain ('Why?') Engine verifying full provenance audit trails without LLM."""

import json
import pytest
from luna.orchestrator.explain import (
    explain_customer,
    explain_action,
    CustomerExplanation,
    ExplainResult,
    SkillChoiceView,
    DecisionView,
    FindingView,
)
from luna.atlas.assign import assign_skills_to_subtasks
from luna.planner.decompose import Subtask


@pytest.mark.integration
def test_explain_uncontested_customer_no_decision(live_store, tmp_graph: str) -> None:
    """Verify that an uncontested customer explanation has decision=None and valid provenance."""
    run_graph = f"{tmp_graph}_run"

    try:
        live_store.query(
            run_graph,
            "CREATE (c:Customer {cid: 'cust-uncontested-01'}) "
            "CREATE (ag:Agent {id: 'agent-alpha'}) "
            "CREATE (f:Finding {"
            "  id: 'find-uncontested-1', "
            "  target_cid: 'cust-uncontested-01', "
            "  skill_id: 'entity-linker', "
            "  verdict: 'suspicious', "
            "  confidence: 0.88, "
            "  status: 'active', "
            "  backend: 'rules', "
            "  reasoning: 'Shared bank account link', "
            "  evidence_cids: ['bank-99']"
            "}) "
            "CREATE (e:Entity {cid: 'bank-99', id: 'bank-99', type: 'BankAccount'}) "
            "CREATE (f)-[:ASSESSES]->(c) "
            "CREATE (f)-[:PROMOTED_FROM]->(ag) "
            "CREATE (f)-[:SUPPORTED_BY]->(e)",
        )

        explanation = explain_customer(live_store, run_graph, "cust-uncontested-01")
        assert isinstance(explanation, CustomerExplanation)
        assert explanation.target_cid == "cust-uncontested-01"
        assert explanation.final_verdict == "suspicious"
        assert explanation.decision is None  # Uncontested has no Decision
        assert len(explanation.findings) == 1
        f_view = explanation.findings[0]
        assert f_view.id == "find-uncontested-1"
        assert f_view.status == "active"
        assert f_view.backend == "rules"
        assert f_view.confidence == 0.88
        assert "cust-uncontested-01" in explanation.narrative
        assert "suspicious" in explanation.narrative
        assert "entity-linker" in explanation.narrative

    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_explain_contested_customer_with_decision(live_store, tmp_graph: str) -> None:
    """Verify that a contested customer explanation exposes DecisionView with snapshot components and superseded status."""
    run_graph = f"{tmp_graph}_run"

    comp_scores = {
        "suspicious": {"score": 0.82, "confidence": 0.90},
        "benign": {"score": 0.45, "confidence": 0.60},
    }
    weights = {"w_conf": 0.5, "w_evid": 0.2, "w_skill": 0.3}
    skill_scores = {"entity-linker": 0.70, "ring-detector": 0.80}

    try:
        live_store.query(
            run_graph,
            "CREATE (c:Customer {cid: 'cust-contested-01'}) "
            "CREATE (f_win:Finding {"
            "  id: 'find-win-01', "
            "  target_cid: 'cust-contested-01', "
            "  skill_id: 'entity-linker', "
            "  verdict: 'suspicious', "
            "  confidence: 0.90, "
            "  status: 'active', "
            "  backend: 'rules', "
            "  evidence_cids: ['phone-01']"
            "}) "
            "CREATE (f_lose:Finding {"
            "  id: 'find-lose-01', "
            "  target_cid: 'cust-contested-01', "
            "  skill_id: 'ring-detector', "
            "  verdict: 'benign', "
            "  confidence: 0.60, "
            "  status: 'superseded', "
            "  backend: 'rules', "
            "  evidence_cids: ['addr-01']"
            "}) "
            "CREATE (d:Decision {"
            "  id: 'dec-contested-01', "
            "  target_cid: 'cust-contested-01', "
            "  chosen_verdict: 'suspicious', "
            "  confidence: 0.90, "
            "  component_scores: $comp, "
            "  weights: $weights, "
            "  skill_scores_json: $skills, "
            "  winning_finding_id: 'find-win-01'"
            "}) "
            "CREATE (f_win)-[:ASSESSES]->(c) "
            "CREATE (f_lose)-[:ASSESSES]->(c) "
            "CREATE (d)-[:UPHELD]->(f_win) "
            "CREATE (d)-[:SUPERSEDES]->(f_lose) "
            "CREATE (d)-[:ABOUT]->(c)",
            {
                "comp": json.dumps(comp_scores),
                "weights": json.dumps(weights),
                "skills": json.dumps(skill_scores),
            },
        )

        explanation = explain_customer(live_store, run_graph, "cust-contested-01")
        assert explanation.final_verdict == "suspicious"
        assert explanation.decision is not None
        d_view = explanation.decision
        assert isinstance(d_view, DecisionView)
        assert d_view.id == "dec-contested-01"
        assert d_view.upheld_finding_id == "find-win-01"
        assert "find-lose-01" in d_view.superseded_finding_ids
        assert d_view.components == comp_scores
        assert d_view.weights == weights
        assert d_view.skill_scores == skill_scores

        # Findings include both active and superseded
        f_ids = {f.id for f in explanation.findings}
        assert f_ids == {"find-win-01", "find-lose-01"}
        statuses = {f.id: f.status for f in explanation.findings}
        assert statuses["find-win-01"] == "active"
        assert statuses["find-lose-01"] == "superseded"

        # Narrative explains arbitration
        assert "arbitrated" in explanation.narrative.lower() or "upheld" in explanation.narrative.lower()

    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_explain_action_batch_customers(live_store, tmp_graph: str) -> None:
    """Verify explain_action traces Action -> Finding -> Entity for batch target customers."""
    run_graph = f"{tmp_graph}_run"

    try:
        live_store.query(
            run_graph,
            "CREATE (c1:Customer {cid: 'cust-batch-A'}) "
            "CREATE (c2:Customer {cid: 'cust-batch-B'}) "
            "CREATE (f1:Finding {id: 'f-b-1', target_cid: 'cust-batch-A', verdict: 'suspicious', confidence: 0.85, status: 'active', backend: 'rules'}) "
            "CREATE (f2:Finding {id: 'f-b-2', target_cid: 'cust-batch-B', verdict: 'suspicious', confidence: 0.90, status: 'active', backend: 'rules'}) "
            "CREATE (a:Action {id: 'act-batch-test', kind: 'flag_for_review', status: 'PENDING', target_cids: ['cust-batch-A', 'cust-batch-B']}) "
            "CREATE (f1)-[:ASSESSES]->(c1) "
            "CREATE (f2)-[:ASSESSES]->(c2) "
            "CREATE (a)-[:BASED_ON]->(f1) "
            "CREATE (a)-[:BASED_ON]->(f2)",
        )

        result = explain_action(live_store, run_graph, "act-batch-test")
        assert isinstance(result, ExplainResult)
        assert result.action_id == "act-batch-test"
        assert len(result.customers) == 2
        cids = {c.target_cid for c in result.customers}
        assert cids == {"cust-batch-A", "cust-batch-B"}

        # Check graph path structure
        gp = result.graph_path
        assert "nodes" in gp and "edges" in gp
        node_ids = {n["id"] for n in gp["nodes"]}
        assert "act-batch-test" in node_ids
        assert "f-b-1" in node_ids
        assert "f-b-2" in node_ids

        # Verify JSON serializability
        serialized = json.dumps(result.model_dump())
        assert len(serialized) > 0

    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_skill_assignment_persisted_and_explained(live_store, tmp_graph: str) -> None:
    """Verify that skill assignment decisions are persisted into run memory with rejected edges and explained."""
    run_graph = f"{tmp_graph}_run"
    atlas_graph = f"{tmp_graph}_atlas"

    try:
        # Seed atlas with eligible and restricted skills
        live_store.query(
            atlas_graph,
            "CREATE (s1:Skill {id: 'entity-linker', name: 'Entity Linker', restricted: false}) "
            "CREATE (s2:Skill {id: 'bulk-linker', name: 'Bulk Linker', restricted: true}) "
            "CREATE (s3:Skill {id: 'entity-linker-lite', name: 'Lite Linker', restricted: false}) "
            "CREATE (c:Capability {name: 'link_entities'}) "
            "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
            "CREATE (s1)-[:PROVIDES]->(c) "
            "CREATE (s2)-[:PROVIDES]->(c) "
            "CREATE (s3)-[:PROVIDES]->(c) "
            "CREATE (s1)-[:SUCCEEDED_ON {score: 0.85, runs: 10}]->(t) "
            "CREATE (s3)-[:SUCCEEDED_ON {score: 0.60, runs: 5}]->(t)",
        )

        subtask = Subtask(id="sub-01", capability="link_entities", description="Link entities by phone")

        # Run skill assignment with run_graph_name to persist Decision nodes
        assignments = assign_skills_to_subtasks(
            live_store,
            subtasks=[subtask],
            task_type="fraud_ring_investigation",
            run_graph_name=run_graph,
            atlas_graph=atlas_graph,
        )

        assert len(assignments) == 1
        assert assignments[0].chosen_skill.id == "entity-linker"

        # Check that Decision kind='skill_assignment' was persisted in run_graph
        dec_nodes = live_store.query(
            run_graph,
            "MATCH (d:Decision {kind: 'skill_assignment'})-[:FOR]->(sub:Subtask {id: 'sub-01'}) "
            "MATCH (d)-[:CHOSE]->(chosen:SkillRef) "
            "RETURN d.id AS did, chosen.id AS chosen_id",
        )
        assert len(dec_nodes) == 1
        assert dec_nodes[0]["chosen_id"] == "entity-linker"

        # Check rejected edges
        rej_nodes = live_store.query(
            run_graph,
            "MATCH (d:Decision {kind: 'skill_assignment'})-[r:REJECTED]->(rej:SkillRef) "
            "RETURN rej.id AS rej_id, r.reason AS reason",
        )
        assert len(rej_nodes) >= 2
        rej_map = {r["rej_id"]: r["reason"] for r in rej_nodes}
        assert "bulk-linker" in rej_map
        assert "Policy restriction" in rej_map["bulk-linker"]
        assert "entity-linker-lite" in rej_map
        assert "Lower historical track record" in rej_map["entity-linker-lite"]

    finally:
        live_store.delete_graph(run_graph)
        live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_explain_output_unchanged_after_atlas_update(live_store, tmp_graph: str) -> None:
    """Verify explain output is purely from Decision snapshots and unchanged when atlas changes later."""
    run_graph = f"{tmp_graph}_run"
    atlas_graph = f"{tmp_graph}_atlas"

    try:
        # Initial atlas score
        live_store.query(
            atlas_graph,
            "CREATE (s:Skill {id: 'entity-linker'}) "
            "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
            "CREATE (s)-[:SUCCEEDED_ON {score: 0.70, runs: 1}]->(t)",
        )

        # Decision with snapshot score 0.70
        live_store.query(
            run_graph,
            "CREATE (c:Customer {cid: 'cust-snapshot'}) "
            "CREATE (f:Finding {id: 'f-snap', target_cid: 'cust-snapshot', skill_id: 'entity-linker', verdict: 'suspicious', confidence: 0.85}) "
            "CREATE (d:Decision {"
            "  id: 'dec-snap', "
            "  target_cid: 'cust-snapshot', "
            "  chosen_verdict: 'suspicious', "
            "  confidence: 0.85, "
            "  component_scores: '{\"suspicious\": {\"score\": 0.82}}', "
            "  weights: '{\"w_conf\": 0.5, \"w_evid\": 0.2, \"w_skill\": 0.3}', "
            "  skill_scores_json: '{\"entity-linker\": 0.70}', "
            "  winning_finding_id: 'f-snap'"
            "}) "
            "CREATE (f)-[:ASSESSES]->(c) "
            "CREATE (d)-[:UPHELD]->(f) "
            "CREATE (d)-[:ABOUT]->(c)",
        )

        exp1 = explain_customer(live_store, run_graph, "cust-snapshot")
        assert exp1.decision.skill_scores["entity-linker"] == 0.70

        # Now alter atlas score drastically to 0.99
        live_store.query(
            atlas_graph,
            "MATCH (:Skill {id: 'entity-linker'})-[r:SUCCEEDED_ON]->() SET r.score = 0.99",
        )

        exp2 = explain_customer(live_store, run_graph, "cust-snapshot")
        assert exp2.decision.skill_scores["entity-linker"] == 0.70
        assert exp1.narrative == exp2.narrative

    finally:
        live_store.delete_graph(run_graph)
        live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_explain_unknown_action_raises_clear_error(live_store, tmp_graph: str) -> None:
    """Verify explaining an unknown action ID raises a clear ValueError."""
    with pytest.raises(ValueError, match="not found"):
        explain_action(live_store, tmp_graph, "act-non-existent")
