"""Deterministic graph algorithm tools for sub-agent investigations."""

from typing import Any, Optional
import networkx as nx
from luna.graph.store import GraphStore


def shared_attribute_links(
    store: GraphStore,
    graph_name: str,
    cid: str,
    attr_types: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Find entities connected to the same attributes (e.g. Phone, BankAccount, Address) as cid.

    Args:
        store: GraphStore connection wrapper
        graph_name: Target graph name (e.g. agent slice or domain)
        cid: Anchor entity CID
        attr_types: Optional list of attribute labels to restrict to (e.g. ['Phone', 'BankAccount'])

    Returns:
        List of dicts documenting shared attribute connections.
    """
    attr_labels = attr_types or []
    query = (
        "MATCH (c1 {cid: $cid})-[r1]->(a)<-[r2]-(c2) "
        "WHERE c1 <> c2 AND (size($attr_labels) = 0 OR labels(a)[0] IN $attr_labels) "
        "RETURN c2.cid AS shared_cid, labels(c2)[0] AS shared_label, "
        "       labels(a)[0] AS attribute_type, a.cid AS attribute_cid, "
        "       type(r1) AS rel_out, type(r2) AS rel_in"
    )
    return store.query(graph_name, query, {"cid": cid, "attr_labels": attr_labels})


def connected_components(
    store: GraphStore,
    graph_name: str,
    cids: list[str],
    rel_types: Optional[list[str]] = None,
) -> list[list[str]]:
    """Compute connected component clusters among specified entity CIDs.

    Connections can be direct edges or shared 2-hop attribute links.

    Args:
        store: GraphStore connection wrapper
        graph_name: Target graph name
        cids: List of entity CIDs to cluster
        rel_types: Optional attribute labels or relationship types to filter on

    Returns:
        List of connected clusters (each cluster is a list of CIDs, sorted largest first).
    """
    if not cids:
        return []

    labels_filter = rel_types or []

    # Query 2-hop connections through shared attributes between any two cids in the list
    query = (
        "MATCH (c1)-[r1]->(a)<-[r2]-(c2) "
        "WHERE c1.cid IN $cids AND c2.cid IN $cids AND c1 <> c2 "
        "  AND (size($labels_filter) = 0 OR labels(a)[0] IN $labels_filter) "
        "RETURN c1.cid AS source, c2.cid AS target, labels(a)[0] AS via"
    )
    rows = store.query(graph_name, query, {"cids": cids, "labels_filter": labels_filter})

    # Construct NetworkX graph for deterministic clustering
    g = nx.Graph()
    for cid in cids:
        g.add_node(cid)

    for row in rows:
        src = row.get("source")
        tgt = row.get("target")
        if src and tgt:
            g.add_edge(src, tgt)

    components = [sorted(list(c)) for c in nx.connected_components(g)]
    components.sort(key=len, reverse=True)
    return components


def pagerank_top(
    store: GraphStore,
    graph_name: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Calculate PageRank centrality across all nodes in the target graph.

    Args:
        store: GraphStore connection wrapper
        graph_name: Target graph name
        limit: Number of top central entities to return

    Returns:
        List of dicts containing 'cid' and 'score', sorted by score descending.
    """
    query = "MATCH (a)-[r]->(b) RETURN a.cid AS source, b.cid AS target"
    rows = store.query(graph_name, query, {})

    if not rows:
        return []

    g = nx.DiGraph()
    for row in rows:
        src = row.get("source")
        tgt = row.get("target")
        if src and tgt:
            g.add_edge(src, tgt)

    if len(g) == 0:
        return []

    try:
        ranks = nx.pagerank(g, alpha=0.85)
    except Exception:
        # Fallback to degree centrality if convergence fails or graph is disconnected
        ranks = nx.degree_centrality(g)

    sorted_ranks = sorted(ranks.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"cid": cid, "score": round(score, 6)} for cid, score in sorted_ranks]


def shortest_path(
    store: GraphStore,
    graph_name: str,
    source_cid: str,
    target_cid: str,
) -> list[dict[str, Any]]:
    """Find the shortest connection path between two entities.

    Args:
        store: GraphStore connection wrapper
        graph_name: Target graph name
        source_cid: Origin entity CID
        target_cid: Destination entity CID

    Returns:
        List containing path hops and entity CIDs.
    """
    query = (
        "MATCH (a {cid: $source_cid}), (b {cid: $target_cid}) "
        "WITH shortestPath((a)-[*]-(b)) AS p "
        "RETURN [n in nodes(p) | n.cid] AS path_cids, "
        "       [r in relationships(p) | type(r)] AS rel_types, "
        "       length(p) AS length"
    )
    rows = store.query(graph_name, query, {"source_cid": source_cid, "target_cid": target_cid})
    if rows:
        return rows

    # Fallback to NetworkX in-memory pathfinding over the graph slice
    edge_query = "MATCH (a)-[r]-(b) RETURN a.cid AS source, b.cid AS target, type(r) AS rel"
    edge_rows = store.query(graph_name, edge_query, {})

    g = nx.Graph()
    for row in edge_rows:
        src = row.get("source")
        tgt = row.get("target")
        if src and tgt:
            g.add_edge(src, tgt, rel=row.get("rel", ""))

    if source_cid in g and target_cid in g and nx.has_path(g, source_cid, target_cid):
        path = nx.shortest_path(g, source_cid, target_cid)
        return [{"path_cids": path, "length": len(path) - 1}]

    return []


def claim_amount_outliers(
    store: GraphStore,
    graph_name: str,
    std_dev_threshold: float = 2.0,
) -> list[dict[str, Any]]:
    """Detect statistical claim amount outliers exceeding mean + threshold * std_dev.

    Args:
        store: GraphStore connection wrapper
        graph_name: Target graph name
        std_dev_threshold: Number of standard deviations above mean to flag

    Returns:
        List of outlier claims with metadata and statistics.
    """
    query = "MATCH (c:InsuranceClaim) RETURN c.cid AS claim_cid, c.amount AS amount"
    rows = store.query(graph_name, query, {})

    if not rows:
        return []

    amounts = [float(r["amount"]) for r in rows if r.get("amount") is not None]
    if not amounts:
        return []

    n = len(amounts)
    mean = sum(amounts) / n
    variance = sum((x - mean) ** 2 for x in amounts) / n
    std_dev = variance ** 0.5
    cutoff = mean + std_dev_threshold * std_dev

    outliers: list[dict[str, Any]] = []
    for r in rows:
        amt = float(r.get("amount", 0.0))
        if amt > cutoff:
            outliers.append({
                "claim_cid": r["claim_cid"],
                "amount": amt,
                "mean": round(mean, 2),
                "std_dev": round(std_dev, 2),
                "cutoff": round(cutoff, 2),
            })

    outliers.sort(key=lambda x: x["amount"], reverse=True)
    return outliers
