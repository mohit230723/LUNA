"""Tests for H2: Per-customer side resolution with conservative tie-break and ABOUT edge."""

import json
import pytest
from luna.orchestrator.resolve import (
    W_CONF,
    W_EVID,
    W_SKILL,
    resolve_conflicts,
    Decision,
)


@pytest.mark.integration
def test_side_resolution_and_about_edge(live_store, tmp_graph: str) -> None:
    """Verify per-customer side resolution scores sides, links ABOUT edge, and stores snapshot fields."""
    run_graph = f"{tmp_graph}_run"
    atlas_graph = f"{tmp_graph}_atlas"

    try:
        # Seed atlas with skill scores
        live_store.query(
            atlas_graph,
            "CREATE (s1:Skill {id: 'entity-linker'}) "
            "CREATE (s2:Skill {id: 'ring-detector'}) "
            "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
            "CREATE (s1)-[:SUCCEEDED_ON {score: 0.70, runs: 5}]->(t) "
            "CREATE (s2)-[:SUCCEEDED_ON {score: 0.80, runs: 5}]->(t)",
        )

        # Customer with 1 suspicious finding (linker) and 1 benign finding (ring-detector)
        # S_sus = 0.5 * 0.60 + 0.2 * (1/5) + 0.3 * 0.70 = 0.30 + 0.04 + 0.21 = 0.55
        # S_ben = 0.5 * 0.85 + 0.2 * (2/5) + 0.3 * 0.80 = 0.425 + 0.08 + 0.24 = 0.745
        # Benign should win decisively
        live_store.query(
            run_graph,
            "CREATE (c:Customer {cid: 'cust-decoy-01'}) "
            "CREATE (f1:Finding {"
            "  id: 'find-sus-1', "
            "  target_cid: 'cust-decoy-01', "
            "  skill_id: 'entity-linker', "
            "  verdict: 'suspicious', "
            "  confidence: 0.60, "
            "  evidence_cids: ['phone-01']"
            "}) "
            "CREATE (f2:Finding {"
            "  id: 'find-ben-1', "
            "  target_cid: 'cust-decoy-01', "
            "  skill_id: 'ring-detector', "
            "  verdict: 'benign', "
            "  confidence: 0.85, "
            "  evidence_cids: ['addr-01', 'cust-02']"
            "}) "
            "CREATE (f1)-[:ASSESSES]->(c) "
            "CREATE (f2)-[:ASSESSES]->(c) "
            "CREATE (f1)-[:CONFLICTS_WITH]->(f2)",
        )

        decisions = resolve_conflicts(
            live_store,
            run_graph_name=run_graph,
            atlas_graph_name=atlas_graph,
            task_type="fraud_ring_investigation",
        )

        assert len(decisions) == 1
        d = decisions[0]
        assert d.target_cid == "cust-decoy-01"
        assert d.chosen_verdict == "benign"
        assert d.winning_finding_id == "find-ben-1"
        assert d.superseded_finding_ids == ["find-sus-1"]

        # Check properties on Decision node in graph
        dec_nodes = live_store.query(
            run_graph,
            "MATCH (d:Decision {id: $did}) "
            "RETURN d.backend AS backend, d.skill_scores_json AS skill_scores_json, "
            "       d.component_scores AS component_scores, d.weights AS weights",
            {"did": d.id},
        )
        assert len(dec_nodes) == 1
        assert dec_nodes[0]["backend"] == "rule"
        assert dec_nodes[0]["skill_scores_json"] is not None
        skill_scores = json.loads(dec_nodes[0]["skill_scores_json"])
        assert "entity-linker" in skill_scores
        assert "ring-detector" in skill_scores

        # Check ABOUT edge: Decision -[:ABOUT]-> Customer
        about_edges = live_store.query(
            run_graph,
            "MATCH (d:Decision {id: $did})-[:ABOUT]->(c:Customer {cid: 'cust-decoy-01'}) "
            "RETURN count(c) AS cnt",
            {"did": d.id},
        )
        assert about_edges[0]["cnt"] == 1

        # Check UPHELD edge to winning finding
        upheld_edges = live_store.query(
            run_graph,
            "MATCH (d:Decision {id: $did})-[:UPHELD]->(f:Finding {id: 'find-ben-1'}) "
            "RETURN count(f) AS cnt",
            {"did": d.id},
        )
        assert upheld_edges[0]["cnt"] == 1

        # Check SUPERSEDES edge to losing finding and status is superseded
        superseded_nodes = live_store.query(
            run_graph,
            "MATCH (d:Decision {id: $did})-[:SUPERSEDES]->(f:Finding {id: 'find-sus-1'}) "
            "RETURN f.status AS status",
            {"did": d.id},
        )
        assert len(superseded_nodes) == 1
        assert superseded_nodes[0]["status"] == "superseded"

    finally:
        live_store.delete_graph(run_graph)
        live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_three_findings_two_suspicious_one_benign(live_store, tmp_graph: str) -> None:
    """Verify that when a side wins, ALL losing findings become superseded while winning findings stay active."""
    run_graph = f"{tmp_graph}_run"
    atlas_graph = f"{tmp_graph}_atlas"

    try:
        live_store.query(
            atlas_graph,
            "CREATE (s1:Skill {id: 'entity-linker'}) "
            "CREATE (s2:Skill {id: 'ring-detector'}) "
            "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
            "CREATE (s1)-[:SUCCEEDED_ON {score: 0.90, runs: 10}]->(t) "
            "CREATE (s2)-[:SUCCEEDED_ON {score: 0.50, runs: 2}]->(t)",
        )

        # 2 suspicious findings (one high conf, one moderate) + 1 weak benign finding
        live_store.query(
            run_graph,
            "CREATE (c:Customer {cid: 'cust-ring-member'}) "
            "CREATE (f_sus1:Finding {"
            "  id: 'f-sus-high', "
            "  target_cid: 'cust-ring-member', "
            "  skill_id: 'entity-linker', "
            "  verdict: 'suspicious', "
            "  confidence: 0.95, "
            "  evidence_cids: ['bank-01', 'cust-02', 'phone-01']"
            "}) "
            "CREATE (f_sus2:Finding {"
            "  id: 'f-sus-mod', "
            "  target_cid: 'cust-ring-member', "
            "  skill_id: 'entity-linker', "
            "  verdict: 'suspicious', "
            "  confidence: 0.80, "
            "  evidence_cids: ['addr-01']"
            "}) "
            "CREATE (f_ben:Finding {"
            "  id: 'f-ben-weak', "
            "  target_cid: 'cust-ring-member', "
            "  skill_id: 'ring-detector', "
            "  verdict: 'benign', "
            "  confidence: 0.60, "
            "  evidence_cids: []"
            "}) "
            "CREATE (f_sus1)-[:ASSESSES]->(c) "
            "CREATE (f_sus2)-[:ASSESSES]->(c) "
            "CREATE (f_ben)-[:ASSESSES]->(c) "
            "CREATE (f_sus1)-[:CONFLICTS_WITH]->(f_ben)",
        )

        decisions = resolve_conflicts(
            live_store,
            run_graph_name=run_graph,
            atlas_graph_name=atlas_graph,
        )

        assert len(decisions) == 1
        d = decisions[0]
        assert d.chosen_verdict == "suspicious"
        assert d.winning_finding_id == "f-sus-high"
        assert d.superseded_finding_ids == ["f-ben-weak"]

        # Winning side findings: both should remain active (status IS NULL or <> 'superseded')
        win_findings = live_store.query(
            run_graph,
            "MATCH (f:Finding) WHERE f.id IN ['f-sus-high', 'f-sus-mod'] "
            "RETURN f.id AS id, f.status AS status",
        )
        assert len(win_findings) == 2
        for wf in win_findings:
            assert wf["status"] != "superseded"

        # Losing side finding: MUST be superseded
        lose_finding = live_store.query(
            run_graph,
            "MATCH (f:Finding {id: 'f-ben-weak'}) RETURN f.status AS status",
        )
        assert lose_finding[0]["status"] == "superseded"

    finally:
        live_store.delete_graph(run_graph)
        live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_tie_break_conservative_benign_wins(live_store, tmp_graph: str) -> None:
    """Verify that in the event of an exact score tie, benign wins conservatively."""
    run_graph = f"{tmp_graph}_run"
    atlas_graph = f"{tmp_graph}_atlas"

    try:
        # Both skills have identical score 0.70
        live_store.query(
            atlas_graph,
            "CREATE (s1:Skill {id: 'skill-sus'}) "
            "CREATE (s2:Skill {id: 'skill-ben'}) "
            "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
            "CREATE (s1)-[:SUCCEEDED_ON {score: 0.70, runs: 5}]->(t) "
            "CREATE (s2)-[:SUCCEEDED_ON {score: 0.70, runs: 5}]->(t)",
        )

        # Identical confidence 0.80 and identical evidence count (2 each)
        live_store.query(
            run_graph,
            "CREATE (c:Customer {cid: 'cust-tie'}) "
            "CREATE (f1:Finding {"
            "  id: 'f-tie-sus', "
            "  target_cid: 'cust-tie', "
            "  skill_id: 'skill-sus', "
            "  verdict: 'suspicious', "
            "  confidence: 0.80, "
            "  evidence_cids: ['e1', 'e2']"
            "}) "
            "CREATE (f2:Finding {"
            "  id: 'f-tie-ben', "
            "  target_cid: 'cust-tie', "
            "  skill_id: 'skill-ben', "
            "  verdict: 'benign', "
            "  confidence: 0.80, "
            "  evidence_cids: ['e3', 'e4']"
            "}) "
            "CREATE (f1)-[:ASSESSES]->(c) "
            "CREATE (f2)-[:ASSESSES]->(c) "
            "CREATE (f1)-[:CONFLICTS_WITH]->(f2)",
        )

        decisions = resolve_conflicts(
            live_store,
            run_graph_name=run_graph,
            atlas_graph_name=atlas_graph,
        )

        assert len(decisions) == 1
        d = decisions[0]
        # Conservative tie break: benign MUST win
        assert d.chosen_verdict == "benign"
        assert d.winning_finding_id == "f-tie-ben"
        assert "f-tie-sus" in d.superseded_finding_ids

        # Suspicious finding is superseded
        sus_status = live_store.query(
            run_graph,
            "MATCH (f:Finding {id: 'f-tie-sus'}) RETURN f.status AS status",
        )
        assert sus_status[0]["status"] == "superseded"

    finally:
        live_store.delete_graph(run_graph)
        live_store.delete_graph(atlas_graph)
