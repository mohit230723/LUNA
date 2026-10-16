"""Integration tests for F8: engineered genuine conflict between skills on decoy vs ring."""

import pytest
from luna.domain.seed import seed_domain
from luna.graph.schema import agent_graph_name, GRAPH_DOMAIN
from luna.llm.client import MockLLMClient
from luna.mcp.client import AgentMCPClient
from luna.mcp.server import create_agent_mcp_server
from luna.orchestrator.slice import extract_subgraph_slice
from luna.agents.models import SubAgentRunConfig
from luna.agents.subagent import SubAgent


@pytest.mark.integration
@pytest.mark.asyncio
async def test_decoy_gets_opposing_verdicts_from_two_skills(live_store):
    """Verify decoy member receives 'suspicious' (0.60-0.70) from entity-linker and 'benign' (0.75-0.85) from community-analyzer."""
    gt = seed_domain(live_store, seed=42, profile="demo")
    decoy_cid = sorted(list(gt.decoy_cids))[0]

    run_id = "test_conflict_decoy_run"
    slice1_name = agent_graph_name(run_id, "agent_linker")
    slice2_name = agent_graph_name(run_id, "agent_comm")

    try:
        # Extract slice for Agent 1 (entity-linker)
        extract_subgraph_slice(
            store=live_store,
            source_graph=GRAPH_DOMAIN,
            target_graph=slice1_name,
            seed_cids=[decoy_cid],
            k_hops=2,
        )

        # Agent 1: entity-linker
        server1 = create_agent_mcp_server(
            agent_id="agent_linker",
            tool_names=["shared_attribute_links"],
            graph_store=live_store,
            agent_graph_name=slice1_name,
        )
        client1 = AgentMCPClient(server1, allowed_tool_names=["shared_attribute_links"])
        subagent1 = SubAgent(
            config=SubAgentRunConfig(
                agent_id="agent_linker",
                skill_id="entity-linker",
                prompt_fragment="Report any customer sharing any attribute (phone, bank account, address) as suspicious with confidence 0.60 to 0.70.",
                target_cids=[decoy_cid],
                private_graph_name=slice1_name,
            ),
            mcp_client=client1,
            llm_client=MockLLMClient(),
        )
        findings1 = await subagent1.run()
        assert len(findings1) == 1
        finding1 = findings1[0]

        # Extract slice for Agent 2 (community-analyzer)
        extract_subgraph_slice(
            store=live_store,
            source_graph=GRAPH_DOMAIN,
            target_graph=slice2_name,
            seed_cids=[decoy_cid],
            k_hops=2,
        )

        # Agent 2: community-analyzer
        server2 = create_agent_mcp_server(
            agent_id="agent_comm",
            tool_names=["shared_attribute_links", "connected_components"],
            graph_store=live_store,
            agent_graph_name=slice2_name,
        )
        client2 = AgentMCPClient(server2, allowed_tool_names=["shared_attribute_links", "connected_components"])
        subagent2 = SubAgent(
            config=SubAgentRunConfig(
                agent_id="agent_comm",
                skill_id="community-analyzer",
                prompt_fragment="Analyze attribute clusters. A customer connected to others only through Address is benign with confidence 0.75 to 0.85; customers connected through BankAccount or Phone are suspicious.",
                target_cids=[decoy_cid],
                private_graph_name=slice2_name,
            ),
            mcp_client=client2,
            llm_client=MockLLMClient(),
        )
        findings2 = await subagent2.run()
        assert len(findings2) == 1
        finding2 = findings2[0]

        # Assert genuine opposing conflict on the same target
        assert finding1.target_cid == decoy_cid
        assert finding2.target_cid == decoy_cid
        assert finding1.verdict == "suspicious"
        assert 0.60 <= finding1.confidence <= 0.70
        assert finding2.verdict == "benign"
        assert 0.75 <= finding2.confidence <= 0.85
        assert finding1.evidence_cids, "Evidence must be cited for suspicious verdict"
    finally:
        live_store.delete_graph(slice1_name)
        live_store.delete_graph(slice2_name)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ring_gets_consistent_suspicious_verdicts(live_store):
    """Verify ring member receives consistent 'suspicious' verdicts from both skills."""
    gt = seed_domain(live_store, seed=42, profile="demo")
    ring_cid = sorted(list(gt.ring_cids))[0]

    run_id = "test_conflict_ring_run"
    slice1_name = agent_graph_name(run_id, "agent_linker_ring")
    slice2_name = agent_graph_name(run_id, "agent_comm_ring")

    try:
        # Extract slices
        extract_subgraph_slice(
            store=live_store,
            source_graph=GRAPH_DOMAIN,
            target_graph=slice1_name,
            seed_cids=[ring_cid],
            k_hops=2,
        )
        extract_subgraph_slice(
            store=live_store,
            source_graph=GRAPH_DOMAIN,
            target_graph=slice2_name,
            seed_cids=[ring_cid],
            k_hops=2,
        )

        server1 = create_agent_mcp_server(
            agent_id="agent_linker_ring",
            tool_names=["shared_attribute_links"],
            graph_store=live_store,
            agent_graph_name=slice1_name,
        )
        client1 = AgentMCPClient(server1, allowed_tool_names=["shared_attribute_links"])
        subagent1 = SubAgent(
            config=SubAgentRunConfig(
                agent_id="agent_linker_ring",
                skill_id="entity-linker",
                prompt_fragment="Report any customer sharing any attribute (phone, bank account, address) as suspicious with confidence 0.60 to 0.70.",
                target_cids=[ring_cid],
                private_graph_name=slice1_name,
            ),
            mcp_client=client1,
            llm_client=MockLLMClient(),
        )
        findings1 = await subagent1.run()

        server2 = create_agent_mcp_server(
            agent_id="agent_comm_ring",
            tool_names=["shared_attribute_links", "connected_components"],
            graph_store=live_store,
            agent_graph_name=slice2_name,
        )
        client2 = AgentMCPClient(server2, allowed_tool_names=["shared_attribute_links", "connected_components"])
        subagent2 = SubAgent(
            config=SubAgentRunConfig(
                agent_id="agent_comm_ring",
                skill_id="community-analyzer",
                prompt_fragment="Analyze attribute clusters. A customer connected to others only through Address is benign with confidence 0.75 to 0.85; customers connected through BankAccount or Phone are suspicious.",
                target_cids=[ring_cid],
                private_graph_name=slice2_name,
            ),
            mcp_client=client2,
            llm_client=MockLLMClient(),
        )
        findings2 = await subagent2.run()

        assert findings1[0].verdict == "suspicious"
        assert findings2[0].verdict == "suspicious"
        assert findings1[0].target_cid == ring_cid
        assert findings2[0].target_cid == ring_cid
    finally:
        live_store.delete_graph(slice1_name)
        live_store.delete_graph(slice2_name)


@pytest.mark.integration
def test_demo_orchestration_gives_agents_slices_containing_decoy_family(live_store):
    """Verify demo orchestration can supply slices that both contain the decoy family (seed list has ring and decoy members)."""
    gt = seed_domain(live_store, seed=42, profile="demo")
    ring_cid = sorted(list(gt.ring_cids))[0]
    decoy_cid = sorted(list(gt.decoy_cids))[0]

    seed_list = [ring_cid, decoy_cid]
    run_id = "test_shared_slices_run"
    slice1 = agent_graph_name(run_id, "agent_1")
    slice2 = agent_graph_name(run_id, "agent_2")

    try:
        s1 = extract_subgraph_slice(
            store=live_store,
            source_graph=GRAPH_DOMAIN,
            target_graph=slice1,
            seed_cids=seed_list,
            k_hops=2,
        )
        s2 = extract_subgraph_slice(
            store=live_store,
            source_graph=GRAPH_DOMAIN,
            target_graph=slice2,
            seed_cids=seed_list,
            k_hops=2,
        )

        assert ring_cid in s1["extracted_cids"]
        assert decoy_cid in s1["extracted_cids"]
        assert "addr_decoy" in s1["extracted_cids"]
        assert ring_cid in s2["extracted_cids"]
        assert decoy_cid in s2["extracted_cids"]
        assert "addr_decoy" in s2["extracted_cids"]
    finally:
        live_store.delete_graph(slice1)
        live_store.delete_graph(slice2)

