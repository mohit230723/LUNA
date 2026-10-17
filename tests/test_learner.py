"""Tests for cross-run learner updating atlas SUCCEEDED_ON edge scores (Plan 3.4)."""

import pytest
from luna.atlas.learner import update_skill_score, learn_from_run
from luna.atlas.seed import seed_atlas
from luna.domain.seed import GroundTruth


@pytest.mark.integration
def test_update_skill_score_ema_calculation(live_store, tmp_graph: str) -> None:
    """Verify that update_skill_score applies EMA: S_new = (1 - alpha) * S_old + alpha * reward."""
    # Seed isolated atlas in tmp_graph
    live_store.query(
        tmp_graph,
        "CREATE (s:Skill {id: 'test-skill', name: 'Test Skill'}) "
        "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
        "CREATE (s)-[r:SUCCEEDED_ON {score: 0.70, runs: 5}]->(t)",
    )

    # Apply reward = 1.0 with alpha = 0.2
    # Expected: 0.70 * 0.80 + 1.0 * 0.20 = 0.56 + 0.20 = 0.76
    res = update_skill_score(
        live_store,
        skill_id="test-skill",
        task_type="fraud_ring_investigation",
        reward=1.0,
        alpha=0.2,
        atlas_graph=tmp_graph,
    )

    assert res["skill_id"] == "test-skill"
    assert round(res["new_score"], 4) == 0.7600
    assert res["runs"] == 6
    assert res["last_updated"] is not None

    # Check database
    edge = live_store.query(
        tmp_graph,
        "MATCH (s:Skill {id: 'test-skill'})-[r:SUCCEEDED_ON]->(t:TaskType {name: 'fraud_ring_investigation'}) "
        "RETURN r.score AS score, r.runs AS runs",
    )
    assert round(edge[0]["score"], 4) == 0.7600
    assert edge[0]["runs"] == 6


@pytest.mark.integration
def test_update_skill_score_penalization(live_store, tmp_graph: str) -> None:
    """Verify that a 0.0 reward decreases the skill score according to EMA."""
    live_store.query(
        tmp_graph,
        "CREATE (s:Skill {id: 'penalized-skill'}) "
        "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
        "CREATE (s)-[r:SUCCEEDED_ON {score: 0.80, runs: 10}]->(t)",
    )

    # 0.80 * 0.80 + 0.0 * 0.20 = 0.64
    res = update_skill_score(
        live_store,
        skill_id="penalized-skill",
        task_type="fraud_ring_investigation",
        reward=0.0,
        alpha=0.2,
        atlas_graph=tmp_graph,
    )
    assert round(res["new_score"], 4) == 0.6400
    assert res["runs"] == 11


@pytest.mark.integration
def test_learn_from_run_updates_skills(live_store, tmp_graph: str) -> None:
    """Verify that learn_from_run inspects run graph decisions and rewards/penalizes skills accordingly."""
    atlas_graph = f"{tmp_graph}_atlas"
    run_graph = f"{tmp_graph}_run"

    try:
        # 1. Setup atlas with skills
        live_store.query(
            atlas_graph,
            "CREATE (s1:Skill {id: 'entity-linker'}) "
            "CREATE (s2:Skill {id: 'community-analyzer'}) "
            "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
            "CREATE (s1)-[:SUCCEEDED_ON {score: 0.70, runs: 1}]->(t) "
            "CREATE (s2)-[:SUCCEEDED_ON {score: 0.80, runs: 1}]->(t)",
        )

        # 2. Setup run graph with a true positive decision on ring member and executed outcome
        live_store.query(
            run_graph,
            "CREATE (c:Customer {cid: 'cust-ring-00'}) "
            "CREATE (f:Finding {id: 'f-ring', skill_id: 'entity-linker', verdict: 'suspicious'}) "
            "CREATE (d:Decision {id: 'd-ring', target_cid: 'cust-ring-00', chosen_verdict: 'suspicious'}) "
            "CREATE (o:Outcome {id: 'out-01', success: true, learned: false}) "
            "CREATE (f)-[:ASSESSES]->(c) "
            "CREATE (d)-[:UPHELD]->(f)",
        )

        gt = GroundTruth(
            ring_cids={"cust-ring-00"},
            decoy_cids={"cust-decoy-00"},
        )

        updates = learn_from_run(
            live_store,
            run_graph_name=run_graph,
            ground_truth=gt,
            atlas_graph=atlas_graph,
            alpha=0.2,
        )

        assert len(updates) >= 1
        # entity-linker score should increase: 0.70 * 0.8 + 1.0 * 0.2 = 0.76
        linker_update = [u for u in updates if u["skill_id"] == "entity-linker"][0]
        assert round(linker_update["new_score"], 4) == 0.7600

    finally:
        live_store.delete_graph(atlas_graph)
        live_store.delete_graph(run_graph)
