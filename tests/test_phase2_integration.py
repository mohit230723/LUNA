"""End-to-end integration test verifying the complete Phase 1 and Phase 2 pipeline.

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
from unittest.mock import MagicMock
from luna.atlas.assign import assign_skills_to_subtasks
from luna.planner.decompose import Subtask
from luna.graph.schema import (
    agent_graph_name,
    run_graph_name,
    GRAPH_ATLAS,
    GRAPH_DOMAIN,
)
from luna.graph.store import GraphStore
from luna.llm.client import MockLLMClient
from luna.mcp.client import AgentMCPClient
from luna.mcp.server import create_agent_mcp_server
from luna.orchestrator.promote import promote_findings
from luna.orchestrator.slice import extract_subgraph_slice
from luna.agents.models import Finding, SubAgentRunConfig
from luna.agents.subagent import SubAgent


@pytest.mark.asyncio
async def test_complete_phase1_phase2_end_to_end_pipeline() -> None:
    """Execute full orchestrator workflow from skill assignment through private slice extraction to promotion."""
    # In-memory graph simulator for offline deterministic integration testing
    graphs: dict[str, dict[str, list[dict]]] = {}

    def get_or_create_graph(gname: str):
        if gname not in graphs:
            graphs[gname] = {"nodes": [], "edges": []}
        return graphs[gname]

    mock_client = MagicMock()

    def mock_query(graph_name: str, query_str: str, params=None):
        g = get_or_create_graph(graph_name)
        p = params or {}

        # 1. Atlas skill matching query
        if "MATCH (s:Skill)-[:PROVIDES]->(c:Capability" in query_str:
            cap = p.get("cap")
            if cap == "link_entities":
                return [
                    {
                        "id": "entity-linker",
                        "name": "Entity Linker",
                        "prompt_fragment": "Identify shared attribute connections.",
                        "restricted": False,
                        "score": 0.85,
                        "requires": [],
                    }
                ]
            return []

        # 2. Slice extraction seed query
        if "MATCH (anchor) WHERE anchor.cid IN $seed_cids" in query_str:
            cids = p.get("seed_cids", [])
            return [
                {
                    "label": "Customer",
                    "props": {"cid": c, "name": f"Customer {c}"},
                }
                for c in cids
            ]

        # 3. Slice extraction k-hop traversal query
        if "path = (anchor)-[*1..2]-(n)" in query_str:
            cids = p.get("seed_cids", [])
            if "cust-000" in cids:
                # Fraud ring k-hop neighborhood
                return [
                    {
                        "label": "Customer",
                        "props": {"cid": "cust-001", "name": "Associate Customer"},
                    },
                    {
                        "label": "BankAccount",
                        "props": {"cid": "ba-ring-01", "account_num": "ACC-RING-99"},
                    },
                ]
            elif "cust-010" in cids:
                # Decoy family k-hop neighborhood
                return [
                    {
                        "label": "Address",
                        "props": {"cid": "addr-decoy-01", "address": "77 Decoy Ave"},
                    }
                ]
            return []

        # 4. Slice extraction induced edges query
        if "MATCH (a)-[r]->(b)" in query_str and "WHERE a.cid IN $cids AND b.cid IN $cids" in query_str:
            cids = set(p.get("cids", []))
            edges = []
            if "cust-000" in cids and "ba-ring-01" in cids:
                edges.append({
                    "from_cid": "cust-000",
                    "to_cid": "ba-ring-01",
                    "rel_type": "HAS_ACCOUNT",
                    "props": {},
                })
            if "cust-001" in cids and "ba-ring-01" in cids:
                edges.append({
                    "from_cid": "cust-001",
                    "to_cid": "ba-ring-01",
                    "rel_type": "HAS_ACCOUNT",
                    "props": {},
                })
            if "cust-010" in cids and "addr-decoy-01" in cids:
                edges.append({
                    "from_cid": "cust-010",
                    "to_cid": "addr-decoy-01",
                    "rel_type": "LIVES_AT",
                    "props": {},
                })
            return edges

        # 5. Insertions into private target graph
        if "UNWIND $batch AS props CREATE (n:" in query_str:
            for item in p.get("batch", []):
                g["nodes"].append(item)
            return []

        if "UNWIND $batch AS edge" in query_str:
            for item in p.get("batch", []):
                g["edges"].append(item)
            return []

        # 6. Shared attribute tool queries
        if "MATCH (c1 {cid: $cid})-[r1]->(a)<-[r2]-(c2)" in query_str:
            cid = p.get("cid")
            if cid == "cust-000":
                return [
                    {
                        "shared_cid": "cust-001",
                        "shared_label": "Customer",
                        "attribute_type": "BankAccount",
                        "attribute_cid": "ba-ring-01",
                        "rel_out": "HAS_ACCOUNT",
                        "rel_in": "HAS_ACCOUNT",
                    }
                ]
            return []

        # 7. Promotion evidence verification query
        if "MATCH (n) WHERE n.cid = $cid RETURN count(n) AS cnt" in query_str:
            cid = p.get("cid")
            # Check if cid exists in graph nodes
            node_exists = any(n.get("cid") == cid for n in g["nodes"])
            return [{"cnt": 1 if node_exists else 0}]

        # 8. Run graph write queries
        if "CREATE (f:Finding" in query_str or "CREATE (f)-[:" in query_str:
            g["nodes"].append(p)
            return []

        return []

    mock_client.select_graph.return_value.query = lambda q, p=None: MagicMock(
        header=[], result_set=[]
    )
    store = GraphStore(client=mock_client)
    store.query = mock_query  # type: ignore

    # Step 1: Assign skills for subtask
    subtask = Subtask(
        id="task-01",
        description="Link entities across claims",
        capability="link_entities",
        target_entities=["cust-000", "cust-010"],
    )
    assignments = assign_skills_to_subtasks(
        store=store,
        subtasks=[subtask],
        task_type="fraud_ring_investigation",
    )
    assert len(assignments) == 1
    assert assignments[0].chosen_skill is not None
    assert assignments[0].chosen_skill.id == "entity-linker"
    chosen_skill = assignments[0].chosen_skill

    # Step 2: Extract private slice for fraud ring customer
    run_id = "run-hackathon-01"
    agent_id = "agent-ring-scout"
    slice_graph = agent_graph_name(run_id, agent_id)

    slice_summary = extract_subgraph_slice(
        store=store,
        source_graph=GRAPH_DOMAIN,
        target_graph=slice_graph,
        seed_cids=["cust-000"],
        k_hops=2,
    )
    assert slice_summary["nodes_extracted"] == 3
    assert set(slice_summary["extracted_cids"]) == {"cust-000", "cust-001", "ba-ring-01"}

    # Step 3: Launch agent FastMCP server and client scoped to slice
    server = create_agent_mcp_server(
        agent_id=agent_id,
        tool_names=["shared_attribute_links"],
        graph_store=store,
        agent_graph_name=slice_graph,
    )
    mcp_client = AgentMCPClient(server, allowed_tool_names=["shared_attribute_links"])

    # Step 4: Autonomous SubAgent runs investigation loop
    subagent = SubAgent(
        config=SubAgentRunConfig(
            agent_id=agent_id,
            skill_id=chosen_skill.id,
            prompt_fragment=chosen_skill.prompt_fragment,
            target_cids=["cust-000"],
            private_graph_name=slice_graph,
        ),
        mcp_client=mcp_client,
        llm_client=MockLLMClient(),
    )
    findings = await subagent.run()
    assert len(findings) == 1
    finding = findings[0]
    assert finding.target_cid == "cust-000"
    assert finding.verdict == "suspicious"
    assert "ba-ring-01" in finding.evidence_cids
    assert "cust-001" in finding.evidence_cids

    # Step 5: Finding promotion into shared run graph
    shared_run_graph = run_graph_name(run_id)
    promo_result = promote_findings(
        store=store,
        agent_graph_name=slice_graph,
        run_graph_name=shared_run_graph,
        findings=[finding],
    )
    assert promo_result.total_promoted == 1
    assert promo_result.total_rejected == 0
    assert promo_result.promoted[0].id == finding.id

    # Step 6: Anti-hallucination check - reject finding with fake evidence
    fake_finding = Finding(
        agent_id=agent_id,
        skill_id="entity-linker",
        target_cid="cust-000",
        verdict="suspicious",
        confidence=0.99,
        reasoning="Fabricated evidence test",
        evidence_cids=["ghost-cid-does-not-exist"],
    )
    fake_promo = promote_findings(
        store=store,
        agent_graph_name=slice_graph,
        run_graph_name=shared_run_graph,
        findings=[fake_finding],
    )
    assert fake_promo.total_promoted == 0
    assert fake_promo.total_rejected == 1
    assert "anti-hallucination barrier" in fake_promo.rejected[0].reason
