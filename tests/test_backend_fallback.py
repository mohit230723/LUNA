"""Unit and integration tests for finding backend tracking, visible fallback, and strict LLM mode."""

import pytest
from luna.agents.models import Finding, SubAgentRunConfig
from luna.agents.subagent import SubAgent
from luna.agents.exceptions import LLMUnavailableError
from luna.llm.client import LLMClient, MockLLMClient
from luna.mcp.client import AgentMCPClient
from luna.mcp.server import create_agent_mcp_server
from luna.orchestrator.promote import promote_findings


class FakeRealLLMClient(LLMClient):
    """Simulates a real LLM that is not MockLLMClient."""
    def complete(self, prompt: str, system: str | None = None, json_schema: dict | None = None) -> dict:
        return {
            "verdict": "suspicious",
            "confidence": 0.93,
            "reasoning": "Real LLM identified fraud ring pattern",
            "evidence_cids": ["ba-ring-01"],
        }


class BrokenLLMClient(LLMClient):
    """Simulates an LLM that raises an error."""
    def complete(self, prompt: str, system: str | None = None, json_schema: dict | None = None) -> dict:
        raise RuntimeError("LLM service unavailable connection refused")


class MalformedLLMClient(LLMClient):
    """Simulates an LLM that returns non-JSON or invalid schema."""
    def complete(self, prompt: str, system: str | None = None, json_schema: dict | None = None) -> dict:
        return {"random_key": "not a verdict"}


@pytest.mark.asyncio
async def test_llm_path_sets_backend_llm(tmp_graph, live_store):
    server = create_agent_mcp_server("agent_01", ["shared_attribute_links"], live_store, tmp_graph)
    mcp = AgentMCPClient(server, allowed_tool_names=["shared_attribute_links"])

    # 1. Non-mock LLM -> backend="llm"
    subagent_real = SubAgent(
        config=SubAgentRunConfig(
            agent_id="agent_01",
            skill_id="entity-linker",
            prompt_fragment="Instructions",
            target_cids=["cust_01"],
            private_graph_name=tmp_graph,
        ),
        mcp_client=mcp,
        llm_client=FakeRealLLMClient(),
    )
    findings_real = await subagent_real.run()
    assert len(findings_real) == 1
    assert findings_real[0].backend == "llm"
    assert findings_real[0].fallback_reason is None

    # 2. MockLLMClient -> backend="scripted"
    mock_llm = MockLLMClient()
    mock_llm.register_response(".*", {"verdict": "benign", "confidence": 0.8, "reasoning": "Mocked", "evidence_cids": []})
    subagent_mock = SubAgent(
        config=SubAgentRunConfig(
            agent_id="agent_01",
            skill_id="entity-linker",
            prompt_fragment="Instructions",
            target_cids=["cust_01"],
            private_graph_name=tmp_graph,
        ),
        mcp_client=mcp,
        llm_client=mock_llm,
    )
    findings_mock = await subagent_mock.run()
    assert len(findings_mock) == 1
    assert findings_mock[0].backend == "scripted"
    assert findings_mock[0].fallback_reason is None


@pytest.mark.asyncio
async def test_fallback_sets_backend_rules_with_reason(tmp_graph, live_store, caplog):
    server = create_agent_mcp_server("agent_01", ["shared_attribute_links"], live_store, tmp_graph)
    mcp = AgentMCPClient(server, allowed_tool_names=["shared_attribute_links"])

    # Broken LLM -> fallback to rules with reason="llm_error"
    subagent = SubAgent(
        config=SubAgentRunConfig(
            agent_id="agent_01",
            skill_id="entity-linker",
            prompt_fragment="Instructions",
            target_cids=["cust_01"],
            private_graph_name=tmp_graph,
        ),
        mcp_client=mcp,
        llm_client=BrokenLLMClient(),
    )

    with caplog.at_level("WARNING"):
        findings = await subagent.run()

    assert len(findings) == 1
    assert findings[0].backend == "rules"
    assert findings[0].fallback_reason == "llm_error"
    assert "falling back to deterministic rules" in caplog.text

    # Malformed LLM -> fallback to rules with reason="invalid_json"
    subagent_malformed = SubAgent(
        config=SubAgentRunConfig(
            agent_id="agent_01",
            skill_id="entity-linker",
            prompt_fragment="Instructions",
            target_cids=["cust_01"],
            private_graph_name=tmp_graph,
        ),
        mcp_client=mcp,
        llm_client=MalformedLLMClient(),
    )
    findings_mal = await subagent_malformed.run()
    assert len(findings_mal) == 1
    assert findings_mal[0].backend == "rules"
    assert findings_mal[0].fallback_reason == "invalid_json"


@pytest.mark.asyncio
async def test_strict_mode_raises_instead_of_falling_back(tmp_graph, live_store, monkeypatch):
    server = create_agent_mcp_server("agent_01", ["shared_attribute_links"], live_store, tmp_graph)
    mcp = AgentMCPClient(server, allowed_tool_names=["shared_attribute_links"])

    # 1. Via constructor argument strict_llm=True
    subagent_strict = SubAgent(
        config=SubAgentRunConfig(
            agent_id="agent_strict",
            skill_id="entity-linker",
            prompt_fragment="Instructions",
            target_cids=["cust_01"],
            private_graph_name=tmp_graph,
        ),
        mcp_client=mcp,
        llm_client=BrokenLLMClient(),
        strict_llm=True,
    )
    with pytest.raises(LLMUnavailableError):
        await subagent_strict.run()

    # 2. Via environment variable LUNA_STRICT_LLM=1
    monkeypatch.setenv("LUNA_STRICT_LLM", "1")
    subagent_env = SubAgent(
        config=SubAgentRunConfig(
            agent_id="agent_env",
            skill_id="entity-linker",
            prompt_fragment="Instructions",
            target_cids=["cust_01"],
            private_graph_name=tmp_graph,
        ),
        mcp_client=mcp,
        llm_client=BrokenLLMClient(),
    )
    with pytest.raises(LLMUnavailableError):
        await subagent_env.run()


@pytest.mark.integration
def test_backend_persisted_on_promoted_finding(live_store, tmp_graph):
    """Verify backend and fallback_reason are persisted on promoted Finding nodes in live FalkorDB."""
    run_graph = f"{tmp_graph}_run"
    try:
        live_store.query(tmp_graph, "CREATE (c:Customer {cid: 'cust_01'})")

        finding = Finding(
            agent_id="agent_test",
            skill_id="entity-linker",
            target_cid="cust_01",
            verdict="suspicious",
            confidence=0.88,
            reasoning="Testing backend persistence",
            evidence_cids=["cust_01"],
            backend="rules",
            fallback_reason="llm_error",
        )

        res = promote_findings(
            store=live_store,
            agent_graph_name=tmp_graph,
            run_graph_name=run_graph,
            findings=[finding],
        )

        assert res.total_promoted == 1

        rows = live_store.query(
            run_graph,
            "MATCH (f:Finding {id: $id}) RETURN f.backend AS backend, f.fallback_reason AS fallback_reason",
            {"id": finding.id},
        )
        assert len(rows) == 1
        assert rows[0]["backend"] == "rules"
        assert rows[0]["fallback_reason"] == "llm_error"
    finally:
        live_store.delete_graph(run_graph)
