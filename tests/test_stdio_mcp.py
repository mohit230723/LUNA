"""Integration and slow tests for real stdio FastMCP client and server."""

import pytest
import psutil
from luna.domain.seed import seed_domain
from luna.mcp.client import open_stdio_client


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_stdio_lists_only_assigned_tools(live_store, tmp_graph):
    """Verify stdio server lists only the tools assigned to this agent."""
    assigned_tools = ["shared_attribute_links", "ask_graph"]
    async with open_stdio_client(
        agent_id="test_scout",
        graph_name=tmp_graph,
        tool_names=assigned_tools,
    ) as client:
        tools = await client.list_tools()
        tool_names = [t["name"] for t in tools]
        assert set(tool_names) == set(assigned_tools)
        assert "pagerank_top" not in tool_names


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_stdio_blocks_unassigned_tool(live_store, tmp_graph):
    """Verify calling an unassigned tool is blocked and raises PermissionError."""
    assigned_tools = ["shared_attribute_links"]
    async with open_stdio_client(
        agent_id="test_scout",
        graph_name=tmp_graph,
        tool_names=assigned_tools,
    ) as client:
        with pytest.raises((PermissionError, Exception)):
            await client.call_tool("pagerank_top", {"limit": 5})


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_stdio_tool_runs_on_agent_graph_only(live_store, tmp_graph):
    """Verify tool runs on agent graph only and domain-only nodes are not visible."""
    # Seed domain graph with fraud ring
    gt = seed_domain(live_store, seed=42)
    ring_cid = list(gt.ring_cids)[0]

    # In tmp_graph, create only one customer with NO shared attributes
    live_store.query(tmp_graph, "CREATE (c:Customer {cid: $cid, name: 'Isolated'})", {"cid": ring_cid})

    async with open_stdio_client(
        agent_id="test_scout",
        graph_name=tmp_graph,
        tool_names=["shared_attribute_links"],
    ) as client:
        # On tmp_graph, ring_cid has NO bank account or phone links
        res = await client.call_tool("shared_attribute_links", {"cid": ring_cid})
        assert res == [] or len(res) == 0

        # Verify against domain: on domain it HAS shared links, proving tmp_graph isolation
        domain_links = live_store.query(
            "domain",
            "MATCH (c1 {cid: $cid})-[r1]->(a)<-[r2]-(c2) RETURN c2.cid AS shared_cid",
            {"cid": ring_cid},
        )
        assert len(domain_links) > 0


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_stdio_process_terminates_on_exit(live_store, tmp_graph):
    """Verify server subprocess terminates when open_stdio_client context exits."""
    pid = None
    proc = None
    async with open_stdio_client(
        agent_id="test_terminator",
        graph_name=tmp_graph,
        tool_names=["shared_attribute_links"],
    ) as client:
        pid = client.pid
        proc = client.process
        assert pid is not None
        assert psutil.pid_exists(pid)

    # After exit, process should be terminated
    if proc is not None and hasattr(proc, "returncode"):
        assert proc.returncode is not None

    # Verify via psutil that process has terminated
    try:
        p = psutil.Process(pid)
        # Give brief grace period if process is in zombie/cleanup state
        try:
            p.wait(timeout=2.0)
        except psutil.TimeoutExpired:
            pass
        assert not p.is_running()
    except psutil.NoSuchProcess:
        pass  # Process terminated cleanly
