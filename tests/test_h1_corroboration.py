"""Tests for H1: Corroboration rules for action targeting."""

import pytest
from luna.orchestrator.actions import (
    CORROBORATION_MIN_SKILLS,
    CORROBORATION_CONF,
    propose_actions,
)


@pytest.mark.integration
def test_lone_low_confidence_finding_not_targeted(live_store, tmp_graph: str) -> None:
    """Verify that a customer with a single finding at confidence 0.65 is NOT targeted."""
    run_graph = tmp_graph
    # Customer with lone finding at 0.65 from 1 skill
    live_store.query(
        run_graph,
        "CREATE (c:Customer {cid: 'cust-lone'}) "
        "CREATE (f:Finding {"
        "  id: 'find-lone', "
        "  target_cid: 'cust-lone', "
        "  skill_id: 'entity-linker', "
        "  verdict: 'suspicious', "
        "  confidence: 0.65"
        "}) "
        "CREATE (f)-[:ASSESSES]->(c)",
    )

    actions = propose_actions(live_store, run_graph)
    target_cids = []
    for a in actions:
        if hasattr(a, "target_cids") and a.target_cids:
            target_cids.extend(a.target_cids)
        elif getattr(a, "target_cid", None):
            target_cids.append(a.target_cid)

    assert "cust-lone" not in target_cids


@pytest.mark.integration
def test_distinct_skills_corroboration_targeted(live_store, tmp_graph: str) -> None:
    """Verify customer with findings from >= 2 distinct skills at 0.65 IS targeted."""
    run_graph = tmp_graph
    live_store.query(
        run_graph,
        "CREATE (c:Customer {cid: 'cust-multi-skill'}) "
        "CREATE (f1:Finding {"
        "  id: 'find-s1', "
        "  target_cid: 'cust-multi-skill', "
        "  skill_id: 'entity-linker', "
        "  verdict: 'suspicious', "
        "  confidence: 0.65"
        "}) "
        "CREATE (f2:Finding {"
        "  id: 'find-s2', "
        "  target_cid: 'cust-multi-skill', "
        "  skill_id: 'community-analyzer', "
        "  verdict: 'suspicious', "
        "  confidence: 0.65"
        "}) "
        "CREATE (f1)-[:ASSESSES]->(c) "
        "CREATE (f2)-[:ASSESSES]->(c)",
    )

    actions = propose_actions(live_store, run_graph)
    target_cids = []
    for a in actions:
        if hasattr(a, "target_cids") and a.target_cids:
            target_cids.extend(a.target_cids)
        elif getattr(a, "target_cid", None):
            target_cids.append(a.target_cid)

    assert "cust-multi-skill" in target_cids


@pytest.mark.integration
def test_high_confidence_lone_finding_targeted(live_store, tmp_graph: str) -> None:
    """Verify customer with best confidence >= CORROBORATION_CONF (0.8) IS targeted even from 1 skill."""
    run_graph = tmp_graph
    live_store.query(
        run_graph,
        "CREATE (c:Customer {cid: 'cust-high-conf'}) "
        "CREATE (f:Finding {"
        "  id: 'find-high', "
        "  target_cid: 'cust-high-conf', "
        "  skill_id: 'entity-linker', "
        "  verdict: 'suspicious', "
        "  confidence: 0.85"
        "}) "
        "CREATE (f)-[:ASSESSES]->(c)",
    )

    actions = propose_actions(live_store, run_graph)
    target_cids = []
    for a in actions:
        if hasattr(a, "target_cids") and a.target_cids:
            target_cids.extend(a.target_cids)
        elif getattr(a, "target_cid", None):
            target_cids.append(a.target_cid)

    assert "cust-high-conf" in target_cids


@pytest.mark.integration
def test_superseded_finding_does_not_corroborate(live_store, tmp_graph: str) -> None:
    """Verify that superseded findings do not count towards active corroboration."""
    run_graph = tmp_graph
    live_store.query(
        run_graph,
        "CREATE (c:Customer {cid: 'cust-with-superseded'}) "
        "CREATE (f1:Finding {"
        "  id: 'find-active', "
        "  target_cid: 'cust-with-superseded', "
        "  skill_id: 'entity-linker', "
        "  verdict: 'suspicious', "
        "  confidence: 0.65"
        "}) "
        "CREATE (f2:Finding {"
        "  id: 'find-old', "
        "  target_cid: 'cust-with-superseded', "
        "  skill_id: 'community-analyzer', "
        "  verdict: 'suspicious', "
        "  confidence: 0.65, "
        "  status: 'superseded'"
        "}) "
        "CREATE (f1)-[:ASSESSES]->(c) "
        "CREATE (f2)-[:ASSESSES]->(c)",
    )

    actions = propose_actions(live_store, run_graph)
    target_cids = []
    for a in actions:
        if hasattr(a, "target_cids") and a.target_cids:
            target_cids.extend(a.target_cids)
        elif getattr(a, "target_cid", None):
            target_cids.append(a.target_cid)

    assert "cust-with-superseded" not in target_cids
