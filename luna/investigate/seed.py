"""Seed investigation capabilities and skills for context graph analysis."""

from __future__ import annotations

from typing import Optional
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_CAPABILITY,
    LABEL_SKILL,
    LABEL_TOOL,
    LABEL_PACK,
    REL_PROVIDES,
    REL_EXPOSES,
    REL_IN_PACK,
)
from luna.graph.store import GraphStore

INVESTIGATION_CAPABILITIES = [
    ("trace_relationships", "Find connection paths and immediate neighbors between entities."),
    ("find_shared_attributes", "Detect shared accounts, phones, addresses, or attributes."),
    ("detect_clusters", "Discover graph components, communities, and high-influence nodes."),
    ("build_timeline", "Assemble chronological sequences of events and dated records."),
    ("check_sources", "Verify claims against exact source document quotes and locators."),
    ("query_graph", "Translate natural language questions into read-only graph queries."),
]

INVESTIGATION_SKILLS = [
    {
        "id": "relationship-tracer",
        "name": "Relationship Tracer",
        "capability": "trace_relationships",
        "tools": ["neighbors", "paths_between", "shortest_path"],
        "prompt_fragment": "Explore multi-hop paths and neighboring connections between target entities.",
        "prior": 0.85,
    },
    {
        "id": "shared-attribute-finder",
        "name": "Shared Attribute Finder",
        "capability": "find_shared_attributes",
        "tools": ["shared_attributes", "common_neighbors"],
        "prompt_fragment": "Identify intermediary entities linked to two or more target subjects.",
        "prior": 0.85,
    },
    {
        "id": "cluster-detector",
        "name": "Cluster Detector",
        "capability": "detect_clusters",
        "tools": ["cluster_of", "central_nodes"],
        "prompt_fragment": "Evaluate connected components and discover influential hub entities in the network.",
        "prior": 0.80,
    },
    {
        "id": "timeline-builder",
        "name": "Timeline Builder",
        "capability": "build_timeline",
        "tools": ["timeline"],
        "prompt_fragment": "Construct chronological timelines of events, transactions, and dated properties.",
        "prior": 0.80,
    },
    {
        "id": "source-checker",
        "name": "Source Checker",
        "capability": "check_sources",
        "tools": ["source_mentions"],
        "prompt_fragment": "Inspect source document quotes and verify factual statements against original text.",
        "prior": 0.90,
    },
    {
        "id": "graph-qa",
        "name": "Graph QA",
        "capability": "query_graph",
        "tools": ["ask_graph"],
        "prompt_fragment": "Query the graph using synthesized read-only Cypher statements.",
        "prior": 0.75,
    },
]


def seed_investigation_atlas(store: Optional[GraphStore] = None, atlas_graph: str = GRAPH_ATLAS) -> None:
    """Idempotently seed investigation capabilities, tools, and skills into atlas."""
    s = store or GraphStore()

    # 1. Ensure Pack node exists
    s.query(
        atlas_graph,
        f"MERGE (p:{LABEL_PACK} {{name: 'investigate'}}) "
        "SET p.title = 'Investigate Pack', p.description = 'Graph investigation and entity tracing'",
    )

    # 2. Seed Capabilities
    for cap_name, desc in INVESTIGATION_CAPABILITIES:
        s.query(
            atlas_graph,
            f"MERGE (c:{LABEL_CAPABILITY} {{name: $name}}) "
            "ON CREATE SET c.description = $desc",
            {"name": cap_name, "desc": desc},
        )

    # 3. Seed Skills and Tools
    for sk in INVESTIGATION_SKILLS:
        s.query(
            atlas_graph,
            f"MERGE (k:{LABEL_SKILL} {{id: $id}}) "
            f"ON CREATE SET k.name = $name, k.prompt_fragment = $prompt, k.prior = $prior, "
            f"              k.restricted = false, k.runs = 0, k.score = $prior "
            f"WITH k "
            f"MATCH (p:{LABEL_PACK} {{name: 'investigate'}}) "
            f"MERGE (k)-[:{REL_IN_PACK}]->(p) "
            f"WITH k "
            f"MATCH (c:{LABEL_CAPABILITY} {{name: $cap}}) "
            f"MERGE (k)-[:{REL_PROVIDES}]->(c)",
            {
                "id": sk["id"],
                "name": sk["name"],
                "prompt": sk["prompt_fragment"],
                "prior": sk["prior"],
                "cap": sk["capability"],
            },
        )

        for tool_name in sk["tools"]:
            s.query(
                atlas_graph,
                f"MERGE (t:{LABEL_TOOL} {{name: $name}}) "
                f"WITH t "
                f"MATCH (k:{LABEL_SKILL} {{id: $sk_id}}) "
                f"MERGE (k)-[:{REL_EXPOSES}]->(t)",
                {"name": tool_name, "sk_id": sk["id"]},
            )
