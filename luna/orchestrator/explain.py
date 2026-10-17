"""Explain ('Why?') provenance engine providing deterministic audit trails for actions and customer verdicts."""

import json
from typing import Any, Optional
from pydantic import BaseModel, Field

from luna.graph.store import GraphStore
from luna.graph.schema import (
    LABEL_FINDING,
    LABEL_CUSTOMER,
    LABEL_DECISION,
    LABEL_ACTION,
    LABEL_AGENT,
    REL_BASED_ON,
    REL_PROMOTED_FROM,
    REL_ASSESSES,
    REL_SUPPORTED_BY,
    REL_UPHELD,
    REL_SUPERSEDES,
    REL_ABOUT,
    REL_FOR,
    REL_CHOSE,
    REL_REJECTED,
)


class SkillChoiceView(BaseModel):
    """Provenance view of a skill selection decision for a subtask."""

    subtask_id: str
    capability: str
    chosen_skill_id: str
    rejected: list[dict[str, str]] = Field(default_factory=list)
    confidence: float = 1.0
    backend: str = "rules"


class FindingView(BaseModel):
    """View of an active or superseded finding promoting evidence."""

    id: str
    agent_id: str
    skill_id: str
    verdict: str
    confidence: float
    status: str
    backend: str
    fallback_reason: Optional[str] = None
    reasoning: str = ""
    evidence_cids: list[str] = Field(default_factory=list)


class DecisionView(BaseModel):
    """View of a per-customer arbitration decision resolving contradictory findings."""

    id: str
    chosen_verdict: str
    confidence: float
    components: dict[str, Any] = Field(default_factory=dict)
    weights: dict[str, Any] = Field(default_factory=dict)
    skill_scores: dict[str, Any] = Field(default_factory=dict)
    upheld_finding_id: str
    superseded_finding_ids: list[str] = Field(default_factory=list)


class CustomerExplanation(BaseModel):
    """Comprehensive explainability record for a single customer verdict."""

    target_cid: str
    final_verdict: str
    findings: list[FindingView] = Field(default_factory=list)
    decision: Optional[DecisionView] = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    skill_choices: list[SkillChoiceView] = Field(default_factory=list)
    narrative: str = ""


class ExplainResult(BaseModel):
    """Top-level explainability record for a proposed or executed Action across all targets."""

    run_id: str
    action_id: Optional[str] = None
    customers: list[CustomerExplanation] = Field(default_factory=list)
    skill_choices: list[SkillChoiceView] = Field(default_factory=list)
    graph_path: dict[str, Any] = Field(default_factory=dict)
    narrative: str = ""


def _fetch_skill_choices(store: GraphStore, run_graph_name: str) -> list[SkillChoiceView]:
    """Fetch all skill assignment decisions stored in the run graph."""
    query = (
        f"MATCH (d:{LABEL_DECISION} {{kind: 'skill_assignment'}})-[:{REL_FOR}]->(sub) "
        f"OPTIONAL MATCH (d)-[:{REL_CHOSE}]->(chosen) "
        "RETURN d.id AS id, d.confidence AS confidence, d.backend AS backend, "
        "       sub.id AS subtask_id, sub.capability AS capability, "
        "       chosen.id AS chosen_id"
    )
    rows = store.query(run_graph_name, query)
    choices: list[SkillChoiceView] = []

    for row in rows:
        dec_id = row.get("id")
        subtask_id = str(row.get("subtask_id") or "")
        capability = str(row.get("capability") or "")
        chosen_id = str(row.get("chosen_id") or "")
        confidence = float(row.get("confidence") or 1.0)
        backend = str(row.get("backend") or "rules")

        # Query rejected skills for this decision
        rej_query = (
            f"MATCH (d:{LABEL_DECISION} {{id: $did}})-[r:{REL_REJECTED}]->(rej) "
            "RETURN rej.id AS rej_id, r.reason AS reason"
        )
        rej_rows = store.query(run_graph_name, rej_query, {"did": dec_id})
        rejected_list: list[dict[str, str]] = []
        for rrow in rej_rows:
            rid = rrow.get("rej_id")
            if rid:
                rejected_list.append({
                    "skill_id": str(rid),
                    "reason": str(rrow.get("reason") or "Alternative candidate"),
                })

        choices.append(
            SkillChoiceView(
                subtask_id=subtask_id,
                capability=capability,
                chosen_skill_id=chosen_id,
                rejected=rejected_list,
                confidence=confidence,
                backend=backend,
            )
        )

    return choices


def explain_customer(
    store: GraphStore,
    run_graph_name: str,
    target_cid: str,
) -> CustomerExplanation:
    """Produce deterministic audit explanation for a specific customer without querying the atlas.

    Traces:
    - Findings (both active and superseded) assessing target_cid
    - Contestation Decision (if customer had conflicting findings arbitrated)
    - Entities supporting findings
    - Skill selection decisions from run memory
    """
    # 1. Fetch all findings assessing target_cid
    finding_query = (
        f"MATCH (f:{LABEL_FINDING})-[:{REL_ASSESSES}]->(c:{LABEL_CUSTOMER} {{cid: $cid}}) "
        f"OPTIONAL MATCH (f)-[:{REL_PROMOTED_FROM}]->(ag:{LABEL_AGENT}) "
        "RETURN f.id AS id, f.agent_id AS agent_id, ag.id AS ag_node_id, "
        "       f.skill_id AS skill_id, f.verdict AS verdict, f.confidence AS confidence, "
        "       f.status AS status, f.backend AS backend, f.fallback_reason AS fallback_reason, "
        "       f.reasoning AS reasoning, f.evidence_cids AS evidence_cids"
    )
    f_rows = store.query(run_graph_name, finding_query, {"cid": target_cid})

    findings: list[FindingView] = []
    evidence_cids_all: set[str] = set()

    for r in f_rows:
        fid = str(r.get("id"))
        raw_ev = r.get("evidence_cids")
        ev_list: list[str] = []
        if isinstance(raw_ev, list):
            ev_list = [str(x) for x in raw_ev]
        elif isinstance(raw_ev, str) and raw_ev:
            try:
                parsed = json.loads(raw_ev)
                if isinstance(parsed, list):
                    ev_list = [str(x) for x in parsed]
                else:
                    ev_list = [raw_ev]
            except Exception:
                ev_list = [raw_ev]

        for e in ev_list:
            evidence_cids_all.add(e)

        findings.append(
            FindingView(
                id=fid,
                agent_id=str(r.get("agent_id") or r.get("ag_node_id") or "unknown_agent"),
                skill_id=str(r.get("skill_id") or "unknown_skill"),
                verdict=str(r.get("verdict") or "unknown"),
                confidence=float(r.get("confidence") or 0.0),
                status=str(r.get("status") or "active"),
                backend=str(r.get("backend") or "rules"),
                fallback_reason=r.get("fallback_reason"),
                reasoning=str(r.get("reasoning") or ""),
                evidence_cids=ev_list,
            )
        )

    # 2. Fetch evidence nodes connected via SUPPORTED_BY
    ev_query = (
        f"MATCH (f:{LABEL_FINDING})-[:{REL_ASSESSES}]->(c:{LABEL_CUSTOMER} {{cid: $cid}}) "
        f"MATCH (f)-[:{REL_SUPPORTED_BY}]->(e) "
        "RETURN DISTINCT e.cid AS cid, e.id AS id, e.type AS type, labels(e) AS lbls"
    )
    ev_rows = store.query(run_graph_name, ev_query, {"cid": target_cid})
    evidence_items: list[dict[str, Any]] = []
    seen_evidence_cids: set[str] = set()

    for er in ev_rows:
        ecid = str(er.get("cid") or er.get("id") or "")
        if ecid and ecid not in seen_evidence_cids:
            seen_evidence_cids.add(ecid)
            etype = er.get("type")
            if not etype:
                lbls = er.get("lbls")
                if isinstance(lbls, list) and lbls:
                    etype = lbls[0]
                else:
                    etype = "Entity"
            evidence_items.append({"cid": ecid, "label": str(etype)})

    # Also include any evidence_cids from findings that did not have explicit SUPPORTED_BY nodes
    for ecid in evidence_cids_all:
        if ecid not in seen_evidence_cids:
            seen_evidence_cids.add(ecid)
            evidence_items.append({"cid": ecid, "label": "Entity"})

    # 3. Check for Decision node about target_cid
    dec_query = (
        f"MATCH (d:{LABEL_DECISION})-[:{REL_ABOUT}]->(c:{LABEL_CUSTOMER} {{cid: $cid}}) "
        f"OPTIONAL MATCH (d)-[:{REL_UPHELD}]->(f_win:{LABEL_FINDING}) "
        f"OPTIONAL MATCH (d)-[:{REL_SUPERSEDES}]->(f_lose:{LABEL_FINDING}) "
        "RETURN d.id AS id, d.chosen_verdict AS chosen_verdict, d.confidence AS confidence, "
        "       d.component_scores AS component_scores, d.weights AS weights, "
        "       d.skill_scores_json AS skill_scores_json, d.winning_finding_id AS winning_finding_id, "
        "       f_win.id AS upheld_id, collect(DISTINCT f_lose.id) AS superseded_ids"
    )
    dec_rows = store.query(run_graph_name, dec_query, {"cid": target_cid})

    decision_view: Optional[DecisionView] = None
    final_verdict = "unknown"

    if dec_rows:
        dr = dec_rows[0]
        d_id = str(dr.get("id") or "")
        d_verdict = str(dr.get("chosen_verdict") or "")
        d_conf = float(dr.get("confidence") or 0.0)
        upheld_id = str(dr.get("winning_finding_id") or dr.get("upheld_id") or "")

        def _safe_json_dict(val: Any) -> dict[str, Any]:
            if isinstance(val, dict):
                return val
            if isinstance(val, str) and val:
                try:
                    p = json.loads(val)
                    if isinstance(p, dict):
                        return p
                except Exception:
                    pass
            return {}

        comps = _safe_json_dict(dr.get("component_scores"))
        wts = _safe_json_dict(dr.get("weights"))
        skills = _safe_json_dict(dr.get("skill_scores_json"))

        raw_sup = dr.get("superseded_ids") or []
        sup_ids = [str(x) for x in raw_sup if x]

        decision_view = DecisionView(
            id=d_id,
            chosen_verdict=d_verdict,
            confidence=d_conf,
            components=comps,
            weights=wts,
            skill_scores=skills,
            upheld_finding_id=upheld_id,
            superseded_finding_ids=sup_ids,
        )
        final_verdict = d_verdict
    else:
        # Uncontested customer: determine verdict from active findings
        active_findings = [f for f in findings if f.status == "active"]
        if active_findings:
            # Sort by confidence descending
            active_findings.sort(key=lambda x: x.confidence, reverse=True)
            final_verdict = active_findings[0].verdict
        elif findings:
            findings_sorted = sorted(findings, key=lambda x: x.confidence, reverse=True)
            final_verdict = findings_sorted[0].verdict
        else:
            final_verdict = "benign"

    # 4. Fetch skill choices
    skill_choices = _fetch_skill_choices(store, run_graph_name)

    # 5. Deterministic narrative construction
    ev_str = ", ".join(f"{item['cid']} ({item['label']})" for item in evidence_items) or "None"
    agents_involved = sorted(list({f.agent_id for f in findings}))
    skills_involved = sorted(list({f.skill_id for f in findings}))

    if decision_view:
        upheld_f = next((f for f in findings if f.id == decision_view.upheld_finding_id), None)
        u_skill = upheld_f.skill_id if upheld_f else "unknown"
        u_agent = upheld_f.agent_id if upheld_f else "unknown"
        sup_count = len(decision_view.superseded_finding_ids)
        narrative = (
            f"Customer '{target_cid}' was contested and arbitrated to final verdict '{final_verdict}' "
            f"(confidence: {decision_view.confidence:.2f}). Upheld winning finding '{decision_view.upheld_finding_id}' "
            f"by skill '{u_skill}' (agent: {u_agent}). Superseded {sup_count} conflicting alternative finding(s) "
            f"({', '.join(decision_view.superseded_finding_ids)}). Score components: {decision_view.components}. "
            f"Evidence items: [{ev_str}]."
        )
    else:
        active_f = [f for f in findings if f.status == "active"]
        best_conf = active_f[0].confidence if active_f else (findings[0].confidence if findings else 0.0)
        narrative = (
            f"Customer '{target_cid}' evaluated as '{final_verdict}' (confidence: {best_conf:.2f}) "
            f"based on uncontested finding(s) by agent(s) {agents_involved} using skill(s) {skills_involved}. "
            f"Evidence items: [{ev_str}]."
        )

    return CustomerExplanation(
        target_cid=target_cid,
        final_verdict=final_verdict,
        findings=findings,
        decision=decision_view,
        evidence=evidence_items,
        skill_choices=skill_choices,
        narrative=narrative,
    )


def explain_action(
    store: GraphStore,
    run_graph_name: str,
    action_id: str,
) -> ExplainResult:
    """Produce complete explainability result for a proposed or executed Action.

    Traces:
    - Action -> Finding -> Entity
    - Finding -> Agent
    - Contestation Decisions for target customers
    - Graph path dictionary with well-formed, JSON-serializable nodes and edges
    """
    # 1. Fetch Action node
    act_query = (
        f"MATCH (a:{LABEL_ACTION} {{id: $aid}}) "
        "RETURN a.id AS id, a.kind AS kind, a.action_type AS action_type, "
        "       a.status AS status, a.target_cids AS target_cids, a.target_cid AS target_cid"
    )
    act_rows = store.query(run_graph_name, act_query, {"aid": action_id})
    if not act_rows:
        raise ValueError(f"Action '{action_id}' not found in run graph '{run_graph_name}'")

    ar = act_rows[0]
    raw_targets = ar.get("target_cids")
    target_cids: list[str] = []
    if isinstance(raw_targets, list):
        target_cids = [str(x) for x in raw_targets if x]
    elif isinstance(raw_targets, str) and raw_targets:
        try:
            parsed = json.loads(raw_targets)
            if isinstance(parsed, list):
                target_cids = [str(x) for x in parsed if x]
            else:
                target_cids = [raw_targets]
        except Exception:
            target_cids = [raw_targets]

    if not target_cids and ar.get("target_cid"):
        target_cids = [str(ar["target_cid"])]

    # Fetch findings linked to this action via BASED_ON
    bf_query = (
        f"MATCH (a:{LABEL_ACTION} {{id: $aid}})-[:{REL_BASED_ON}]->(f:{LABEL_FINDING}) "
        "RETURN f.id AS fid, f.target_cid AS target_cid"
    )
    bf_rows = store.query(run_graph_name, bf_query, {"aid": action_id})
    for bfr in bf_rows:
        tcid = bfr.get("target_cid")
        if tcid and tcid not in target_cids:
            target_cids.append(str(tcid))

    # Derive bare run_id from run_graph_name
    run_id = run_graph_name[4:] if run_graph_name.startswith("run_") else run_graph_name

    # 2. Explain each target customer
    customer_explanations: list[CustomerExplanation] = []
    for cid in target_cids:
        c_exp = explain_customer(store, run_graph_name, cid)
        customer_explanations.append(c_exp)

    # 3. Fetch skill choices
    skill_choices = _fetch_skill_choices(store, run_graph_name)

    # 4. Construct graph path (nodes and edges)
    nodes_dict: dict[str, dict[str, Any]] = {}
    edges_list: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def _add_node(nid: str, label: str, props: dict[str, Any]) -> None:
        if nid not in nodes_dict:
            # Ensure props are JSON serializable
            clean_props = {k: v for k, v in props.items() if v is not None}
            nodes_dict[nid] = {"id": nid, "label": label, "props": clean_props}

    def _add_edge(src: str, dst: str, rel: str) -> None:
        key = (src, dst, rel)
        if key not in seen_edges:
            seen_edges.add(key)
            edges_list.append({"src": src, "dst": dst, "rel": rel})

    # Add Action node
    _add_node(
        action_id,
        LABEL_ACTION,
        {"id": action_id, "kind": ar.get("kind") or ar.get("action_type"), "status": ar.get("status")},
    )

    for c_exp in customer_explanations:
        cid = c_exp.target_cid
        _add_node(cid, LABEL_CUSTOMER, {"cid": cid, "final_verdict": c_exp.final_verdict})

        # Add findings
        for f in c_exp.findings:
            _add_node(
                f.id,
                LABEL_FINDING,
                {
                    "id": f.id,
                    "verdict": f.verdict,
                    "confidence": f.confidence,
                    "status": f.status,
                    "skill_id": f.skill_id,
                    "backend": f.backend,
                },
            )
            # Edge Action -> Finding (if linked)
            _add_edge(action_id, f.id, REL_BASED_ON)
            # Edge Finding -> Customer
            _add_edge(f.id, cid, REL_ASSESSES)

            # Edge Finding -> Agent
            if f.agent_id:
                _add_node(f.agent_id, LABEL_AGENT, {"id": f.agent_id})
                _add_edge(f.id, f.agent_id, REL_PROMOTED_FROM)

            # Edge Finding -> Evidence Entities
            for ecid in f.evidence_cids:
                _add_node(ecid, "Entity", {"cid": ecid})
                _add_edge(f.id, ecid, REL_SUPPORTED_BY)

        # Add Decision if present
        if c_exp.decision:
            d = c_exp.decision
            _add_node(
                d.id,
                LABEL_DECISION,
                {
                    "id": d.id,
                    "chosen_verdict": d.chosen_verdict,
                    "confidence": d.confidence,
                },
            )
            _add_edge(d.id, cid, REL_ABOUT)
            if d.upheld_finding_id:
                _add_edge(d.id, d.upheld_finding_id, REL_UPHELD)
            for sid in d.superseded_finding_ids:
                _add_edge(d.id, sid, REL_SUPERSEDES)

    graph_path = {
        "nodes": list(nodes_dict.values()),
        "edges": edges_list,
    }

    # 5. Build overall deterministic narrative
    lines = [
        f"Action '{action_id}' (status: {ar.get('status')}) targets {len(customer_explanations)} customer(s):"
    ]
    for c_exp in customer_explanations:
        lines.append(f"  * {c_exp.narrative}")
    narrative = "\n".join(lines)

    return ExplainResult(
        run_id=run_id,
        action_id=action_id,
        customers=customer_explanations,
        skill_choices=skill_choices,
        graph_path=graph_path,
        narrative=narrative,
    )
