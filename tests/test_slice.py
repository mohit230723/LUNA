"""Unit tests for sub-graph slice extraction and isolation."""

import pytest
from unittest.mock import MagicMock
from luna.graph.store import GraphStore
from luna.orchestrator.slice import extract_subgraph_slice


@pytest.fixture
def mock_graph_store() -> GraphStore:
    """Create a GraphStore with a mock FalkorDB client."""
    mock_client = MagicMock()
    mock_graph = MagicMock()
    mock_client.select_graph.return_value = mock_graph
    return GraphStore(client=mock_client)


def test_extract_subgraph_slice_validation(mock_graph_store: GraphStore) -> None:
    """Verify input validation for slice extraction."""
    with pytest.raises(ValueError, match="seed_cids cannot be empty"):
        extract_subgraph_slice(mock_graph_store, "domain", "agent_slice", seed_cids=[])

    with pytest.raises(ValueError, match="k_hops must be between 0 and 5"):
        extract_subgraph_slice(mock_graph_store, "domain", "agent_slice", seed_cids=["c1"], k_hops=-1)

    with pytest.raises(ValueError, match="k_hops must be between 0 and 5"):
        extract_subgraph_slice(mock_graph_store, "domain", "agent_slice", seed_cids=["c1"], k_hops=6)


def test_extract_subgraph_slice_structure(mock_graph_store: GraphStore) -> None:
    """Verify that slice extraction collects seed, k-hop nodes, and induced edges."""
    executed_queries: list[tuple[str, str, dict]] = []

    def mock_query(graph_name: str, query_str: str, params=None):
        executed_queries.append((graph_name, query_str, params or {}))
        # 1. Seed query
        if "MATCH (anchor) WHERE anchor.cid IN $seed_cids" in query_str:
            return [{"label": "Customer", "props": {"cid": "cust-000", "name": "Target Customer"}}]
        # 2. Hop query
        elif "path = (anchor)-[*1..2]-(n)" in query_str:
            return [
                {"label": "Customer", "props": {"cid": "cust-001", "name": "Associate 1"}},
                {"label": "BankAccount", "props": {"cid": "ba-ring-01", "account_num": "ACC123"}},
            ]
        # 3. Induced edges query
        elif "MATCH (a)-[r]->(b)" in query_str:
            return [
                {
                    "from_cid": "cust-000",
                    "to_cid": "ba-ring-01",
                    "rel_type": "HAS_ACCOUNT",
                    "props": {"role": "primary"},
                },
                {
                    "from_cid": "cust-001",
                    "to_cid": "ba-ring-01",
                    "rel_type": "HAS_ACCOUNT",
                    "props": {"role": "secondary"},
                },
            ]
        # Target graph insertions
        return []

    # Patch query method on store
    mock_graph_store.query = mock_query  # type: ignore

    summary = extract_subgraph_slice(
        store=mock_graph_store,
        source_graph="domain",
        target_graph="agent_run1_agent01",
        seed_cids=["cust-000"],
        k_hops=2,
    )

    assert summary["nodes_extracted"] == 3
    assert summary["edges_extracted"] == 2
    assert set(summary["extracted_cids"]) == {"cust-000", "cust-001", "ba-ring-01"}
    assert summary["target_graph"] == "agent_run1_agent01"

    # Verify that target_graph received node and edge creation queries
    target_queries = [q for q in executed_queries if q[0] == "agent_run1_agent01"]
    assert len(target_queries) >= 2  # Customer nodes batch, BankAccount batch, and Edge batch
    node_create_queries = [q for q in target_queries if "CREATE (n:" in q[1]]
    assert len(node_create_queries) >= 2  # Customer + BankAccount
    edge_create_queries = [q for q in target_queries if "CREATE (a)-[r:" in q[1]]
    assert len(edge_create_queries) == 1
    assert "HAS_ACCOUNT" in edge_create_queries[0][1]


def test_subgraph_isolation_decoy_vs_ring(mock_graph_store: GraphStore) -> None:
    """Verify that decoy customer slice is completely isolated from fraud ring nodes."""
    def mock_query(graph_name: str, query_str: str, params=None):
        if "MATCH (anchor) WHERE anchor.cid IN $seed_cids" in query_str:
            return [{"label": "Customer", "props": {"cid": "cust-010", "name": "Decoy Customer"}}]
        elif "path = (anchor)-[*1..2]-(n)" in query_str:
            return [
                {"label": "Address", "props": {"cid": "addr-decoy-01", "address": "123 Family Rd"}},
            ]
        elif "MATCH (a)-[r]->(b)" in query_str:
            return [
                {"from_cid": "cust-010", "to_cid": "addr-decoy-01", "rel_type": "LIVES_AT", "props": {}},
            ]
        return []

    mock_graph_store.query = mock_query  # type: ignore

    summary = extract_subgraph_slice(
        store=mock_graph_store,
        source_graph="domain",
        target_graph="agent_run1_decoy_agent",
        seed_cids=["cust-010"],
        k_hops=2,
    )

    assert summary["nodes_extracted"] == 2
    assert "cust-010" in summary["extracted_cids"]
    assert "addr-decoy-01" in summary["extracted_cids"]
    # Verify no fraud ring entities leaked into decoy slice
    assert "cust-000" not in summary["extracted_cids"]
    assert "ba-ring-01" not in summary["extracted_cids"]


def test_empty_slice_handling(mock_graph_store: GraphStore) -> None:
    """Verify behavior when seed_cids yield no matching nodes."""
    mock_graph_store.query = lambda graph, query, params=None: []  # type: ignore

    summary = extract_subgraph_slice(
        store=mock_graph_store,
        source_graph="domain",
        target_graph="agent_slice_empty",
        seed_cids=["cust-nonexistent"],
        k_hops=2,
    )

    assert summary["nodes_extracted"] == 0
    assert summary["edges_extracted"] == 0
    assert summary["extracted_cids"] == []
