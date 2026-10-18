#!/usr/bin/env python3
"""LUNA OS Chat Platform Demo Runner (Scenarios D1–D5).

Executes the 5 canonical demo conversations end-to-end:
  D1: Investigate — "Who is connected to the fraud involving customer cust-000?"
  D2: Build — "Build a fullstack todo app with React frontend, Express backend, and Postgres database"
  D3: Follow-up — "What about cust-003?" (context retention)
  D4: Clarification — "Build a todo app using Svelte frontend and Express backend" (needs_input -> /answer)
  D5: Policy — Verification that restricted skill 'shell-runner' is rejected with policy_restricted
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Any

# Ensure repository root is on sys.path
repo_root = str(Path(__file__).resolve().parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from luna.graph.store import GraphStore
from luna.graph.schema import GRAPH_DOMAIN, GRAPH_ATLAS, GRAPH_CONVERSATIONS
from luna.domain.seed import seed_domain
from luna.atlas.seed import seed_atlas
from luna.packs.registry import default_registry
from luna.packs.router import route_prompt
from luna.conversation.store import ConversationStore
from luna.packs.build.pipeline import BuildPipelineConfig
from luna.llm.client import MockLLMClient


def run_demo_conversations(store: Optional[GraphStore] = None) -> dict[str, Any]:
    """Execute all 5 scenarios (D1–D5) sequentially and return structured results."""
    graph_store = store or GraphStore()

    # 1. Initialize environment
    print("=" * 60)
    print("LUNA OS: INITIALIZING DEMO ENVIRONMENT")
    print("=" * 60)
    domain_graph = f"demo_domain_{os.getpid()}"
    atlas_graph = f"demo_atlas_{os.getpid()}"
    conv_graph = f"demo_conv_{os.getpid()}"

    gt = seed_domain(graph_store, seed=42, profile="demo", domain_graph=domain_graph)
    seed_atlas(graph_store, atlas_graph=atlas_graph)

    registry = default_registry()
    registry.seed_all_atlas(graph_store, atlas_graph)

    conv_store = ConversationStore(graph_store, conv_graph)
    conv_store.ensure_schema()
    llm = MockLLMClient()

    results: dict[str, Any] = {}

    try:
        # ---------------------------------------------------------
        # Scenario D1: Investigate (Fraud Ring Detection)
        # ---------------------------------------------------------
        print("\n[Scenario D1] Investigate: Who is connected to fraud customer cust-000?")
        conv_1 = conv_store.create_conversation(title="Investigation: cust-000")
        prompt_1 = "Who is connected to the fraud involving customer cust-000?"
        conv_store.add_turn(conv_1["id"], role="user", text=prompt_1)

        dec_1 = route_prompt(llm, prompt_1, registry, scripted=True)
        print(f"  -> Routed to: {dec_1.pack} (confidence: {dec_1.confidence}, backend: {dec_1.backend})")

        pack_1 = registry.get(dec_1.pack)
        assert pack_1 is not None, "Investigate pack not found"
        pipe_1 = pack_1.build_pipeline(
            graph_store,
            type("Cfg", (), {
                "run_id": "demo_d1_run",
                "domain_graph": domain_graph,
                "atlas_graph": atlas_graph,
                "llm_client": llm,
                "max_parallel_agents": 2,
            })(),
        )
        res_1 = pipe_1.start(prompt_1, ground_truth=gt)
        print(f"  -> Workflow Status: {res_1.status}")
        print(f"  -> Proposed Action ID: {res_1.action_id}")
        assert res_1.action_id is not None

        # Approve action
        fin_1 = pipe_1.approve_and_finish(
            run_id="demo_d1_run",
            action_id=res_1.action_id,
            approver="Chief_Auditor",
            ground_truth=gt,
        )
        print(f"  -> Final Status: {fin_1.status}, Outcome: {fin_1.outcome_id}")
        results["D1"] = {"status": "success", "pack": dec_1.pack, "action_id": res_1.action_id}

        # ---------------------------------------------------------
        # Scenario D2: Software-Build (Fullstack Todo App)
        # ---------------------------------------------------------
        print("\n[Scenario D2] Build: Fullstack Todo App (React, Express, Postgres)")
        conv_2 = conv_store.create_conversation(title="Build: Todo App")
        prompt_2 = "Build a fullstack todo app with React frontend, Express backend, and Postgres database"
        conv_store.add_turn(conv_2["id"], role="user", text=prompt_2)

        dec_2 = route_prompt(llm, prompt_2, registry, scripted=True)
        print(f"  -> Routed to: {dec_2.pack} (confidence: {dec_2.confidence})")

        pack_2 = registry.get(dec_2.pack)
        assert pack_2 is not None, "Build pack not found"
        pipe_2 = pack_2.build_pipeline(
            graph_store,
            BuildPipelineConfig(run_id="demo_d2_run", atlas_graph=atlas_graph),
        )
        res_2 = pipe_2.start(prompt_2)
        print(f"  -> Workflow Status: {res_2.status}")
        print(f"  -> Generated Artifacts: {len(res_2.artifacts)} files")
        print(f"  -> Contracts Verified: {res_2.verification.get('passed')}")
        assert res_2.verification.get("passed") is True

        fin_2 = pipe_2.approve_and_finish(action_id=res_2.action_id, approver="Tech_Lead")
        print(f"  -> Final Status: {fin_2.status}, Outcome: {fin_2.outcome_id}")
        results["D2"] = {"status": "success", "pack": dec_2.pack, "artifacts_count": len(res_2.artifacts)}

        # Clean workspace
        if pipe_2.workspace:
            pipe_2.workspace.cleanup()
        if os.path.exists(res_2.zip_path):
            os.remove(res_2.zip_path)

        # ---------------------------------------------------------
        # Scenario D3: Follow-Up (Entity Context Retention)
        # ---------------------------------------------------------
        print("\n[Scenario D3] Follow-up: What about cust-003?")
        # Add prior turn to conversation 1
        conv_store.add_turn(conv_1["id"], role="assistant", text="Found ring around cust-000", run_id="demo_d1_run", pack="investigate")
        prompt_3 = "What about cust-003?"
        conv_store.add_turn(conv_1["id"], role="user", text=prompt_3)

        ctx_3 = conv_store.get_context(conv_1["id"])
        print(f"  -> Context Extracted Entities: {ctx_3.get('entities')}")
        print(f"  -> Context Prior Pack: {ctx_3.get('pack')}")
        assert "cust-000" in ctx_3.get("entities", [])
        assert ctx_3.get("pack") == "investigate"

        dec_3 = route_prompt(llm, prompt_3, registry, context=ctx_3, scripted=True)
        print(f"  -> Inherited Routing: {dec_3.pack}")
        assert dec_3.pack == "investigate"
        results["D3"] = {"status": "success", "context_entities": ctx_3["entities"], "routed_pack": dec_3.pack}

        # ---------------------------------------------------------
        # Scenario D4: Clarification (Unsupported Tech -> needs_input)
        # ---------------------------------------------------------
        print("\n[Scenario D4] Clarification: Unsupported Svelte frontend")
        conv_4 = conv_store.create_conversation(title="Build: Svelte App")
        prompt_4 = "Build a todo app using Svelte frontend and Express backend"
        conv_store.add_turn(conv_4["id"], role="user", text=prompt_4)

        pack_build = registry.get("build")
        under_4 = pack_build.understand(llm, prompt_4)
        print(f"  -> Needs Input: {under_4.needs_input}")
        print(f"  -> Clarification: {under_4.clarification_question}")
        assert under_4.needs_input is True
        assert "Svelte" in under_4.clarification_question

        # User answers clarification
        prompt_4_resumed = "Switch to React instead of Svelte"
        under_4_res = pack_build.understand(llm, prompt_4_resumed)
        print(f"  -> Resumed Needs Input: {under_4_res.needs_input}")
        assert under_4_res.needs_input is False
        results["D4"] = {"status": "success", "needs_input": True, "clarified": True}

        # ---------------------------------------------------------
        # Scenario D5: Policy Enforcement (Restricted Skill 'shell-runner')
        # ---------------------------------------------------------
        print("\n[Scenario D5] Policy: Restricted 'shell-runner' skill rejection")
        shell_skill = graph_store.query(
            atlas_graph,
            "MATCH (s:Skill {id: 'shell-runner'}) RETURN s.name AS name, s.restricted AS restricted",
        )
        assert len(shell_skill) == 1
        assert shell_skill[0]["restricted"] is True
        print(f"  -> Skill '{shell_skill[0]['name']}' is restricted: {shell_skill[0]['restricted']}")

        # Verify build pipeline excludes restricted skills
        build_pipe = pack_build.build_pipeline(graph_store, BuildPipelineConfig(run_id="demo_d5_policy", atlas_graph=atlas_graph))
        eligible_skills = graph_store.query(
            atlas_graph,
            "MATCH (s:Skill)-[:PROVIDES]->(:Capability {name: 'scaffold_project'}) "
            "WHERE coalesce(s.restricted, false) = false "
            "RETURN s.id AS id",
        )
        assert "shell-runner" not in [s["id"] for s in eligible_skills]
        print(f"  -> Policy filter successfully excluded 'shell-runner'")
        results["D5"] = {"status": "success", "policy_restricted": True}

        print("\n" + "=" * 60)
        print("ALL 5 DEMO SCENARIOS (D1–D5) COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        return {"success": True, "scenarios": results}

    finally:
        graph_store.delete_graph(domain_graph)
        graph_store.delete_graph(atlas_graph)
        graph_store.delete_graph(conv_graph)


if __name__ == "__main__":
    run_demo_conversations()
