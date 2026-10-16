"""Integration tests for F9: Native FalkorDB graph algorithms and NetworkX fallback."""

import pytest
from luna.domain.seed import seed_domain
from luna.tools.algorithms import connected_components, pagerank_top, shortest_path


@pytest.mark.integration
def test_supports_procedure_caching(live_store):
    """Verify GraphStore.supports_procedure discovers procedures and caches the lookup."""
    # First call probes live FalkorDB
    has_wcc = live_store.supports_procedure("algo.WCC")
    has_pr = live_store.supports_procedure("algo.pageRank")
    has_fake = live_store.supports_procedure("algo.non_existent_procedure")

    assert has_wcc is True
    assert has_pr is True
    assert has_fake is False

    # Second call uses cache
    assert live_store.supports_procedure("algo.WCC") is True


@pytest.mark.integration
def test_native_and_networkx_components_agree(live_store):
    """Verify native algo.WCC and NetworkX connected_components produce identical component sets."""
    gt = seed_domain(live_store, seed=42, profile="small")
    all_cids = sorted(list(gt.ring_cids | gt.decoy_cids))

    # Run with native FalkorDB algo.WCC explicitly
    native_comps = connected_components(live_store, "domain", cids=all_cids, use_native=True)

    # Run with NetworkX explicitly
    nx_comps = connected_components(live_store, "domain", cids=all_cids, use_native=False)

    assert native_comps == nx_comps
    assert len(native_comps) == 2
    assert native_comps[0] == sorted(list(gt.ring_cids))
    assert native_comps[1] == sorted(list(gt.decoy_cids))


@pytest.mark.integration
def test_native_pagerank_top_k_matches_networkx_ranking_order(live_store, tmp_graph):
    """Verify native algo.pageRank top-k ranking matches NetworkX ranking order."""
    # Create directed toy graph with unambiguous centrality hierarchy
    live_store.query(
        tmp_graph,
        """
        CREATE (a:Item {cid: 'A'}), (b:Item {cid: 'B'}), (c:Item {cid: 'C'}), (d:Item {cid: 'D'})
        CREATE (a)-[:CONNECTED]->(b)
        CREATE (c)-[:CONNECTED]->(b)
        CREATE (b)-[:CONNECTED]->(d)
        """,
    )

    # Native PageRank
    native_res = pagerank_top(
        live_store,
        tmp_graph,
        limit=3,
        node_label="Item",
        rel_type="CONNECTED",
        use_native=True,
    )
    native_top_3 = [r["cid"] for r in native_res]

    # NetworkX PageRank
    nx_res = pagerank_top(
        live_store,
        tmp_graph,
        limit=3,
        use_native=False,
    )
    nx_top_3 = [r["cid"] for r in nx_res]

    assert native_top_3 == ["D", "B", "A"] or native_top_3 == ["D", "B", "C"]
    assert nx_top_3 == ["D", "B", "A"] or nx_top_3 == ["D", "B", "C"]
    assert native_top_3[0] == nx_top_3[0] == "D"
    assert native_top_3[1] == nx_top_3[1] == "B"


@pytest.mark.integration
def test_falls_back_when_procedure_missing(live_store, monkeypatch):
    """Verify algorithms smoothly fall back to NetworkX when supports_procedure returns False."""
    gt = seed_domain(live_store, seed=42, profile="small")
    all_cids = sorted(list(gt.ring_cids | gt.decoy_cids))

    # Mock supports_procedure to return False
    monkeypatch.setattr(live_store, "supports_procedure", lambda name: False)

    # Auto-detect should use NetworkX fallback
    comps = connected_components(live_store, "domain", cids=all_cids, use_native=None)
    assert len(comps) == 2
    assert comps[0] == sorted(list(gt.ring_cids))
    assert comps[1] == sorted(list(gt.decoy_cids))

    # Shortest path fallback
    path = shortest_path(live_store, "domain", "cust_ring_1", "cust_ring_2", use_native=False)
    assert len(path) > 0
    assert "cust_ring_1" in path[0]["path_cids"]
    assert "cust_ring_2" in path[0]["path_cids"]
