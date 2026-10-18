"""Compute GraphStats and warnings for an ingested context graph."""

from __future__ import annotations

from typing import Any, Optional
from luna.graph.store import GraphStore
from luna.ingest.models import GraphStats, TopEntity, ExtractionStats


def compute_graph_summary(
    store: GraphStore,
    graph_name: str,
    sources_count: int,
    extraction_stats: Optional[ExtractionStats] = None,
    extra_warnings: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Calculate node/edge counts, label distributions, top-degree entities, and compilation warnings."""
    warnings = list(extra_warnings or [])

    # Labels distribution (exclude Source)
    by_label: dict[str, int] = {}
    try:
        label_rows = store.query(
            graph_name,
            "MATCH (n) WHERE NOT n:Source "
            "RETURN labels(n)[0] AS lbl, count(n) AS cnt "
            "ORDER BY cnt DESC",
        )
        for r in label_rows:
            lbl = r.get("lbl")
            if lbl:
                by_label[lbl] = int(r.get("cnt") or 0)
    except Exception:
        pass

    total_nodes = sum(by_label.values())

    # Relationship distribution (exclude MENTIONED_IN)
    by_rel: dict[str, int] = {}
    try:
        rel_rows = store.query(
            graph_name,
            "MATCH ()-[r]->() WHERE type(r) <> 'MENTIONED_IN' "
            "RETURN type(r) AS rel, count(r) AS cnt "
            "ORDER BY cnt DESC",
        )
        for r in rel_rows:
            rel = r.get("rel")
            if rel:
                by_rel[rel] = int(r.get("cnt") or 0)
    except Exception:
        pass

    total_edges = sum(by_rel.values())

    # Top 8 entities by degree
    top_entities: list[dict[str, Any]] = []
    try:
        degree_rows = store.query(
            graph_name,
            "MATCH (n) WHERE NOT n:Source "
            "OPTIONAL MATCH (n)-[r]-() WHERE type(r) <> 'MENTIONED_IN' "
            "RETURN n.cid AS cid, n.name AS name, labels(n)[0] AS type, count(r) AS degree "
            "ORDER BY degree DESC LIMIT 8",
        )
        for r in degree_rows:
            cid = r.get("cid")
            if cid:
                top_entities.append({
                    "cid": cid,
                    "name": r.get("name") or cid,
                    "type": r.get("type") or "Entity",
                    "degree": int(r.get("degree") or 0),
                })
    except Exception:
        pass

    # Append extraction warnings
    if extraction_stats:
        if extraction_stats.entities_dropped > 0:
            warnings.append(
                f"{extraction_stats.entities_dropped} extracted items were dropped because their quotes did not match the text"
            )
        failed_chunks = extraction_stats.chunks_total - extraction_stats.chunks_ok
        if failed_chunks > 0:
            warnings.append(f"{failed_chunks} chunks failed extraction and were skipped")

    return {
        "nodes": total_nodes,
        "edges": total_edges,
        "sources": sources_count,
        "by_label": by_label,
        "by_rel": by_rel,
        "top_entities": top_entities,
        "warnings": warnings,
        "extraction": extraction_stats.model_dump() if extraction_stats else None,
    }
