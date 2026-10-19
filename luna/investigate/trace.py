"""Trace response generation, explainability ('Why?'), and dynamic graph suggestions."""

from __future__ import annotations

import json
from typing import Any, Optional
from luna.graph.store import GraphStore
from luna.investigate.recorder import describe_edge



def resolve_run_graph(store: GraphStore, run_id: str) -> str:
    """Return the FalkorDB graph that holds a run.

    Investigation runs are stored as ``run_<run_id>`` where the id itself starts with ``run_``
    (e.g. ``run_run_ab12cd34``), while older pipelines normalise the prefix away. Pick whichever
    graph actually exists.
    """
    candidates = [f"run_{run_id}"]
    if run_id.startswith("run_"):
        candidates.append(run_id)
    try:
        existing = set(store.list_graphs())
    except Exception:
        return candidates[0]
    for name in candidates:
        if name in existing:
            return name
    return candidates[0]


def build_trace_response(
    store: GraphStore,
    run_id: str,
    ctx_graph: Optional[str] = None,
) -> dict[str, Any]:
    """Build the TraceResponse per Part 3.6 specifications."""
    run_graph = resolve_run_graph(store, run_id)

    # 1. Fetch TraversalStep nodes from run graph
    step_rows = store.query(
        run_graph,
        "MATCH (ts:TraversalStep) "
        "RETURN ts.seq AS seq, ts.tool AS tool, ts.agent_id AS agent_id, "
        "       ts.from_cid AS from_cid, ts.to_cid AS to_cid, ts.rel AS rel, "
        "       ts.note AS note, ts.edge_source_id AS source_id, "
        "       ts.edge_locator AS locator, ts.edge_quote AS quote "
        "ORDER BY ts.seq ASC",
    )
    all_recorded_steps = step_rows or []
    total_explored = len(all_recorded_steps)

    # 2. Fetch Answer and cited findings
    ans_rows = store.query(
        run_graph,
        "MATCH (a:Answer) RETURN a.cited_cids AS cited_cids, a.text AS text",
    )
    cited_cids = []
    if ans_rows and ans_rows[0].get("cited_cids"):
        raw_cited = ans_rows[0].get("cited_cids")
        if isinstance(raw_cited, list):
            cited_cids = raw_cited
        elif isinstance(raw_cited, str):
            try:
                cited_cids = json.loads(raw_cited)
            except Exception:
                pass

    # Fetch active findings
    finding_rows = store.query(
        run_graph,
        "MATCH (f:Finding) "
        "RETURN f.id AS id, f.kind AS kind, f.claim AS claim, "
        "       f.subject_cids AS subject_cids, f.evidence_cids AS evidence_cids, "
        "       f.confidence AS confidence, f.status AS status, "
        "       f.path_json AS path_json, f.agent_id AS agent_id, f.skill_id AS skill_id "
        "ORDER BY f.confidence DESC",
    )
    findings = []
    for fr in (finding_rows or []):
        sub_cids = fr.get("subject_cids") or []
        if isinstance(sub_cids, str):
            try:
                sub_cids = json.loads(sub_cids)
            except Exception:
                sub_cids = [sub_cids]
        ev_cids = fr.get("evidence_cids") or []
        if isinstance(ev_cids, str):
            try:
                ev_cids = json.loads(ev_cids)
            except Exception:
                ev_cids = [ev_cids]
        p_json = fr.get("path_json")
        path_list = []
        if p_json:
            try:
                path_list = json.loads(p_json) if isinstance(p_json, str) else p_json
            except Exception:
                path_list = []

        findings.append({
            "id": fr.get("id"),
            "kind": fr.get("kind"),
            "claim": fr.get("claim"),
            "subject_cids": sub_cids,
            "evidence_cids": ev_cids,
            "confidence": float(fr.get("confidence") or 0.0),
            "status": fr.get("status") or "active",
            "path": path_list,
            "agent_id": fr.get("agent_id") or "",
            "skill_id": fr.get("skill_id") or "",
        })

    # 3. Determine PRIMARY PATH steps
    # Active path/link findings cited in the answer, ranked by confidence
    primary_steps: list[dict[str, Any]] = []
    path_node_ids: list[str] = []

    # Map of edge hops to recorded step info for richer notes/sources
    hop_to_step: dict[tuple[str, str, str], dict[str, Any]] = {}
    for s in all_recorded_steps:
        key = (s.get("from_cid", ""), s.get("rel", ""), s.get("to_cid", ""))
        if key not in hop_to_step:
            hop_to_step[key] = s

    # Check path findings
    active_path_findings = [
        f for f in findings
        if f["status"] == "active" and f["kind"] in ("path", "link") and f["path"]
    ]

    # Prioritize findings that overlap with cited_cids
    def finding_priority(f: dict[str, Any]) -> tuple[int, float]:
        overlap = 1 if any(c in cited_cids for c in f["subject_cids"] + f["evidence_cids"]) else 0
        return (overlap, f["confidence"])

    active_path_findings.sort(key=finding_priority, reverse=True)

    seen_edges: set[tuple[str, str, str]] = set()

    for f in active_path_findings:
        for hop in f["path"]:
            if len(primary_steps) >= 25:
                break
            h_from = hop.get("from") or hop.get("src")
            h_to = hop.get("to") or hop.get("dst")
            h_rel = hop.get("rel") or "CONNECTED_TO"
            if not h_from or not h_to:
                continue
            edge_tuple = (h_from, h_rel, h_to)
            if edge_tuple in seen_edges:
                continue
            seen_edges.add(edge_tuple)

            recorded = hop_to_step.get(edge_tuple) or hop_to_step.get((h_from, "", h_to)) or {}
            primary_steps.append({
                "from": h_from,
                "to": h_to,
                "rel": h_rel,
                "tool": recorded.get("tool") or "paths_between",
                "agent_id": recorded.get("agent_id") or f["agent_id"],
                "note": recorded.get("note") or f"{h_from} —{h_rel}→ {h_to}",
                "source_id": recorded.get("source_id"),
                "locator": recorded.get("locator"),
                "quote": recorded.get("quote"),
            })

    # Fallback if no path findings: use first investigator's recorded steps (max 12)
    if not primary_steps and all_recorded_steps:
        first_agent = all_recorded_steps[0].get("agent_id")
        for s in all_recorded_steps:
            if s.get("agent_id") == first_agent and len(primary_steps) < 12:
                h_from = s.get("from_cid")
                h_to = s.get("to_cid")
                h_rel = s.get("rel")
                if h_from and h_to:
                    edge_tuple = (h_from, h_rel, h_to)
                    if edge_tuple not in seen_edges:
                        seen_edges.add(edge_tuple)
                        primary_steps.append({
                            "from": h_from,
                            "to": h_to,
                            "rel": h_rel,
                            "tool": s.get("tool") or "neighbors",
                            "agent_id": s.get("agent_id") or first_agent,
                            "note": s.get("note") or f"{h_from} —{h_rel}→ {h_to}",
                            "source_id": s.get("source_id"),
                            "locator": s.get("locator"),
                            "quote": s.get("quote"),
                        })

    # Build path_node_ids
    for s in primary_steps:
        if s["from"] not in path_node_ids:
            path_node_ids.append(s["from"])
        if s["to"] not in path_node_ids:
            path_node_ids.append(s["to"])

    # 4. Collect whole investigation subgraph nodes & edges
    # Primary nodes: all nodes in recorded steps and tool outputs
    primary_cids: set[str] = set(path_node_ids)
    for s in all_recorded_steps:
        if s.get("from_cid"):
            primary_cids.add(s["from_cid"])
        if s.get("to_cid"):
            primary_cids.add(s["to_cid"])
    for f in findings:
        for c in f["subject_cids"] + f["evidence_cids"]:
            primary_cids.add(c)

    # Determine context graph to fetch node details and 1-hop neighbors
    graph_to_query = ctx_graph
    if not graph_to_query:
        # Check if run graph has nodes
        graph_to_query = run_graph

    # Fetch primary node details
    raw_nodes_map: dict[str, dict[str, Any]] = {}
    if primary_cids:
        cid_list = list(primary_cids)
        # Fetch from graph_to_query
        try:
            p_rows = store.query(
                graph_to_query,
                "MATCH (n) WHERE n.cid IN $cids AND NOT n:Source "
                "RETURN n.cid AS cid, labels(n)[0] AS lbl, properties(n) AS props",
                {"cids": cid_list},
            )
            for r in p_rows:
                cid = str(r.get("cid"))
                raw_nodes_map[cid] = {
                    "id": cid,
                    "label": r.get("lbl") or "Entity",
                    "props": r.get("props") or {},
                    "context": False,
                }
        except Exception:
            pass

    # If any primary cids were missing, check run_graph
    missing = primary_cids - set(raw_nodes_map.keys())
    if missing and graph_to_query != run_graph:
        try:
            m_rows = store.query(
                run_graph,
                "MATCH (n) WHERE n.cid IN $cids "
                "RETURN n.cid AS cid, labels(n)[0] AS lbl, properties(n) AS props",
                {"cids": list(missing)},
            )
            for r in m_rows:
                cid = str(r.get("cid"))
                raw_nodes_map[cid] = {
                    "id": cid,
                    "label": r.get("lbl") or "Entity",
                    "props": r.get("props") or {},
                    "context": False,
                }
        except Exception:
            pass

    # Ensure all primary cids have a stub if not found in DB
    for cid in primary_cids:
        if cid not in raw_nodes_map:
            raw_nodes_map[cid] = {
                "id": cid,
                "label": "Entity",
                "props": {"name": cid, "type": "Entity"},
                "context": False,
            }

    # Fetch 1-hop context neighbors
    context_cids: set[str] = set()
    if primary_cids and graph_to_query:
        try:
            c_rows = store.query(
                graph_to_query,
                "MATCH (a)-[r]-(b) "
                "WHERE a.cid IN $cids AND NOT b:Source AND NOT (b.cid IN $cids) "
                "RETURN b.cid AS cid, labels(b)[0] AS lbl, properties(b) AS props "
                "LIMIT 250",
                {"cids": list(primary_cids)},
            )
            for r in c_rows:
                cid = str(r.get("cid"))
                if cid and cid not in raw_nodes_map:
                    context_cids.add(cid)
                    raw_nodes_map[cid] = {
                        "id": cid,
                        "label": r.get("lbl") or "Entity",
                        "props": r.get("props") or {},
                        "context": True,
                    }
        except Exception:
            pass

    # Limit total nodes to 400
    truncated = False
    all_cids_ordered = list(path_node_ids) + [
        c for c in raw_nodes_map if c not in path_node_ids and not raw_nodes_map[c].get("context")
    ] + [
        c for c in raw_nodes_map if raw_nodes_map[c].get("context")
    ]

    if len(all_cids_ordered) > 400:
        truncated = True
        all_cids_ordered = all_cids_ordered[:400]

    included_cids = set(all_cids_ordered)

    # Format nodes
    nodes: list[dict[str, Any]] = []
    for cid in all_cids_ordered:
        item = raw_nodes_map[cid]
        p = item.get("props") or {}
        name = p.get("name") or cid
        ntype = p.get("type") or item.get("label") or "Entity"

        # Up to 6 scalar properties
        props_clean: dict[str, Any] = {"name": name, "type": ntype}
        # Parse props_json if available
        if "props_json" in p and isinstance(p["props_json"], str):
            try:
                pj = json.loads(p["props_json"])
                for k, v in pj.items():
                    if len(props_clean) >= 8:
                        break
                    if isinstance(v, (str, int, float, bool)):
                        props_clean[k] = v
            except Exception:
                pass
        for k, v in p.items():
            if len(props_clean) >= 8:
                break
            if k not in ("props_json", "aliases", "source_ids") and isinstance(v, (str, int, float, bool)):
                props_clean[k] = v

        nodes.append({
            "id": cid,
            "label": item.get("label", "Entity"),
            "props": props_clean,
            "context": bool(item.get("context", False)),
        })

    # Fetch edges between included nodes
    edges: list[dict[str, Any]] = []
    edge_set: set[tuple[str, str, str]] = set()

    path_edge_tuples = set(seen_edges)

    if graph_to_query and len(included_cids) > 1:
        try:
            edge_rows = store.query(
                graph_to_query,
                "MATCH (a)-[r]->(b) "
                "WHERE a.cid IN $cids AND b.cid IN $cids AND type(r) <> 'MENTIONED_IN' "
                "RETURN a.cid AS src, b.cid AS dst, type(r) AS rel "
                "LIMIT 1200",
                {"cids": list(included_cids)},
            )
            for er in edge_rows:
                src = str(er.get("src"))
                dst = str(er.get("dst"))
                rel = str(er.get("rel"))
                tup = (src, rel, dst)
                if tup not in edge_set:
                    edge_set.add(tup)
                    on_p = tup in path_edge_tuples or (src, "", dst) in path_edge_tuples
                    edges.append({
                        "id": f"e_{len(edges)+1}_{src}_{dst}",
                        "src": src,
                        "dst": dst,
                        "rel": rel,
                        "on_path": on_p,
                    })
        except Exception:
            pass

    # Ensure all primary steps have an edge in edges
    for s in primary_steps:
        src = s["from"]
        dst = s["to"]
        rel = s["rel"]
        tup = (src, rel, dst)
        if tup not in edge_set:
            edge_set.add(tup)
            edges.append({
                "id": f"e_path_{len(edges)+1}_{src}_{dst}",
                "src": src,
                "dst": dst,
                "rel": rel,
                "on_path": True,
            })

    # 5. Build TraceStep list (Tour steps)
    steps: list[dict[str, Any]] = []
    for idx, s in enumerate(primary_steps, start=1):
        to_node = raw_nodes_map.get(s["to"]) or {}
        to_props = to_node.get("props") or {}
        to_name = to_props.get("name") or s["to"]
        to_type = to_props.get("type") or to_node.get("label") or "Entity"

        # Up to 4 properties
        prop_pairs: list[dict[str, str]] = []
        if "props_json" in to_props and isinstance(to_props["props_json"], str):
            try:
                pj = json.loads(to_props["props_json"])
                for k, v in pj.items():
                    if len(prop_pairs) >= 4:
                        break
                    prop_pairs.append({"k": str(k), "v": str(v)[:60]})
            except Exception:
                pass
        if not prop_pairs:
            for k, v in to_props.items():
                if len(prop_pairs) >= 4:
                    break
                if k not in ("name", "type", "cid", "props_json", "aliases", "source_ids"):
                    prop_pairs.append({"k": str(k), "v": str(v)[:60]})

        step_dict: dict[str, Any] = {
            "seq": idx,
            "from": s["from"],
            "to": s["to"],
            "rel": s["rel"],
            "tool": s["tool"],
            "agent_id": s["agent_id"],
            "note": s["note"],
            "focus": s["to"],
            "value": {
                "title": to_name,
                "subtitle": to_type.upper(),
                "properties": prop_pairs,
            },
        }
        if s.get("source_id") or s.get("locator") or s.get("quote"):
            step_dict["source"] = {
                "name": s.get("source_id") or "Source",
                "locator": s.get("locator") or "",
                "quote": s.get("quote"),
            }
        steps.append(step_dict)

    # 6. Summary string
    # One line built in code: e.g. 'Alice Moreno —WORKS_FOR→ Acme Ltd —PAID→ Bob Chen'
    summary = ""
    if steps:
        seq_tokens: list[str] = []
        start_id = steps[0]["from"]
        start_node = raw_nodes_map.get(start_id, {}).get("props", {}).get("name") or start_id
        seq_tokens.append(start_node)
        for st in steps:
            rel = st["rel"]
            dst_name = st["value"]["title"]
            seq_tokens.append(f"—{rel}→")
            seq_tokens.append(dst_name)

        # Count nodes in the chain (every even index: 0, 2, 4...)
        node_names = [seq_tokens[i] for i in range(0, len(seq_tokens), 2)]
        if len(node_names) > 6:
            # show first 3, ellipsis, last 2
            first_three = f"{node_names[0]} —{steps[0]['rel']}→ {node_names[1]} —{steps[1]['rel']}→ {node_names[2]}"
            last_step_idx = len(steps) - 1
            last_two = f"{node_names[-2]} —{steps[last_step_idx]['rel']}→ {node_names[-1]}"
            summary = f"{first_three} … {last_two}"
        else:
            summary = " ".join(seq_tokens)
    elif nodes:
        summary = f"Investigation graph with {len(nodes)} entities and {len(edges)} links."
    else:
        summary = "No traversal recorded."

    return {
        "mode": "traversal",
        "nodes": nodes,
        "edges": edges,
        "steps": steps,
        "path_node_ids": path_node_ids,
        "summary": summary,
        "truncated": truncated,
        "explored_steps": total_explored,
    }


def build_why_response(
    store: GraphStore,
    run_id: str,
    target_cid: str,
) -> dict[str, Any]:
    """Build Why explainability response adapted for generic investigation findings (Part 3.7)."""
    run_graph = resolve_run_graph(store, run_id)

    # 1. Fetch findings involving target_cid (either as subject, evidence, or customer)
    f_rows = store.query(
        run_graph,
        "MATCH (f:Finding) "
        "RETURN f.id AS id, f.kind AS kind, f.claim AS claim, "
        "       f.subject_cids AS subject_cids, f.evidence_cids AS evidence_cids, "
        "       f.confidence AS confidence, f.status AS status, "
        "       f.agent_id AS agent_id, f.skill_id AS skill_id, f.verdict AS verdict",
    )
    matching_findings = []
    for fr in (f_rows or []):
        sub_cids = fr.get("subject_cids") or []
        if isinstance(sub_cids, str):
            try:
                sub_cids = json.loads(sub_cids)
            except Exception:
                sub_cids = [sub_cids]
        ev_cids = fr.get("evidence_cids") or []
        if isinstance(ev_cids, str):
            try:
                ev_cids = json.loads(ev_cids)
            except Exception:
                ev_cids = [ev_cids]

        if target_cid in sub_cids or target_cid in ev_cids:
            matching_findings.append({
                "id": fr.get("id"),
                "agent_id": fr.get("agent_id") or "agent-1",
                "skill_id": fr.get("skill_id") or "investigate",
                "verdict": fr.get("verdict") or fr.get("kind") or "fact",
                "confidence": float(fr.get("confidence") or 0.8),
                "status": fr.get("status") or "active",
                "backend": "llm",
                "reasoning": fr.get("claim") or "",
                "evidence_cids": ev_cids,
            })

    # 2. Fetch skill choices from Decision nodes
    d_rows = store.query(
        run_graph,
        "MATCH (d:Decision {kind: 'skill_assignment'})-[:FOR]->(sub) "
        "OPTIONAL MATCH (d)-[:CHOSE]->(c) "
        "RETURN d.id AS id, d.confidence AS confidence, d.backend AS backend, "
        "       sub.id AS subtask_id, sub.capability AS capability, c.id AS chosen_id",
    )
    skill_choices = []
    for dr in (d_rows or []):
        skill_choices.append({
            "subtask_id": dr.get("subtask_id") or "subtask",
            "capability": dr.get("capability") or "investigate",
            "chosen_skill_id": dr.get("chosen_id") or "skill",
            "rejected": [],
            "confidence": float(dr.get("confidence") or 1.0),
            "backend": dr.get("backend") or "llm",
        })

    # 3. Build narrative
    if matching_findings:
        active_f = [f for f in matching_findings if f["status"] == "active"]
        top_f = active_f[0] if active_f else matching_findings[0]
        narrative = f"Investigation found {len(matching_findings)} claim(s) regarding {target_cid}: {top_f['reasoning']} (Confidence: {top_f['confidence']:.2f})."
        final_verdict = top_f["verdict"]
    else:
        narrative = f"No direct verified findings recorded for entity {target_cid}."
        final_verdict = "benign"

    evidence_items = [{"cid": target_cid, "label": "Entity"}]
    for f in matching_findings:
        for ec in f["evidence_cids"]:
            if ec not in [e["cid"] for e in evidence_items]:
                evidence_items.append({"cid": ec, "label": "Evidence"})

    return {
        "target_cid": target_cid,
        "final_verdict": final_verdict,
        "findings": matching_findings,
        "decision": None,
        "evidence": evidence_items,
        "skill_choices": skill_choices,
        "narrative": narrative,
    }


def generate_suggestions(store: GraphStore, ctx_graph: str) -> list[str]:
    """Generate 3 to 4 dynamic question suggestions from real graph entities (Part 3.2)."""
    suggestions: list[str] = []

    try:
        # 1. Top-degree entity: "Who is connected to <name>?"
        top_rows = store.query(
            ctx_graph,
            "MATCH (n) WHERE NOT n:Source "
            "OPTIONAL MATCH (n)-[r]-() WHERE type(r) <> 'MENTIONED_IN' "
            "RETURN n.cid AS cid, coalesce(n.name, n.cid) AS name, count(r) AS degree "
            "ORDER BY degree DESC LIMIT 1",
        )
        if top_rows and top_rows[0].get("name"):
            name = str(top_rows[0]["name"])
            suggestions.append(f"Who is connected to {name}?")

        # 2. A connected pair: "How is <A> connected to <B>?"
        pair_rows = store.query(
            ctx_graph,
            "MATCH (a)-[r]->(b) "
            "WHERE NOT a:Source AND NOT b:Source AND type(r) <> 'MENTIONED_IN' "
            "RETURN coalesce(a.name, a.cid) AS a_name, coalesce(b.name, b.cid) AS b_name "
            "LIMIT 1",
        )
        if pair_rows and pair_rows[0].get("a_name") and pair_rows[0].get("b_name"):
            a_name = str(pair_rows[0]["a_name"])
            b_name = str(pair_rows[0]["b_name"])
            suggestions.append(f"How is {a_name} connected to {b_name}?")

        # 3. Entity that appears in the most sources: "Which sources mention <name>?"
        src_rows = store.query(
            ctx_graph,
            "MATCH (n)-[r:MENTIONED_IN]->(s:Source) "
            "RETURN coalesce(n.name, n.cid) AS name, count(s) AS s_count "
            "ORDER BY s_count DESC LIMIT 1",
        )
        if src_rows and src_rows[0].get("name"):
            s_name = str(src_rows[0]["name"])
            suggestions.append(f"Which sources mention {s_name}?")

        # 4. If dates exist: "What happened around <name>, in order?"
        date_rows = store.query(
            ctx_graph,
            "MATCH (n) WHERE (n:Event OR n.date IS NOT NULL OR n.props_json CONTAINS 'date') AND NOT n:Source "
            "RETURN coalesce(n.name, n.cid) AS name LIMIT 1",
        )
        if date_rows and date_rows[0].get("name"):
            d_name = str(date_rows[0]["name"])
            suggestions.append(f"What happened around {d_name}, in order?")

    except Exception:
        pass

    # Ensure at least 1 suggestion fallback if query failed on empty graph
    if not suggestions:
        suggestions = ["What are the key entities in this graph?"]

    return suggestions[:4]
