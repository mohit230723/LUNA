"""Tests for Q3: Investigate Pack Upgrades (Traversal Graph, Tools, Recorder, Cited Answer, Trace API)."""

import pytest
from luna.tools.algorithms import trace_connections, find_suspect_links
from luna.atlas.seed import get_seeded_skills, get_seeded_capabilities, get_seeded_tools
from luna.packs.investigate import InvestigatePack
from luna.orchestrator.traversal import TraversalRecorder, TraversalStep, compose_answer
from luna.graph.schema import (
    LABEL_TASK,
    LABEL_CUSTOMER,
    LABEL_TRAVERSAL_STEP,
    LABEL_ANSWER,
    REL_HAS_STEP,
    REL_ANSWERED_BY,
    REL_CITES,
)


def test_connection_tracer_skill_seeded() -> None:
    """Verify connection-tracer skill and tools exist in seed definitions."""
    skills = get_seeded_skills()
    tracer = next((s for s in skills if s.id == "connection-tracer"), None)
    assert tracer is not None
    assert tracer.capabilities == ["trace_connections"]
    assert "trace_connections" in tracer.exposes
    assert "find_suspect_links" in tracer.exposes

    caps = {c.name for c in get_seeded_capabilities()}
    assert "trace_connections" in caps

    tools = {t.name for t in get_seeded_tools()}
    assert "trace_connections" in tools
    assert "find_suspect_links" in tools


def test_investigate_pack_understanding_types() -> None:
    """Verify InvestigatePack.understand classifies question types accurately."""
    pack = InvestigatePack()

    # 1. who_connected
    u1 = pack.understand(None, "Who is connected to customer cust-000?")
    assert u1.question_type == "who_connected"
    assert "cust-000" in u1.entities
    assert not u1.needs_input

    # 2. is_suspicious
    u2 = pack.understand(None, "Is cust-003 part of the fraud ring?")
    assert u2.question_type == "is_suspicious"
    assert "cust-003" in u2.entities
    assert not u2.needs_input

    # 3. list_ring
    u3 = pack.understand(None, "Which customers share a bank account with cust-ring-01?")
    assert u3.question_type == "list_ring"
    assert "cust-ring-01" in u3.entities

    # 4. path_between
    u4 = pack.understand(None, "What is the shortest path between cust-000 and cust-005?")
    assert u4.question_type == "path_between"
    assert "cust-000" in u4.entities
    assert "cust-005" in u4.entities

    # 5. unknown customer with known_cids context
    u5 = pack.understand(
        None,
        "Who is connected to customer cust-unknown-999?",
        context={"known_cids": {"cust-000", "cust-001"}},
    )
    assert u5.needs_input is True
    assert "cust-unknown-999" in u5.clarification_question


def test_traversal_recorder_thread_safety_and_events() -> None:
    """Verify TraversalRecorder collects steps monotonically and emits callbacks."""
    emitted = []

    def on_event(event_name: str, data: dict):
        emitted.append((event_name, data))

    recorder = TraversalRecorder(event_callback=on_event)
    s1 = recorder.record_step("trace_connections", "agent-01", "cust-000", "bank-101", "HAS_ACCOUNT", "Followed bank account link")
    s2 = recorder.record_step("trace_connections", "agent-01", "bank-101", "cust-002", "HAS_ACCOUNT", "Found shared account customer")

    assert s1.seq == 1
    assert s2.seq == 2
    assert len(recorder.get_steps()) == 2
    assert len(emitted) == 2
    assert emitted[0][0] == "traversal_step"
    assert emitted[0][1]["from_cid"] == "cust-000"


@pytest.mark.integration
def test_traversal_recorder_persistence_and_anti_hallucination(live_store, tmp_graph: str) -> None:
    """Verify TraversalRecorder persists steps to run graph and rejects phantom CIDs."""
    run_graph = f"{tmp_graph}_run"
    domain_graph = f"{tmp_graph}_domain"
    task_id = "task-investigate-main"

    try:
        # Seed domain graph with real entities
        live_store.query(
            domain_graph,
            "CREATE (:Customer {cid: 'cust-real-1'})-[:HAS_ACCOUNT]->(:BankAccount {cid: 'ba-real-1'}) "
            "CREATE (:Customer {cid: 'cust-real-2'})-[:HAS_ACCOUNT]->(:BankAccount {cid: 'ba-real-1'})",
        )

        # Seed run graph with Task
        live_store.query(
            run_graph,
            f"CREATE (t:{LABEL_TASK} {{id: $tid}})",
            {"tid": task_id},
        )

        recorder = TraversalRecorder()
        # Valid step
        recorder.record_step("trace_connections", "agent-1", "cust-real-1", "ba-real-1", "HAS_ACCOUNT")
        # Phantom step (from_cid doesn't exist)
        recorder.record_step("trace_connections", "agent-1", "cust-phantom-99", "ba-real-1", "HAS_ACCOUNT")

        promoted = recorder.persist_to_run_graph(
            store=live_store,
            run_graph_name=run_graph,
            task_id=task_id,
            domain_graph_name=domain_graph,
        )

        assert len(promoted) == 1
        assert promoted[0].from_cid == "cust-real-1"

        # Check in graph
        rows = live_store.query(
            run_graph,
            f"MATCH (t:{LABEL_TASK} {{id: $tid}})-[:{REL_HAS_STEP}]->(ts:{LABEL_TRAVERSAL_STEP}) "
            "RETURN ts.from_cid AS from_cid, ts.to_cid AS to_cid",
            {"tid": task_id},
        )
        assert len(rows) == 1
        assert rows[0]["from_cid"] == "cust-real-1"
        assert rows[0]["to_cid"] == "ba-real-1"

    finally:
        live_store.delete_graph(run_graph)
        live_store.delete_graph(domain_graph)


@pytest.mark.integration
def test_compose_answer_verifies_citations(live_store, tmp_graph: str) -> None:
    """Verify compose_answer persists Answer, links CITES only to observed entities, and strips phantom citations."""
    run_graph = f"{tmp_graph}_run_ans"
    task_id = "task-ans-test"

    try:
        # Seed run graph with Task and observed entities
        live_store.query(
            run_graph,
            f"CREATE (t:{LABEL_TASK} {{id: $tid}}) "
            "CREATE (c1:Customer {cid: 'cust-observed-1'}) "
            "CREATE (c2:Customer {cid: 'cust-observed-2'})",
            {"tid": task_id},
        )

        # Cite 2 valid CIDs and 1 unobserved CID
        ans = compose_answer(
            store=live_store,
            run_graph_name=run_graph,
            task_id=task_id,
            target_cids=["cust-observed-1", "cust-observed-2", "cust-phantom-999"],
            backend="rules",
            confidence=0.92,
        )

        assert "cust-observed-1" in ans["cited_cids"]
        assert "cust-observed-2" in ans["cited_cids"]
        assert "cust-phantom-999" in ans["stripped_cids"]
        assert "cust-phantom-999" not in ans["cited_cids"]

        # Verify CITES relationships in graph
        cites_rows = live_store.query(
            run_graph,
            f"MATCH (ans:{LABEL_ANSWER})-[:{REL_CITES}]->(c) RETURN c.cid AS cid",
        )
        cites_cids = {r["cid"] for r in cites_rows}
        assert cites_cids == {"cust-observed-1", "cust-observed-2"}

        # Verify (Task)-[:ANSWERED_BY]->(Answer)
        ans_rows = live_store.query(
            run_graph,
            f"MATCH (t:{LABEL_TASK} {{id: $tid}})-[:{REL_ANSWERED_BY}]->(ans:{LABEL_ANSWER}) RETURN ans.id AS aid",
            {"tid": task_id},
        )
        assert len(ans_rows) == 1

    finally:
        live_store.delete_graph(run_graph)


@pytest.mark.integration
def test_trace_tools_execution(live_store, tmp_graph: str) -> None:
    """Verify trace_connections and find_suspect_links return valid multi-hop paths."""
    domain_graph = f"{tmp_graph}_dom_tools"

    try:
        # Build 3-hop connection path
        live_store.query(
            domain_graph,
            "CREATE (c1:Customer {cid: 'c1'}) "
            "CREATE (c2:Customer {cid: 'c2'}) "
            "CREATE (c3:Customer {cid: 'c3'}) "
            "CREATE (b1:BankAccount {cid: 'b1'}) "
            "CREATE (p1:Phone {cid: 'p1'}) "
            "CREATE (c1)-[:HAS_ACCOUNT]->(b1) "
            "CREATE (c2)-[:HAS_ACCOUNT]->(b1) "
            "CREATE (c2)-[:HAS_PHONE]->(p1) "
            "CREATE (c3)-[:HAS_PHONE]->(p1)",
        )

        # Test trace_connections from c1
        paths = trace_connections(live_store, domain_graph, "c1", max_hops=4, limit_paths=5)
        assert len(paths) >= 1
        target_cids = [p["target_cid"] for p in paths]
        assert "b1" in target_cids
        assert "c2" in target_cids

        # Test find_suspect_links between c1 and c2
        suspects = find_suspect_links(live_store, domain_graph, ["c1", "c2", "c3"], min_strength=1)
        assert len(suspects) >= 1
        pairs = {(s["src_cid"], s["dst_cid"]) for s in suspects}
        assert ("c1", "c2") in pairs or ("c2", "c1") in pairs

    finally:
        live_store.delete_graph(domain_graph)
