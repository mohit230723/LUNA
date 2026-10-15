"""Seed synthetic domain dataset into FalkorDB domain named graph."""

from typing import Any
from luna.graph.schema import GRAPH_DOMAIN
from luna.graph.store import GraphStore
from luna.domain.generate import GroundTruth, generate_insurance_dataset


def seed_domain(store: GraphStore, seed: int = 42) -> GroundTruth:
    """Populate domain graph in FalkorDB with synthetic insurance data."""
    dataset, ground_truth = generate_insurance_dataset(seed=seed)

    # Recreate clean domain graph
    store.delete_graph(GRAPH_DOMAIN)

    # Group nodes by label for parameterized batch creation
    nodes_by_label: dict[str, list[dict[str, Any]]] = {}
    for node in dataset["nodes"]:
        label = node["label"]
        nodes_by_label.setdefault(label, []).append(node["properties"])

    for label, batch in nodes_by_label.items():
        # Parameterized query using $batch
        query = f"UNWIND $batch AS props CREATE (n:{label}) SET n += props"
        store.query(GRAPH_DOMAIN, query, {"batch": batch})

    # Group edges by relationship type for parameterized batch creation
    edges_by_rel: dict[str, list[dict[str, Any]]] = {}
    for edge in dataset["edges"]:
        rel = edge["rel_type"]
        edges_by_rel.setdefault(rel, []).append({
            "source": edge["source_cid"],
            "target": edge["target_cid"],
            "props": edge.get("properties", {}),
        })

    for rel, batch in edges_by_rel.items():
        query = (
            f"UNWIND $batch AS item "
            f"MATCH (a {{cid: item.source}}), (b {{cid: item.target}}) "
            f"CREATE (a)-[r:{rel}]->(b) SET r += item.props"
        )
        store.query(GRAPH_DOMAIN, query, {"batch": batch})

    return ground_truth
