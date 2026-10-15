"""Unit tests for finding promotion engine and anti-hallucination barrier."""

from unittest.mock import MagicMock
from luna.agents.models import Finding
from luna.graph.store import GraphStore
from luna.orchestrator.promote import promote_findings


def test_promote_valid_findings() -> None:
    """Verify that findings with verified evidence in the agent slice are promoted."""
    executed_queries: list[tuple[str, str, dict]] = []

    def mock_query(graph_name: str, query_str: str, params=None):
        executed_queries.append((graph_name, query_str, params or {}))
        # Evidence check in agent graph slice
        if "MATCH (n) WHERE n.cid = $cid" in query_str:
            cid = (params or {}).get("cid")
            if cid in ("ba-ring-01", "cust-001"):
                return [{"cnt": 1}]
            return [{"cnt": 0}]
        return []

    mock_store = GraphStore(client=MagicMock())
    mock_store.query = mock_query  # type: ignore

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
        store=mock_store,
        agent_graph_name="agent_slice_01",
        run_graph_name="run_001",
        findings=[finding],
    )

    assert res.total_promoted == 1
    assert res.total_rejected == 0
    assert len(res.promoted) == 1
    assert res.promoted[0].id == "find-valid-01"

    # Verify write queries executed against run graph
    run_queries = [q for q in executed_queries if q[0] == "run_001"]
    assert len(run_queries) == 3  # Finding node + 2 evidence edge queries
    assert any("PROMOTED_FROM" in q[1] for q in run_queries)
    assert any("ASSESSES" in q[1] for q in run_queries)
    assert any("SUPPORTED_BY" in q[1] for q in run_queries)


def test_reject_hallucinated_evidence() -> None:
    """Verify that findings citing non-existent evidence CIDs are rejected."""
    executed_queries: list[tuple[str, str, dict]] = []

    def mock_query(graph_name: str, query_str: str, params=None):
        executed_queries.append((graph_name, query_str, params or {}))
        # Evidence check in agent graph slice
        if "MATCH (n) WHERE n.cid = $cid" in query_str:
            cid = (params or {}).get("cid")
            if cid == "ba-ring-01":
                return [{"cnt": 1}]
            # Hallucinated CID
            return [{"cnt": 0}]
        return []

    mock_store = GraphStore(client=MagicMock())
    mock_store.query = mock_query  # type: ignore

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
        store=mock_store,
        agent_graph_name="agent_slice_01",
        run_graph_name="run_001",
        findings=[hallucinated_finding],
    )

    assert res.total_promoted == 0
    assert res.total_rejected == 1
    assert len(res.rejected) == 1
    assert res.rejected[0].finding.id == "find-hallucinated-02"
    assert "cust-fake-999" in res.rejected[0].reason
    assert "anti-hallucination barrier" in res.rejected[0].reason

    # Verify no writes occurred on run graph
    run_queries = [q for q in executed_queries if q[0] == "run_001"]
    assert len(run_queries) == 0


def test_partial_batch_promotion() -> None:
    """Verify mixed batch with 1 valid and 1 invalid finding."""
    def mock_query(graph_name: str, query_str: str, params=None):
        if "MATCH (n) WHERE n.cid = $cid" in query_str:
            cid = (params or {}).get("cid")
            if cid == "valid-evidence-cid":
                return [{"cnt": 1}]
            return [{"cnt": 0}]
        return []

    mock_store = GraphStore(client=MagicMock())
    mock_store.query = mock_query  # type: ignore

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
        store=mock_store,
        agent_graph_name="agent_slice_01",
        run_graph_name="run_001",
        findings=[f1, f2],
    )

    assert res.total_promoted == 1
    assert res.total_rejected == 1
    assert res.promoted[0].id == "find-good"
    assert res.rejected[0].finding.id == "find-bad"
