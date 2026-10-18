"""Central tool registry mapping tools to functions and JSON schema definitions."""

from dataclasses import dataclass
from typing import Any, Callable, Optional
from luna.tools.algorithms import (
    shared_attribute_links,
    connected_components,
    pagerank_top,
    shortest_path,
    claim_amount_outliers,
    trace_connections,
    find_suspect_links,
)
from luna.tools.ask_graph import ask_graph
from luna.atlas.seed import get_seeded_skills


@dataclass(frozen=True)
class ToolInfo:
    """Metadata, schema, and callable reference for an agent tool."""

    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]


TOOL_REGISTRY: dict[str, ToolInfo] = {
    "shared_attribute_links": ToolInfo(
        name="shared_attribute_links",
        description="Find entities sharing phone numbers, bank accounts, or addresses with a given entity CID.",
        parameters={
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "Unique identifier of the entity to analyze",
                },
                "attr_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of attribute labels to filter (e.g. ['Phone', 'BankAccount'])",
                },
            },
            "required": ["cid"],
        },
        func=shared_attribute_links,
    ),
    "connected_components": ToolInfo(
        name="connected_components",
        description="Compute connected component clusters among a specified list of entity CIDs.",
        parameters={
            "type": "object",
            "properties": {
                "cids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of entity CIDs to cluster",
                },
                "rel_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional attribute labels or relationship types to filter connections",
                },
            },
            "required": ["cids"],
        },
        func=connected_components,
    ),
    "pagerank_top": ToolInfo(
        name="pagerank_top",
        description="Calculate PageRank centrality across all entities in the target graph slice.",
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of top central entities to return (default: 10)",
                    "default": 10,
                },
            },
            "required": [],
        },
        func=pagerank_top,
    ),
    "shortest_path": ToolInfo(
        name="shortest_path",
        description="Compute the shortest connection path between two entity CIDs.",
        parameters={
            "type": "object",
            "properties": {
                "source_cid": {
                    "type": "string",
                    "description": "Origin entity CID",
                },
                "target_cid": {
                    "type": "string",
                    "description": "Destination entity CID",
                },
            },
            "required": ["source_cid", "target_cid"],
        },
        func=shortest_path,
    ),
    "claim_amount_outliers": ToolInfo(
        name="claim_amount_outliers",
        description="Detect statistical outliers in insurance claim amounts exceeding the standard deviation threshold.",
        parameters={
            "type": "object",
            "properties": {
                "std_dev_threshold": {
                    "type": "number",
                    "description": "Number of standard deviations above mean to flag (default: 2.0)",
                    "default": 2.0,
                },
            },
            "required": [],
        },
        func=claim_amount_outliers,
    ),
    "ask_graph": ToolInfo(
        name="ask_graph",
        description="Natural language query tool that translates questions into Cypher using domain ontology.",
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Natural language query about entities, claims, or connections",
                },
            },
            "required": ["question"],
        },
        func=ask_graph,
    ),
    "trace_connections": ToolInfo(
        name="trace_connections",
        description="Trace multi-hop connection paths outward from an entity up to max_hops.",
        parameters={
            "type": "object",
            "properties": {
                "src_cid": {
                    "type": "string",
                    "description": "Origin entity CID to trace outward from",
                },
                "max_hops": {
                    "type": "integer",
                    "description": "Maximum traversal depth (default: 4)",
                    "default": 4,
                },
                "limit_paths": {
                    "type": "integer",
                    "description": "Maximum number of shortest paths to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["src_cid"],
        },
        func=trace_connections,
    ),
    "find_suspect_links": ToolInfo(
        name="find_suspect_links",
        description="Find shared links and connection strengths among a specified list of entity CIDs.",
        parameters={
            "type": "object",
            "properties": {
                "cids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of entity CIDs to check for connections",
                },
                "min_strength": {
                    "type": "integer",
                    "description": "Minimum shared attributes required (default: 1)",
                    "default": 1,
                },
            },
            "required": ["cids"],
        },
        func=find_suspect_links,
    ),
}


def get_tool(name: str) -> Optional[ToolInfo]:
    """Retrieve tool metadata by tool name."""
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[ToolInfo]:
    """List all registered tools."""
    return list(TOOL_REGISTRY.values())


def get_tools_for_skill(skill_id: str) -> list[ToolInfo]:
    """Retrieve all ToolInfo objects exposed by a specific skill in the atlas catalog."""
    skills = get_seeded_skills()
    matching_skill = next((s for s in skills if s.id == skill_id), None)
    if not matching_skill:
        return []

    tools: list[ToolInfo] = []
    for tool_name in matching_skill.exposes:
        tool_info = get_tool(tool_name)
        if tool_info:
            tools.append(tool_info)
    return tools
