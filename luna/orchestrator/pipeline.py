"""Autonomous multi-agent pipeline orchestrator with thread-safe event stream and concurrency safety."""

import asyncio
import concurrent.futures
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from pydantic import BaseModel, Field

from luna.graph.store import GraphStore
from luna.graph.schema import (
    GRAPH_ATLAS,
    GRAPH_DOMAIN,
    run_graph_name as get_run_graph_name,
    agent_graph_name,
    LABEL_TASK,
    LABEL_SUBTASK,
    LABEL_AGENT,
    LABEL_SKILL,
    LABEL_ACTION,
    LABEL_OUTCOME,
    LABEL_CUSTOMER,
)
from luna.atlas.seed import seed_atlas
from luna.domain.seed import seed_domain, GroundTruth
from luna.planner.decompose import decompose_task, Subtask
from luna.atlas.assign import assign_skills_to_subtasks, equip_agent_with_skill
from luna.agents.models import Finding, SubAgentRunConfig
from luna.agents.subagent import SubAgent
from luna.agents.provenance import ToolCallLog
from luna.mcp.client import open_stdio_client
from luna.orchestrator.slice import extract_subgraph_slice
from luna.orchestrator.promote import promote_findings
from luna.orchestrator.conflicts import detect_contradictions
from luna.orchestrator.resolve import resolve_conflicts
from luna.orchestrator.actions import (
    propose_actions,
    approve_action,
    reject_action,
    execute_action,
    evaluate_outcomes,
    EvaluationMetrics,
)
from luna.atlas.learner import learn_from_run
from luna.orchestrator.explain import explain_action
from luna.llm.client import LLMClient, MockLLMClient

logger = logging.getLogger(__name__)


class PipelineConfig(BaseModel):
    """Configuration for an autonomous investigation pipeline run."""

    run_id: str
    domain_graph: str = GRAPH_DOMAIN
    atlas_graph: str = GRAPH_ATLAS
    task_type: str = "fraud_ring_investigation"
    k_hops: int = 2
    strict_llm: bool = False
    max_parallel_agents: int = 3
    min_confidence: float = 0.6
    require_observed: bool = True
    max_hops: Optional[int] = 3
    seed_cids: Optional[list[str]] = None
    llm_client: Optional[Any] = None
    keep_slice_graphs: bool = False

    def normalized_run_id(self) -> str:
        """Return bare run ID without redundant 'run_' prefix."""
        return self.run_id[4:] if self.run_id.startswith("run_") else self.run_id

    def run_graph_name(self) -> str:
        """Return canonical run graph name."""
        return f"run_{self.normalized_run_id()}"


class PipelineEvent(BaseModel):
    """Discrete, monotonic event emitted during pipeline lifecycle."""

    step: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    seq: int


class PipelineRunResult(BaseModel):
    """Immutable outcome report of a pipeline execution phase."""

    run_id: str
    status: str
    action_id: Optional[str] = None
    outcome_id: Optional[str] = None
    metrics: Optional[EvaluationMetrics] = None
    backend_counts: dict[str, int] = Field(default_factory=lambda: {"llm": 0, "rules": 0, "scripted": 0})
    rejected_findings: list[dict[str, Any]] = Field(default_factory=list)
    conflicts_resolved: int = 0
    events: list[PipelineEvent] = Field(default_factory=list)
    skill_scores_before: dict[str, float] = Field(default_factory=dict)
    skill_scores_after: dict[str, float] = Field(default_factory=dict)


def find_seeds(store: GraphStore, domain_graph_name: str) -> list[str]:
    """Find investigative seed customer CIDs in domain graph.

    Guarantees inclusion of both ring and decoy candidates in demo scenarios
    to trigger genuine conflict detection and resolution.
    """
    seeds: list[str] = []
    # 1. Ring candidate
    ring_check = store.query(domain_graph_name, "MATCH (c:Customer {cid: 'cust_ring_1'}) RETURN c.cid AS cid")
    if ring_check:
        seeds.append("cust_ring_1")
    else:
        ring_recs = store.query(
            domain_graph_name,
            "MATCH (c:Customer)-[:PAYS_FROM]->(b:BankAccount) "
            "WITH b, collect(c.cid) AS cids WHERE size(cids) > 1 "
            "RETURN cids[0] AS cid LIMIT 1",
        )
        if ring_recs and ring_recs[0].get("cid"):
            seeds.append(str(ring_recs[0]["cid"]))

    # 2. Decoy candidate
    decoy_check = store.query(domain_graph_name, "MATCH (c:Customer {cid: 'cust_decoy_1'}) RETURN c.cid AS cid")
    if decoy_check:
        seeds.append("cust_decoy_1")
    else:
        decoy_recs = store.query(
            domain_graph_name,
            "MATCH (c:Customer)-[:LIVES_AT]->(a:Address) "
            "WHERE NOT (c)-[:PAYS_FROM]->(:BankAccount)<-[:PAYS_FROM]-(:Customer) "
            "WITH a, collect(c.cid) AS cids WHERE size(cids) > 1 "
            "RETURN cids[0] AS cid LIMIT 1",
        )
        if decoy_recs and decoy_recs[0].get("cid"):
            seeds.append(str(decoy_recs[0]["cid"]))

    if not seeds:
        # Fallback to any customers in domain
        any_recs = store.query(domain_graph_name, "MATCH (c:Customer) RETURN c.cid AS cid LIMIT 2")
        seeds = [str(r["cid"]) for r in any_recs if r.get("cid")]

    return seeds


class LunaPipeline:
    """Autonomous orchestrator managing the full investigation lifecycle."""

    def __init__(self, store: GraphStore, config: PipelineConfig) -> None:
        self.store = store
        self.config = config
        self.run_id = config.normalized_run_id()
        self.run_graph = config.run_graph_name()

        self._events: list[PipelineEvent] = []
        self._seq_counter = 0
        self._event_lock = threading.Lock()
        self._subscribers: list[Callable[[PipelineEvent], None]] = []
        self._scores_before: dict[str, float] = {}

    def subscribe(self, callback: Callable[[PipelineEvent], None]) -> None:
        """Register a subscriber callback for streaming pipeline events."""
        with self._event_lock:
            self._subscribers.append(callback)

    def emit(self, step: str, message: str, data: Optional[dict[str, Any]] = None) -> PipelineEvent:
        """Thread-safe event emission guaranteeing strictly monotonic sequence numbers."""
        with self._event_lock:
            self._seq_counter += 1
            event = PipelineEvent(
                step=step,
                message=message,
                data=data or {},
                timestamp=datetime.now(timezone.utc).isoformat(),
                seq=self._seq_counter,
            )
            self._events.append(event)
            for sub in self._subscribers:
                try:
                    sub(event)
                except Exception as err:
                    logger.warning("Event subscriber error: %s", err)
            return event

    def _get_skill_scores(self) -> dict[str, float]:
        """Fetch current reputation scores for skills in atlas."""
        query = (
            f"MATCH (s:{LABEL_SKILL})-[r:SUCCEEDED_ON]->(t:TaskType {{name: $task_type}}) "
            "RETURN s.id AS id, r.score AS score"
        )
        rows = self.store.query(self.config.atlas_graph, query, {"task_type": self.config.task_type})
        return {r["id"]: float(r["score"]) for r in rows if r.get("id") and r.get("score") is not None}

    def _run_single_agent(
        self,
        agent_id: str,
        skill_id: str,
        prompt_fragment: str,
        target_cids: list[str],
        slice_graph_name: str,
        exposed_tools: list[str],
        llm_client: Any,
        strict_llm: bool,
    ) -> tuple[str, list[Finding], ToolCallLog]:
        """Run a single sub-agent on its isolated stdio FastMCP server inside worker thread."""
        config = SubAgentRunConfig(
            agent_id=agent_id,
            skill_id=skill_id,
            prompt_fragment=prompt_fragment,
            target_cids=target_cids,
            private_graph_name=slice_graph_name,
        )

        async def _exec():
            async with open_stdio_client(
                agent_id=agent_id,
                graph_name=slice_graph_name,
                tool_names=exposed_tools,
            ) as mcp_client:
                agent = SubAgent(
                    config=config,
                    mcp_client=mcp_client,
                    llm_client=llm_client,
                    strict_llm=strict_llm,
                )
                findings = await agent.run()
                return findings, agent.tool_log

        findings, tool_log = asyncio.run(_exec())
        return agent_id, findings, tool_log

    def start(
        self,
        task_description: str,
        ground_truth: Optional[GroundTruth] = None,
        injected_subtasks: Optional[list[Subtask]] = None,
    ) -> PipelineRunResult:
        """Run workflow up to propose: stops with Action PENDING for review."""
        now = datetime.now(timezone.utc).isoformat()
        llm = self.config.llm_client or MockLLMClient()

        try:
            # Step 1: Init & graph existence check
            self.emit("init", f"Initializing run '{self.run_id}'", {"run_id": self.run_id})

            # Guarantee fresh run graph
            try:
                self.store.delete_graph(self.run_graph)
            except Exception:
                pass

            # Check atlas graph; seed if empty
            atlas_cnt = self.store.query(self.config.atlas_graph, "MATCH (n) RETURN count(n) AS cnt")
            if not atlas_cnt or atlas_cnt[0]["cnt"] == 0:
                seed_atlas(self.store, atlas_graph=self.config.atlas_graph)

            # Check domain graph; seed if empty
            domain_cnt = self.store.query(self.config.domain_graph, "MATCH (n) RETURN count(n) AS cnt")
            if not domain_cnt or domain_cnt[0]["cnt"] == 0:
                seed_domain(self.store, domain_graph=self.config.domain_graph)

            # Record Task in run memory
            task_cypher = (
                f"MERGE (t:{LABEL_TASK} {{id: $tid}}) "
                "ON CREATE SET t.description = $desc, t.status = 'running', "
                "              t.task_type = $task_type, t.created_at = $now"
            )
            self.store.query(
                self.run_graph,
                task_cypher,
                {
                    "tid": f"task-{self.run_id}",
                    "desc": task_description,
                    "task_type": self.config.task_type,
                    "now": now,
                },
            )

            scores_before = self._get_skill_scores()
            self._scores_before = dict(scores_before)

            # Step 2: Decompose
            self.emit("decompose", "Decomposing task requirements into subtasks")
            if injected_subtasks is not None:
                subtasks = injected_subtasks
            else:
                subtasks = decompose_task(
                    task_text=task_description,
                    task_type=self.config.task_type,
                    llm=llm,
                    strict_llm=self.config.strict_llm,
                )


            # Validate capabilities against atlas
            cap_rows = self.store.query(self.config.atlas_graph, "MATCH (c:Capability) RETURN c.name AS name")
            known_caps = {r["name"] for r in cap_rows}
            for sub in subtasks:
                if sub.capability not in known_caps:
                    err_msg = f"Unknown capability: {sub.capability} not in atlas"
                    self.emit("failed", err_msg, {"capability": sub.capability})
                    self.store.query(
                        self.run_graph,
                        f"MATCH (t:{LABEL_TASK}) SET t.status = 'failed', t.failure_reason = $reason",
                        {"reason": err_msg},
                    )
                    raise ValueError(err_msg)

            # Step 3: Assign skills & persist decisions
            self.emit("assign_skills", f"Assigning skills for {len(subtasks)} subtask(s)")
            assignments = assign_skills_to_subtasks(
                self.store,
                subtasks=subtasks,
                task_type=self.config.task_type,
                run_graph_name=self.run_graph,
                atlas_graph=self.config.atlas_graph,
            )

            # Step 4: Equip agents
            self.emit("equip_agents", "Equipping sub-agents with selected skills and tool permissions")
            agent_configs: list[dict[str, Any]] = []
            for idx, assign in enumerate(assignments):
                if not assign.chosen_skill:
                    continue
                ag_id = f"agent_{assign.subtask.capability}_{idx}"
                equip_agent_with_skill(self.store, self.run_graph, ag_id, assign.chosen_skill.id)

                # Fetch exposed tools from atlas
                tool_rows = self.store.query(
                    self.config.atlas_graph,
                    "MATCH (s:Skill {id: $sid})-[:EXPOSES]->(t:Tool) RETURN t.name AS name",
                    {"sid": assign.chosen_skill.id},
                )
                exposed = [r["name"] for r in tool_rows if r.get("name")]
                if not exposed:
                    exposed = ["shared_attribute_links", "connected_components", "claim_amount_outliers", "ask_graph"]

                agent_configs.append({
                    "agent_id": ag_id,
                    "skill_id": assign.chosen_skill.id,
                    "prompt_fragment": assign.chosen_skill.prompt_fragment,
                    "exposed_tools": exposed,
                })

            # Step 5: Choose seeds and extract slices
            self.emit("seeds", "Identifying seed entities and extracting isolated slices")
            if self.config.seed_cids is not None:
                seeds = self.config.seed_cids
            else:
                seeds = find_seeds(self.store, self.config.domain_graph)

            agent_target_cids: dict[str, list[str]] = {}
            for ag in agent_configs:
                slice_name = agent_graph_name(self.run_id, ag["agent_id"])
                # Extract induced subgraph
                extract_subgraph_slice(
                    self.store,
                    self.config.domain_graph,
                    slice_name,
                    seed_cids=seeds,
                    k_hops=self.config.k_hops,
                )
                # Query target customers in slice
                slice_custs = self.store.query(slice_name, "MATCH (c:Customer) RETURN c.cid AS cid")
                targets = sorted([str(r["cid"]) for r in slice_custs if r.get("cid")])
                agent_target_cids[ag["agent_id"]] = targets

            # Step 6: Run sub-agents in parallel
            self.emit("run_agents", f"Executing {len(agent_configs)} sub-agents in parallel (max_workers={self.config.max_parallel_agents})")
            findings_by_agent: dict[str, list[Finding]] = {}
            tool_logs_by_agent: dict[str, ToolCallLog] = {}
            failed_agents = 0

            max_workers = max(1, self.config.max_parallel_agents)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_agent = {}
                for ag in agent_configs:
                    ag_id = ag["agent_id"]
                    slice_name = agent_graph_name(self.run_id, ag_id)
                    targets = agent_target_cids.get(ag_id, [])
                    fut = executor.submit(
                        self._run_single_agent,
                        ag_id,
                        ag["skill_id"],
                        ag["prompt_fragment"],
                        targets,
                        slice_name,
                        ag["exposed_tools"],
                        llm,
                        self.config.strict_llm,
                    )
                    future_to_agent[fut] = ag_id

                for fut in concurrent.futures.as_completed(future_to_agent):
                    ag_id = future_to_agent[fut]
                    try:
                        ret_agent_id, ag_findings, tool_log = fut.result()
                        findings_by_agent[ret_agent_id] = ag_findings
                        tool_logs_by_agent[ret_agent_id] = tool_log
                    except Exception as ag_err:
                        failed_agents += 1
                        err_str = str(ag_err)
                        logger.error("Agent '%s' failed: %s", ag_id, err_str)
                        self.emit("agent_failed", f"Agent '{ag_id}' failed: {err_str}", {"agent_id": ag_id, "error": err_str})
                        self.store.query(
                            self.run_graph,
                            "MERGE (a:Agent {id: $aid}) SET a.status = 'failed', a.failure_reason = $reason",
                            {"aid": ag_id, "reason": err_str},
                        )

            if failed_agents == len(agent_configs) and len(agent_configs) > 0:
                err_msg = "All agents failed during execution"
                self.emit("failed", err_msg)
                self.store.query(
                    self.run_graph,
                    f"MATCH (t:{LABEL_TASK}) SET t.status = 'failed', t.failure_reason = $reason",
                    {"reason": err_msg},
                )
                raise RuntimeError(err_msg)

            # Step 7: Promote findings (main thread, deterministically ordered by agent_id)
            self.emit("promote", "Validating evidence and promoting findings to run memory")
            all_promoted: list[Finding] = []
            all_rejected: list[dict[str, Any]] = []
            backend_counts = {"llm": 0, "rules": 0, "scripted": 0}

            for ag_id in sorted(findings_by_agent.keys()):
                ag_findings = findings_by_agent[ag_id]
                tool_log = tool_logs_by_agent.get(ag_id, ToolCallLog())
                slice_name = agent_graph_name(self.run_id, ag_id)

                prom_res = promote_findings(
                    self.store,
                    slice_name,
                    self.run_graph,
                    ag_findings,
                    observed=tool_log.observed_strings(),
                    require_observed=self.config.require_observed,
                    max_hops=self.config.max_hops,
                    threshold=self.config.min_confidence,
                )
                all_promoted.extend(prom_res.promoted)
                for rej in prom_res.rejected:
                    all_rejected.append({"finding_id": rej.finding.id, "reason": rej.reason})

                for f in ag_findings:
                    b_type = f.backend if f.backend in backend_counts else "rules"
                    backend_counts[b_type] += 1

            # Clean up transient agent slice graphs if not explicitly preserved
            if not self.config.keep_slice_graphs:
                for ag in agent_configs:
                    try:
                        self.store.delete_graph(agent_graph_name(self.run_id, ag["agent_id"]))
                    except Exception:
                        pass

            # Step 8: Detect contradictions
            self.emit("detect_contradictions", "Scanning for contradictory verdicts")
            contradictions = detect_contradictions(self.store, self.run_graph)

            # Step 9: Resolve conflicts
            self.emit("resolve_conflicts", f"Resolving {len(contradictions)} contradiction(s)")
            decisions = resolve_conflicts(
                self.store,
                self.run_graph,
                task_type=self.config.task_type,
                atlas_graph=self.config.atlas_graph,
            )

            # Step 10: Propose batch action
            self.emit("propose", "Synthesizing corroborated findings and proposing action")
            actions = propose_actions(self.store, self.run_graph)
            action_id = actions[0].id if actions else None

            status = "PENDING" if action_id else "COMPLETED"
            self.store.query(
                self.run_graph,
                f"MATCH (t:{LABEL_TASK}) SET t.status = $status",
                {"status": "pending_approval" if action_id else "completed"},
            )

            return PipelineRunResult(
                run_id=self.run_id,
                status=status,
                action_id=action_id,
                outcome_id=None,
                metrics=None,
                backend_counts=backend_counts,
                rejected_findings=all_rejected,
                conflicts_resolved=len(decisions),
                events=list(self._events),
                skill_scores_before=scores_before,
                skill_scores_after={},
            )

        except Exception as err:
            self.emit("failed", f"Pipeline execution failed: {err}", {"error": str(err)})
            try:
                self.store.query(
                    self.run_graph,
                    f"MATCH (t:{LABEL_TASK}) SET t.status = 'failed', t.failure_reason = $reason",
                    {"reason": str(err)},
                )
            except Exception:
                pass
            raise

    def approve_and_finish(
        self,
        run_id: str,
        action_id: str,
        approver: str = "human",
        ground_truth: Optional[GroundTruth] = None,
    ) -> PipelineRunResult:
        """Approve proposed Action, execute domain mutation, evaluate metrics, and update reputation."""
        try:
            # 1. Approve
            self.emit("approve", f"Approving action '{action_id}' by approver '{approver}'")
            approved_act = approve_action(self.store, self.run_graph, action_id, approver=approver)

            # 2. Execute
            self.emit("execute", f"Executing domain mutation for action '{action_id}'")
            outcome = execute_action(
                self.store,
                self.run_graph,
                self.config.domain_graph,
                action_id,
                run_id=self.run_id,
            )

            # 3. Evaluate (run-scoped)
            self.emit("evaluate", "Evaluating run-scoped detection accuracy")
            metrics = evaluate_outcomes(
                self.store,
                self.config.domain_graph,
                ground_truth=ground_truth,
                run_id=self.run_id,
                run_graph_name=self.run_graph,
            )

            # 4. Learn
            self.emit("learn", "Updating atlas skill reputation scores via EMA")
            if ground_truth:
                learn_from_run(
                    self.store,
                    self.run_graph,
                    ground_truth,
                    atlas_graph=self.config.atlas_graph,
                    task_type=self.config.task_type,
                )
            scores_after = self._get_skill_scores()

            # 5. Explain
            self.emit("explain", "Generating comprehensive 'Why?' provenance audit trail")
            explain_action(self.store, self.run_graph, action_id)

            self.store.query(
                self.run_graph,
                f"MATCH (t:{LABEL_TASK}) SET t.status = 'completed'",
            )

            # Count backends
            f_rows = self.store.query(self.run_graph, "MATCH (f:Finding) RETURN f.backend AS backend")
            b_counts = {"llm": 0, "rules": 0, "scripted": 0}
            for r in f_rows:
                b = r.get("backend")
                if b in b_counts:
                    b_counts[b] += 1
                else:
                    b_counts["rules"] += 1

            return PipelineRunResult(
                run_id=self.run_id,
                status="EXECUTED",
                action_id=action_id,
                outcome_id=outcome.id,
                metrics=metrics,
                backend_counts=b_counts,
                events=list(self._events),
                skill_scores_before=dict(self._scores_before) if self._scores_before else self._get_skill_scores(),
                skill_scores_after=scores_after,
            )

        except Exception as err:
            self.emit("failed", f"Approve and finish failed: {err}", {"error": str(err)})
            raise

    def reject(
        self,
        run_id: str,
        action_id: str,
        approver: str = "human",
        reason: str = "",
    ) -> PipelineRunResult:
        """Reject proposed Action and record rejection justification."""
        self.emit("reject", f"Action '{action_id}' rejected by '{approver}': {reason}")
        rejected_act = reject_action(
            self.store,
            self.run_graph,
            action_id,
            approver=approver,
            reason=reason,
        )
        self.store.query(
            self.run_graph,
            f"MATCH (t:{LABEL_TASK}) SET t.status = 'rejected', t.rejection_reason = $reason",
            {"reason": reason},
        )
        return PipelineRunResult(
            run_id=self.run_id,
            status="REJECTED",
            action_id=action_id,
            events=list(self._events),
        )
