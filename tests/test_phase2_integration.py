"""End-to-end integration test verifying the complete Phase 1 and Phase 2 pipeline on live FalkorDB.

Pipeline flow:
1. Seed synthetic domain dataset with planted fraud ring and decoy family.
2. Decompose task and assign skills from atlas catalog.
3. Extract private k-hop sub-graph slices for sub-agents.
4. Launch scoped FastMCP servers pinned to private slices.
5. Autonomous sub-agents execute observe-orient-decide-act loop.
6. Finding promotion engine validates evidence CIDs against private slices and merges to run memory.
7. Anti-hallucination barrier rejects findings citing unverified evidence.
"""

import pytest
from luna.atlas.seed import seed_atlas
from luna.atlas.assign import assign_skills_to_subtasks
from luna.domain.seed import seed_domain
from luna.planner.decompose import Subtask
from luna.graph.schema import (
    agent_graph_name,
    run_graph_name,
    GRAPH_DOMAIN,
)
from luna.llm.client import MockLLMClient
from luna.mcp.client import AgentMCPClient
from luna.mcp.server import create_agent_mcp_server
from luna.orchestrator.promote import promote_findings
from luna.orchestrator.slice import extract_subgraph_slice
from luna.agents.models import Finding, SubAgentRunConfig
from luna.agents.subagent import SubAgent


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_phase1_phase2_end_to_end_pipeline(live_store) -> None:
    """Execute full orchestrator workflow against live FalkorDB instance."""
    # Step 1: Seed atlas skill catalog and synthetic domain graph
    seed_atlas(live_store)
    gt = seed_domain(live_store, seed=42)
    ring_cids = sorted(list(gt.ring_cids))
    target_cid = ring_cids[0]

    run_id = "phase2_e2e_run"
    agent_id = "agent_ring_scout"
    slice_graph = agent_graph_name(run_id, agent_id)
    shared_run_graph = run_graph_name(run_id)

    try:
        # Step 2: Assign skills from catalog for subtask
        subtask = Subtask(
            id="task-01",
            description="Link entities across claims",
            capability="link_entities",
            target_entities=[target_cid],
        )
        assignments = assign_skills_to_subtasks(
            store=live_store,
            subtasks=[subtask],
            task_type="fraud_ring_investigation",
        )
        assert len(assignments) == 1
        assert assignments[0].chosen_skill is not None
        assert assignments[0].chosen_skill.id == "entity-linker"
        chosen_skill = assignments[0].chosen_skill

        # Step 3: Extract private slice for fraud ring customer
        slice_summary = extract_subgraph_slice(
            store=live_store,
            source_graph=GRAPH_DOMAIN,
            target_graph=slice_graph,
            seed_cids=[target_cid],
            k_hops=2,
        )
        assert slice_summary["nodes_extracted"] > 0
        assert target_cid in slice_summary["extracted_cids"]

        # Step 4: Launch agent FastMCP server and client scoped to slice
        server = create_agent_mcp_server(
            agent_id=agent_id,
            tool_names=["shared_attribute_links"],
            graph_store=live_store,
            agent_graph_name=slice_graph,
        )
        mcp_client = AgentMCPClient(server, allowed_tool_names=["shared_attribute_links"])

        # Step 5: Autonomous SubAgent runs investigation loop
        subagent = SubAgent(
            config=SubAgentRunConfig(
                agent_id=agent_id,
                skill_id=chosen_skill.id,
                prompt_fragment=chosen_skill.prompt_fragment,
                target_cids=[target_cid],
                private_graph_name=slice_graph,
            ),
            mcp_client=mcp_client,
            llm_client=MockLLMClient(),
        )
        findings = await subagent.run()
        assert len(findings) == 1
        finding = findings[0]
        assert finding.target_cid == target_cid
        assert finding.verdict == "suspicious"
        assert len(finding.evidence_cids) > 0

        # Step 6: Finding promotion into shared run graph
        promo_result = promote_findings(
            store=live_store,
            agent_graph_name=slice_graph,
            run_graph_name=shared_run_graph,
            findings=[finding],
        )
        assert promo_result.total_promoted == 1
        assert promo_result.total_rejected == 0
        assert promo_result.promoted[0].id == finding.id

        # Verify Finding node exists in live run graph
        f_nodes = live_store.query(shared_run_graph, "MATCH (f:Finding) RETURN f.id AS id")
        assert len(f_nodes) == 1

        # Step 7: Anti-hallucination barrier - reject finding citing unverified evidence
        fake_finding = Finding(
            agent_id=agent_id,
            skill_id="entity-linker",
            target_cid=target_cid,
            verdict="suspicious",
            confidence=0.99,
            reasoning="Fabricated evidence test",
            evidence_cids=["ghost-cid-does-not-exist"],
        )
        fake_promo = promote_findings(
            store=live_store,
            agent_graph_name=slice_graph,
            run_graph_name=shared_run_graph,
            findings=[fake_finding],
        )
        assert fake_promo.total_promoted == 0
        assert fake_promo.total_rejected == 1
        assert "anti-hallucination barrier" in fake_promo.rejected[0].reason
    finally:
        live_store.delete_graph(slice_graph)
        live_store.delete_graph(shared_run_graph)
