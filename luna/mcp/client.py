"""Agent-scoped MCP client adapter enforcing tool permission checks and clean unwrapping."""

import json
from typing import Any, Optional
from mcp.server.fastmcp import FastMCP


def _unwrap_mcp_result(res: Any) -> Any:
    """Unwrap FastMCP call_tool result into native Python objects."""
    if isinstance(res, list):
        if not res:
            return None
        # Check first TextContent block
        item = res[0]
        if hasattr(item, "text") and isinstance(item.text, str):
            try:
                return json.loads(item.text)
            except Exception:
                return item.text
    elif isinstance(res, tuple):
        # Format (blocks, parsed_meta)
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


class AgentMCPClient:
    """Scoped MCP client adapter for a sub-agent.
    
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
        """Call an MCP tool with strict permission checking.
        
        Raises PermissionError if the tool is not exposed to this agent.
        """
        if name not in self.allowed_tool_names:
            raise PermissionError(
                f"Tool '{name}' is not exposed to this agent. Allowed tools: {sorted(self.allowed_tool_names)}"
            )

        raw_result = await self.server.call_tool(name, arguments or {})
        return _unwrap_mcp_result(raw_result)
