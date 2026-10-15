"""Unit tests for algorithm tools, ask_graph, and the central TOOL_REGISTRY."""

from unittest.mock import MagicMock
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
    get_tool,
    list_tools,
    get_tools_for_skill,
)


def test_tool_registry_completeness():
    """Verify that TOOL_REGISTRY contains all 6 required tools with valid JSON schemas."""
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
    """Verify that skills correctly resolve their primary tool plus ask_graph."""
    entity_linker_tools = get_tools_for_skill("entity-linker")
    tool_names = {t.name for t in entity_linker_tools}
    assert tool_names == {"shared_attribute_links", "ask_graph"}

    ring_detector_tools = get_tools_for_skill("ring-detector")
    tool_names = {t.name for t in ring_detector_tools}
    assert tool_names == {"connected_components", "ask_graph"}

    anomaly_tools = get_tools_for_skill("anomaly-scout")
    tool_names = {t.name for t in anomaly_tools}
    assert tool_names == {"claim_amount_outliers", "ask_graph"}


def test_shared_attribute_links():
    """Verify shared_attribute_links queries with proper parameters."""
    mock_store = MagicMock()
    mock_store.query.return_value = [
        {"shared_cid": "cust_ring_2", "attribute_type": "BankAccount", "attribute_cid": "ba_ring"}
    ]

    res = shared_attribute_links(mock_store, "test_slice", "cust_ring_1", ["BankAccount"])
    assert len(res) == 1
    assert res[0]["shared_cid"] == "cust_ring_2"
    mock_store.query.assert_called_once()
    args = mock_store.query.call_args[0]
    assert args[0] == "test_slice"
    assert "$cid" in args[1]
    assert args[2] == {"cid": "cust_ring_1", "attr_labels": ["BankAccount"]}


def test_connected_components():
    """Verify connected_components clusters entities via NetworkX."""
    mock_store = MagicMock()
    # Mock connections: A-B, B-C, and isolated D
    mock_store.query.return_value = [
        {"source": "cust_1", "target": "cust_2", "via": "BankAccount"},
        {"source": "cust_2", "target": "cust_3", "via": "Phone"},
    ]

    cids = ["cust_1", "cust_2", "cust_3", "cust_4"]
    components = connected_components(mock_store, "test_slice", cids)

    assert len(components) == 2
    # Largest cluster: cust_1, cust_2, cust_3
    assert set(components[0]) == {"cust_1", "cust_2", "cust_3"}
    # Isolated node: cust_4
    assert components[1] == ["cust_4"]


def test_pagerank_top():
    """Verify pagerank_top computes centrality ranking."""
    mock_store = MagicMock()
    # Hub node A connected to B, C, D
    mock_store.query.return_value = [
        {"source": "node_B", "target": "node_A"},
        {"source": "node_C", "target": "node_A"},
        {"source": "node_D", "target": "node_A"},
    ]

    ranks = pagerank_top(mock_store, "test_slice", limit=2)
    assert len(ranks) == 2
    # Node A receives all incoming links, so it has highest centrality
    assert ranks[0]["cid"] == "node_A"
    assert ranks[0]["score"] > ranks[1]["score"]


def test_shortest_path():
    """Verify shortest_path query execution and fallback."""
    mock_store = MagicMock()
    mock_store.query.side_effect = [
        [],  # Cypher shortestPath returns empty
        [
            {"source": "A", "target": "B", "rel": "USES"},
            {"source": "B", "target": "C", "rel": "HOLDS"},
        ],  # Edge query for fallback
    ]

    path = shortest_path(mock_store, "test_slice", "A", "C")
    assert len(path) == 1
    assert path[0]["path_cids"] == ["A", "B", "C"]
    assert path[0]["length"] == 2


def test_claim_amount_outliers():
    """Verify claim_amount_outliers identifies statistical anomalies."""
    mock_store = MagicMock()
    # Normal claims (~1000) and one large outlier (50000)
    mock_store.query.return_value = [
        {"claim_cid": "claim_1", "amount": 1000.0},
        {"claim_cid": "claim_2", "amount": 1200.0},
        {"claim_cid": "claim_3", "amount": 800.0},
        {"claim_cid": "claim_4", "amount": 1100.0},
        {"claim_cid": "claim_outlier", "amount": 55000.0},
    ]

    outliers = claim_amount_outliers(mock_store, "test_slice", std_dev_threshold=1.5)
    assert len(outliers) == 1
    assert outliers[0]["claim_cid"] == "claim_outlier"
    assert outliers[0]["amount"] == 55000.0
    assert outliers[0]["amount"] > outliers[0]["cutoff"]


def test_ask_graph_nl_query():
    """Verify ask_graph translates natural language queries into Cypher."""
    mock_store = MagicMock()
    mock_store.query.return_value = [{"bank_account": "ba_ring", "customers": ["cust_1", "cust_2"]}]

    res = ask_graph(mock_store, "domain", "Who are the customers sharing a bank account?")
    assert "cypher" in res
    assert "PAYS_FROM" in res["cypher"]
    assert len(res["results"]) == 1
    assert "ontology_entities" in res
