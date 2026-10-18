#!/usr/bin/env python3
"""LUNA OS Autonomous Fraud Investigation Demo & Replay CLI.

Supports:
  --scripted (deterministic MockLLMClient, default)
  --live (real Ollama LLM)
  --strict (strict LLM mode without rules fallback)
  --replay (deterministic replay from artifacts/replay_recording.json)
  --fast (skip replay delays)
  --runs N (default: 2, updates skill reputation across runs)
  --parallel K (default: 3 worker agents)
  --recording-file PATH (target replay recording JSON)
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# Ensure repository root is on sys.path for standalone script execution
repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from luna.graph.store import GraphStore
from luna.graph.schema import GRAPH_DOMAIN, GRAPH_ATLAS
from luna.domain.seed import seed_domain, GroundTruth
from luna.atlas.seed import seed_atlas
from luna.orchestrator.pipeline import LunaPipeline, PipelineConfig, PipelineEvent, PipelineRunResult
from luna.orchestrator.actions import reset_flags, approve_action
from luna.orchestrator.explain import explain_customer
from luna.llm.client import MockLLMClient, OllamaClient


DEFAULT_RECORDING_PATH = os.path.join("artifacts", "replay_recording.json")


def capture_graph_snapshot(
    store: GraphStore,
    graph_name: str,
    max_nodes: int = 500,
    max_edges: int = 1500,
) -> dict[str, list[dict[str, Any]]]:
    """Capture a capped node and edge topology snapshot from a FalkorDB named graph."""
    try:
        node_query = (
            f"MATCH (n) "
            f"RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props "
            f"LIMIT {max_nodes}"
        )
        node_rows = store.query(graph_name, node_query)
        nodes = []
        for r in node_rows:
            props = r.get("props") or {}
            nid = props.get("id") or props.get("cid") or str(r.get("id"))
            nodes.append({
                "id": str(nid),
                "labels": r.get("labels", []),
                "properties": props,
            })

        edge_query = (
            f"MATCH (a)-[r]->(b) "
            f"RETURN id(r) AS id, id(a) AS src_id, id(b) AS dst_id, "
            f"       coalesce(a.cid, a.id) AS src_name, coalesce(b.cid, b.id) AS dst_name, "
            f"       type(r) AS rel, properties(r) AS props "
            f"LIMIT {max_edges}"
        )
        edge_rows = store.query(graph_name, edge_query)
        edges = []
        for r in edge_rows:
            src = r.get("src_name") or str(r.get("src_id"))
            dst = r.get("dst_name") or str(r.get("dst_id"))
            edges.append({
                "id": str(r.get("id")),
                "source": str(src),
                "target": str(dst),
                "rel": r.get("rel"),
                "properties": r.get("props") or {},
            })

        return {"nodes": nodes, "edges": edges}
    except Exception:
        return {"nodes": [], "edges": []}


def format_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Format tabular data into an aligned plain text table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(val)))

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_str = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"

    lines = [sep, header_str, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)) + " |")
    lines.append(sep)
    return "\n".join(lines)


def play_replay(
    recording_file: str = DEFAULT_RECORDING_PATH,
    fast: bool = False,
    event_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    speed_factor: float = 1.0,
) -> dict[str, Any]:
    """Replay recorded execution from JSON file with original relative timing."""
    if not os.path.exists(recording_file):
        raise FileNotFoundError(f"Replay recording not found at '{recording_file}'.")

    with open(recording_file, "r", encoding="utf-8") as f:
        recording = json.load(f)

    print(f"\n================================================================================")
    print(f"  LUNA OS REPLAY ENGINE - PLAYING FROM '{recording_file}'")
    print(f"  Mode: {recording.get('mode', 'scripted')} | Runs recorded: {len(recording.get('runs', []))}")
    print(f"================================================================================\n")

    for run_idx, run_data in enumerate(recording.get("runs", [])):
        run_id = run_data.get("run_id")
        events = run_data.get("events", [])
        print(f"\n>>> [Replay] Commencing Run {run_idx + 1} ({run_id}) - {len(events)} events <<<")

        last_rel = 0.0
        for ev in events:
            rel_time = ev.get("rel_time_seconds", 0.0)
            if not fast and rel_time > last_rel:
                delay = (rel_time - last_rel) / max(0.1, speed_factor)
                time.sleep(min(delay, 1.5))
            last_rel = rel_time

            print(f"  [+{rel_time:6.2f}s] {ev.get('step', '').ljust(22)} {ev.get('message', '')}")
            if event_callback:
                event_callback(ev)

        # Print stored metrics
        m = run_data.get("metrics")
        if m:
            print("\n  Recorded Evaluation Metrics:")
            print(f"    TP: {m.get('true_positives')} | FP: {m.get('false_positives')} | TN: {m.get('true_negatives')} | FN: {m.get('false_negatives')}")
            print(f"    Precision: {m.get('precision', 0):.4f} | Recall: {m.get('recall', 0):.4f} | F1: {m.get('f1', 0):.4f}")

        # Print skill score evolution
        s_before = run_data.get("skill_scores_before", {})
        s_after = run_data.get("skill_scores_after", {})
        if s_before or s_after:
            all_skills = sorted(set(s_before.keys()) | set(s_after.keys()))
            score_rows = [
                [sk, f"{s_before.get(sk, 0.0):.3f}", f"{s_after.get(sk, 0.0):.3f}", f"{s_after.get(sk, 0.0) - s_before.get(sk, 0.0):+.3f}"]
                for sk in all_skills
            ]
            print("\n  Skill Reputation (Before -> After):")
            print(format_table(["Skill ID", "Before", "After", "Delta"], score_rows))

    print("\n[Replay Completed Successfully]")
    return recording


def run_demo(
    store: Optional[GraphStore] = None,
    domain_graph: str = GRAPH_DOMAIN,
    atlas_graph: str = GRAPH_ATLAS,
    runs: int = 2,
    parallel: int = 3,
    mode: str = "scripted",
    recording_file: str = DEFAULT_RECORDING_PATH,
    replay: bool = False,
    fast: bool = False,
    strict: bool = False,
    ground_truth: Optional[GroundTruth] = None,
    quiet: bool = False,
) -> dict[str, Any]:
    """Execute autonomous fraud investigation demo or replay recorded session."""
    if replay:
        return play_replay(recording_file=recording_file, fast=fast)

    store = store or GraphStore()

    # 1. Ensure Domain & Atlas are seeded
    gt = ground_truth
    domain_cnt = store.query(domain_graph, "MATCH (n) RETURN count(n) AS cnt")
    if not domain_cnt or domain_cnt[0]["cnt"] == 0 or gt is None:
        if not quiet:
            print(f"[*] Seeding domain graph '{domain_graph}' with demo insurance fraud ring scenario...")
        gt = seed_domain(store, seed=42, profile="demo", domain_graph=domain_graph)

    atlas_cnt = store.query(atlas_graph, "MATCH (n) RETURN count(n) AS cnt")
    if not atlas_cnt or atlas_cnt[0]["cnt"] == 0:
        if not quiet:
            print(f"[*] Seeding atlas graph '{atlas_graph}' with standard skills catalog...")
        seed_atlas(store, atlas_graph=atlas_graph)

    llm_client = OllamaClient() if mode == "live" else MockLLMClient()

    recorded_runs: list[dict[str, Any]] = []

    print(f"\n================================================================================")
    print(f"  LUNA OS AUTONOMOUS INVESTIGATION DEMO")
    print(f"  Mode: {mode.upper()} (strict={strict}) | Runs: {runs} | Parallel Workers: {parallel}")
    print(f"================================================================================\n")

    for run_idx in range(1, runs + 1):
        run_id = f"demo_run_{run_idx}_{int(time.time())}"
        run_graph = f"run_{run_id}"

        # If secondary run, reset customer flagged status, preserving atlas!
        if run_idx > 1:
            if not quiet:
                print(f"\n[*] Resetting domain flags before Run {run_idx} (Atlas reputation is preserved)...")
            reset_flags(store, domain_graph)

        print(f"\n--------------------------------------------------------------------------------")
        print(f"  RUN {run_idx}/{runs}: Initializing Investigation '{run_id}'")
        print(f"--------------------------------------------------------------------------------")

        config = PipelineConfig(
            run_id=run_id,
            domain_graph=domain_graph,
            atlas_graph=atlas_graph,
            max_parallel_agents=parallel,
            strict_llm=strict,
            llm_client=llm_client,
        )

        pipeline = LunaPipeline(store, config)
        run_start_time = time.time()
        event_log: list[dict[str, Any]] = []

        def on_event(ev: PipelineEvent):
            rel_sec = time.time() - run_start_time
            ev_dict = ev.model_dump()
            ev_dict["rel_time_seconds"] = round(rel_sec, 3)
            event_log.append(ev_dict)
            if not quiet:
                print(f"  [+{rel_sec:6.2f}s] {ev.step.ljust(22)} {ev.message}")

        pipeline.subscribe(on_event)

        # Step A: Run workflow up to propose
        start_result = pipeline.start(
            task_description="Investigate suspected auto insurance fraud ring and suspicious cluster anomalies",
            ground_truth=gt,
        )

        # Step B: Auto-approve with approver="auto"
        finish_result = pipeline.approve_and_finish(
            run_id=run_id,
            action_id=start_result.action_id,
            approver="auto",
            ground_truth=gt,
        )

        # Capture Graph Snapshots (Run graph and agent graphs, capped)
        run_snapshot = capture_graph_snapshot(store, run_graph, max_nodes=500, max_edges=1500)
        snapshots = {"run": run_snapshot}

        # Query Promoted Findings Table
        findings_query = (
            "MATCH (f:Finding) "
            "RETURN f.id AS id, f.agent_id AS agent_id, f.skill_id AS skill_id, "
            "       f.target_cid AS target, f.verdict AS verdict, f.confidence AS conf, "
            "       f.status AS status, coalesce(f.backend, 'rules') AS backend, "
            "       f.fallback_reason AS fallback_reason "
            "ORDER BY f.target_cid, f.id"
        )
        finding_rows = store.query(run_graph, findings_query)
        findings_table_data = [
            [
                r.get("agent_id", "")[:24],
                r.get("skill_id", ""),
                r.get("target", ""),
                r.get("verdict", "").upper(),
                f"{float(r.get('conf', 0.0)):.2f}",
                r.get("status", ""),
                r.get("backend", ""),
            ]
            for r in finding_rows
        ]

        if not quiet:
            print(f"\n--- Findings Synthesized ({len(finding_rows)} total) ---")
            print(format_table(["Agent", "Skill", "Target", "Verdict", "Conf", "Status", "Backend"], findings_table_data))

        # Query Contradictions & Conflict Resolution
        decisions_query = (
            "MATCH (d:Decision {kind: 'contradiction_resolution'}) "
            "OPTIONAL MATCH (d)-[:ABOUT]->(c:Customer) "
            "OPTIONAL MATCH (d)-[:UPHELD]->(uf:Finding) "
            "OPTIONAL MATCH (d)-[:SUPERSEDES]->(sf:Finding) "
            "RETURN d.id AS id, c.cid AS customer, d.winning_verdict AS winner, "
            "       d.confidence AS conf, d.components_json AS components, "
            "       d.weights_json AS weights, uf.id AS upheld_id, "
            "       collect(DISTINCT sf.id) AS superseded_ids"
        )
        decision_rows = store.query(run_graph, decisions_query)
        if decision_rows and not quiet:
            print("\n--- Contradiction Detection & Arbitration ---")
            for d in decision_rows:
                print(f"  Contested Entity: {d.get('customer')}")
                print(f"  Arbitration Winner: {str(d.get('winner')).upper()} (Confidence: {float(d.get('conf') or 0.0):.2f})")
                print(f"  Score Components: {d.get('components')} | Weights: {d.get('weights')}")
                print(f"  Upheld Finding: {d.get('upheld_id')} | Superseded Findings: {d.get('superseded_ids')}")

        # Metrics Display
        metrics = finish_result.metrics
        if metrics and not quiet:
            print("\n--- Domain Action & Run-Scoped Evaluation ---")
            print(f"  Action Status: {finish_result.status} (Action ID: {finish_result.action_id}, Approver: auto)")
            print(f"  Performance vs Ground Truth: Precision={metrics.precision:.4f}, Recall={metrics.recall:.4f}, F1={metrics.f1:.4f}")
            print(f"  Confusion Matrix: TP={metrics.true_positives}, FP={metrics.false_positives}, TN={metrics.true_negatives}, FN={metrics.false_negatives}")

        # Skill Reputation Delta Display
        scores_before = finish_result.skill_scores_before
        scores_after = finish_result.skill_scores_after
        if not quiet:
            all_sids = sorted(set(scores_before.keys()) | set(scores_after.keys()))
            score_rows = [
                [
                    sid,
                    f"{scores_before.get(sid, 0.0):.3f}",
                    f"{scores_after.get(sid, 0.0):.3f}",
                    f"{scores_after.get(sid, 0.0) - scores_before.get(sid, 0.0):+.3f}",
                ]
                for sid in all_sids
            ]
            print("\n--- Atlas Skill Reputation Updates (EMA alpha=0.2) ---")
            print(format_table(["Skill ID", "Score Before", "Score After", "Delta"], score_rows))

        # Explain "Why?" Narrative for Ring Customer and Decoy Customer
        explain_data = {}
        try:
            exp_ring = explain_customer(store, run_graph, "cust_ring_1")
            exp_decoy = explain_customer(store, run_graph, "cust_decoy_1")
            explain_data["cust_ring_1"] = exp_ring.model_dump()
            explain_data["cust_decoy_1"] = exp_decoy.model_dump()

            if not quiet:
                print("\n--- Explainability ('Why?') Narrative: Flagged Ring Customer ('cust_ring_1') ---")
                print(f"  {exp_ring.narrative}")
                print("\n--- Explainability ('Why?') Narrative: Cleared Decoy Customer ('cust_decoy_1') ---")
                print(f"  {exp_decoy.narrative}")
        except Exception as e:
            if not quiet:
                print(f"[!] Explainability generation note: {e}")

        # Store run record
        recorded_runs.append({
            "run_id": run_id,
            "events": event_log,
            "graph_snapshots": snapshots,
            "metrics": metrics.model_dump() if metrics else None,
            "skill_scores_before": scores_before,
            "skill_scores_after": scores_after,
            "explain_result": explain_data,
        })

    # Save replay recording file
    Path(recording_file).parent.mkdir(parents=True, exist_ok=True)
    full_recording = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "runs": recorded_runs,
    }
    with open(recording_file, "w", encoding="utf-8") as f:
        json.dump(full_recording, f, indent=2)

    if not quiet:
        print(f"\n[+] Replay recording written successfully to '{recording_file}'")

    return {
        "success": True,
        "runs_completed": len(recorded_runs),
        "recording_file": recording_file,
    }


def main():
    parser = argparse.ArgumentParser(description="LUNA OS Autonomous Fraud Investigation Demo & Replay CLI")
    parser.add_argument("--scripted", action="store_true", default=True, help="Deterministic MockLLMClient execution (default)")
    parser.add_argument("--live", action="store_true", help="Execute with live Ollama LLM")
    parser.add_argument("--strict", action="store_true", help="Strict LLM mode (fail if LLM unavailable)")
    parser.add_argument("--replay", action="store_true", help="Replay from artifacts/replay_recording.json")
    parser.add_argument("--fast", action="store_true", help="Skip playback delay in replay mode")
    parser.add_argument("--runs", type=int, default=2, help="Number of consecutive investigation runs (default: 2)")
    parser.add_argument("--parallel", type=int, default=3, help="Max parallel worker agents (default: 3)")
    parser.add_argument("--recording-file", type=str, default=DEFAULT_RECORDING_PATH, help="Path for replay JSON recording")
    parser.add_argument("--domain", type=str, default=GRAPH_DOMAIN, help="Domain graph name")
    parser.add_argument("--atlas", type=str, default=GRAPH_ATLAS, help="Atlas graph name")

    args = parser.parse_args()
    mode = "live" if args.live else "scripted"

    try:
        run_demo(
            domain_graph=args.domain,
            atlas_graph=args.atlas,
            runs=args.runs,
            parallel=args.parallel,
            mode=mode,
            recording_file=args.recording_file,
            replay=args.replay,
            fast=args.fast,
            strict=args.strict,
        )
    except KeyboardInterrupt:
        print("\n[!] Demo interrupted by user.")
        sys.exit(130)
    except Exception as err:
        print(f"\n[ERROR] Demo execution failed: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
