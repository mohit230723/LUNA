"""Domain-agnostic, read-only graph investigation tools with TraversalStep recording."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional
from luna.graph.store import GraphStore
from luna.investigate.recorder import TraversalRecorder, describe_edge
from luna.tools.cypher_guard import validate_read_only, UnsafeCypherError


class ContextGraphTools:
    """Suite of domain-agnostic investigative tools bound to a specific agent's graph slice."""

    def __init__(
        self,
        store: GraphStore,
        graph_name: str,
        agent_id: str,
        recorder: Optional[TraversalRecorder] = None,
        llm: Optional[Any] = None,
    ) -> None:
        self.store = store
        self.graph_name = graph_name
        self.agent_id = agent_id
        self.recorder = recorder
        self.llm = llm
        self._cid_cache: dict[str, str] = {}
        # Models often shorten or mistype identifiers ("acc-9821" for "account:acc-9821-9984bf").
        # Resolve them to the real cid before any tool runs so a near-miss is not an empty result.
        for _name in (
            "neighbors", "paths_between", "shortest_path", "shared_attributes",
            "common_neighbors", "cluster_of", "timeline", "source_mentions",
        ):
            setattr(self, _name, self._with_cid_resolution(getattr(self, _name)))

    _CID_PARAMS = ("cid", "src_cid", "dst_cid", "cid_a", "cid_b", "source_cid", "target_cid")

    def resolve_cid(self, value: Any) -> Any:
        """Map a possibly shortened identifier or entity name to the exact cid in this graph."""
        if not isinstance(value, str) or not value.strip():
            return value
        raw = value.strip()
        if raw in self._cid_cache:
            return self._cid_cache[raw]
        resolved = raw
        try:
            exact = self.store.read_query(
                self.graph_name, "MATCH (n {cid: $c}) RETURN n.cid AS cid LIMIT 1", {"c": raw}
            )
            if not exact:
                needle = raw.split(":", 1)[-1].lower()
                rows = self.store.read_query(
                    self.graph_name,
                    "MATCH (n) WHERE n.cid IS NOT NULL AND NOT n:Source AND "
                    "(toLower(n.cid) CONTAINS $n OR toLower(n.name) = $n OR toLower(n.name) CONTAINS $n) "
                    "RETURN DISTINCT n.cid AS cid, n.name AS name",
                    {"n": needle},
                )
                cids = [r["cid"] for r in rows if r.get("cid")]
                if len(cids) > 1:
                    exact_name = [r["cid"] for r in rows if str(r.get("name", "")).lower() == needle]
                    cids = exact_name or cids
                if len(cids) == 1:
                    resolved = cids[0]
        except Exception:
            resolved = raw
        self._cid_cache[raw] = resolved
        return resolved

    def _with_cid_resolution(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        import functools
        import inspect

        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                bound = sig.bind_partial(*args, **kwargs)
            except TypeError:
                return fn(*args, **kwargs)
            for pname in self._CID_PARAMS:
                if pname in bound.arguments:
                    bound.arguments[pname] = self.resolve_cid(bound.arguments[pname])
            return fn(*bound.args, **bound.kwargs)

        return wrapper

    def _record(
        self,
        tool: str,
        from_cid: str,
        to_cid: str,
        rel: str,
        direction: str = "out",
        note: str = "",
        quote: str = "",
        locator: str = "",
        source_id: str = "",
    ) -> None:
        if self.recorder:
            self.recorder.record_step(
                agent_id=self.agent_id,
                tool=tool,
                from_cid=from_cid,
                to_cid=to_cid,
                rel=rel,
                direction=direction,
                note=note,
                edge_source_id=source_id,
                edge_locator=locator,
                edge_quote=quote,
                agent_graph_name=self.graph_name,
            )

    def neighbors(
        self,
        cid: str,
        hops: int = 1,
        rel_types: Optional[list[str]] = None,
        labels: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Find immediate or k-hop neighbors around an entity."""
        hops = max(1, min(3, hops))
        cypher = (
            f"MATCH (src {{cid: $cid}})-[r*1..{hops}]-(dst) "
            f"WHERE dst.cid <> $cid AND NOT dst:Source "
            f"RETURN DISTINCT dst.cid AS cid, dst.name AS name, labels(dst)[0] AS type, "
            f"       type(last(r)) AS via_rel, properties(last(r)) AS edge_props, length(r) AS distance "
            f"LIMIT {int(limit)}"
        )
        rows = self.store.query(self.graph_name, cypher, {"cid": cid})

        results = []
        for r in rows:
            dst_cid = r.get("cid")
            dst_name = r.get("name") or dst_cid
            via_rel = r.get("via_rel") or "RELATED"
            edge_props = r.get("edge_props") or {}
            quote = edge_props.get("quote", "")
            locator = edge_props.get("locator", "")
            src_id = edge_props.get("source_id", "")

            note = describe_edge(cid, dst_name, via_rel, quote=quote, locator=locator)
            self._record("neighbors", cid, dst_cid, via_rel, note=note, quote=quote, locator=locator, source_id=src_id)

            results.append({
                "cid": dst_cid,
                "name": dst_name,
                "type": r.get("type") or "Entity",
                "via_rel": via_rel,
                "distance": int(r.get("distance") or 1),
            })
        return results

    def paths_between(
        self,
        src_cid: str,
        dst_cid: str,
        max_hops: int = 4,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find bounded paths between two entities ranked by length and confidence."""
        hops = max(1, min(5, max_hops))
        cypher = (
            f"MATCH p = (src {{cid: $src}})-[*1..{hops}]-(dst {{cid: $dst}}) "
            f"RETURN [n IN nodes(p) | {{cid: n.cid, name: n.name, type: labels(n)[0]}}] AS nodes, "
            f"       [r IN relationships(p) | type(r)] AS rels, "
            f"       [r IN relationships(p) | properties(r)] AS edge_props, "
            f"       length(p) AS length "
            f"LIMIT {int(limit)}"
        )
        rows = self.store.query(self.graph_name, cypher, {"src": src_cid, "dst": dst_cid})

        paths = []
        for r in rows:
            p_nodes = r.get("nodes") or []
            p_rels = r.get("rels") or []
            p_props = r.get("edge_props") or []
            length = int(r.get("length") or len(p_rels))

            # Record hops in sequence
            for i in range(len(p_rels)):
                u = p_nodes[i].get("cid")
                v = p_nodes[i + 1].get("cid")
                rel = p_rels[i]
                ep = p_props[i] if i < len(p_props) else {}
                note = describe_edge(p_nodes[i].get("name", u), p_nodes[i + 1].get("name", v), rel, quote=ep.get("quote", ""), locator=ep.get("locator", ""))
                self._record("paths_between", u, v, rel, note=note, quote=ep.get("quote", ""), locator=ep.get("locator", ""), source_id=ep.get("source_id", ""))

            paths.append({
                "nodes": p_nodes,
                "rels": p_rels,
                "length": length,
                "score": round(1.0 / length, 2),
            })
        return paths

    def shortest_path(
        self,
        src_cid: str,
        dst_cid: str,
        max_hops: int = 6,
    ) -> Optional[dict[str, Any]]:
        """Find shortest connection between src and dst entities."""
        paths = self.paths_between(src_cid, dst_cid, max_hops=max_hops, limit=1)
        return paths[0] if paths else None

    def shared_attributes(
        self,
        cid_a: str,
        cid_b: str,
    ) -> list[dict[str, Any]]:
        """Discover entities linked to both cid_a and cid_b."""
        cypher = (
            "MATCH (a {cid: $a})-[r1]->(shared)<-[r2]-(b {cid: $b}) "
            "WHERE NOT shared:Source "
            "RETURN shared.cid AS cid, shared.name AS name, labels(shared)[0] AS type, "
            "       type(r1) AS rel_a, type(r2) AS rel_b, "
            "       properties(r1) AS ep1, properties(r2) AS ep2"
        )
        rows = self.store.query(self.graph_name, cypher, {"a": cid_a, "b": cid_b})

        results = []
        for r in rows:
            s_cid = r.get("cid")
            s_name = r.get("name") or s_cid
            rel_a = r.get("rel_a")
            rel_b = r.get("rel_b")
            ep1 = r.get("ep1") or {}
            ep2 = r.get("ep2") or {}

            self._record("shared_attributes", cid_a, s_cid, rel_a, note=describe_edge(cid_a, s_name, rel_a, quote=ep1.get("quote", "")), quote=ep1.get("quote", ""), source_id=ep1.get("source_id", ""))
            self._record("shared_attributes", cid_b, s_cid, rel_b, note=describe_edge(cid_b, s_name, rel_b, quote=ep2.get("quote", "")), quote=ep2.get("quote", ""), source_id=ep2.get("source_id", ""))

            results.append({
                "cid": s_cid,
                "name": s_name,
                "type": r.get("type") or "Entity",
                "rel_a": rel_a,
                "rel_b": rel_b,
            })
        return results

    def common_neighbors(self, cid_a: str, cid_b: str) -> list[dict[str, Any]]:
        return self.shared_attributes(cid_a, cid_b)

    def cluster_of(self, cid: str, via_labels: Optional[list[str]] = None) -> dict[str, Any]:
        """Find the connected component around cid using Python BFS/union-find."""
        visited: set[str] = set()
        queue = [cid]
        members = []

        while queue and len(members) < 50:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)

            rows = self.store.query(
                self.graph_name,
                "MATCH (n {cid: $cid})-[r]-(m) WHERE NOT m:Source "
                "RETURN m.cid AS cid, m.name AS name, labels(m)[0] AS type "
                "LIMIT 20",
                {"cid": curr},
            )
            for r in rows:
                m_cid = r.get("cid")
                if m_cid and m_cid not in visited:
                    queue.append(m_cid)
                    members.append({
                        "cid": m_cid,
                        "name": r.get("name") or m_cid,
                        "type": r.get("type") or "Entity",
                    })

        return {"members": members, "size": len(members)}

    def central_nodes(self, k: int = 5) -> list[dict[str, Any]]:
        """Rank nodes by graph degree centrality."""
        cypher = (
            f"MATCH (n) WHERE NOT n:Source "
            f"OPTIONAL MATCH (n)-[r]-() WHERE type(r) <> 'MENTIONED_IN' "
            f"RETURN n.cid AS cid, n.name AS name, labels(n)[0] AS type, count(r) AS degree "
            f"ORDER BY degree DESC LIMIT {int(k)}"
        )
        rows = self.store.query(self.graph_name, cypher)
        return [
            {
                "cid": r.get("cid"),
                "name": r.get("name") or r.get("cid"),
                "type": r.get("type") or "Entity",
                "score": int(r.get("degree") or 0),
            }
            for r in rows
        ]

    def timeline(self, cid: str, hops: int = 1) -> list[dict[str, Any]]:
        """Collect dated events and properties around an entity, sorted chronologically."""
        cypher = (
            f"MATCH (n {{cid: $cid}})-[*0..{hops}]-(m) WHERE NOT m:Source "
            f"RETURN m.cid AS cid, m.name AS name, labels(m)[0] AS type, m.props_json AS props_json"
        )
        rows = self.store.query(self.graph_name, cypher, {"cid": cid})

        events: list[dict[str, Any]] = []
        for r in rows:
            m_cid = r.get("cid")
            m_name = r.get("name") or m_cid
            m_type = r.get("type") or "Entity"
            props_raw = r.get("props_json")
            if props_raw:
                try:
                    props = json.loads(props_raw)
                    for k, v in props.items():
                        if any(d in k.lower() for d in ("date", "time", "created", "timestamp", "year")):
                            events.append({
                                "date": str(v),
                                "cid": m_cid,
                                "name": m_name,
                                "type": m_type,
                                "note": f"{k}: {v}",
                            })
                except Exception:
                    pass

        events.sort(key=lambda x: str(x.get("date", "")))
        return events[:30]

    def source_mentions(self, cid: str) -> list[dict[str, Any]]:
        """Retrieve original source document locators and exact quotes citing an entity."""
        cypher = (
            "MATCH (n {cid: $cid})-[r:MENTIONED_IN]->(s:Source) "
            "RETURN s.name AS source, r.locator AS locator, r.quote AS quote "
            "LIMIT 20"
        )
        rows = self.store.query(self.graph_name, cypher, {"cid": cid})
        return [
            {
                "source": r.get("source") or "Document",
                "locator": r.get("locator") or "",
                "quote": r.get("quote") or "",
            }
            for r in rows
        ]

    def ask_graph(self, question: str) -> dict[str, Any]:
        """Allow LLM to construct a parameterized read-only Cypher query on the agent slice."""
        if not self.llm:
            return {"error": "llm_unavailable"}

        system = (
            "You write read-only Cypher queries for a FalkorDB graph. Return ONLY the Cypher query. "
            "Only MATCH and RETURN statements. Never use CREATE, MERGE, SET, DELETE, DETACH, or CALL. "
            "Always include a LIMIT clause (max 100)."
        )
        try:
            cypher_raw = self.llm.complete_text(system=system, user=question).strip()
            # Strip markdown fences
            if cypher_raw.startswith("```"):
                cypher_raw = re.sub(r"^```[a-z]*\n?", "", cypher_raw)
                cypher_raw = re.sub(r"\n?```$", "", cypher_raw).strip()

            safe_cypher = validate_read_only(cypher_raw, max_rows=100)
            rows = self.store.query(self.graph_name, safe_cypher)
            return {"cypher": safe_cypher, "rows": rows[:100]}
        except UnsafeCypherError:
            return {"error": "unsafe_query"}
        except Exception as e:
            return {"error": str(e)}
