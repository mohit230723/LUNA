"""Local LLM benchmark script for LUNA OS (F14).

Runs the SubAgent against the demo profile with real OllamaLLM and strict_llm=True for N runs.
Evaluates JSON validity rate, evidence provenance validity rate (per F2 checks), execution time,
and tool calls per run. Always exits with code 0.
"""

import sys
import time
import uuid
import asyncio
import argparse
import statistics
from pathlib import Path
from typing import Any, Optional

# Ensure repository root is on sys.path when invoked directly
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from luna.graph.store import GraphStore
from luna.graph.schema import GRAPH_DOMAIN
from luna.domain.seed import seed_domain
from luna.orchestrator.slice import extract_subgraph_slice
from luna.mcp.server import create_agent_mcp_server
from luna.mcp.client import AgentMCPClient
from luna.llm.client import OllamaLLM
from luna.agents.models import SubAgentRunConfig
from luna.agents.subagent import SubAgent, LLMUnavailableError


async def run_single_benchmark(
    store: GraphStore,
    target_cid: str,
    run_idx: int,
    model: str,
    base_url: str,
) -> dict[str, Any]:
    """Execute a single SubAgent benchmark run with strict_llm=True."""
    slice_name = f"bench_slice_{uuid.uuid4().hex[:8]}"
    tool_names = ["shared_attribute_links", "connected_components"]

    # 1. Extract slice from demo domain
    try:
        extract_subgraph_slice(
            store=store,
            source_graph=GRAPH_DOMAIN,
            target_graph=slice_name,
            seed_cids=[target_cid],
            k_hops=2,
        )
    except Exception as e:
        return {
            "run": run_idx,
            "duration": 0.0,
            "tool_calls": 0,
            "valid_json": False,
            "valid_evidence": False,
            "error": f"SliceExtractionError: {e}",
        }

    # 2. Setup MCP server and client
    server = create_agent_mcp_server(
        agent_id=f"bench_agent_{run_idx}",
        tool_names=tool_names,
        graph_store=store,
        agent_graph_name=slice_name,
    )
    client = AgentMCPClient(server, allowed_tool_names=tool_names)

    # 3. Setup SubAgent with strict_llm
    config = SubAgentRunConfig(
        agent_id=f"bench_agent_{run_idx}",
        skill_id="entity-linker",
        prompt_fragment="Report any customer sharing attributes with others as suspicious with confidence 0.60 to 0.70.",
        target_cids=[target_cid],
        private_graph_name=slice_name,
    )
    llm = OllamaLLM(base_url=base_url, model=model)
    agent = SubAgent(config=config, mcp_client=client, llm_client=llm, strict_llm=True)

    # 4. Measure execution
    t0 = time.perf_counter()
    valid_json = False
    valid_evidence = False
    tool_calls = 0
    err_msg: Optional[str] = None

    try:
        findings = await agent.run()
        duration = time.perf_counter() - t0
        tool_calls = len(agent.tool_log.calls)

        if findings and len(findings) > 0:
            valid_json = True
            finding = findings[0]
            observed_strs = agent.tool_log.observed_strings()

            # F2 Checks:
            # Check 1: Evidence CIDs not empty & all exist in slice
            has_evidence = len(finding.evidence_cids) > 0
            all_exist = True
            for cid in finding.evidence_cids:
                recs = store.query(slice_name, "MATCH (n) WHERE n.cid = $cid RETURN count(n) AS cnt", {"cid": cid})
                if not recs or recs[0].get("cnt", 0) == 0:
                    all_exist = False
                    break

            # Check 2: All evidence CIDs were observed in tool outputs
            all_observed = all(cid in observed_strs for cid in finding.evidence_cids)

            # Check 3: All evidence connected within max_hops=3
            all_connected = True
            for cid in finding.evidence_cids:
                sp_query = "MATCH (a), (b) WHERE a.cid = $t AND b.cid = $e WITH shortestPath((a)-[*..3]-(b)) AS p RETURN p"
                recs = store.query(slice_name, sp_query, {"t": finding.target_cid, "e": cid})
                if not recs or recs[0].get("p") is None:
                    all_connected = False
                    break

            if has_evidence and all_exist and all_observed and all_connected:
                valid_evidence = True

    except (LLMUnavailableError, Exception) as e:
        duration = time.perf_counter() - t0
        tool_calls = len(agent.tool_log.calls) if hasattr(agent, "tool_log") else 0
        err_msg = f"{type(e).__name__}: {e}"
    finally:
        try:
            store.delete_graph(slice_name)
        except Exception:
            pass

    return {
        "run": run_idx,
        "duration": duration,
        "tool_calls": tool_calls,
        "valid_json": valid_json,
        "valid_evidence": valid_evidence,
        "error": err_msg,
    }


async def main_async() -> int:
    parser = argparse.ArgumentParser(description="LUNA OS Local LLM Benchmark")
    parser.add_argument("--n", type=int, default=5, help="Number of benchmark runs (default: 5)")
    parser.add_argument("--model", type=str, default="llama3.1", help="Ollama model name (default: llama3.1)")
    parser.add_argument("--base-url", type=str, default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--host", type=str, default="localhost", help="FalkorDB host")
    parser.add_argument("--port", type=int, default=6379, help="FalkorDB port")
    parser.add_argument("--markdown", action="store_true", help="Print results as a Markdown table")

    args = parser.parse_args()
    n = max(1, args.n)

    # Connect to FalkorDB
    try:
        store = GraphStore(host=args.host, port=args.port)
        gt = seed_domain(store, seed=42, profile="demo")
        target_cid = sorted(list(gt.ring_cids))[0]
    except Exception as e:
        # Gracefully handle if DB or domain cannot be loaded
        if args.markdown:
            print("| Metric | Value |")
            print("|---|---|")
            print(f"| Runs | {n} |")
            print("| Status | Failed to connect to FalkorDB |")
            print(f"| Error | {e} |")
        else:
            print(f"Benchmark aborted: could not connect to FalkorDB ({e})")
        return 0

    results = []
    for i in range(1, n + 1):
        res = await run_single_benchmark(
            store=store,
            target_cid=target_cid,
            run_idx=i,
            model=args.model,
            base_url=args.base_url,
        )
        results.append(res)

    # Compute metrics
    durations = [r["duration"] for r in results]
    tool_calls = [r["tool_calls"] for r in results]
    valid_json_count = sum(1 for r in results if r["valid_json"])
    valid_evidence_count = sum(1 for r in results if r["valid_evidence"])

    valid_json_rate = (valid_json_count / n) * 100.0
    valid_evidence_rate = (valid_evidence_count / n) * 100.0
    median_duration = statistics.median(durations) if durations else 0.0
    max_duration = max(durations) if durations else 0.0
    avg_tool_calls = statistics.mean(tool_calls) if tool_calls else 0.0

    errors = [r["error"] for r in results if r.get("error")]
    first_error = errors[0] if errors else None

    if args.markdown:
        print("| Metric | Value |")
        print("|---|---|")
        print(f"| Model | {args.model} |")
        print(f"| Runs | {n} |")
        print(f"| Valid JSON Rate | {valid_json_rate:.1f}% ({valid_json_count}/{n}) |")
        print(f"| Valid Evidence Rate (F2) | {valid_evidence_rate:.1f}% ({valid_evidence_count}/{n}) |")
        print(f"| Median Duration | {median_duration:.2f}s |")
        print(f"| Max Duration | {max_duration:.2f}s |")
        print(f"| Tool Calls / Run | {avg_tool_calls:.1f} (per run: {tool_calls}) |")
        if first_error:
            # Truncate error for table display
            short_err = first_error.split("\n")[0][:80]
            print(f"| LLM Status | Offline / Error: {short_err} |")
        else:
            print("| LLM Status | Online (All runs generated valid schema) |")
    else:
        print("========================================")
        print("      LUNA Local LLM Benchmark Report   ")
        print("========================================")
        print(f"Model: {args.model} (base_url: {args.base_url})")
        print(f"Runs: {n}")
        print(f"Valid JSON Rate: {valid_json_rate:.1f}% ({valid_json_count}/{n})")
        print(f"Valid Evidence Rate (F2): {valid_evidence_rate:.1f}% ({valid_evidence_count}/{n})")
        print(f"Median Duration: {median_duration:.2f}s")
        print(f"Max Duration: {max_duration:.2f}s")
        print(f"Tool Calls / Run: {tool_calls} (Mean: {avg_tool_calls:.1f})")
        if first_error:
            print(f"Note: {first_error}")

    return 0


def main() -> None:
    try:
        code = asyncio.run(main_async())
        sys.exit(code)
    except Exception as e:
        print(f"Benchmark encountered unexpected error: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()
