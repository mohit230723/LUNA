"""Unit and integration tests for luna.graph.schema and luna.graph.store."""

import pytest
from unittest.mock import MagicMock
from luna.graph.schema import (
    GRAPH_ATLAS,
    GRAPH_DOMAIN,
    LABEL_CUSTOMER,
    LABEL_SKILL,
    LABEL_FINDING,
    run_graph_name,
    agent_graph_name,
)
from luna.graph.store import GraphStore


def test_schema_naming_helpers():
    """Verify graph naming conventions and sanitization."""
    assert GRAPH_ATLAS == "atlas"
    assert GRAPH_DOMAIN == "domain"
    assert run_graph_name("run_123") == "run_run_123"
    assert run_graph_name("test-run-456") == "run_test_run_456"
    assert agent_graph_name("run_1", "agent_alpha") == "agent_run_1_agent_alpha"
    assert agent_graph_name("run:1", "agent/sub") == "agent_run_1_agent_sub"
    assert LABEL_CUSTOMER == "Customer"
    assert LABEL_SKILL == "Skill"
    assert LABEL_FINDING == "Finding"


def test_query_safety_validation():
    """Verify parameterized query validation rules."""
    store = GraphStore(client=MagicMock())

    # Empty query string
    with pytest.raises(ValueError, match="non-empty string"):
        store.query("test_graph", "")

    # Formatting placeholders (%s)
    with pytest.raises(ValueError, match="Unsafe string formatting"):
        store.query("test_graph", "MATCH (c:Customer {cid: %s}) RETURN c")

    # Formatting placeholders ({})
    with pytest.raises(ValueError, match="Unsafe string formatting"):
        store.query("test_graph", "MATCH (c:Customer {cid: '{}'}) RETURN c")

    # Semicolon injection chaining
    with pytest.raises(ValueError, match="Multiple statements"):
        store.query("test_graph", "MATCH (c:Customer) RETURN c; DROP GRAPH test")

    # Parameter in query without params dict
    with pytest.raises(ValueError, match="references parameters"):
        store.query("test_graph", "MATCH (c:Customer {cid: $cid}) RETURN c")

    # Missing specific param in params dict
    with pytest.raises(ValueError, match="Missing query parameters"):
        store.query("test_graph", "MATCH (c:Customer {cid: $cid, name: $name}) RETURN c", {"cid": "c1"})


def test_query_mock_execution():
    """Verify query execution and row mapping with mocked FalkorDB client."""
    mock_client = MagicMock()
    mock_graph = MagicMock()
    mock_client.select_graph.return_value = mock_graph

    # Mock QueryResult
    mock_result = MagicMock()
    mock_result.header = [[0, "name"], [0, "score"]]
    mock_result.result_set = [
        ["Alice", 0.95],
        ["Bob", 0.80],
    ]
    mock_graph.query.return_value = mock_result

    store = GraphStore(client=mock_client)
    rows = store.query("test_graph", "MATCH (u:User) RETURN u.name AS name, u.score AS score")

    assert len(rows) == 2
    assert rows[0] == {"name": "Alice", "score": 0.95}
    assert rows[1] == {"name": "Bob", "score": 0.80}
    mock_client.select_graph.assert_called_with("test_graph")
    mock_graph.query.assert_called_once_with(
        "MATCH (u:User) RETURN u.name AS name, u.score AS score", {}
    )


def test_query_node_property_extraction():
    """Verify that FalkorDB Node objects extract properties into row dictionaries."""
    mock_client = MagicMock()
    mock_graph = MagicMock()
    mock_client.select_graph.return_value = mock_graph

    class MockNode:
        def __init__(self, props):
            self.properties = props

    mock_result = MagicMock()
    mock_result.header = [[0, "c"]]
    mock_result.result_set = [
        [MockNode({"cid": "cust_101", "name": "John Doe"})]
    ]
    mock_graph.query.return_value = mock_result

    store = GraphStore(client=mock_client)
    rows = store.query("domain", "MATCH (c:Customer {cid: $cid}) RETURN c", {"cid": "cust_101"})

    assert len(rows) == 1
    assert rows[0] == {"c": {"cid": "cust_101", "name": "John Doe"}}


def test_graph_lifecycle_methods():
    """Verify delete, list, and copy graph operations."""
    mock_client = MagicMock()
    mock_graph = MagicMock()
    mock_client.select_graph.return_value = mock_graph
    mock_client.list_graphs.return_value = ["atlas", "domain"]

    store = GraphStore(client=mock_client)

    assert store.list_graphs() == ["atlas", "domain"]
    assert store.delete_graph("temp_graph") is True
    mock_graph.delete.assert_called_once()

    assert store.copy_graph("source_graph", "target_graph") is True
    mock_graph.copy.assert_called_once_with("target_graph")
