"""Tests for main-agent conflict resolution logic and Decision graph records (Plan 3.2)."""

import pytest
from unittest.mock import MagicMock
from luna.orchestrator.resolve import resolve_conflicts, Decision
from luna.graph.store import GraphStore


def test_resolve_conflicts_unit_arbitration() -> None:
    """Verify that conflict resolver correctly weighs confidence, evidence, and skill score."""
    mock_store = MagicMock(spec=GraphStore)

    # Mock finding conflicting findings query
    mock_store.query.side_effect = [
        # 1. Fetch unresolved conflicts
        [
            {"target_cid": "cust_decoy_01"}
        ],
        # 2. Fetch active findings on cust_decoy_01
        [
            {
                "id": "find-01",
                "verdict": "suspicious",
                "confidence": 0.65,
                "reasoning": "Shared phone",
                "skill_id": "entity-linker",
                "evidence_cids": ["ph-01"],
            },
            {
                "id": "find-02",
                "verdict": "benign",
                "confidence": 0.85,
                "reasoning": "Family structure",
                "skill_id": "community-analyzer",
                "evidence_cids": ["addr-01", "cust_decoy_02"],
            },
        ],
        # 3. Fetch atlas skill scores for entity-linker
        [{"score": 0.70}],
        # 4. Fetch atlas skill scores for community-analyzer
        [{"score": 0.80}],
        # 5. Insert Decision node
        [],
        # 6. Create UPHELD edge
        [],
        # 7. Create ABOUT edge
        [],
        # 8. Create SUPERSEDES edge and set status
        [],
    ]

    decisions = resolve_conflicts(mock_store, "run_test", atlas_graph_name="atlas")
    assert len(decisions) == 1
    d = decisions[0]
    assert isinstance(d, Decision)
    assert d.target_cid == "cust_decoy_01"
    assert d.chosen_verdict == "benign"
    assert d.winning_finding_id == "find-02"
    assert "find-01" in d.superseded_finding_ids
    assert "community-analyzer" in d.reasoning.lower() or "benign" in d.reasoning.lower()


@pytest.mark.integration
def test_resolve_conflicts_live_graph(live_store, tmp_graph: str) -> None:
    """Verify conflict resolution creates Decision, links UPHELD/SUPERSEDES, and preserves all findings."""
    # Seed conflicting findings on customer cust_42 in tmp_graph
    live_store.query(
        tmp_graph,
        "CREATE (c:Customer {cid: 'cust_42'}) "
        "CREATE (f1:Finding {id: 'find-A', verdict: 'suspicious', confidence: 0.62, skill_id: 'entity-linker', evidence_cids: ['ph-01'], reasoning: 'shares phone'}) "
        "CREATE (f2:Finding {id: 'find-B', verdict: 'benign', confidence: 0.80, skill_id: 'community-analyzer', evidence_cids: ['addr-01'], reasoning: 'benign address cluster'}) "
        "CREATE (f1)-[:ASSESSES]->(c) "
        "CREATE (f2)-[:ASSESSES]->(c) "
        "CREATE (f1)-[:CONFLICTS_WITH]->(f2)",
    )

    decisions = resolve_conflicts(live_store, tmp_graph)
    assert len(decisions) == 1
    d = decisions[0]
    assert d.chosen_verdict == "benign"
    assert d.winning_finding_id == "find-B"
    assert d.superseded_finding_ids == ["find-A"]

    # 1. Decision node exists
    dec_nodes = live_store.query(
        tmp_graph,
        "MATCH (d:Decision {id: $id}) RETURN d.chosen_verdict AS v, d.target_cid AS cid",
        {"id": d.id},
    )
    assert len(dec_nodes) == 1
    assert dec_nodes[0]["v"] == "benign"

    # 2. UPHELD edge to winner
    upheld = live_store.query(
        tmp_graph,
        "MATCH (d:Decision {id: $id})-[:UPHELD]->(w:Finding) RETURN w.id AS wid",
        {"id": d.id},
    )
    assert len(upheld) == 1
    assert upheld[0]["wid"] == "find-B"

    # 3. SUPERSEDES edge to loser and loser status marked superseded
    supersedes = live_store.query(
        tmp_graph,
        "MATCH (d:Decision {id: $id})-[:SUPERSEDES]->(l:Finding) RETURN l.id AS lid, l.status AS status",
        {"id": d.id},
    )
    assert len(supersedes) == 1
    assert supersedes[0]["lid"] == "find-A"
    assert supersedes[0]["status"] == "superseded"

    # 4. Critical Explainability Contract: Total findings count is unchanged (zero deletions)
    all_findings = live_store.query(tmp_graph, "MATCH (f:Finding) RETURN count(f) AS cnt")
    assert all_findings[0]["cnt"] == 2
