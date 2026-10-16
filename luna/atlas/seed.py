"""Seed the atlas skill catalog graph in FalkorDB with skills, capabilities, and tools."""

from typing import Any
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_CAPABILITY,
    LABEL_SKILL,
    LABEL_TOOL,
    LABEL_TASK_TYPE,
    REL_PROVIDES,
    REL_REQUIRES,
    REL_EXPOSES,
    REL_SUCCEEDED_ON,
)
from luna.graph.store import GraphStore
from luna.atlas.models import CapabilityDef, ToolDef, SkillDef, SkillScore


def get_seeded_capabilities() -> list[CapabilityDef]:
    """Return catalog of standardized capabilities."""
    return [
        CapabilityDef(name="link_entities", description="Link entities by shared identifiers or attributes"),
        CapabilityDef(name="detect_communities", description="Detect graph clusters and connected components"),
        CapabilityDef(name="rank_influence", description="Rank entity centrality and graph influence"),
        CapabilityDef(name="explain_connection", description="Trace and articulate shortest connection paths"),
        CapabilityDef(name="detect_amount_anomalies", description="Detect statistical outliers in transaction amounts"),
    ]


def get_seeded_tools() -> list[ToolDef]:
    """Return catalog of available tools."""
    return [
        ToolDef(name="shared_attribute_links", description="Find entities sharing phone, bank account, or address"),
        ToolDef(name="connected_components", description="Compute connected component clusters over entities"),
        ToolDef(name="pagerank_top", description="Find top nodes by PageRank or degree centrality"),
        ToolDef(name="shortest_path", description="Compute shortest path between two entities"),
        ToolDef(name="claim_amount_outliers", description="Identify claim amounts exceeding statistical thresholds"),
        ToolDef(name="ask_graph", description="Natural language Cypher query tool via GraphRAG SDK"),
    ]


def get_seeded_skills() -> list[SkillDef]:
    """Return catalog of 7 core equipable skills."""
    return [
        SkillDef(
            id="entity-linker",
            name="Entity Linker",
            prompt_fragment="Report any customer sharing any attribute (phone, bank account, address) as suspicious with confidence 0.60 to 0.70.",
            capabilities=["link_entities"],
            requires=[],
            exposes=["shared_attribute_links", "ask_graph"],
            restricted=False,
            scores=[SkillScore(task_type="fraud_ring_investigation", score=0.70, runs=5)],
        ),
        SkillDef(
            id="bulk-linker",
            name="Bulk Linker",
            prompt_fragment="Link all entities with matching identifiers indiscriminately.",
            capabilities=["link_entities"],
            requires=[],
            exposes=["shared_attribute_links", "ask_graph"],
            restricted=True,
            scores=[SkillScore(task_type="fraud_ring_investigation", score=0.95, runs=10)],
        ),
        SkillDef(
            id="ring-detector",
            name="Fraud Ring Detector",
            prompt_fragment="Analyze attribute clusters. A customer connected to others only through Address is benign with confidence 0.75 to 0.85; customers connected through BankAccount or Phone are suspicious.",
            capabilities=["detect_communities"],
            requires=["entity-linker"],
            exposes=["connected_components", "ask_graph"],
            restricted=False,
            scores=[SkillScore(task_type="fraud_ring_investigation", score=0.80, runs=8)],
        ),
        SkillDef(
            id="ring-detector-lite",
            name="Ring Detector Lite",
            prompt_fragment="Detect basic components without secondary heuristic validation.",
            capabilities=["detect_communities"],
            requires=[],
            exposes=["connected_components", "ask_graph"],
            restricted=False,
            scores=[SkillScore(task_type="fraud_ring_investigation", score=0.50, runs=4)],
        ),
        SkillDef(
            id="influence-ranker",
            name="Influence Ranker",
            prompt_fragment="Identify high centrality hubs and orchestrators across graph edges.",
            capabilities=["rank_influence"],
            requires=[],
            exposes=["pagerank_top", "ask_graph"],
            restricted=False,
            scores=[SkillScore(task_type="fraud_ring_investigation", score=0.60, runs=6)],
        ),
        SkillDef(
            id="path-explainer",
            name="Path Explainer",
            prompt_fragment="Trace and articulate the shortest evidence paths between entities.",
            capabilities=["explain_connection"],
            requires=[],
            exposes=["shortest_path", "ask_graph"],
            restricted=False,
            scores=[SkillScore(task_type="fraud_ring_investigation", score=0.60, runs=6)],
        ),
        SkillDef(
            id="anomaly-scout",
            name="Anomaly Scout",
            prompt_fragment="Flag statistical claim amount outliers across providers.",
            capabilities=["detect_amount_anomalies"],
            requires=[],
            exposes=["claim_amount_outliers", "ask_graph"],
            restricted=False,
            scores=[SkillScore(task_type="fraud_ring_investigation", score=0.60, runs=5)],
        ),
    ]


def seed_atlas(store: GraphStore) -> None:
    """Recreate and seed the atlas skill catalog graph in FalkorDB."""
    store.delete_graph(GRAPH_ATLAS)

    # 1. Create Capabilities
    caps = get_seeded_capabilities()
    store.query(
        GRAPH_ATLAS,
        f"UNWIND $batch AS c CREATE (n:{LABEL_CAPABILITY}) SET n += c",
        {"batch": [c.model_dump() for c in caps]},
    )

    # 2. Create Tools
    tools = get_seeded_tools()
    store.query(
        GRAPH_ATLAS,
        f"UNWIND $batch AS t CREATE (n:{LABEL_TOOL}) SET n += t",
        {"batch": [t.model_dump() for t in tools]},
    )

    # 3. Create TaskType
    store.query(
        GRAPH_ATLAS,
        f"MERGE (t:{LABEL_TASK_TYPE} {{name: $name}})",
        {"name": "fraud_ring_investigation"},
    )

    # 4. Create Skills
    skills = get_seeded_skills()
    skill_nodes: list[dict[str, Any]] = []
    provides_edges: list[dict[str, str]] = []
    requires_edges: list[dict[str, str]] = []
    exposes_edges: list[dict[str, str]] = []
    succeeded_edges: list[dict[str, Any]] = []

    for s in skills:
        skill_nodes.append({
            "id": s.id,
            "name": s.name,
            "prompt_fragment": s.prompt_fragment,
            "restricted": s.restricted,
        })
        for cap in s.capabilities:
            provides_edges.append({"skill_id": s.id, "cap_name": cap})
        for req in s.requires:
            requires_edges.append({"skill_id": s.id, "req_id": req})
        for tool in s.exposes:
            exposes_edges.append({"skill_id": s.id, "tool_name": tool})
        for score in s.scores:
            succeeded_edges.append({
                "skill_id": s.id,
                "task_type": score.task_type,
                "score": score.score,
                "runs": score.runs,
            })

    # Batch write Skill nodes
    store.query(
        GRAPH_ATLAS,
        f"UNWIND $batch AS s CREATE (n:{LABEL_SKILL}) SET n += s",
        {"batch": skill_nodes},
    )

    # Batch write PROVIDES edges
    store.query(
        GRAPH_ATLAS,
        f"UNWIND $batch AS item "
        f"MATCH (s:{LABEL_SKILL} {{id: item.skill_id}}), (c:{LABEL_CAPABILITY} {{name: item.cap_name}}) "
        f"CREATE (s)-[:{REL_PROVIDES}]->(c)",
        {"batch": provides_edges},
    )

    # Batch write REQUIRES edges
    if requires_edges:
        store.query(
            GRAPH_ATLAS,
            f"UNWIND $batch AS item "
            f"MATCH (s:{LABEL_SKILL} {{id: item.skill_id}}), (req:{LABEL_SKILL} {{id: item.req_id}}) "
            f"CREATE (s)-[:{REL_REQUIRES}]->(req)",
            {"batch": requires_edges},
        )

    # Batch write EXPOSES edges
    store.query(
        GRAPH_ATLAS,
        f"UNWIND $batch AS item "
        f"MATCH (s:{LABEL_SKILL} {{id: item.skill_id}}), (t:{LABEL_TOOL} {{name: item.tool_name}}) "
        f"CREATE (s)-[:{REL_EXPOSES}]->(t)",
        {"batch": exposes_edges},
    )

    # Batch write SUCCEEDED_ON edges
    store.query(
        GRAPH_ATLAS,
        f"UNWIND $batch AS item "
        f"MATCH (s:{LABEL_SKILL} {{id: item.skill_id}}), (t:{LABEL_TASK_TYPE} {{name: item.task_type}}) "
        f"CREATE (s)-[:{REL_SUCCEEDED_ON} {{score: item.score, runs: item.runs}}]->(t)",
        {"batch": succeeded_edges},
    )
