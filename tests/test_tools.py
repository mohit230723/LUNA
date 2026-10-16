"""Unit and integration tests for algorithm tools, ask_graph, and the central TOOL_REGISTRY."""

import pytest
from luna.domain.seed import seed_domain
from luna.tools.algorithms import (
    shared_attribute_links,
    connected_components,
    pagerank_top,
    shortest_path,
    claim_amount_outliers,
)
from luna.tools.ask_graph import ask_graph
from luna.tools.registry import (
    TOOL_REGISTRY,
    list_tools,
    get_tools_for_skill,
)


def test_tool_registry_completeness():
    """Verify that TOOL_REGISTRY contains all 6 required tools with valid JSON schemas (pure logic)."""
    expected_tools = {
        "shared_attribute_links",
        "connected_components",
        "pagerank_top",
        "shortest_path",
        "claim_amount_outliers",
        "ask_graph",
    }
    assert set(TOOL_REGISTRY.keys()) == expected_tools
    assert len(list_tools()) == 6

    for name, tool in TOOL_REGISTRY.items():
        assert tool.name == name
        assert tool.description
        assert callable(tool.func)
        assert tool.parameters["type"] == "object"
        assert "properties" in tool.parameters


def test_get_tools_for_skill():
    """Verify that skills correctly resolve their primary tool plus ask_graph (pure logic)."""
    entity_linker_tools = get_tools_for_skill("entity-linker")
    tool_names = {t.name for t in entity_linker_tools}
    assert tool_names == {"shared_attribute_links", "ask_graph"}

    ring_detector_tools = get_tools_for_skill("ring-detector")
    tool_names = {t.name for t in ring_detector_tools}
    assert tool_names == {"connected_components", "ask_graph"}

    anomaly_tools = get_tools_for_skill("anomaly-scout")
    tool_names = {t.name for t in anomaly_tools}
    assert tool_names == {"claim_amount_outliers", "ask_graph"}


@pytest.mark.integration
def test_shared_attribute_links(live_store):
    """Verify shared_attribute_links finds connections via bank account on live domain."""
    gt = seed_domain(live_store, seed=42)
    ring_cids = sorted(list(gt.ring_cids))

    res = shared_attribute_links(live_store, "domain", ring_cids[0], ["BankAccount"])
    assert len(res) >= 1
    shared_cids = {r["shared_cid"] for r in res}
    assert any(c in ring_cids for c in shared_cids)
    assert any(r["attribute_cid"] == gt.ring_bank_account for r in res)


@pytest.mark.integration
def test_connected_components(live_store):
    """Verify connected_components clusters entities over live domain."""
    gt = seed_domain(live_store, seed=42)
    sample_cids = sorted(list(gt.ring_cids))[:4]
    components = connected_components(live_store, "domain", sample_cids)

    assert len(components) >= 1
    assert set(components[0]) == set(sample_cids)


@pytest.mark.integration
def test_pagerank_top(live_store):
    """Verify pagerank_top computes centrality ranking on live domain."""
    seed_domain(live_store, seed=42)
    ranks = pagerank_top(live_store, "domain", limit=3)
    assert len(ranks) == 3
    assert ranks[0]["score"] >= ranks[1]["score"] >= ranks[2]["score"]


@pytest.mark.integration
def test_shortest_path(live_store):
    """Verify shortest_path query execution on live domain."""
    gt = seed_domain(live_store, seed=42)
    ring_list = sorted(list(gt.ring_cids))

    path = shortest_path(live_store, "domain", ring_list[0], ring_list[1])
    assert len(path) >= 1
    assert path[0]["length"] == 2
    assert path[0]["path_cids"][0] == ring_list[0]
    assert path[0]["path_cids"][-1] == ring_list[1]


@pytest.mark.integration
def test_claim_amount_outliers(live_store):
    """Verify claim_amount_outliers identifies statistical anomalies on live domain."""
    seed_domain(live_store, seed=42)
    outliers = claim_amount_outliers(live_store, "domain", std_dev_threshold=1.5)
    assert len(outliers) >= 8
    assert all(o["amount"] >= 25000.0 for o in outliers)


@pytest.mark.integration
def test_ask_graph_nl_query(live_store):
    """Verify ask_graph translates natural language queries into Cypher and executes on live domain."""
    seed_domain(live_store, seed=42)
    res = ask_graph(live_store, "domain", "Who are the customers sharing a bank account?")
    assert "cypher" in res
    assert "PAYS_FROM" in res["cypher"]
    assert len(res["results"]) >= 1
    assert "ontology_entities" in res
