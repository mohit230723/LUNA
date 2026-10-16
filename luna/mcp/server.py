"""Agent-scoped FastMCP server factory enforcing tool scoping and private graph binding."""

from typing import Any, Callable, Optional
from mcp.server.fastmcp import FastMCP
from luna.graph.store import GraphStore
from luna.tools.registry import TOOL_REGISTRY, ToolInfo, get_tool


def _make_tool_wrapper(
    tool_info: ToolInfo,
    graph_store: GraphStore,
    agent_graph_name: str,
) -> Callable[..., Any]:
    """Create a scoped tool wrapper that injects graph_store and agent_graph_name."""
    target_func = tool_info.func
    tool_name = tool_info.name

    if tool_name == "shared_attribute_links":
        def shared_attribute_links_wrapper(
            cid: str,
            attr_types: Optional[list[str]] = None,
        ) -> list[dict]:
            """Find entities sharing attributes with a given CID."""
            return target_func(
                store=graph_store,
                graph_name=agent_graph_name,
                cid=cid,
                attr_types=attr_types,
            )

        shared_attribute_links_wrapper.__name__ = tool_name
        shared_attribute_links_wrapper.__doc__ = tool_info.description
        return shared_attribute_links_wrapper

    elif tool_name == "connected_components":
        def connected_components_wrapper(
            cids: list[str],
            rel_types: Optional[list[str]] = None,
        ) -> list[list[str]]:
            """Compute connected component clusters for entity CIDs."""
            return target_func(
                store=graph_store,
                graph_name=agent_graph_name,
                cids=cids,
                rel_types=rel_types,
            )

        connected_components_wrapper.__name__ = tool_name
        connected_components_wrapper.__doc__ = tool_info.description
        return connected_components_wrapper

    elif tool_name == "pagerank_top":
        def pagerank_top_wrapper(limit: int = 10) -> list[dict]:
            """Calculate top PageRank centrality nodes in the private graph slice."""
            return target_func(
                store=graph_store,
                graph_name=agent_graph_name,
                limit=limit,
            )

        pagerank_top_wrapper.__name__ = tool_name
        pagerank_top_wrapper.__doc__ = tool_info.description
        return pagerank_top_wrapper

    elif tool_name == "shortest_path":
        def shortest_path_wrapper(
            source_cid: str,
            target_cid: str,
        ) -> Optional[list[str]]:
            """Compute shortest path between two entities in the private graph slice."""
            return target_func(
                store=graph_store,
                graph_name=agent_graph_name,
                source_cid=source_cid,
                target_cid=target_cid,
            )

        shortest_path_wrapper.__name__ = tool_name
        shortest_path_wrapper.__doc__ = tool_info.description
        return shortest_path_wrapper

    elif tool_name == "claim_amount_outliers":
        def claim_amount_outliers_wrapper(
            std_dev_threshold: float = 2.0,
        ) -> list[dict]:
            """Detect claim amount statistical outliers in the private graph slice."""
            return target_func(
                store=graph_store,
                graph_name=agent_graph_name,
                std_dev_threshold=std_dev_threshold,
            )

        claim_amount_outliers_wrapper.__name__ = tool_name
        claim_amount_outliers_wrapper.__doc__ = tool_info.description
        return claim_amount_outliers_wrapper

    elif tool_name == "ask_graph":
        def ask_graph_wrapper(question: str) -> dict:
            """Natural language query tool against the private graph slice."""
            return target_func(
                store=graph_store,
                graph_name=agent_graph_name,
                question=question,
            )

        ask_graph_wrapper.__name__ = tool_name
        ask_graph_wrapper.__doc__ = tool_info.description
        return ask_graph_wrapper

    else:
        # Generic dynamic wrapper
        def generic_wrapper(**kwargs: Any) -> Any:
            return target_func(
                store=graph_store,
                graph_name=agent_graph_name,
                **kwargs,
            )

        generic_wrapper.__name__ = tool_name
        generic_wrapper.__doc__ = tool_info.description
        return generic_wrapper


def create_agent_mcp_server(
    agent_id: str,
    tool_names: list[str],
    graph_store: GraphStore,
    agent_graph_name: str,
) -> FastMCP:
    """Create a scoped FastMCP server exposing ONLY the specified tool_names.
    
    CRITICAL ISOLATION:
    - Every tool is bound to `agent_graph_name`.
    - Tools outside `tool_names` are NOT registered.
    - If an invalid tool name is passed, raises ValueError.
    """
    server = FastMCP(f"agent-{agent_id}")

    for name in tool_names:
        tool_info = get_tool(name)
        if not tool_info:
            raise ValueError(f"Unknown or unauthorized tool '{name}' requested for agent '{agent_id}'")

        wrapper = _make_tool_wrapper(
            tool_info=tool_info,
            graph_store=graph_store,
            agent_graph_name=agent_graph_name,
        )
        server.add_tool(wrapper, name=name, description=tool_info.description)

    return server


def get_server_tool_names(server: FastMCP) -> list[str]:
    """Retrieve list of tool names currently registered on a FastMCP server."""
    if hasattr(server, "_tool_manager") and hasattr(server._tool_manager, "_tools"):
        return list(server._tool_manager._tools.keys())
    return []


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Scoped Agent FastMCP Stdio Server")
    parser.add_argument("--agent", required=True, help="Agent ID")
    parser.add_argument("--graph", required=True, help="Scoped graph name")
    parser.add_argument("--tools", required=True, help="Comma-separated tool names")
    parser.add_argument("--host", default="localhost", help="FalkorDB host")
    parser.add_argument("--port", type=int, default=6379, help="FalkorDB port")
    args = parser.parse_args()

    tool_names = [t.strip() for t in args.tools.split(",") if t.strip()]
    store = GraphStore(host=args.host, port=args.port)
    server = create_agent_mcp_server(
        agent_id=args.agent,
        tool_names=tool_names,
        graph_store=store,
        agent_graph_name=args.graph,
    )
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
