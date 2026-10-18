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
    use_native: Optional[bool] = None,
) -> list[list[str]]:
    """Compute connected component clusters among specified entity CIDs.

    Connections can be direct edges or shared 2-hop attribute links.

    Args:
        store: GraphStore connection wrapper
        graph_name: Target graph name
        cids: List of entity CIDs to cluster
        rel_types: Optional attribute labels or relationship types to filter on
        use_native: True for native algo.WCC, False for NetworkX, None for auto-detect

    Returns:
        List of connected clusters (each cluster is a list of CIDs, sorted largest first).
    """
    if not cids:
        return []

    should_use_native = (
        use_native
        if use_native is not None
        else (hasattr(store, "supports_procedure") and store.supports_procedure("algo.WCC") and not rel_types)
    )

    if should_use_native:
        try:
            wcc_query = "CALL algo.WCC() YIELD node, componentId RETURN node.cid AS cid, componentId"
            rows = store.query(graph_name, wcc_query)
            cids_set = set(cids)
            comps_by_id: dict[Any, set[str]] = {}
            seen_cids: set[str] = set()
            for r in rows:
                cid = r.get("cid")
                if cid and cid in cids_set:
                    comps_by_id.setdefault(r["componentId"], set()).add(cid)
                    seen_cids.add(cid)

            result_comps = [sorted(list(c)) for c in comps_by_id.values()]
            unseen = cids_set - seen_cids
            for u in sorted(unseen):
                result_comps.append([u])

            result_comps.sort(key=len, reverse=True)
            return result_comps
        except Exception:
            pass

    # NetworkX fallback
    labels_filter = rel_types or []
    query = (
        "MATCH (c1)-[r1]->(a)<-[r2]-(c2) "
        "WHERE c1.cid IN $cids AND c2.cid IN $cids AND c1 <> c2 "
        "  AND (size($labels_filter) = 0 OR labels(a)[0] IN $labels_filter) "
        "RETURN c1.cid AS source, c2.cid AS target, labels(a)[0] AS via"
    )
    rows = store.query(graph_name, query, {"cids": cids, "labels_filter": labels_filter})

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
    node_label: Optional[str] = None,
    rel_type: Optional[str] = None,
    use_native: Optional[bool] = None,
) -> list[dict[str, Any]]:
    """Calculate PageRank centrality across nodes in the target graph.

    Args:
        store: GraphStore connection wrapper
        graph_name: Target graph name
        limit: Number of top central entities to return
        node_label: Target node label for native algo.pageRank
        rel_type: Target relationship type for native algo.pageRank
        use_native: True for native algo.pageRank, False for NetworkX, None for auto-detect

    Returns:
        List of dicts containing 'cid' and 'score', sorted by score descending.
    """
    should_use_native = (
        use_native
        if use_native is not None
        else (hasattr(store, "supports_procedure") and store.supports_procedure("algo.pageRank") and bool(node_label and rel_type))
    )

    if should_use_native and node_label and rel_type:
        try:
            query = (
                f"CALL algo.pageRank('{node_label}', '{rel_type}') YIELD node, score "
                f"RETURN node.cid AS cid, score ORDER BY score DESC LIMIT $limit"
            )
            rows = store.query(graph_name, query, {"limit": limit})
            if rows:
                return [{"cid": r["cid"], "score": round(float(r["score"]), 6)} for r in rows if r.get("cid")]
        except Exception:
            pass

    # NetworkX fallback
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
        ranks = nx.degree_centrality(g)

    sorted_ranks = sorted(ranks.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"cid": cid, "score": round(score, 6)} for cid, score in sorted_ranks]


def shortest_path(
    store: GraphStore,
    graph_name: str,
    source_cid: str,
    target_cid: str,
    use_native: Optional[bool] = None,
) -> list[dict[str, Any]]:
    """Find the shortest connection path between two entities.

    Args:
        store: GraphStore connection wrapper
        graph_name: Target graph name
        source_cid: Origin entity CID
        target_cid: Destination entity CID
        use_native: True for native Cypher shortestPath, False for NetworkX fallback

    Returns:
        List containing path hops and entity CIDs.
    """
    should_use_native = use_native if use_native is not None else True

    if should_use_native:
        try:
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
        except Exception:
            pass

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


def trace_connections(
    store: GraphStore,
    graph_name: str,
    src_cid: str,
    max_hops: int = 4,
    via_labels: Optional[list[str]] = None,
    limit_paths: int = 5,
) -> list[dict[str, Any]]:
    """Trace multi-hop connection paths outward from src_cid up to max_hops.

    Returns list of discovered paths with nodes, relationships, and hop counts,
    ranked by length and centrality.
    """
    edge_query = (
        "MATCH (a)-[r]-(b) "
        "RETURN a.cid AS source, b.cid AS target, type(r) AS rel"
    )
    edge_rows = store.query(graph_name, edge_query, {})

    g = nx.Graph()
    for row in edge_rows:
        src = row.get("source")
        tgt = row.get("target")
        rel = row.get("rel", "")
        if src and tgt:
            g.add_edge(src, tgt, rel=rel)

    if src_cid not in g:
        return []

    # BFS outward from src_cid up to max_hops
    paths: list[dict[str, Any]] = []
    all_paths = nx.single_source_shortest_path(g, src_cid, cutoff=max_hops)

    for target_cid, path in all_paths.items():
        if target_cid == src_cid:
            continue
        rel_types = []
        for i in range(len(path) - 1):
            edge_data = g.get_edge_data(path[i], path[i + 1])
            rel_types.append(edge_data.get("rel", "") if edge_data else "")

        paths.append({
            "target_cid": target_cid,
            "hops": len(path) - 1,
            "path": path,
            "rel_types": rel_types,
        })

    # Sort paths by hop count (shorter first)
    paths.sort(key=lambda p: (p["hops"], p["target_cid"]))
    return paths[:limit_paths]


def find_suspect_links(
    store: GraphStore,
    graph_name: str,
    cids: list[str],
    min_strength: int = 1,
) -> list[dict[str, Any]]:
    """Find shared links connecting pairs among cids with connection strength."""
    if not cids:
        return []

    query = (
        "MATCH (c1)-[r1]->(a)<-[r2]-(c2) "
        "WHERE c1.cid IN $cids AND c2.cid IN $cids AND c1.cid < c2.cid "
        "RETURN c1.cid AS src_cid, c2.cid AS dst_cid, labels(a)[0] AS attr_label, a.cid AS attr_cid, type(r1) AS r1, type(r2) AS r2"
    )
    rows = store.query(graph_name, query, {"cids": cids})

    pair_links: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        pair = (r["src_cid"], r["dst_cid"])
        pair_links.setdefault(pair, []).append({
            "attr_label": r.get("attr_label"),
            "attr_cid": r.get("attr_cid"),
            "r1": r.get("r1"),
            "r2": r.get("r2"),
        })

    result: list[dict[str, Any]] = []
    for (src, dst), links in pair_links.items():
        if len(links) >= min_strength:
            result.append({
                "src_cid": src,
                "dst_cid": dst,
                "strength": len(links),
                "shared_attributes": links,
            })

    result.sort(key=lambda x: x["strength"], reverse=True)
    return result
