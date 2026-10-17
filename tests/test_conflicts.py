import pytest
from unittest.mock import MagicMock
from luna.orchestrator.conflicts import detect_contradictions, Contradiction
from luna.graph.store import GraphStore


def test_detect_contradictions_unit_pure_logic() -> None:
    """Verify contradiction detection model conversion and query execution with mock store."""
    mock_store = MagicMock(spec=GraphStore)
    mock_store.query.return_value = [
        {
            "f1_id": "find-10",
            "f2_id": "find-20",
            "target_cid": "cust-01",
            "v1": "suspicious",
            "v2": "benign",
            "detected_at": "2026-10-18T00:00:00Z",
        }
    ]

    res = detect_contradictions(mock_store, "run_test")
    assert len(res) == 1
    assert res[0].finding1_id == "find-10"
    assert res[0].finding2_id == "find-20"
    assert res[0].target_cid == "cust-01"
    assert res[0].verdict1 == "suspicious"
    assert res[0].verdict2 == "benign"
    assert res[0].detected_at == "2026-10-18T00:00:00Z"
    mock_store.query.assert_called_once()



@pytest.mark.integration
def test_detect_contradictions_opposing_verdicts(live_store, tmp_graph: str) -> None:
    """Verify that opposing verdicts on the same customer are detected and linked via CONFLICTS_WITH."""
    # Seed a run graph with two findings assessing the same customer with opposing verdicts
    live_store.query(
        tmp_graph,
        "CREATE (c:Customer {cid: 'cust_decoy_01'}) "
        "CREATE (f1:Finding {id: 'find-01', verdict: 'suspicious', confidence: 0.65, reasoning: 'Shares phone'}) "
        "CREATE (f2:Finding {id: 'find-02', verdict: 'benign', confidence: 0.82, reasoning: 'Family address pattern'}) "
        "CREATE (f1)-[:ASSESSES]->(c) "
        "CREATE (f2)-[:ASSESSES]->(c)",
    )

    conflicts = detect_contradictions(live_store, tmp_graph)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert isinstance(c, Contradiction)
    assert c.finding1_id == "find-01"
    assert c.finding2_id == "find-02"
    assert c.target_cid == "cust_decoy_01"
    assert c.verdict1 == "suspicious"
    assert c.verdict2 == "benign"
    assert c.detected_at is not None

    # Check graph edge
    edges = live_store.query(
        tmp_graph,
        "MATCH (f1:Finding {id: 'find-01'})-[r:CONFLICTS_WITH]-(f2:Finding {id: 'find-02'}) "
        "RETURN r.detected_at AS detected_at",
    )
    assert len(edges) == 1
    assert edges[0]["detected_at"] == c.detected_at


@pytest.mark.integration
def test_no_contradiction_when_findings_agree(live_store, tmp_graph: str) -> None:
    """Verify that agreeing verdicts on the same customer produce zero conflicts."""
    live_store.query(
        tmp_graph,
        "CREATE (c:Customer {cid: 'cust_ring_01'}) "
        "CREATE (f1:Finding {id: 'find-01', verdict: 'suspicious', confidence: 0.90}) "
        "CREATE (f2:Finding {id: 'find-02', verdict: 'suspicious', confidence: 0.85}) "
        "CREATE (f1)-[:ASSESSES]->(c) "
        "CREATE (f2)-[:ASSESSES]->(c)",
    )

    conflicts = detect_contradictions(live_store, tmp_graph)
    assert len(conflicts) == 0

    edges = live_store.query(tmp_graph, "MATCH ()-[r:CONFLICTS_WITH]->() RETURN count(r) AS cnt")
    assert edges[0]["cnt"] == 0


@pytest.mark.integration
def test_no_contradiction_different_customers(live_store, tmp_graph: str) -> None:
    """Verify that opposing verdicts on different customers do not conflict."""
    live_store.query(
        tmp_graph,
        "CREATE (c1:Customer {cid: 'cust_01'}) "
        "CREATE (c2:Customer {cid: 'cust_02'}) "
        "CREATE (f1:Finding {id: 'find-01', verdict: 'suspicious'}) "
        "CREATE (f2:Finding {id: 'find-02', verdict: 'benign'}) "
        "CREATE (f1)-[:ASSESSES]->(c1) "
        "CREATE (f2)-[:ASSESSES]->(c2)",
    )

    conflicts = detect_contradictions(live_store, tmp_graph)
    assert len(conflicts) == 0


@pytest.mark.integration
def test_detect_contradictions_idempotent(live_store, tmp_graph: str) -> None:
    """Verify that running detection multiple times does not duplicate CONFLICTS_WITH edges."""
    live_store.query(
        tmp_graph,
        "CREATE (c:Customer {cid: 'cust_decoy_01'}) "
        "CREATE (f1:Finding {id: 'find-01', verdict: 'suspicious', confidence: 0.65}) "
        "CREATE (f2:Finding {id: 'find-02', verdict: 'benign', confidence: 0.80}) "
        "CREATE (f1)-[:ASSESSES]->(c) "
        "CREATE (f2)-[:ASSESSES]->(c)",
    )

    c1 = detect_contradictions(live_store, tmp_graph)
    assert len(c1) == 1

    # Second run
    c2 = detect_contradictions(live_store, tmp_graph)
    assert len(c2) == 1
    assert c2[0].finding1_id == c1[0].finding1_id
    assert c2[0].detected_at == c1[0].detected_at

    edges = live_store.query(
        tmp_graph,
        "MATCH (f1:Finding)-[r:CONFLICTS_WITH]->(f2:Finding) RETURN count(r) AS cnt",
    )
    assert edges[0]["cnt"] == 1
