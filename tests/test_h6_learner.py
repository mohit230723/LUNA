"""Tests for H6: Learner gating on EXECUTED Outcome, full finding grading, and 0.5 prior."""

import pytest
from luna.atlas.learner import learn_from_run, update_skill_score
from luna.domain.seed import GroundTruth


@pytest.mark.integration
def test_learner_grades_all_findings_active_and_superseded(live_store, tmp_graph: str) -> None:
    """Verify that learner grades EVERY finding (active or superseded):
    suspicious on ring=1, benign on ring=0, benign on non-ring=1, suspicious on non-ring=0.
    """
    run_graph = f"{tmp_graph}_run"
    atlas_graph = f"{tmp_graph}_atlas"

    gt = GroundTruth(
        ring_cids={"cust-ring"},
        decoy_cids={"cust-decoy"},
    )

    try:
        # Seed atlas with 0.5 baseline for skill-win and skill-lose
        live_store.query(
            atlas_graph,
            "CREATE (s1:Skill {id: 'skill-win'}) "
            "CREATE (s2:Skill {id: 'skill-lose'}) "
            "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
            "CREATE (s1)-[:SUCCEEDED_ON {score: 0.5, runs: 0}]->(t) "
            "CREATE (s2)-[:SUCCEEDED_ON {score: 0.5, runs: 0}]->(t)",
        )

        # Setup run memory:
        # 1. EXECUTED Action + Outcome with learned=false
        # 2. Ring customer has:
        #    - skill-win: suspicious (reward=1)
        #    - skill-lose: benign superseded (reward=0)
        # 3. Decoy customer has:
        #    - skill-win: benign (reward=1)
        #    - skill-lose: suspicious superseded (reward=0)
        live_store.query(
            run_graph,
            "CREATE (a:Action {id: 'act-1', status: 'EXECUTED'}) "
            "CREATE (o:Outcome {id: 'out-1', action_id: 'act-1', success: true, learned: false}) "
            "CREATE (a)-[:RESULTED_IN]->(o) "
            "CREATE (cr:Customer {cid: 'cust-ring'}) "
            "CREATE (cd:Customer {cid: 'cust-decoy'}) "
            "CREATE (f1:Finding {id: 'f1', target_cid: 'cust-ring', skill_id: 'skill-win', verdict: 'suspicious', status: 'active'}) "
            "CREATE (f2:Finding {id: 'f2', target_cid: 'cust-ring', skill_id: 'skill-lose', verdict: 'benign', status: 'superseded'}) "
            "CREATE (f3:Finding {id: 'f3', target_cid: 'cust-decoy', skill_id: 'skill-win', verdict: 'benign', status: 'active'}) "
            "CREATE (f4:Finding {id: 'f4', target_cid: 'cust-decoy', skill_id: 'skill-lose', verdict: 'suspicious', status: 'superseded'}) "
            "CREATE (f1)-[:ASSESSES]->(cr) "
            "CREATE (f2)-[:ASSESSES]->(cr) "
            "CREATE (f3)-[:ASSESSES]->(cd) "
            "CREATE (f4)-[:ASSESSES]->(cd)",
        )

        # Run learner
        updates = learn_from_run(
            live_store,
            run_graph_name=run_graph,
            ground_truth=gt,
            atlas_graph=atlas_graph,
            alpha=0.2,
        )

        assert len(updates) == 2
        upd_map = {u["skill_id"]: u for u in updates}

        # skill-win: 2 correct findings -> mean reward = 1.0 -> new score = 0.8*0.5 + 0.2*1.0 = 0.60
        assert round(upd_map["skill-win"]["new_score"], 2) == 0.60

        # skill-lose: 2 wrong findings -> mean reward = 0.0 -> new score = 0.8*0.5 + 0.2*0.0 = 0.40
        assert round(upd_map["skill-lose"]["new_score"], 2) == 0.40

        # Verify Outcome node learned flag was set to true
        out_nodes = live_store.query(run_graph, "MATCH (o:Outcome {id: 'out-1'}) RETURN o.learned AS learned")
        assert len(out_nodes) == 1
        assert out_nodes[0]["learned"] is True

    finally:
        live_store.delete_graph(run_graph)
        live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_learner_idempotent_no_op_on_second_call(live_store, tmp_graph: str) -> None:
    """Verify that calling learn_from_run twice is a no-op on the second call when learned=true."""
    run_graph = f"{tmp_graph}_run"
    atlas_graph = f"{tmp_graph}_atlas"

    gt = GroundTruth(ring_cids={"cust-ring"})

    try:
        live_store.query(
            atlas_graph,
            "CREATE (s:Skill {id: 'skill-idem'}) "
            "CREATE (t:TaskType {name: 'fraud_ring_investigation'}) "
            "CREATE (s)-[:SUCCEEDED_ON {score: 0.5, runs: 0}]->(t)",
        )
        live_store.query(
            run_graph,
            "CREATE (a:Action {id: 'act-1', status: 'EXECUTED'}) "
            "CREATE (o:Outcome {id: 'out-1', action_id: 'act-1', success: true, learned: false}) "
            "CREATE (a)-[:RESULTED_IN]->(o) "
            "CREATE (c:Customer {cid: 'cust-ring'}) "
            "CREATE (f:Finding {id: 'f1', target_cid: 'cust-ring', skill_id: 'skill-idem', verdict: 'suspicious'}) "
            "CREATE (f)-[:ASSESSES]->(c)",
        )

        # First call updates atlas
        first_updates = learn_from_run(live_store, run_graph, gt, atlas_graph=atlas_graph)
        assert len(first_updates) == 1

        # Check atlas runs count is 1
        rec1 = live_store.query(atlas_graph, "MATCH (:Skill {id: 'skill-idem'})-[r:SUCCEEDED_ON]->() RETURN r.runs AS runs")
        assert int(rec1[0]["runs"]) == 1

        # Second call MUST be a no-op
        second_updates = learn_from_run(live_store, run_graph, gt, atlas_graph=atlas_graph)
        assert second_updates == []

        # Atlas runs count unchanged
        rec2 = live_store.query(atlas_graph, "MATCH (:Skill {id: 'skill-idem'})-[r:SUCCEEDED_ON]->() RETURN r.runs AS runs")
        assert int(rec2[0]["runs"]) == 1

    finally:
        live_store.delete_graph(run_graph)
        live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_missing_skill_merged_at_prior_0_5(live_store, tmp_graph: str) -> None:
    """Verify that an unrecorded skill is merged into atlas with a baseline prior of 0.5."""
    atlas_graph = f"{tmp_graph}_atlas"

    try:
        res = update_skill_score(
            live_store,
            skill_id="brand-new-skill",
            task_type="fraud_ring_investigation",
            reward=1.0,
            alpha=0.2,
            atlas_graph=atlas_graph,
        )
        # Prior is 0.5: S_new = 0.8 * 0.5 + 0.2 * 1.0 = 0.60
        assert round(res["new_score"], 2) == 0.60
        assert res["runs"] == 1

        # Verify node and edge exist in atlas
        edges = live_store.query(
            atlas_graph,
            "MATCH (s:Skill {id: 'brand-new-skill'})-[r:SUCCEEDED_ON]->(t:TaskType {name: 'fraud_ring_investigation'}) "
            "RETURN r.score AS score",
        )
        assert len(edges) == 1
        assert round(float(edges[0]["score"]), 2) == 0.60

    finally:
        live_store.delete_graph(atlas_graph)
