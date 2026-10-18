"""Integration tests for P4: FastAPI Backend with Server-Sent Events (SSE)."""

import json
import time
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from luna.graph.store import GraphStore
from luna.domain.seed import seed_domain, GroundTruth
from luna.atlas.seed import seed_atlas
from luna.api.app import create_app


@pytest.fixture
def api_client(live_store: GraphStore, tmp_graph: str):
    """Create isolated FastAPI TestClient with dedicated temporary graphs."""
    domain_graph = f"{tmp_graph}_domain"
    atlas_graph = f"{tmp_graph}_atlas"

    gt = seed_domain(live_store, seed=42, profile="demo", domain_graph=domain_graph)
    seed_atlas(live_store, atlas_graph=atlas_graph)

    app = create_app(
        store=live_store,
        config={
            "domain_graph": domain_graph,
            "atlas_graph": atlas_graph,
            "ground_truth": gt,
        },
    )
    client = TestClient(app)

    yield client, live_store, domain_graph, atlas_graph, gt

    live_store.delete_graph(domain_graph)
    live_store.delete_graph(atlas_graph)


def test_health_reports_healthy(api_client) -> None:
    """Verify /health reports healthy status and database reachability."""
    client, store, domain, atlas, gt = api_client
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["falkordb"] == "connected"
    assert "ollama" in data


def test_create_and_get_run(api_client) -> None:
    """Verify creating a run initiates execution and status can be queried."""
    client, store, domain, atlas, gt = api_client
    res = client.post(
        "/api/runs",
        json={"task": "Investigate fraud ring", "mode": "scripted", "parallel": 2},
    )
    assert res.status_code == 200
    init_data = res.json()
    run_id = init_data["run_id"]
    assert run_id

    # Poll until run reaches pending_approval
    status = None
    for _ in range(40):
        time.sleep(0.5)
        get_res = client.get(f"/api/runs/{run_id}")
        assert get_res.status_code == 200
        run_data = get_res.json()
        status = run_data["status"]
        if status in ("pending_approval", "completed", "failed"):
            break

    assert status == "pending_approval"
    assert run_data["action_id"] is not None
    assert "backend_counts" in run_data

    # Verify listing runs includes this run
    list_res = client.get("/api/runs")
    assert list_res.status_code == 200
    runs = list_res.json()
    assert any(r["run_id"] == run_id for r in runs)


def test_sse_stream_receives_ordered_events(api_client) -> None:
    """Verify /api/runs/{run_id}/events streams SSE events in order with monotonic sequence IDs."""
    client, store, domain, atlas, gt = api_client
    res = client.post(
        "/api/runs",
        json={"task": "Investigate fraud ring", "mode": "scripted", "parallel": 2},
    )
    run_id = res.json()["run_id"]

    # Read SSE stream
    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        events = []
        for line in stream.iter_lines():
            if line.startswith("id:"):
                seq = int(line.split(":", 1)[1].strip())
            elif line.startswith("event:"):
                step = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_json = json.loads(line.split(":", 1)[1].strip())
                events.append((seq, step, data_json))
                if step == "propose":
                    break

        assert len(events) >= 4
        seqs = [e[0] for e in events]
        assert seqs == sorted(seqs)
        steps = [e[1] for e in events]
        assert "init" in steps
        assert "decompose" in steps


def test_last_event_id_resume(api_client) -> None:
    """Verify Last-Event-ID skips previously received events."""
    client, store, domain, atlas, gt = api_client
    res = client.post(
        "/api/runs",
        json={"task": "Investigate fraud ring", "mode": "scripted", "parallel": 2},
    )
    run_id = res.json()["run_id"]

    # Wait until run has produced at least 4 events
    for _ in range(40):
        time.sleep(0.3)
        st = client.get(f"/api/runs/{run_id}").json()
        if len(st.get("events", [])) >= 4:
            break

    # Connect with Last-Event-ID = 2
    with client.stream("GET", f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "2"}) as stream:
        received_seqs = []
        for line in stream.iter_lines():
            if line.startswith("id:"):
                seq = int(line.split(":", 1)[1].strip())
                received_seqs.append(seq)
                if len(received_seqs) >= 2:
                    break

        assert all(s > 2 for s in received_seqs)


def test_approval_gate_and_execute(api_client) -> None:
    """Verify action approval executes domain mutation and produces metrics."""
    client, store, domain, atlas, gt = api_client
    res = client.post(
        "/api/runs",
        json={"task": "Investigate fraud ring", "mode": "scripted", "parallel": 2},
    )
    run_id = res.json()["run_id"]

    for _ in range(40):
        time.sleep(0.4)
        run_data = client.get(f"/api/runs/{run_id}").json()
        if run_data["status"] == "pending_approval":
            break

    action_id = run_data["action_id"]
    assert action_id is not None

    # Approve action
    app_res = client.post(
        f"/api/runs/{run_id}/actions/{action_id}/approve",
        json={"approver": "Investigator_Jane"},
    )
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["status"] == "EXECUTED"
    assert app_data["metrics"]["precision"] == 1.0

    # Verify domain customer is flagged
    flagged = store.query(domain, "MATCH (c:Customer {cid: 'cust_ring_1'}) RETURN c.flagged AS flagged")
    assert flagged[0]["flagged"] is True


def test_rejection_flow(api_client) -> None:
    """Verify action rejection updates status and prevents domain mutation."""
    client, store, domain, atlas, gt = api_client
    res = client.post(
        "/api/runs",
        json={"task": "Investigate fraud ring", "mode": "scripted", "parallel": 2},
    )
    run_id = res.json()["run_id"]

    for _ in range(40):
        time.sleep(0.4)
        run_data = client.get(f"/api/runs/{run_id}").json()
        if run_data["status"] == "pending_approval":
            break

    action_id = run_data["action_id"]

    rej_res = client.post(
        f"/api/runs/{run_id}/actions/{action_id}/reject",
        json={"approver": "Investigator_Bob", "reason": "Insufficient corroboration"},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "REJECTED"

    # Verify domain customers are NOT flagged
    flagged = store.query(domain, "MATCH (c:Customer {flagged: true}) RETURN count(c) AS cnt")
    assert flagged[0]["cnt"] == 0


def test_why_explanation_endpoint(api_client) -> None:
    """Verify /api/runs/{run_id}/why/{cid} returns explanation narrative and findings."""
    client, store, domain, atlas, gt = api_client
    res = client.post(
        "/api/runs",
        json={"task": "Investigate fraud ring", "mode": "scripted", "parallel": 2},
    )
    run_id = res.json()["run_id"]

    for _ in range(40):
        time.sleep(0.4)
        run_data = client.get(f"/api/runs/{run_id}").json()
        if run_data["status"] == "pending_approval":
            break

    # Approve to finish workflow
    client.post(
        f"/api/runs/{run_id}/actions/{run_data['action_id']}/approve",
        json={"approver": "auto"},
    )

    why_res = client.get(f"/api/runs/{run_id}/why/cust_ring_1")
    assert why_res.status_code == 200
    why_data = why_res.json()
    assert why_data["target_cid"] == "cust_ring_1"
    assert why_data["final_verdict"] == "suspicious"
    assert "narrative" in why_data
    assert len(why_data["findings"]) >= 1


def test_graphs_endpoint_caps_and_sanitizes(api_client) -> None:
    """Verify /api/graphs/{scope} returns topology, enforces node caps, and rejects unsafe scopes."""
    client, store, domain, atlas, gt = api_client

    # Safe domain graph
    res = client.get("/api/graphs/domain")
    assert res.status_code == 200
    g_data = res.json()
    assert "nodes" in g_data
    assert "edges" in g_data
    assert "truncated" in g_data
    assert len(g_data["nodes"]) <= 500
    assert len(g_data["edges"]) <= 1500

    # Unsafe scope
    unsafe_res = client.get("/api/graphs/unsafe;DROP%20ALL;")
    assert unsafe_res.status_code == 400
    err_data = unsafe_res.json()
    assert "error" in err_data


def test_replay_endpoint(api_client) -> None:
    """Verify /api/replay serves the recording JSON file."""
    client, store, domain, atlas, gt = api_client
    res = client.get("/api/replay")
    assert res.status_code == 200
    data = res.json()
    assert "runs" in data
