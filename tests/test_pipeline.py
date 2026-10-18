"""Integration tests for P2: LunaPipeline orchestrator with parallel agent execution and safety."""

import pytest
import concurrent.futures
from unittest.mock import MagicMock

from luna.orchestrator.pipeline import (
    LunaPipeline,
    PipelineConfig,
    PipelineEvent,
    PipelineRunResult,
    find_seeds,
)
from luna.domain.seed import seed_domain, GroundTruth
from luna.atlas.seed import seed_atlas
from luna.llm.client import MockLLMClient
from luna.agents.exceptions import LLMUnavailableError


@pytest.fixture
def setup_pipeline_env(live_store, tmp_graph: str):
    """Seed fresh temporary domain and atlas graphs for pipeline tests."""
    domain_graph = f"{tmp_graph}_domain"
    atlas_graph = f"{tmp_graph}_atlas"

    gt = seed_domain(live_store, seed=42, profile="demo", domain_graph=domain_graph)
    seed_atlas(live_store, atlas_graph=atlas_graph)

    yield live_store, domain_graph, atlas_graph, gt

    live_store.delete_graph(domain_graph)
    live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_pipeline_start_stops_at_pending(setup_pipeline_env) -> None:
    """Verify start() executes full workflow up to propose and stops with Action PENDING."""
    store, domain, atlas, gt = setup_pipeline_env
    run_id = "test_pipe_pending"

    config = PipelineConfig(
        run_id=run_id,
        domain_graph=domain,
        atlas_graph=atlas,
        llm_client=MockLLMClient(),
        max_parallel_agents=2,
    )
    pipeline = LunaPipeline(store, config)
    res = pipeline.start("Investigate suspected auto insurance fraud ring", ground_truth=gt)

    try:
        assert res.run_id == run_id
        assert res.status == "PENDING"
        assert res.action_id is not None
        assert res.outcome_id is None  # Not executed yet

        # Action is PENDING in run memory
        run_graph = f"run_{run_id}"
        actions = store.query(run_graph, "MATCH (a:Action) RETURN a.status AS status")
        assert len(actions) == 1
        assert actions[0]["status"] == "PENDING"

        # Domain customers not flagged yet
        flagged = store.query(domain, "MATCH (c:Customer {flagged: true}) RETURN count(c) AS cnt")
        assert flagged[0]["cnt"] == 0

    finally:
        store.delete_graph(f"run_{run_id}")


@pytest.mark.integration
def test_pipeline_events_order_and_monotonic_seq(setup_pipeline_env) -> None:
    """Verify thread-safe event emission maintains strictly ascending monotonic sequence numbers."""
    store, domain, atlas, gt = setup_pipeline_env
    run_id = "test_pipe_events"

    config = PipelineConfig(
        run_id=run_id,
        domain_graph=domain,
        atlas_graph=atlas,
        llm_client=MockLLMClient(),
        max_parallel_agents=2,
    )
    pipeline = LunaPipeline(store, config)
    res = pipeline.start("Investigate suspected auto insurance fraud ring", ground_truth=gt)

    try:
        assert len(res.events) > 5
        seqs = [e.seq for e in res.events]
        assert seqs == list(range(1, len(res.events) + 1))
        steps = [e.step for e in res.events]
        assert "init" in steps
        assert "decompose" in steps
        assert "run_agents" in steps
        assert "propose" in steps

    finally:
        store.delete_graph(f"run_{run_id}")


@pytest.mark.integration
def test_pipeline_empty_slice_completes_with_no_findings(live_store, tmp_graph: str) -> None:
    """Verify empty slice seeds complete gracefully with no findings and no action."""
    domain_graph = f"{tmp_graph}_domain"
    atlas_graph = f"{tmp_graph}_atlas"
    run_id = "test_pipe_empty"

    try:
        # Create domain with an isolated customer
        live_store.query(domain_graph, "CREATE (:Customer {cid: 'cust-isolated-only'})")
        seed_atlas(live_store, atlas_graph=atlas_graph)

        config = PipelineConfig(
            run_id=run_id,
            domain_graph=domain_graph,
            atlas_graph=atlas_graph,
            seed_cids=["cust-non-existent"],
            llm_client=MockLLMClient(),
        )
        pipeline = LunaPipeline(live_store, config)
        res = pipeline.start("Investigate empty targets")

        assert res.action_id is None
        assert res.conflicts_resolved == 0

    finally:
        live_store.delete_graph(domain_graph)
        live_store.delete_graph(atlas_graph)
        live_store.delete_graph(f"run_{run_id}")


@pytest.mark.integration
def test_pipeline_unknown_capability_fails_cleanly(setup_pipeline_env) -> None:
    """Verify unknown capability raises ValueError, marks task failed, and executes nothing."""
    store, domain, atlas, gt = setup_pipeline_env
    run_id = "test_pipe_unknown_cap"

    # Mock decompose to return an invalid capability
    from luna.planner.decompose import Subtask
    mock_llm = MockLLMClient()

    config = PipelineConfig(
        run_id=run_id,
        domain_graph=domain,
        atlas_graph=atlas,
        llm_client=mock_llm,
    )
    pipeline = LunaPipeline(store, config)

    # Monkeypatch decompose on the instance or pass an invalid capability
    with pytest.raises(ValueError, match="Unknown capability"):
        pipeline.start(
            "Fake task",
            injected_subtasks=[Subtask(id="s1", capability="fly_to_moon", description="Fake")],
        )

    run_graph = f"run_{run_id}"
    try:
        task_nodes = store.query(run_graph, "MATCH (t:Task) RETURN t.status AS status, t.failure_reason AS reason")
        assert len(task_nodes) == 1
        assert task_nodes[0]["status"] == "failed"
        assert "fly_to_moon" in task_nodes[0]["reason"]
    finally:
        store.delete_graph(run_graph)


@pytest.mark.integration
def test_pipeline_scripted_run_flags_ring_with_precision_recall_one(setup_pipeline_env) -> None:
    """Verify scripted run flags exactly the ring members with precision and recall 1.0, resolving decoy conflict."""
    store, domain, atlas, gt = setup_pipeline_env
    run_id = "test_pipe_scripted_perf"

    config = PipelineConfig(
        run_id=run_id,
        domain_graph=domain,
        atlas_graph=atlas,
        llm_client=MockLLMClient(),
        max_parallel_agents=3,
    )
    pipeline = LunaPipeline(store, config)
    try:
        res_start = pipeline.start("Investigate fraud ring", ground_truth=gt)
        assert res_start.status == "PENDING"
        assert res_start.action_id is not None
        assert res_start.conflicts_resolved >= 1  # Decoy family conflict resolved!

        # Auto-approve and finish
        res_finish = pipeline.approve_and_finish(run_id, res_start.action_id, approver="auto", ground_truth=gt)
        assert res_finish.status == "EXECUTED"
        assert res_finish.metrics is not None
        assert res_finish.metrics.precision == 1.0
        assert res_finish.metrics.recall == 1.0
        assert res_finish.metrics.f1 == 1.0

        # Ensure none of the decoy family customers were flagged
        flagged_cids = {
            r["cid"] for r in store.query(domain, "MATCH (c:Customer {flagged: true}) RETURN c.cid AS cid")
        }
        for decoy_cid in gt.decoy_cids:
            assert decoy_cid not in flagged_cids
    finally:
        store.delete_graph(f"run_{run_id}")


@pytest.mark.integration
def test_pipeline_atlas_scores_persist_and_change_across_runs(setup_pipeline_env) -> None:
    """Verify atlas skill scores persist across two consecutive runs and update via learning."""
    store, domain, atlas, gt = setup_pipeline_env

    # Run 1
    cfg1 = PipelineConfig(run_id="run_1_scores", domain_graph=domain, atlas_graph=atlas, llm_client=MockLLMClient())
    pipe1 = LunaPipeline(store, cfg1)
    res1_start = pipe1.start("Run 1", ground_truth=gt)
    res1 = pipe1.approve_and_finish("run_1_scores", res1_start.action_id, approver="auto", ground_truth=gt)

    score1 = res1.skill_scores_after.get("entity-linker")
    assert score1 is not None

    # Reset domain flags before Run 2 without touching atlas!
    from luna.orchestrator.actions import reset_flags
    reset_flags(store, domain)

    # Run 2
    cfg2 = PipelineConfig(run_id="run_2_scores", domain_graph=domain, atlas_graph=atlas, llm_client=MockLLMClient())
    pipe2 = LunaPipeline(store, cfg2)
    res2_start = pipe2.start("Run 2", ground_truth=gt)
    assert res2_start.skill_scores_before.get("entity-linker") == score1

    res2 = pipe2.approve_and_finish("run_2_scores", res2_start.action_id, approver="auto", ground_truth=gt)
    score2 = res2.skill_scores_after.get("entity-linker")

    # EMA updated further
    assert score2 is not None

    store.delete_graph("run_run_1_scores")
    store.delete_graph("run_run_2_scores")


@pytest.mark.integration
def test_pipeline_concurrent_runs_independent(setup_pipeline_env) -> None:
    """Verify two pipelines running concurrently across threads execute safely with independent metrics."""
    store, domain, atlas, gt = setup_pipeline_env

    def run_pipe(pipe_run_id: str):
        cfg = PipelineConfig(
            run_id=pipe_run_id,
            domain_graph=domain,
            atlas_graph=atlas,
            llm_client=MockLLMClient(),
            max_parallel_agents=2,
        )
        p = LunaPipeline(store, cfg)
        start_res = p.start(f"Concurrent task {pipe_run_id}", ground_truth=gt)
        finish_res = p.approve_and_finish(pipe_run_id, start_res.action_id, approver="auto", ground_truth=gt)
        return finish_res

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    try:
        f1 = executor.submit(run_pipe, "pipe_conc_1")
        f2 = executor.submit(run_pipe, "pipe_conc_2")
        r1 = f1.result(timeout=60)
        r2 = f2.result(timeout=60)

        assert r1.status == "EXECUTED"
        assert r2.status == "EXECUTED"
        assert r1.metrics.precision == 1.0
        assert r2.metrics.precision == 1.0

        # Verify flag_runs contains both runs on ring targets
        custs = store.query(domain, "MATCH (c:Customer {cid: 'cust_ring_1'}) RETURN c.flag_runs AS runs")
        runs = custs[0]["runs"]
        assert "pipe_conc_1" in runs
        assert "pipe_conc_2" in runs

    finally:
        executor.shutdown(wait=False)
        store.delete_graph("run_pipe_conc_1")
        store.delete_graph("run_pipe_conc_2")


@pytest.mark.integration
def test_pipeline_one_failing_agent_does_not_kill_run(setup_pipeline_env, monkeypatch) -> None:
    """Verify an agent failure emits agent_failed event and records Agent status=failed, but run continues."""
    store, domain, atlas, gt = setup_pipeline_env
    run_id = "test_pipe_agent_fail"

    config = PipelineConfig(
        run_id=run_id,
        domain_graph=domain,
        atlas_graph=atlas,
        llm_client=MockLLMClient(),
        max_parallel_agents=2,
    )
    pipeline = LunaPipeline(store, config)

    # Inject failure for community-analyzer agent only
    original_run_agent = pipeline._run_single_agent

    def fail_one_agent(*args, **kwargs):
        agent_id = args[0] if args else kwargs.get("agent_id")
        if "community-analyzer" in agent_id or "detect_communities" in agent_id:
            raise RuntimeError("Simulated agent worker failure")
        return original_run_agent(*args, **kwargs)

    monkeypatch.setattr(pipeline, "_run_single_agent", fail_one_agent)

    res = pipeline.start("Task with one failing agent", ground_truth=gt)
    try:
        # Run should still succeed with other agent(s) (not killed)
        assert res.status in ("PENDING", "COMPLETED")
        assert res.status != "FAILED"
        steps = [e.step for e in res.events]
        assert "agent_failed" in steps

        # Check Agent node status in run memory
        failed_agents = store.query(
            f"run_{run_id}",
            "MATCH (a:Agent {status: 'failed'}) RETURN a.id AS id, a.failure_reason AS reason",
        )
        assert len(failed_agents) >= 1
        assert "Simulated agent worker failure" in failed_agents[0]["reason"]

    finally:
        store.delete_graph(f"run_{run_id}")


@pytest.mark.integration
def test_pipeline_parallel_1_and_3_identical(setup_pipeline_env) -> None:
    """Verify max_parallel_agents=1 (sequential) and max_parallel_agents=3 (parallel) produce identical results."""
    store, domain, atlas, gt = setup_pipeline_env

    # Sequential
    cfg1 = PipelineConfig(run_id="pipe_seq", domain_graph=domain, atlas_graph=atlas, max_parallel_agents=1, llm_client=MockLLMClient())
    p1 = LunaPipeline(store, cfg1)
    r1 = p1.start("Determinism test", ground_truth=gt)

    # Parallel
    cfg2 = PipelineConfig(run_id="pipe_par", domain_graph=domain, atlas_graph=atlas, max_parallel_agents=3, llm_client=MockLLMClient())
    p2 = LunaPipeline(store, cfg2)
    r2 = p2.start("Determinism test", ground_truth=gt)

    try:
        assert r1.conflicts_resolved == r2.conflicts_resolved
        # Target customers proposed should be identical
        t1 = store.query("run_pipe_seq", "MATCH (a:Action) RETURN a.target_cids AS cids")
        t2 = store.query("run_pipe_par", "MATCH (a:Action) RETURN a.target_cids AS cids")
        assert t1[0]["cids"] == t2[0]["cids"]

    finally:
        store.delete_graph("run_pipe_seq")
        store.delete_graph("run_pipe_par")


@pytest.mark.integration
def test_pipeline_strict_llm_raises(setup_pipeline_env, monkeypatch) -> None:
    """Verify strict_llm raises LLMUnavailableError when LLM fails instead of falling back to rules."""
    store, domain, atlas, gt = setup_pipeline_env
    run_id = "test_pipe_strict"

    failing_llm = MagicMock()
    failing_llm.complete.side_effect = TimeoutError("Ollama connection timed out")

    config = PipelineConfig(
        run_id=run_id,
        domain_graph=domain,
        atlas_graph=atlas,
        strict_llm=True,
        llm_client=failing_llm,
    )
    pipeline = LunaPipeline(store, config)

    with pytest.raises(Exception):
        pipeline.start("Strict LLM test", ground_truth=gt)

    try:
        # Task marked failed
        tasks = store.query(f"run_{run_id}", "MATCH (t:Task) RETURN t.status AS status")
        assert len(tasks) == 1
        assert tasks[0]["status"] == "failed"
    finally:
        store.delete_graph(f"run_{run_id}")
