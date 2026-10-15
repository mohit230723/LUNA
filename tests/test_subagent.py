"""Unit tests for sub-agent execution loop and finding generation."""

import pytest
from luna.agents.models import Finding, SubAgentRunConfig
from luna.agents.subagent import SubAgent
from luna.llm.client import MockLLMClient
from luna.mcp.client import AgentMCPClient
from luna.mcp.server import create_agent_mcp_server
from luna.graph.store import GraphStore
from unittest.mock import MagicMock


def test_finding_model_validation() -> None:
    """Verify validation rules on Finding model."""
    f = Finding(
        agent_id="agent-01",
        skill_id="entity-linker",
        target_cid="cust-000",
        verdict="suspicious",
        confidence=0.95,
        reasoning="Shared high-risk bank account with cust-001",
        evidence_cids=["ba-ring-01", "cust-001"],
    )
    assert f.id.startswith("find-")
    assert f.verdict == "suspicious"
    assert f.confidence == 0.95
    assert len(f.evidence_cids) == 2

    # Invalid confidence
    with pytest.raises(ValueError):
        Finding(
            agent_id="agent-01",
            skill_id="entity-linker",
            target_cid="cust-000",
            verdict="suspicious",
            confidence=1.5,  # > 1.0
            reasoning="test",
        )

    # Invalid verdict
    with pytest.raises(ValueError):
        Finding(
            agent_id="agent-01",
            skill_id="entity-linker",
            target_cid="cust-000",
            verdict="unknown",  # type: ignore
            confidence=0.5,
            reasoning="test",
        )


@pytest.mark.asyncio
async def test_subagent_suspicious_fraud_ring_execution() -> None:
    """Verify subagent correctly detects fraud ring indicators and outputs suspicious finding."""
    mock_client = MagicMock()
    mock_graph = MagicMock()
    mock_client.select_graph.return_value = mock_graph

    # Mock tool query result: cust-000 shares bank account with cust-001
    mock_graph.query.return_value.header = [
        [1, b"shared_cid"],
        [1, b"shared_label"],
        [1, b"attribute_type"],
        [1, b"attribute_cid"],
        [1, b"rel_out"],
        [1, b"rel_in"],
    ]
    mock_graph.query.return_value.result_set = [
        ["cust-001", "Customer", "BankAccount", "ba-ring-01", "HAS_ACCOUNT", "HAS_ACCOUNT"],
    ]

    store = GraphStore(client=mock_client)
    server = create_agent_mcp_server(
        agent_id="agent-ring",
        tool_names=["shared_attribute_links"],
        graph_store=store,
        agent_graph_name="agent_slice_ring",
    )
    mcp_client = AgentMCPClient(server, allowed_tool_names=["shared_attribute_links"])
    mock_llm = MockLLMClient()  # Falls back to heuristic evaluator

    config = SubAgentRunConfig(
        agent_id="agent-ring",
        skill_id="entity-linker",
        prompt_fragment="Detect shared attribute linkages.",
        target_cids=["cust-000"],
        private_graph_name="agent_slice_ring",
    )

    subagent = SubAgent(config=config, mcp_client=mcp_client, llm_client=mock_llm)
    findings = await subagent.run()

    assert len(findings) == 1
    f = findings[0]
    assert f.target_cid == "cust-000"
    assert f.verdict == "suspicious"
    assert f.confidence >= 0.90
    assert "cust-001" in f.evidence_cids
    assert "ba-ring-01" in f.evidence_cids


@pytest.mark.asyncio
async def test_subagent_benign_decoy_execution() -> None:
    """Verify subagent correctly identifies benign entity with no shared high-risk attributes."""
    mock_client = MagicMock()
    mock_graph = MagicMock()
    mock_client.select_graph.return_value = mock_graph

    # Mock tool query result: empty (no shared attributes)
    mock_graph.query.return_value.header = []
    mock_graph.query.return_value.result_set = []

    store = GraphStore(client=mock_client)
    server = create_agent_mcp_server(
        agent_id="agent-decoy",
        tool_names=["shared_attribute_links"],
        graph_store=store,
        agent_graph_name="agent_slice_decoy",
    )
    mcp_client = AgentMCPClient(server, allowed_tool_names=["shared_attribute_links"])
    mock_llm = MockLLMClient()

    config = SubAgentRunConfig(
        agent_id="agent-decoy",
        skill_id="entity-linker",
        prompt_fragment="Detect shared attribute linkages.",
        target_cids=["cust-010"],
        private_graph_name="agent_slice_decoy",
    )

    subagent = SubAgent(config=config, mcp_client=mcp_client, llm_client=mock_llm)
    findings = await subagent.run()

    assert len(findings) == 1
    f = findings[0]
    assert f.target_cid == "cust-010"
    assert f.verdict == "benign"
    assert f.confidence >= 0.80


@pytest.mark.asyncio
async def test_subagent_llm_structured_response() -> None:
    """Verify that structured LLM output is honored when provided."""
    mock_client = MagicMock()
    mock_graph = MagicMock()
    mock_client.select_graph.return_value = mock_graph
    mock_graph.query.return_value.result_set = []

    store = GraphStore(client=mock_client)
    server = create_agent_mcp_server(
        agent_id="agent-llm",
        tool_names=["shared_attribute_links"],
        graph_store=store,
        agent_graph_name="agent_slice_llm",
    )
    mcp_client = AgentMCPClient(server, allowed_tool_names=["shared_attribute_links"])

    mock_llm = MockLLMClient()
    mock_llm.register_response(
        pattern="cust-099",
        response={
            "verdict": "suspicious",
            "confidence": 0.99,
            "reasoning": "LLM verified synthetic identity collision.",
            "evidence_cids": ["cust-099", "ba-fake-1"],
        },
    )

    config = SubAgentRunConfig(
        agent_id="agent-llm",
        skill_id="entity-linker",
        prompt_fragment="Analyze identity collisions.",
        target_cids=["cust-099"],
        private_graph_name="agent_slice_llm",
    )

    subagent = SubAgent(config=config, mcp_client=mcp_client, llm_client=mock_llm)
    findings = await subagent.run()

    assert len(findings) == 1
    f = findings[0]
    assert f.verdict == "suspicious"
    assert f.confidence == 0.99
    assert "LLM verified" in f.reasoning
    assert "ba-fake-1" in f.evidence_cids
