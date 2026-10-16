"""Agent-scoped MCP client adapters enforcing tool permission checks and clean unwrapping."""

import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Optional
from mcp.server.fastmcp import FastMCP
from mcp import ClientSession


def _unwrap_mcp_result(res: Any) -> Any:
    """Unwrap FastMCP call_tool result into native Python objects."""
    if hasattr(res, "structuredContent") and res.structuredContent:
        if isinstance(res.structuredContent, dict) and "result" in res.structuredContent:
            return res.structuredContent["result"]
        return res.structuredContent
    if hasattr(res, "content") and isinstance(res.content, list):
        if not res.content:
            return None
        items = []
        for item in res.content:
            if hasattr(item, "text") and isinstance(item.text, str):
                try:
                    items.append(json.loads(item.text))
                except Exception:
                    items.append(item.text)
        if len(items) == 1:
            return items[0]
        return items
    if isinstance(res, list):
        if not res:
            return None
        item = res[0]
        if hasattr(item, "text") and isinstance(item.text, str):
            try:
                return json.loads(item.text)
            except Exception:
                return item.text
    elif isinstance(res, tuple):
        blocks, extra = res
        if isinstance(extra, dict) and "result" in extra:
            return extra["result"]
        return _unwrap_mcp_result(blocks)
    elif hasattr(res, "text") and isinstance(res.text, str):
        try:
            return json.loads(res.text)
        except Exception:
            return res.text
    return res


class InProcessAgentMCPClient:
    """In-process scoped FastMCP client adapter for a sub-agent.
    
    Operates in-memory directly with a FastMCP server instance.
    Enforces that sub-agents can only call tools explicitly exposed to their skill.
    """

    def __init__(self, server: FastMCP, allowed_tool_names: list[str]) -> None:
        self.server = server
        self.allowed_tool_names: set[str] = set(allowed_tool_names)

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all tools exposed on this agent's server."""
        raw_tools = await self.server.list_tools()
        result: list[dict[str, Any]] = []
        for t in raw_tools:
            if t.name in self.allowed_tool_names:
                result.append({
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema,
                })
        return result

    async def call_tool(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Call an MCP tool with strict permission checking in-process.
        
        Raises PermissionError if the tool is not exposed to this agent.
        """
        if name not in self.allowed_tool_names:
            raise PermissionError(
                f"Tool '{name}' is not exposed to this agent. Allowed tools: {sorted(self.allowed_tool_names)}"
            )

        raw_result = await self.server.call_tool(name, arguments or {})
        return _unwrap_mcp_result(raw_result)


# Backwards compatibility alias for existing in-process callers
AgentMCPClient = InProcessAgentMCPClient


class StdioAgentMCPClient:
    """Client adapter communicating with an out-of-process FastMCP server over stdio."""

    def __init__(
        self,
        session: ClientSession,
        allowed_tool_names: list[str],
        process: Optional[Any] = None,
    ) -> None:
        self.session = session
        self.allowed_tool_names: set[str] = set(allowed_tool_names)
        self.process = process
        self.pid: Optional[int] = getattr(process, "pid", None)

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all tools exposed on this agent's stdio server."""
        response = await self.session.list_tools()
        result: list[dict[str, Any]] = []
        for t in response.tools:
            if t.name in self.allowed_tool_names:
                result.append({
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema,
                })
        return result

    async def call_tool(
        self,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Call tool via stdio with strict permission checking."""
        if name not in self.allowed_tool_names:
            raise PermissionError(
                f"Tool '{name}' is not exposed to this agent. Allowed tools: {sorted(self.allowed_tool_names)}"
            )

        raw_result = await self.session.call_tool(name, arguments or {})
        return _unwrap_mcp_result(raw_result)


@asynccontextmanager
async def open_stdio_client(
    agent_id: str,
    graph_name: str,
    tool_names: list[str],
    host: str = "localhost",
    port: int = 6379,
):
    """Context manager that spawns the FastMCP stdio server and yields a StdioAgentMCPClient."""
    import mcp.client.stdio as stdio_module
    from mcp.client.stdio import stdio_client, StdioServerParameters

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m", "luna.mcp.server",
            "--agent", agent_id,
            "--graph", graph_name,
            "--tools", ",".join(tool_names),
            "--host", host,
            "--port", str(port),
        ],
        env=dict(os.environ),
    )

    captured_procs: list[Any] = []
    orig_create = stdio_module._create_platform_compatible_process

    async def _intercepting_create(*args, **kwargs):
        proc = await orig_create(*args, **kwargs)
        captured_procs.append(proc)
        return proc

    stdio_module._create_platform_compatible_process = _intercepting_create
    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                proc = captured_procs[0] if captured_procs else None
                client = StdioAgentMCPClient(session, tool_names, proc)
                yield client
    finally:
        stdio_module._create_platform_compatible_process = orig_create
