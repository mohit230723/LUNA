"""Autonomous graph investigation pipeline for case questioning."""

from __future__ import annotations

import concurrent.futures
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import uuid4

from luna.agents.models import Finding
from luna.cases.store import CaseStore
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_TASK,
    LABEL_SUBTASK,
    LABEL_AGENT,
    LABEL_SKILL_REF,
    LABEL_DECISION,
    LABEL_FINDING,
    LABEL_ANSWER,
    REL_HAS_SUBTASK,
    REL_CHOSE,
    REL_REJECTED,
    REL_EQUIPPED,
    REL_ANSWERED_BY,
    REL_CITES,
    REL_SUPERSEDES,
)
from luna.graph.store import GraphStore
from luna.investigate.recorder import TraversalRecorder, describe_edge
from luna.investigate.seed import seed_investigation_atlas, INVESTIGATION_CAPABILITIES
from luna.investigate.tools import ContextGraphTools
from luna.llm.client import LLMClient
from luna.orchestrator.promote import promote_findings
from luna.orchestrator.slice import extract_subgraph_slice

# Approximate string matching with difflib fallback
try:
    from rapidfuzz import fuzz
    def wratio(s1: str, s2: str) -> float:
        return float(fuzz.WRatio(s1, s2))
except ImportError:
    import difflib
    def wratio(s1: str, s2: str) -> float:
        return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio() * 100.0


UNDERSTAND_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "who_connected", "path_between", "shortest_path", "shared_attributes",
                "cluster", "timeline", "sources", "summary", "other"
            ],
        },
        "mentions": {"type": "array", "items": {"type": "string"}},
        "constraints": {
            "type": "object",
            "properties": {
                "max_hops": {"type": "integer"},
                "types": {"type": "array", "items": {"type": "string"}},
            },
        },
        "clarification": {"type": "string"},
    },
    "required": ["intent", "mentions"],
}

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "subtasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "capability": {"type": "string"},
                    "goal": {"type": "string"},
                },
                "required": ["capability", "goal"],
            },
        }
    },
    "required": ["subtasks"],
}


class InvestigationPipeline:
    """Orchestrates multi-agent graph investigations backed by real LLM tool loops."""

    def __init__(
        self,
        case_id: str,
        run_id: str,
        question: str,
        case_store: CaseStore,
        graph_store: Optional[GraphStore] = None,
        llm: Optional[LLMClient] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> None:
        self.case_id = case_id
        self.run_id = run_id
        self.question = question
        self.case_store = case_store
        self.store = graph_store or GraphStore()
        self.llm = llm
        self.options = options or {}
        self.max_hops = max(1, min(5, int(self.options.get("max_hops") or 3)))
        self.investigators_limit = max(1, min(4, int(self.options.get("investigators") or 3)))

        self.case_data = self.case_store.get_case(case_id) or {}
        self.ctx_graph = self.case_data.get("context_graph") or f"ctx_{case_id}"
        self.run_graph = f"run_{run_id}"

        self.seq = 0
        self.recorder = TraversalRecorder(self.store)
        self.observed_cids: set[str] = set()
        self.observed_edges: set[tuple[str, str, str]] = set()

    def _emit(self, emit_fn: Callable[[dict[str, Any]], None], event_type: str, data: dict[str, Any]) -> None:
        self.seq += 1
        event = {
            "run_id": self.run_id,
            "seq": self.seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "backend": "llm",
            "data": data,
        }
        emit_fn(event)

    def execute(
        self,
        emit_fn: Callable[[dict[str, Any]], None],
        is_cancelled: Callable[[], bool],
        answer_receiver: Optional[Callable[[], Optional[str]]] = None,
    ) -> dict[str, Any]:
        """Execute all 10 steps of the investigation pipeline."""
        if not self.llm:
            raise RuntimeError("No LLM client configured for investigation pipeline")

        # Ensure seed
        seed_investigation_atlas(self.store)

        # Initialize run graph
        task_id = f"task_{self.run_id[:8]}"
        self.store.query(
            self.run_graph,
            f"MERGE (t:{LABEL_TASK} {{id: $task_id}}) SET t.prompt = $prompt, t.status = 'running'",
            {"task_id": task_id, "prompt": self.question},
        )

        warnings: list[str] = []

        # ---------------------------------------------------------------------
        # Step 1: UNDERSTAND
        # ---------------------------------------------------------------------
        if is_cancelled():
            self._emit(emit_fn, "cancelled", {})
            return {}

        vocab_rows = self.store.query(
            self.ctx_graph,
            "MATCH (n) WHERE NOT n:Source RETURN labels(n)[0] AS lbl, count(n) AS cnt",
        )
        vocab_desc = ", ".join(f"{r.get('lbl')}: {r.get('cnt')}" for r in vocab_rows if r.get("lbl"))

        understand_sys = (
            "You turn a question about a graph of people, organizations, accounts, places and events "
            "into a structured request. Use only the vocabulary provided. Put every entity the user names "
            "in mentions exactly as written. If the question cannot be answered from a graph of this kind, "
            "set clarification to a short question."
        )
        understand_user = f"Question: {self.question}\nGraph Vocabulary: {vocab_desc}"

        understand_res = self.llm.complete_json(understand_sys, understand_user, UNDERSTAND_SCHEMA)
        intent = understand_res.get("intent", "who_connected")
        mentions = understand_res.get("mentions", [])
        clarification = understand_res.get("clarification")

        self._emit(emit_fn, "understood", {
            "intent": intent,
            "mentions": mentions,
            "clarification": clarification,
        })

        # ---------------------------------------------------------------------
        # Step 2: RESOLVE MENTIONS
        # ---------------------------------------------------------------------
        if is_cancelled():
            self._emit(emit_fn, "cancelled", {})
            return {}

        resolved_entities: list[dict[str, Any]] = []

        # Load all graph nodes for resolution
        all_nodes_rows = self.store.query(
            self.ctx_graph,
            "MATCH (n) WHERE NOT n:Source RETURN n.cid AS cid, n.name AS name, labels(n)[0] AS type, n.aliases AS aliases",
        )

        for mention in mentions:
            mention_clean = mention.strip().lower()
            exact_match = None
            candidates: list[tuple[dict[str, Any], float]] = []

            for r in all_nodes_rows:
                cid = r.get("cid", "")
                name = r.get("name", "")
                aliases = r.get("aliases") or []
                if not isinstance(aliases, list):
                    aliases = []

                if cid.lower() == mention_clean or name.lower() == mention_clean:
                    exact_match = r
                    break
                for a in aliases:
                    if str(a).lower() == mention_clean:
                        exact_match = r
                        break
                if exact_match:
                    break

                # Fuzzy candidate
                score = max(wratio(mention_clean, name.lower()), *(wratio(mention_clean, str(a).lower()) for a in aliases or [""]))
                if score >= 80.0:
                    candidates.append((r, score))

            if exact_match:
                resolved_entities.append({
                    "mention": mention,
                    "cid": exact_match["cid"],
                    "name": exact_match["name"] or exact_match["cid"],
                    "type": exact_match["type"] or "Entity",
                })
            elif candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                top = candidates[0]
                # Check for ambiguity
                if len(candidates) > 1 and (candidates[0][1] - candidates[1][1] < 5.0):
                    options_list = [c[0]["name"] for c in candidates[:3]]
                    self._emit(emit_fn, "needs_input", {
                        "question": f"Multiple entities match '{mention}'. Which one did you mean?",
                        "options": options_list,
                    })
                    # Pause waiting for answer if receiver provided
                    chosen_name = None
                    if answer_receiver:
                        for _ in range(300):
                            if is_cancelled():
                                self._emit(emit_fn, "cancelled", {})
                                return {}
                            ans = answer_receiver()
                            if ans:
                                chosen_name = ans
                                break
                            time.sleep(0.5)

                    selected_r = next((c[0] for c in candidates if c[0]["name"] == chosen_name), candidates[0][0])
                    resolved_entities.append({
                        "mention": mention,
                        "cid": selected_r["cid"],
                        "name": selected_r["name"] or selected_r["cid"],
                        "type": selected_r["type"] or "Entity",
                    })
                else:
                    resolved_entities.append({
                        "mention": mention,
                        "cid": top[0]["cid"],
                        "name": top[0]["name"] or top[0]["cid"],
                        "type": top[0]["type"] or "Entity",
                    })
            else:
                warnings.append(f"Entity '{mention}' was not found in the context graph")

        self._emit(emit_fn, "entities_resolved", {"entities": resolved_entities})

        # ---------------------------------------------------------------------
        # Step 3: PLAN
        # ---------------------------------------------------------------------
        if is_cancelled():
            self._emit(emit_fn, "cancelled", {})
            return {}

        valid_caps = [c[0] for c in INVESTIGATION_CAPABILITIES]
        plan_sys = (
            "You decompose an investigation question into 1 to 4 focused subtasks. "
            f"Allowed capabilities: {', '.join(valid_caps)}. "
            "Choose only from this list. Return ONLY JSON matching schema."
        )
        plan_user = (
            f"Question: {self.question}\n"
            f"Intent: {intent}\n"
            f"Resolved Entities: {[e['name'] + ' (' + e['cid'] + ')' for e in resolved_entities]}\n"
        )

        plan_res = self.llm.complete_json(plan_sys, plan_user, PLAN_SCHEMA)
        raw_subtasks = plan_res.get("subtasks", [])

        subtasks = []
        for idx, st in enumerate(raw_subtasks[:self.investigators_limit], start=1):
            cap = st.get("capability")
            if cap not in valid_caps:
                cap = "trace_relationships"
            subtasks.append({
                "id": f"subtask_{idx}",
                "capability": cap,
                "goal": st.get("goal") or f"Execute {cap} analysis",
            })

        if not subtasks:
            subtasks.append({
                "id": "subtask_1",
                "capability": "trace_relationships",
                "goal": "Trace connections from target entities",
            })

        self._emit(emit_fn, "plan", {"subtasks": subtasks})

        # ---------------------------------------------------------------------
        # Step 4: ASSIGN SKILLS
        # ---------------------------------------------------------------------
        if is_cancelled():
            self._emit(emit_fn, "cancelled", {})
            return {}

        skill_assignments = []
        investigator_configs = []

        for st in subtasks:
            cap = st["capability"]
            # Query atlas for skills providing this capability
            rows = self.store.query(
                GRAPH_ATLAS,
                "MATCH (k:Skill)-[:PROVIDES]->(c:Capability {name: $cap}) "
                "MATCH (k)-[:IN_PACK]->(p:Pack {name: 'investigate'}) "
                "WHERE k.source IS NULL "
                "OPTIONAL MATCH (k)-[:EXPOSES]->(t:Tool) "
                "RETURN k.id AS id, k.name AS name, k.prompt_fragment AS prompt, "
                "       k.score AS score, k.restricted AS restricted, collect(t.name) AS tools "
                "ORDER BY k.score DESC",
                {"cap": cap},
            )

            chosen_skill = None
            rejected_skills = []
            for r in rows:
                sk_id = r.get("id")
                if r.get("restricted"):
                    rejected_skills.append({"skill": sk_id, "reason": "policy_restricted"})
                    continue
                if not chosen_skill:
                    chosen_skill = r
                else:
                    rejected_skills.append({"skill": sk_id, "reason": "lower_track_record"})

            if not chosen_skill and rows:
                chosen_skill = rows[0]

            sk_name = chosen_skill.get("name", "Relationship Tracer") if chosen_skill else "Relationship Tracer"
            sk_id = chosen_skill.get("id", "relationship-tracer") if chosen_skill else "relationship-tracer"
            sk_prompt = chosen_skill.get("prompt", "") if chosen_skill else ""
            sk_tools = chosen_skill.get("tools", ["neighbors", "paths_between"]) if chosen_skill else ["neighbors", "paths_between"]

            agent_id = f"agent_{st['id']}"

            # Persist Decision and SkillRef in run graph
            dec_id = f"dec_skill_{st['id']}"
            self.store.query(
                self.run_graph,
                f"MATCH (t:{LABEL_TASK} {{id: $task_id}}) "
                f"CREATE (st:{LABEL_SUBTASK} {{id: $st_id, capability: $cap, goal: $goal}}) "
                f"CREATE (t)-[:{REL_HAS_SUBTASK}]->(st) "
                f"CREATE (d:{LABEL_DECISION} {{id: $dec_id, kind: 'skill_assignment'}}) "
                f"CREATE (sr:{LABEL_SKILL_REF} {{id: $sk_id, name: $sk_name}}) "
                f"CREATE (d)-[:{REL_CHOSE}]->(sr) "
                f"CREATE (ag:{LABEL_AGENT} {{id: $agent_id}}) "
                f"CREATE (ag)-[:{REL_EQUIPPED}]->(sr)",
                {
                    "task_id": task_id,
                    "st_id": st["id"],
                    "cap": cap,
                    "goal": st["goal"],
                    "dec_id": dec_id,
                    "sk_id": sk_id,
                    "sk_name": sk_name,
                    "agent_id": agent_id,
                },
            )

            for rej in rejected_skills:
                self.store.query(
                    self.run_graph,
                    f"MATCH (d:{LABEL_DECISION} {{id: $dec_id}}) "
                    f"CREATE (sr:{LABEL_SKILL_REF} {{id: $sk_id}}) "
                    f"CREATE (d)-[:{REL_REJECTED} {{reason: $reason}}]->(sr)",
                    {"dec_id": dec_id, "sk_id": rej["skill"], "reason": rej["reason"]},
                )

            skill_assignments.append({
                "subject": st["id"],
                "chosen": sk_id,
                "backend": "llm",
                "rejected": rejected_skills,
            })

            investigator_configs.append({
                "agent_id": agent_id,
                "skill_id": sk_id,
                "skill_name": sk_name,
                "prompt_fragment": sk_prompt,
                "goal": st["goal"],
                "tools": sk_tools,
            })

        self._emit(emit_fn, "skill_assigned", {"assignments": skill_assignments})

        # ---------------------------------------------------------------------
        # Step 5: SLICE
        # ---------------------------------------------------------------------
        seed_cids = [e["cid"] for e in resolved_entities]
        if not seed_cids:
            # Fall back to high-degree central nodes
            top_rows = self.store.query(
                self.ctx_graph,
                "MATCH (n) WHERE NOT n:Source RETURN n.cid AS cid ORDER BY size((n)--()) DESC LIMIT 3",
            )
            seed_cids = [r["cid"] for r in top_rows if r.get("cid")]

        slice_truncated = False
        for inv in investigator_configs:
            agent_graph = f"agent_{self.run_id}_{inv['agent_id']}"
            if seed_cids:
                try:
                    slice_res = extract_subgraph_slice(
                        store=self.store,
                        source_graph=self.ctx_graph,
                        target_graph=agent_graph,
                        seed_cids=seed_cids,
                        k_hops=self.max_hops,
                        max_nodes=800,
                    )
                    if slice_res.get("truncated"):
                        slice_truncated = True
                except Exception as slice_err:
                    warnings.append(f"Slice extraction warning: {slice_err}")

        if slice_truncated:
            warnings.append("Graph slice was capped at 800 nodes; some distant paths may be unexamined")

        # ---------------------------------------------------------------------
        # Step 6: INVESTIGATE IN PARALLEL
        # ---------------------------------------------------------------------
        if is_cancelled():
            self._emit(emit_fn, "cancelled", {})
            return {}

        collected_raw_findings: list[dict[str, Any]] = []

        def run_single_investigator(inv: dict[str, Any]) -> list[dict[str, Any]]:
            ag_id = inv["agent_id"]
            ag_graph = f"agent_{self.run_id}_{ag_id}"
            self._emit(emit_fn, "agent_started", {"agent_id": ag_id, "skill": inv["skill_id"]})

            # Bind tools
            tool_suite = ContextGraphTools(
                store=self.store,
                graph_name=ag_graph,
                agent_id=ag_id,
                recorder=self.recorder,
                llm=self.llm,
            )

            # Build tool dispatch mapping
            tool_map: dict[str, Callable[..., Any]] = {
                "neighbors": tool_suite.neighbors,
                "paths_between": tool_suite.paths_between,
                "shortest_path": tool_suite.shortest_path,
                "shared_attributes": tool_suite.shared_attributes,
                "common_neighbors": tool_suite.common_neighbors,
                "cluster_of": tool_suite.cluster_of,
                "central_nodes": tool_suite.central_nodes,
                "timeline": tool_suite.timeline,
                "source_mentions": tool_suite.source_mentions,
                "ask_graph": tool_suite.ask_graph,
            }

            active_tools = [tool_map[t] for t in inv["tools"] if t in tool_map]
            if not active_tools:
                active_tools = [tool_suite.neighbors, tool_suite.paths_between]

            call_count = 0

            def call_tool_wrapper(name: str, args: dict[str, Any]) -> Any:
                nonlocal call_count
                call_count += 1
                t0 = time.time()
                fn = tool_map.get(name, tool_suite.neighbors)
                res = fn(**args)
                duration_ms = int((time.time() - t0) * 1000)

                # Record observed entities
                if isinstance(res, list):
                    for item in res:
                        if isinstance(item, dict) and "cid" in item:
                            self.observed_cids.add(item["cid"])

                self._emit(emit_fn, "tool_call", {
                    "agent_id": ag_id,
                    "tool": name,
                    "args_summary": str(args)[:100],
                    "duration_ms": duration_ms,
                })
                # Emit any newly recorded steps
                for step in self.recorder.get_steps():
                    self.observed_cids.add(step.from_cid)
                    self.observed_cids.add(step.to_cid)
                    self.observed_edges.add((step.from_cid, step.to_cid, step.rel))
                    self._emit(emit_fn, "traversal_step", {
                        "seq": step.seq,
                        "tool": step.tool,
                        "agent_id": step.agent_id,
                        "from": step.from_cid,
                        "to": step.to_cid,
                        "rel": step.rel,
                        "note": step.note,
                    })
                return res

            sys_prompt = (
                f"You are an investigator with the skill {inv['skill_name']}: {inv['prompt_fragment']}\n"
                f"Goal: {inv['goal']}\n"
                f"Entities of interest (use these exact identifiers in tool calls): {', '.join(seed_cids)}\n"
                f"Use only your tools to gather evidence from the graph. Every claim you report must cite "
                f"evidence cids that appeared in your tool outputs. Report absence honestly: if you looked "
                f"and found no connection within the hop limit, report kind 'absence'. Finish by returning ONLY JSON "
                f"with schema: {{\"findings\": [{{\"kind\": \"path\"|\"link\"|\"cluster\"|\"timeline\"|\"fact\"|\"absence\", \"claim\": \"...\", \"subject_cids\": [\"...\"], \"evidence_cids\": [\"...\"], \"confidence\": 0.0..1.0}}]}}"
            )
            user_prompt = f"Investigate the network around: {', '.join(seed_cids)}"

            try:
                loop_out = self.llm.run_tool_loop(
                    system=sys_prompt,
                    user=user_prompt,
                    tools=active_tools,
                    call_tool=call_tool_wrapper,
                    max_steps=8,
                )
                parsed_findings = []
                try:
                    f_dict = json.loads(loop_out)
                    parsed_findings = f_dict.get("findings", [])
                except Exception:
                    match = re.search(r"\{.*\}", loop_out, re.DOTALL)
                    if match:
                        try:
                            f_dict = json.loads(match.group(0))
                            parsed_findings = f_dict.get("findings", [])
                        except Exception:
                            pass

                self._emit(emit_fn, "agent_done", {"agent_id": ag_id, "findings_count": len(parsed_findings)})
                return parsed_findings
            except Exception as ag_err:
                self._emit(emit_fn, "agent_failed", {"agent_id": ag_id, "reason": str(ag_err)})
                return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.investigators_limit) as executor:
            future_to_inv = {executor.submit(run_single_investigator, inv): inv for inv in investigator_configs}
            for fut in concurrent.futures.as_completed(future_to_inv):
                findings_batch = fut.result()
                collected_raw_findings.extend(findings_batch)

        # ---------------------------------------------------------------------
        # Step 7: PROMOTE & VERIFY FINDINGS
        # ---------------------------------------------------------------------
        if is_cancelled():
            self._emit(emit_fn, "cancelled", {})
            return {}

        verified_findings = []
        rejected_findings = []

        for f_idx, rf in enumerate(collected_raw_findings, start=1):
            claim = rf.get("claim") or f"Finding {f_idx}"
            kind = rf.get("kind") or "fact"
            subj_cids = rf.get("subject_cids") or seed_cids[:1] or ["unknown"]
            ev_cids = rf.get("evidence_cids") or []
            conf = float(rf.get("confidence") or 0.8)

            # Verification: evidence must be observed
            ev_ok = all(e_cid in self.observed_cids for e_cid in ev_cids) if ev_cids else True

            f_id = f"find_{self.run_id[:6]}_{f_idx}"
            if ev_ok:
                verified_findings.append({
                    "id": f_id,
                    "agent_id": f"agent_subtask_1",
                    "skill_id": "relationship-tracer",
                    "kind": kind,
                    "claim": claim,
                    "subject_cids": subj_cids,
                    "evidence_cids": ev_cids,
                    "confidence": conf,
                    "status": "active",
                    "backend": "llm",
                })
            else:
                rejected_findings.append({
                    "id": f_id,
                    "claim": claim,
                    "reason": "evidence_not_observed",
                })

        # De-duplicate findings with same kind + subject_cids
        seen_keys = {}
        final_findings = []
        superseded_count = 0
        for f in verified_findings:
            key = (f["kind"], tuple(sorted(f["subject_cids"])))
            if key not in seen_keys:
                seen_keys[key] = f
                final_findings.append(f)
            else:
                existing = seen_keys[key]
                if f["confidence"] > existing["confidence"]:
                    existing["status"] = "superseded"
                    seen_keys[key] = f
                    final_findings.append(f)
                else:
                    f["status"] = "superseded"
                    final_findings.append(f)
                superseded_count += 1

        self._emit(emit_fn, "promoted", {
            "findings": final_findings,
            "promoted": len([f for f in final_findings if f["status"] == "active"]),
            "rejected": len(rejected_findings),
            "superseded": superseded_count,
        })

        # ---------------------------------------------------------------------
        # Step 8: ANSWER
        # ---------------------------------------------------------------------
        if is_cancelled():
            self._emit(emit_fn, "cancelled", {})
            return {}

        active_findings = [f for f in final_findings if f["status"] == "active"]

        # Gather node names for cited cids
        cids_to_resolve = set(self.observed_cids)
        for f in active_findings:
            cids_to_resolve.update(f["subject_cids"])
            cids_to_resolve.update(f["evidence_cids"])

        name_lookup = {}
        if cids_to_resolve:
            name_rows = self.store.query(
                self.ctx_graph,
                "MATCH (n) WHERE n.cid IN $cids RETURN n.cid AS cid, n.name AS name",
                {"cids": list(cids_to_resolve)},
            )
            for r in name_rows:
                name_lookup[r["cid"]] = r.get("name") or r["cid"]

        findings_summary_lines = []
        for f in active_findings:
            sub_names = [name_lookup.get(c, c) for c in f["subject_cids"]]
            ev_names = [name_lookup.get(c, c) for c in f["evidence_cids"]]
            findings_summary_lines.append(
                f"- [{f['kind'].upper()}] {f['claim']} (Subjects: {', '.join(f['subject_cids'])}; Evidence: {', '.join(f['evidence_cids'])})"
            )

        answer_sys = (
            "Answer the user's question using ONLY the verified findings provided. "
            "Cite every entity you mention as [[cid]] using the exact cids given. "
            "Structure:\n"
            "First a direct answer of 2 to 5 sentences;\n"
            "then 'HOW THEY CONNECT' as a numbered list of hops written as [[cid]] relation [[cid]];\n"
            "then 'NOT CHECKED' listing limits (hop limit, truncated slice, failed investigators, rejected findings).\n"
            "If there are no findings, say plainly that nothing was found within the limits. "
            "Never state a number for confidence."
        )
        answer_user = (
            f"Question: {self.question}\n\n"
            f"Verified Findings:\n" + ("\n".join(findings_summary_lines) if findings_summary_lines else "None") + "\n\n"
            f"Coverage Notes: Max hops={self.max_hops}, Slice truncated={slice_truncated}, Rejected findings={len(rejected_findings)}"
        )

        answer_text = self.llm.complete_text(answer_sys, answer_user)

        # Strip unobserved CIDs
        cited_cids = re.findall(r"\[\[(.*?)\]\]", answer_text)
        cleaned_cids = []
        stripped_any = False
        for c in cited_cids:
            if c in self.observed_cids or c in seed_cids:
                cleaned_cids.append(c)
            else:
                answer_text = answer_text.replace(f"[[{c}]]", c)
                stripped_any = True

        if stripped_any:
            warnings.append("Some unobserved entity citations were stripped from the generated answer")

        # Append computed confidence line
        confs = [f["confidence"] for f in active_findings]
        mean_conf = sum(confs) / len(confs) if confs else 0.5
        conf_tier = "low" if mean_conf < 0.5 else ("medium" if mean_conf < 0.75 else "high")
        answer_text += f"\n\nConfidence: {conf_tier} ({mean_conf:.2f})"

        model_name = getattr(self.llm, "model", "default")
        self._emit(emit_fn, "answer", {
            "text": answer_text,
            "cited_cids": list(set(cleaned_cids)),
            "backend": "llm",
            "model": model_name,
        })

        # Persist Answer in run graph
        ans_id = f"ans_{self.run_id[:8]}"
        self.store.query(
            self.run_graph,
            f"MATCH (t:{LABEL_TASK} {{id: $task_id}}) "
            f"CREATE (a:{LABEL_ANSWER} {{id: $ans_id, text: $text, backend: 'llm', model: $model}}) "
            f"CREATE (t)-[:{REL_ANSWERED_BY}]->(a)",
            {"task_id": task_id, "ans_id": ans_id, "text": answer_text, "model": model_name},
        )

        # Promote traversal steps to run graph
        self.recorder.promote_to_run_graph(self.run_graph, task_id, self.observed_cids)

        # ---------------------------------------------------------------------
        # Step 9: MESSAGE ASSEMBLY & TURN PERSISTENCE
        # ---------------------------------------------------------------------
        # Build blocks
        blocks: list[dict[str, Any]] = [
            {"type": "plan", "data": {"subtasks": subtasks}},
            {"type": "skills", "data": {"assignments": skill_assignments}},
            {"type": "findings", "data": {"items": final_findings}},
            {
                "type": "answer",
                "data": {
                    "text": answer_text,
                    "cited_cids": list(set(cleaned_cids)),
                    "backend": "llm",
                    "model": model_name,
                },
            },
            {
                "type": "trace_preview",
                "data": {
                    "run_id": self.run_id,
                    "mode": "traversal",
                    "path_node_ids": list(set(cleaned_cids)),
                    "summary": f"{len(active_findings)} findings verified across {len(self.observed_cids)} entities",
                },
            },
        ]
        for w in warnings:
            blocks.append({"type": "warning", "data": {"text": w}})

        self.case_store.add_turn(self.case_id, role="assistant", blocks=blocks, run_id=self.run_id)

        # ---------------------------------------------------------------------
        # Step 10: LEARNING (Update SUCCEEDED_ON in atlas)
        # ---------------------------------------------------------------------
        if final_findings:
            promoted_share = len(active_findings) / len(final_findings)
            for inv in investigator_configs:
                try:
                    self.store.query(
                        GRAPH_ATLAS,
                        "MATCH (k:Skill {id: $sk_id}) "
                        "SET k.score = round(k.score * 0.8 + $share * 0.2, 3), k.runs = k.runs + 1",
                        {"sk_id": inv["skill_id"], "share": promoted_share},
                    )
                except Exception:
                    pass

        self._emit(emit_fn, "completed", {"run_id": self.run_id, "status": "completed"})
        return {"status": "completed", "answer": answer_text}
