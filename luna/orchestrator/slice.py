"""Sub-graph slice extraction logic isolating k-hop induced subgraphs into private agent graphs."""

import re
from typing import Any, Optional
from luna.graph.store import GraphStore

# Strict whitelist of allowed node labels and relationship types to prevent Cypher injection
SAFE_LABEL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
SAFE_REL_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _sanitize_identifier(name: str, pattern: re.Pattern) -> str:
    """Validate that a label or relationship type matches safe identifier rules."""
    if not name or not pattern.match(name):
        raise ValueError(f"Unsafe graph identifier rejected: '{name}'")
    return name


def extract_subgraph_slice(
    store: GraphStore,
    source_graph: str,
    target_graph: str,
    seed_cids: list[str],
    k_hops: int = 2,
    max_nodes: int = 2000,
) -> dict[str, Any]:
    """Extract a k-hop induced subgraph centered on seed_cids from source_graph into target_graph.

    Args:
        store: GraphStore connection wrapper
        source_graph: Graph name to extract from (e.g. 'domain')
        target_graph: Dedicated private graph name (e.g. 'agent_<run>_<agent>')
        seed_cids: List of anchor entity CIDs
        k_hops: Number of traversal hops (default: 2)

    Returns:
        Summary dict containing counts and metadata.
    """
    if not seed_cids:
        raise ValueError("seed_cids cannot be empty")
    if k_hops < 0 or k_hops > 5:
        raise ValueError("k_hops must be between 0 and 5")

    # Step 1: Collect seed nodes
    seed_query = (
        "MATCH (anchor) WHERE anchor.cid IN $seed_cids "
        "RETURN DISTINCT labels(anchor)[0] AS label, properties(anchor) AS props"
    )
    seed_rows = store.query(source_graph, seed_query, {"seed_cids": seed_cids})

    nodes_by_cid: dict[str, dict[str, Any]] = {}
    for row in seed_rows:
        props = row.get("props") or {}
        cid = props.get("cid")
        if cid:
            nodes_by_cid[cid] = {
                "label": row.get("label") or "Entity",
                "props": props,
            }

    # Step 2: If k_hops >= 1, collect k-hop neighborhood nodes
    if k_hops >= 1:
        hop_pattern = f"[*1..{k_hops}]"
        hop_query = (
            f"MATCH path = (anchor)-{hop_pattern}-(n) "
            "WHERE anchor.cid IN $seed_cids "
            "UNWIND nodes(path) AS node "
            "RETURN DISTINCT labels(node)[0] AS label, properties(node) AS props"
        )
        hop_rows = store.query(source_graph, hop_query, {"seed_cids": seed_cids})
        for row in hop_rows:
            props = row.get("props") or {}
            cid = props.get("cid")
            if cid:
                nodes_by_cid[cid] = {
                    "label": row.get("label") or "Entity",
                    "props": props,
                }

    if not nodes_by_cid:
        return {
            "source_graph": source_graph,
            "target_graph": target_graph,
            "seed_cids": seed_cids,
            "k_hops": k_hops,
            "max_nodes": max_nodes,
            "truncated": False,
            "nodes_extracted": 0,
            "edges_extracted": 0,
            "extracted_cids": [],
        }

    all_cids = sorted(nodes_by_cid.keys())
    truncated = False
    if len(all_cids) > max_nodes:
        extracted_cids = all_cids[:max_nodes]
        truncated = True
        nodes_by_cid = {cid: nodes_by_cid[cid] for cid in extracted_cids}
    else:
        extracted_cids = all_cids

    # Step 3: Extract induced edges connecting extracted nodes
    edge_query = (
        "MATCH (a)-[r]->(b) "
        "WHERE a.cid IN $cids AND b.cid IN $cids "
        "RETURN a.cid AS from_cid, b.cid AS to_cid, type(r) AS rel_type, properties(r) AS props"
    )
    edge_rows = store.query(source_graph, edge_query, {"cids": extracted_cids})

    # Step 4: Recreate nodes in target_graph
    # Group nodes by label for safe batch insertion
    nodes_by_label: dict[str, list[dict[str, Any]]] = {}
    for item in nodes_by_cid.values():
        lbl = _sanitize_identifier(item["label"], SAFE_LABEL_PATTERN)
        nodes_by_label.setdefault(lbl, []).append(item["props"])

    for label, props_list in nodes_by_label.items():
        create_node_query = f"UNWIND $batch AS props CREATE (n:{label}) SET n = props"
        store.query(target_graph, create_node_query, {"batch": props_list})

    # Step 5: Recreate edges in target_graph
    # Group edges by rel_type for safe batch insertion
    edges_by_type: dict[str, list[dict[str, Any]]] = {}
    for r in edge_rows:
        rel_type = _sanitize_identifier(r["rel_type"], SAFE_REL_PATTERN)
        edges_by_type.setdefault(rel_type, []).append({
            "from_cid": r["from_cid"],
            "to_cid": r["to_cid"],
            "props": r.get("props") or {},
        })

    for rel_type, edge_list in edges_by_type.items():
        create_edge_query = (
            "UNWIND $batch AS edge "
            "MATCH (a {cid: edge.from_cid}), (b {cid: edge.to_cid}) "
            f"CREATE (a)-[r:{rel_type}]->(b) "
            "SET r = edge.props"
        )
        store.query(target_graph, create_edge_query, {"batch": edge_list})

    return {
        "source_graph": source_graph,
        "target_graph": target_graph,
        "seed_cids": seed_cids,
        "k_hops": k_hops,
        "max_nodes": max_nodes,
        "truncated": truncated,
        "nodes_extracted": len(nodes_by_cid),
        "edges_extracted": len(edge_rows),
        "extracted_cids": extracted_cids,
    }
