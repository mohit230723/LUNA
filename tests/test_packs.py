"""Tests for Q1: Pack Protocol, PackRegistry, and Prompt Router."""

import pytest
from luna.packs.base import Pack, RoutingDecision, Understanding
from luna.packs.registry import PackRegistry, default_registry
from luna.packs.investigate import InvestigatePack
from luna.packs.router import (
    route_prompt,
    persist_routing_decision,
    ROUTE_MIN_CONF,
)
from luna.llm.client import MockLLMClient
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_PACK,
    LABEL_SKILL,
    LABEL_DECISION,
    LABEL_TASK,
    REL_IN_PACK,
    REL_FOR,
)


def test_pack_protocol_conformance() -> None:
    """Verify InvestigatePack conforms to Pack protocol."""
    pack = InvestigatePack()
    assert isinstance(pack, Pack)
    assert pack.name == "investigate"
    assert pack.title == "Investigate"
    assert len(pack.capabilities) >= 5
    assert len(pack.example_prompts) >= 1


def test_pack_registry_basic_operations() -> None:
    """Verify registration, lookup, list, and names on PackRegistry."""
    registry = PackRegistry()
    assert registry.list() == []
    assert registry.names() == []

    pack = InvestigatePack()
    registry.register(pack)
    assert registry.get("investigate") is pack
    assert registry.get("unknown") is None
    assert registry.names() == ["investigate"]
    assert len(registry.list()) == 1


def test_default_registry_includes_investigate() -> None:
    """Verify default_registry includes investigate pack."""
    reg = default_registry()
    assert reg.get("investigate") is not None
    assert "investigate" in reg.names()


def test_keyword_routing_investigate() -> None:
    """Verify keyword routing routes fraud queries to investigate pack."""
    registry = PackRegistry()
    registry.register(InvestigatePack())

    # Build dummy second pack so routing has multiple choices
    class DummyBuildPack:
        name = "build"
        title = "Build"
        description = "Build software"
        example_prompts = []
        capabilities = []
        def seed_atlas(self, store, atlas_graph): pass
        def seed_data(self, store, domain_graph): pass
        def understand(self, llm, prompt, context=None): return Understanding(question_type="software_build")
        def build_pipeline(self, store, config): pass

    registry.register(DummyBuildPack())

    decision = route_prompt(
        llm=None,
        prompt="Who is connected to the fraud involving customer cust-000?",
        registry=registry,
        backend="rules",
    )
    assert decision.pack == "investigate"
    assert decision.backend == "rules"
    assert decision.confidence >= ROUTE_MIN_CONF
    assert not decision.needs_input
    assert decision.clarification_question is None


def test_keyword_routing_build() -> None:
    """Verify keyword routing routes app generation queries to build pack."""
    registry = PackRegistry()
    registry.register(InvestigatePack())

    class DummyBuildPack:
        name = "build"
        title = "Build"
        description = "Build apps"
        example_prompts = []
        capabilities = []
        def seed_atlas(self, store, atlas_graph): pass
        def seed_data(self, store, domain_graph): pass
        def understand(self, llm, prompt, context=None): return Understanding(question_type="software_build")
        def build_pipeline(self, store, config): pass

    registry.register(DummyBuildPack())

    decision = route_prompt(
        llm=None,
        prompt="Build a fullstack todo app with React frontend, Express backend, and Postgres database",
        registry=registry,
        backend="rules",
    )
    assert decision.pack == "build"
    assert decision.confidence >= ROUTE_MIN_CONF
    assert not decision.needs_input


def test_keyword_routing_unmatched_returns_needs_input() -> None:
    """Verify prompt with no pack signals returns needs_input=True with clarifying question."""
    registry = PackRegistry()
    registry.register(InvestigatePack())

    decision = route_prompt(
        llm=None,
        prompt="What is the weather in Tokyo today?",
        registry=registry,
        backend="rules",
    )
    assert decision.pack is None
    assert decision.needs_input is True
    assert decision.confidence < ROUTE_MIN_CONF
    assert decision.clarification_question is not None
    assert "investigate" in decision.clarification_question


def test_llm_routing_fallback_to_rules() -> None:
    """Verify LLM failure or invalid response falls back gracefully to keyword rules."""
    registry = PackRegistry()
    registry.register(InvestigatePack())

    # MockLLM that returns invalid garbage
    mock_llm = MockLLMClient(default_response="Not a JSON at all! Just raw text.")

    decision = route_prompt(
        llm=mock_llm,
        prompt="Who is connected to the fraud involving customer cust-000?",
        registry=registry,
        backend="auto",
    )
    # Should fall back to rules and succeed
    assert decision.pack == "investigate"
    assert decision.backend == "rules"


def test_llm_routing_success() -> None:
    """Verify successful LLM routing with valid JSON schema response."""
    registry = PackRegistry()
    registry.register(InvestigatePack())

    canned_llm_response = {
        "pack": "investigate",
        "intent": "fraud_network_trace",
        "confidence": 0.95,
        "reasoning": "User asks about fraud ring and connected entities.",
    }
    mock_llm = MockLLMClient(default_response=canned_llm_response)

    decision = route_prompt(
        llm=mock_llm,
        prompt="Trace all accounts linked to cust-000",
        registry=registry,
        backend="auto",
    )
    assert decision.pack == "investigate"
    assert decision.backend == "llm"
    assert decision.confidence == 0.95
    assert not decision.needs_input


@pytest.mark.integration
def test_persist_routing_decision(live_store, tmp_graph: str) -> None:
    """Verify Decision(kind='routing') is persisted and linked to Task."""
    run_graph = f"{tmp_graph}_run"
    task_id = "task-main"

    try:
        # Create Task node
        live_store.query(
            run_graph,
            f"CREATE (t:{LABEL_TASK} {{id: $tid, description: 'Main user prompt'}})",
            {"tid": task_id},
        )

        decision = RoutingDecision(
            pack="investigate",
            intent="fraud_investigation",
            confidence=0.88,
            reasoning="Matched fraud and cust keywords",
            backend="rules",
            needs_input=False,
        )

        dec_id = persist_routing_decision(live_store, run_graph, decision, task_id)
        assert dec_id.startswith("dec-route-")

        # Verify in graph
        rows = live_store.query(
            run_graph,
            f"MATCH (d:{LABEL_DECISION} {{kind: 'routing'}})-[:{REL_FOR}]->(t:{LABEL_TASK} {{id: $tid}}) "
            "RETURN d.pack AS pack, d.confidence AS conf, d.backend AS backend, d.needs_input AS needs_input",
            {"tid": task_id},
        )
        assert len(rows) == 1
        assert rows[0]["pack"] == "investigate"
        assert rows[0]["backend"] == "rules"
        assert rows[0]["needs_input"] is False

    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_seed_all_atlas_persists_pack_nodes_and_edges(live_store, tmp_graph: str) -> None:
    """Verify PackRegistry.seed_all_atlas creates Pack nodes and IN_PACK edges."""
    atlas_graph = f"{tmp_graph}_atlas"

    try:
        registry = PackRegistry()
        registry.register(InvestigatePack())

        registry.seed_all_atlas(live_store, atlas_graph)

        # Check Pack node
        packs = live_store.query(
            atlas_graph,
            f"MATCH (p:{LABEL_PACK} {{name: 'investigate'}}) RETURN p.title AS title",
        )
        assert len(packs) == 1
        assert packs[0]["title"] == "Investigate"

        # Check Skill-[:IN_PACK]->Pack edges
        in_pack_skills = live_store.query(
            atlas_graph,
            f"MATCH (s:{LABEL_SKILL})-[:{REL_IN_PACK}]->(p:{LABEL_PACK} {{name: 'investigate'}}) "
            "RETURN s.id AS skill_id",
        )
        assert len(in_pack_skills) >= 1

    finally:
        live_store.delete_graph(atlas_graph)
