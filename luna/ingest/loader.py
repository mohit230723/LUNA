"""FalkorDB graph loader executing parameterized UNWIND batches and creating indices."""

from __future__ import annotations

import json
import re
from typing import Any
from luna.graph.store import GraphStore
from luna.ingest.resolve import ResolvedNode, ResolvedEdge

SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,40}$")


def sanitize_label(label: str) -> str:
    """Ensure label matches safe Cypher identifier regex."""
    clean = re.sub(r"[^A-Za-z0-9_]", "", label)
    if not clean or not clean[0].isalpha():
        clean = f"Entity_{clean}"
    return clean[:40]


def sanitize_rel(rel: str) -> str:
    """Ensure relationship type matches uppercase Cypher identifier regex."""
    clean = re.sub(r"[^A-Za-z0-9_]", "", rel.upper())
    if not clean or not clean[0].isalpha():
        clean = f"REL_{clean}"
    return clean[:40]


def load_context_graph(
    store: GraphStore,
    graph_name: str,
    nodes: list[ResolvedNode],
    edges: list[ResolvedEdge],
    possible_duplicates: list[tuple[str, str, float]],
    sources_info: list[dict[str, Any]],
    batch_size: int = 500,
) -> tuple[int, int]:
    """Load resolved nodes and edges into ctx_<id> FalkorDB graph.

    Returns:
        (nodes_loaded, edges_loaded)
    """
    # 1. Group nodes by label
    nodes_by_label: dict[str, list[dict[str, Any]]] = {}
    for n in nodes:
        lbl = sanitize_label(n.type)
        if lbl not in nodes_by_label:
            nodes_by_label[lbl] = []
        nodes_by_label[lbl].append({
            "cid": n.cid,
            "name": n.name,
            "type": n.type,
            "aliases": list(n.aliases),
            "source_ids": list(n.source_ids),
            "confidence": float(n.confidence),
            "props_json": json.dumps(n.props or {}),
        })

    total_nodes = 0
    # 2. Insert nodes by label with indices
    for lbl, label_nodes in nodes_by_label.items():
        # Ensure index on cid
        try:
            store.query(graph_name, f"CREATE INDEX ON :{lbl}(cid)")
        except Exception:
            pass

        for i in range(0, len(label_nodes), batch_size):
            batch = label_nodes[i : i + batch_size]
            cypher = (
                f"UNWIND $batch AS item "
                f"MERGE (n:{lbl} {{cid: item.cid}}) "
                f"ON CREATE SET n.name = item.name, n.type = item.type, "
                f"              n.aliases = item.aliases, n.source_ids = item.source_ids, "
                f"              n.confidence = item.confidence, n.props_json = item.props_json "
                f"ON MATCH SET n.name = item.name, n.aliases = item.aliases, "
                f"             n.source_ids = item.source_ids, n.props_json = item.props_json"
            )
            store.query(graph_name, cypher, {"batch": batch})
            total_nodes += len(batch)

    # 3. Create Source nodes
    if sources_info:
        store.query(
            graph_name,
            "UNWIND $sources AS s "
            "MERGE (src:Source {id: s.id}) "
            "SET src.name = s.name, src.kind = s.kind",
            {"sources": sources_info},
        )

    # 4. Group edges by relationship type
    edges_by_rel: dict[str, list[dict[str, Any]]] = {}
    for e in edges:
        r_type = sanitize_rel(e.rel)
        if r_type not in edges_by_rel:
            edges_by_rel[r_type] = []
        edges_by_rel[r_type].append({
            "src": e.src_cid,
            "dst": e.dst_cid,
            "source_id": e.source_id,
            "locator": e.locator[:200],
            "quote": e.quote[:200],
            "confidence": float(e.confidence),
            "method": e.method,
        })

    total_edges = 0
    # 5. Insert edges by relationship type
    for r_type, rel_edges in edges_by_rel.items():
        for i in range(0, len(rel_edges), batch_size):
            batch = rel_edges[i : i + batch_size]
            cypher = (
                f"UNWIND $batch AS item "
                f"MATCH (a {{cid: item.src}}) "
                f"MATCH (b {{cid: item.dst}}) "
                f"CREATE (a)-[r:{r_type} {{"
                f"  source_id: item.source_id, locator: item.locator, "
                f"  quote: item.quote, confidence: item.confidence, method: item.method"
                f"}}]->(b)"
            )
            store.query(graph_name, cypher, {"batch": batch})
            total_edges += len(batch)

    # 6. Insert MENTIONED_IN edges to Source nodes
    mention_batch = []
    for n in nodes:
        for q in n.quotes[:20]:
            mention_batch.append({
                "cid": n.cid,
                "src_id": q.get("source_id", ""),
                "locator": q.get("locator", "")[:200],
                "quote": q.get("quote", "")[:200],
            })

    for i in range(0, len(mention_batch), batch_size):
        batch = mention_batch[i : i + batch_size]
        cypher = (
            "UNWIND $batch AS item "
            "MATCH (a {cid: item.cid}) "
            "MATCH (s:Source {id: item.src_id}) "
            "CREATE (a)-[:MENTIONED_IN {locator: item.locator, quote: item.quote}]->(s)"
        )
        try:
            store.query(graph_name, cypher, {"batch": batch})
        except Exception:
            pass

    # 7. Insert POSSIBLY_SAME_AS edges for fuzzy matches
    dup_batch = []
    for src_cid, dst_cid, score in possible_duplicates:
        dup_batch.append({
            "src": src_cid,
            "dst": dst_cid,
            "score": round(score / 100.0, 2),
        })

    if dup_batch:
        cypher = (
            "UNWIND $batch AS item "
            "MATCH (a {cid: item.src}) "
            "MATCH (b {cid: item.dst}) "
            "CREATE (a)-[:POSSIBLY_SAME_AS {score: item.score}]->(b)"
        )
        try:
            store.query(graph_name, cypher, {"batch": dup_batch})
            total_edges += len(dup_batch)
        except Exception:
            pass

    return total_nodes, total_edges
