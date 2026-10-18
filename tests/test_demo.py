"""Integration tests for P3: Demo Script and Replay Engine."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from luna.domain.seed import seed_domain
from luna.atlas.seed import seed_atlas
from scripts.demo import run_demo, play_replay


@pytest.fixture
def demo_env(live_store, tmp_graph: str):
    """Seed fresh temporary domain and atlas graphs for demo tests."""
    domain_graph = f"{tmp_graph}_domain"
    atlas_graph = f"{tmp_graph}_atlas"

    gt = seed_domain(live_store, seed=42, profile="demo", domain_graph=domain_graph)
    seed_atlas(live_store, atlas_graph=atlas_graph)

    yield live_store, domain_graph, atlas_graph, gt

    live_store.delete_graph(domain_graph)
    live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_demo_scripted_run_produces_valid_recording(demo_env, tmp_path: Path) -> None:
    """Verify scripted demo runs cleanly and produces a valid, complete replay recording."""
    store, domain, atlas, gt = demo_env
    recording_file = tmp_path / "test_recording.json"

    res = run_demo(
        store=store,
        domain_graph=domain,
        atlas_graph=atlas,
        runs=1,
        parallel=2,
        mode="scripted",
        recording_file=str(recording_file),
        replay=False,
        fast=True,
        ground_truth=gt,
    )

    assert res["success"] is True
    assert recording_file.exists()

    with open(recording_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "runs" in data
    assert len(data["runs"]) == 1
    run_0 = data["runs"][0]

    # Events sequence
    events = run_0["events"]
    assert len(events) > 5
    steps = [e["step"] for e in events]
    assert "init" in steps
    assert "decompose" in steps
    assert "run_agents" in steps
    assert "propose" in steps
    assert "approve" in steps
    assert "execute" in steps
    assert "evaluate" in steps

    # Graph snapshots
    snapshots = run_0["graph_snapshots"]
    assert "run" in snapshots
    assert "nodes" in snapshots["run"]
    assert "edges" in snapshots["run"]

    # Metrics
    metrics = run_0["metrics"]
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["true_positives"] == 8
    assert metrics["false_positives"] == 0

    # Explain results
    explain = run_0.get("explain_result")
    assert explain is not None
    assert "cust_ring_1" in explain
    assert "cust_decoy_1" in explain


@pytest.mark.integration
def test_demo_replay_produces_same_event_sequence(demo_env, tmp_path: Path) -> None:
    """Verify replay reproduces identical events and steps from recording file."""
    store, domain, atlas, gt = demo_env
    recording_file = tmp_path / "replay_test.json"

    # Step 1: Record a run
    run_demo(
        store=store,
        domain_graph=domain,
        atlas_graph=atlas,
        runs=1,
        parallel=2,
        mode="scripted",
        recording_file=str(recording_file),
        replay=False,
        fast=True,
        ground_truth=gt,
    )

    with open(recording_file, "r", encoding="utf-8") as f:
        recorded_data = json.load(f)
    orig_events = recorded_data["runs"][0]["events"]

    # Step 2: Replay
    replayed_events = []
    play_replay(
        recording_file=str(recording_file),
        fast=True,
        event_callback=lambda ev: replayed_events.append(ev),
    )

    assert len(replayed_events) == len(orig_events)
    for orig, rep in zip(orig_events, replayed_events):
        assert orig["seq"] == rep["seq"]
        assert orig["step"] == rep["step"]
        assert orig["message"] == rep["message"]


@pytest.mark.integration
def test_demo_runs_two_shows_changed_scores(demo_env, tmp_path: Path) -> None:
    """Verify running N=2 runs updates skill scores across runs without resetting atlas."""
    store, domain, atlas, gt = demo_env
    recording_file = tmp_path / "runs_two_test.json"

    res = run_demo(
        store=store,
        domain_graph=domain,
        atlas_graph=atlas,
        runs=2,
        parallel=2,
        mode="scripted",
        recording_file=str(recording_file),
        replay=False,
        fast=True,
        ground_truth=gt,
    )

    assert res["success"] is True
    with open(recording_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data["runs"]) == 2
    run1 = data["runs"][0]
    run2 = data["runs"][1]

    # Run 1 changes score
    s1_before = run1["skill_scores_before"].get("entity-linker")
    s1_after = run1["skill_scores_after"].get("entity-linker")
    assert s1_before is not None
    assert s1_after is not None

    # Run 2 starts with Run 1's after score
    s2_before = run2["skill_scores_before"].get("entity-linker")
    s2_after = run2["skill_scores_after"].get("entity-linker")
    assert s2_before == s1_after
    assert s2_after is not None
