"""Unit tests for agent FastMCP server factory and client session adapter."""

import pytest
from unittest.mock import MagicMock
from luna.graph.store import GraphStore
from luna.tools.registry import get_tools_for_skill
from luna.mcp.server import create_agent_mcp_server, get_server_tool_names
from luna.mcp.client import AgentMCPClient


@pytest.fixture
def mock_graph_store() -> GraphStore:
    """Create a GraphStore with a mock FalkorDB client."""
    mock_client = MagicMock()
    mock_graph = MagicMock()
    mock_client.select_graph.return_value = mock_graph
    return GraphStore(client=mock_client)


def test_mcp_server_tool_registration(mock_graph_store: GraphStore) -> None:
    """Verify that FastMCP server registers only the requested tools."""
    tools = get_tools_for_skill("entity-linker")
    tool_names = [t.name for t in tools]
    assert "shared_attribute_links" in tool_names
    assert "ask_graph" in tool_names
    assert "pagerank_top" not in tool_names

    server = create_agent_mcp_server(
        agent_id="agent-01",
        tool_names=tool_names,
        graph_store=mock_graph_store,
        agent_graph_name="agent_run1_agent01",
    )

    registered = get_server_tool_names(server)
    assert set(registered) == {"shared_attribute_links", "ask_graph"}
    assert "pagerank_top" not in registered


def test_mcp_server_rejects_unknown_tool(mock_graph_store: GraphStore) -> None:
    """Verify that requesting an unknown tool raises ValueError."""
    with pytest.raises(ValueError, match="Unknown or unauthorized tool"):
        create_agent_mcp_server(
            agent_id="agent-01",
            tool_names=["non_existent_tool"],
            graph_store=mock_graph_store,
            agent_graph_name="agent_run1_agent01",
        )


@pytest.mark.asyncio
async def test_mcp_client_permission_check(mock_graph_store: GraphStore) -> None:
    """Verify that AgentMCPClient blocks calls to unexposed tools."""
    server = create_agent_mcp_server(
        agent_id="agent-01",
        tool_names=["shared_attribute_links"],
        graph_store=mock_graph_store,
        agent_graph_name="agent_run1_agent01",
    )

    client = AgentMCPClient(server, allowed_tool_names=["shared_attribute_links"])

    # List tools reflects only allowed tools
    tools = await client.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "shared_attribute_links"

    # Calling unexposed tool raises PermissionError
    with pytest.raises(PermissionError, match="not exposed to this agent"):
        await client.call_tool("pagerank_top", {"limit": 5})


@pytest.mark.asyncio
async def test_mcp_client_tool_invocation_and_graph_pinning(
    mock_graph_store: GraphStore,
) -> None:
    """Verify that tool invocation correctly delegates and pins to the agent's private graph."""
    # Mock Cypher response with header from query
    mock_graph = mock_graph_store.client.select_graph.return_value
    mock_graph.query.return_value.header = [
        [1, b"shared_cid"],
        [1, b"shared_label"],
        [1, b"attribute_type"],
        [1, b"attribute_cid"],
        [1, b"rel_out"],
        [1, b"rel_in"],
    ]
    mock_graph.query.return_value.result_set = [
        ["cust-001", "Customer", "BankAccount", "acc-100", "HAS_ACCOUNT", "HAS_ACCOUNT"],
    ]

    server = create_agent_mcp_server(
        agent_id="agent-01",
        tool_names=["shared_attribute_links"],
        graph_store=mock_graph_store,
        agent_graph_name="agent_run1_agent01",
    )

    client = AgentMCPClient(server, allowed_tool_names=["shared_attribute_links"])

    res = await client.call_tool("shared_attribute_links", {"cid": "cust-000"})
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]["shared_cid"] == "cust-001"
    assert res[0]["attribute_cid"] == "acc-100"

    # Verify that select_graph was called strictly for the agent's private slice
    mock_graph_store.client.select_graph.assert_called_with("agent_run1_agent01")
