"""Integration and unit tests for sub-graph slice extraction and isolation."""

import pytest
from unittest.mock import MagicMock
from luna.graph.store import GraphStore
from luna.orchestrator.slice import extract_subgraph_slice
from luna.domain.seed import seed_domain


def test_extract_subgraph_slice_validation() -> None:
    """Verify input validation for slice extraction (pure logic)."""
    mock_store = GraphStore(client=MagicMock())
    with pytest.raises(ValueError, match="seed_cids cannot be empty"):
        extract_subgraph_slice(mock_store, "domain", "agent_slice", seed_cids=[])

    with pytest.raises(ValueError, match="k_hops must be between 0 and 5"):
        extract_subgraph_slice(mock_store, "domain", "agent_slice", seed_cids=["c1"], k_hops=-1)

    with pytest.raises(ValueError, match="k_hops must be between 0 and 5"):
        extract_subgraph_slice(mock_store, "domain", "agent_slice", seed_cids=["c1"], k_hops=6)


@pytest.mark.integration
def test_extract_subgraph_slice_structure(live_store, tmp_graph: str) -> None:
    """Verify that slice extraction collects seed, k-hop nodes, and induced edges from live domain."""
    gt = seed_domain(live_store, seed=42)
    ring_cid = list(gt.ring_cids)[0]

    summary = extract_subgraph_slice(
        store=live_store,
        source_graph="domain",
        target_graph=tmp_graph,
        seed_cids=[ring_cid],
        k_hops=2,
    )

    assert summary["nodes_extracted"] > 0
    assert summary["edges_extracted"] > 0
    assert ring_cid in summary["extracted_cids"]
    assert summary["target_graph"] == tmp_graph

    # Verify that tmp_graph received node and edge creation queries
    nodes = live_store.query(tmp_graph, "MATCH (n) RETURN count(n) AS cnt")
    assert nodes[0]["cnt"] == summary["nodes_extracted"]
    edges = live_store.query(tmp_graph, "MATCH ()-[r]->() RETURN count(r) AS cnt")
    assert edges[0]["cnt"] == summary["edges_extracted"]


@pytest.mark.integration
def test_subgraph_isolation_decoy_vs_ring(live_store, tmp_graph: str) -> None:
    """Verify that decoy customer slice is completely isolated from fraud ring nodes."""
    gt = seed_domain(live_store, seed=42)
    decoy_cid = list(gt.decoy_cids)[0]

    summary = extract_subgraph_slice(
        store=live_store,
        source_graph="domain",
        target_graph=tmp_graph,
        seed_cids=[decoy_cid],
        k_hops=2,
    )

    assert summary["nodes_extracted"] > 0
    assert decoy_cid in summary["extracted_cids"]

    # Verify no fraud ring entities leaked into decoy slice
    for ring_cid in gt.ring_cids:
        assert ring_cid not in summary["extracted_cids"]
    assert gt.ring_bank_account not in summary["extracted_cids"]


@pytest.mark.integration
def test_empty_slice_handling(live_store, tmp_graph: str) -> None:
    """Verify behavior when seed_cids yield no matching nodes."""
    summary = extract_subgraph_slice(
        store=live_store,
        source_graph="domain",
        target_graph=tmp_graph,
        seed_cids=["cust-nonexistent-999"],
        k_hops=2,
    )

    assert summary["nodes_extracted"] == 0
    assert summary["edges_extracted"] == 0
    assert summary["extracted_cids"] == []
