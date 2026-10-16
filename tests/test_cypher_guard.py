"""Tests for Cypher read-only validation guard and ask_graph safety."""

import pytest
import inspect
from luna.tools.cypher_guard import UnsafeCypherError, validate_read_only
from luna.tools.ask_graph import ask_graph
from luna.mcp.server import create_agent_mcp_server, _make_tool_wrapper
from luna.tools.registry import get_tool
from luna.domain.seed import seed_domain


def test_blocks_create():
    with pytest.raises(UnsafeCypherError):
        validate_read_only("CREATE (n:Customer {name: 'Alice'})")


def test_blocks_set():
    with pytest.raises(UnsafeCypherError):
        validate_read_only("MATCH (n) SET n.x = 1 RETURN n")


def test_blocks_delete():
    with pytest.raises(UnsafeCypherError):
        validate_read_only("MATCH (n) DELETE n")


def test_blocks_merge():
    with pytest.raises(UnsafeCypherError):
        validate_read_only("MERGE (n:Customer {cid: 'c1'})")


def test_blocks_call():
    with pytest.raises(UnsafeCypherError):
        validate_read_only("CALL db.labels()")


def test_blocks_multi_statement():
    with pytest.raises(UnsafeCypherError):
        validate_read_only("MATCH (n) RETURN n; MATCH (m) RETURN m")
    with pytest.raises(UnsafeCypherError):
        validate_read_only("MATCH (n) RETURN n; DROP GRAPH test")


def test_ignores_keywords_inside_string_literals():
    query = "MATCH (n) WHERE n.name = 'create' RETURN n"
    validated = validate_read_only(query)
    assert "LIMIT 100" in validated
    assert "WHERE n.name = 'create'" in validated

    double_quoted = 'MATCH (n) WHERE n.name = "delete" RETURN n'
    validated_dq = validate_read_only(double_quoted)
    assert "LIMIT 100" in validated_dq


def test_appends_limit_when_missing():
    query = "MATCH (n) RETURN n"
    validated = validate_read_only(query, max_rows=50)
    assert validated.endswith("LIMIT 50")


def test_lowers_excessive_limit():
    query = "MATCH (n) RETURN n LIMIT 500"
    validated = validate_read_only(query, max_rows=100)
    assert "LIMIT 100" in validated
    assert "LIMIT 500" not in validated

    # When limit is within threshold, keep it
    within = "MATCH (n) RETURN n LIMIT 25"
    validated_within = validate_read_only(within, max_rows=100)
    assert "LIMIT 25" in validated_within


def test_ask_graph_uses_pinned_graph(live_store, tmp_graph):
    """Verify tool wrapper for ask_graph has no parameter that selects the graph."""
    server = create_agent_mcp_server(
        agent_id="test_agent",
        tool_names=["ask_graph"],
        graph_store=live_store,
        agent_graph_name=tmp_graph,
    )
    tool_info = get_tool("ask_graph")
    wrapper = _make_tool_wrapper(tool_info, live_store, tmp_graph)
    sig = inspect.signature(wrapper)
    assert "graph" not in sig.parameters
    assert "graph_name" not in sig.parameters
    assert "question" in sig.parameters


@pytest.mark.integration
def test_ask_graph_never_writes(live_store, tmp_graph, monkeypatch):
    """Assert the slice is unchanged and ask_graph returns unsafe_query error on write query."""
    # Seed a simple node in tmp_graph
    live_store.query(tmp_graph, "CREATE (c:Customer {cid: 'c1', x: 0})")

    # Monkeypatch translation heuristic to return a write query
    def fake_translate(question: str):
        return ("MATCH (c:Customer {cid: 'c1'}) SET c.x = 999 RETURN c", {})

    monkeypatch.setattr("luna.tools.ask_graph._nl_to_cypher_heuristic", fake_translate)

    res = ask_graph(live_store, tmp_graph, "Hack the graph")
    assert res == {"error": "unsafe_query"}

    # Verify node was NOT modified
    rows = live_store.query(tmp_graph, "MATCH (c:Customer {cid: 'c1'}) RETURN c.x AS x")
    assert rows[0]["x"] == 0
