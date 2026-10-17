"""Cross-run learning engine updating atlas skill reputation scores via Exponential Moving Average."""

from datetime import datetime, timezone
from typing import Any, Optional

from luna.graph.store import GraphStore
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_SKILL,
    LABEL_TASK_TYPE,
    LABEL_FINDING,
    LABEL_CUSTOMER,
    LABEL_OUTCOME,
    LABEL_ACTION,
    REL_SUCCEEDED_ON,
    REL_ASSESSES,
    REL_RESULTED_IN,
)
from luna.domain.seed import GroundTruth


def update_skill_score(
    store: GraphStore,
    skill_id: str,
    task_type: str = "fraud_ring_investigation",
    reward: float = 1.0,
    alpha: float = 0.2,
    atlas_graph: str = GRAPH_ATLAS,
) -> dict[str, Any]:
    """Update a skill's SUCCEEDED_ON edge score using Exponential Moving Average.

    Formula: S_new = (1.0 - alpha) * S_old + alpha * reward
    where alpha is the learning rate (default 0.2). Missing relations merge at 0.5.

    Args:
        store: GraphStore connection
        skill_id: Target Skill identifier
        task_type: Target TaskType name
        reward: Outcome reward (1.0 for positive success, 0.0 for failure/penalty)
        alpha: Exponential moving average learning rate
        atlas_graph: Name of atlas catalog graph

    Returns:
        Dictionary with updated skill_id, task_type, new_score, runs, and last_updated.
    """
    now = datetime.now(timezone.utc).isoformat()

    # 1. Check if relationship exists
    check_query = (
        f"MATCH (s:{LABEL_SKILL} {{id: $skill_id}})-[r:{REL_SUCCEEDED_ON}]->(t:{LABEL_TASK_TYPE} {{name: $task_type}}) "
        "RETURN r.score AS score, r.runs AS runs"
    )
    existing = store.query(atlas_graph, check_query, {"skill_id": skill_id, "task_type": task_type})

    if existing and existing[0].get("score") is not None:
        old_score = float(existing[0]["score"])
        old_runs = int(existing[0].get("runs", 0))
        new_score = (1.0 - alpha) * old_score + (alpha * reward)
        new_runs = old_runs + 1

        update_query = (
            f"MATCH (s:{LABEL_SKILL} {{id: $skill_id}})-[r:{REL_SUCCEEDED_ON}]->(t:{LABEL_TASK_TYPE} {{name: $task_type}}) "
            "SET r.score = $new_score, r.runs = $new_runs, r.last_updated = $timestamp "
            "RETURN s.id AS skill_id, t.name AS task_type, r.score AS new_score, r.runs AS runs, r.last_updated AS last_updated"
        )
        res = store.query(
            atlas_graph,
            update_query,
            {
                "skill_id": skill_id,
                "task_type": task_type,
                "new_score": new_score,
                "new_runs": new_runs,
                "timestamp": now,
            },
        )
    else:
        # H6: MERGE a missing SUCCEEDED_ON at 0.5 baseline prior
        default_prior = 0.50
        new_score = (1.0 - alpha) * default_prior + (alpha * reward)
        new_runs = 1
        create_query = (
            f"MERGE (s:{LABEL_SKILL} {{id: $skill_id}}) "
            f"MERGE (t:{LABEL_TASK_TYPE} {{name: $task_type}}) "
            f"MERGE (s)-[r:{REL_SUCCEEDED_ON}]->(t) "
            "ON CREATE SET r.score = $new_score, r.runs = $new_runs, r.last_updated = $timestamp "
            "ON MATCH SET r.score = $new_score, r.runs = $new_runs, r.last_updated = $timestamp "
            "RETURN s.id AS skill_id, t.name AS task_type, r.score AS new_score, r.runs AS runs, r.last_updated AS last_updated"
        )
        res = store.query(
            atlas_graph,
            create_query,
            {
                "skill_id": skill_id,
                "task_type": task_type,
                "new_score": new_score,
                "new_runs": new_runs,
                "timestamp": now,
            },
        )

    return {
        "skill_id": skill_id,
        "task_type": task_type,
        "new_score": float(res[0]["new_score"]),
        "runs": int(res[0]["runs"]),
        "last_updated": res[0]["last_updated"],
    }


def learn_from_run(
    store: GraphStore,
    run_graph_name: str,
    ground_truth: GroundTruth,
    atlas_graph: str = GRAPH_ATLAS,
    alpha: float = 0.2,
    task_type: str = "fraud_ring_investigation",
) -> list[dict[str, Any]]:
    """Inspect all findings in run memory, compute rewards against ground truth, and update atlas skill scores.

    H6 Learner:
    - Learn only for an EXECUTED Outcome with learned=false; set learned=true afterwards (no-op if already true).
    - Grade EVERY finding (active or superseded, contested or not) against truth:
      suspicious on ring=1, benign on ring=0, benign on non-ring=1, suspicious on non-ring=0.
    - One EMA update per skill per run using the mean reward (alpha=0.2); MERGE a missing SUCCEEDED_ON at 0.5.

    Args:
        store: GraphStore connection
        run_graph_name: Target run memory graph
        ground_truth: GroundTruth dataset annotations
        atlas_graph: Name of atlas catalog graph
        alpha: Exponential moving average learning rate
        task_type: Target task type name

    Returns:
        List of updated skill score dictionaries.
    """
    # 1. Gate: Learn only for an EXECUTED Outcome with learned=false
    outcome_query = (
        f"MATCH (o:{LABEL_OUTCOME}) "
        f"OPTIONAL MATCH (a:{LABEL_ACTION})-[:{REL_RESULTED_IN}]->(o) "
        "RETURN o.id AS id, o.learned AS learned, a.status AS act_status"
    )
    outcome_rows = store.query(run_graph_name, outcome_query)
    if not outcome_rows:
        return []

    unlearned_outcomes = [
        o for o in outcome_rows
        if (o.get("learned") is not True) and (o.get("act_status") in ("EXECUTED", None))
    ]
    if not unlearned_outcomes:
        # Already learned or no executed outcome -> idempotent no-op
        return []

    ring_cids = set(ground_truth.ring_cids)

    # 2. Grade EVERY finding (active or superseded, contested or not)
    findings_query = (
        f"MATCH (f:{LABEL_FINDING}) "
        f"OPTIONAL MATCH (f)-[:{REL_ASSESSES}]->(c:{LABEL_CUSTOMER}) "
        "RETURN f.id AS finding_id, f.skill_id AS skill_id, f.verdict AS verdict, "
        "       f.status AS status, coalesce(f.target_cid, c.cid) AS target_cid"
    )
    findings = store.query(run_graph_name, findings_query)

    skill_rewards: dict[str, list[float]] = {}

    for f in findings:
        skill_id = f.get("skill_id")
        if not skill_id:
            continue

        verdict = (f.get("verdict") or "").lower()
        target_cid = f.get("target_cid")
        is_ring = target_cid in ring_cids

        # H6 grading rules:
        # suspicious on ring = 1
        # benign on ring = 0
        # benign on non-ring = 1
        # suspicious on non-ring = 0
        if is_ring:
            if verdict == "suspicious":
                reward = 1.0
            elif verdict == "benign":
                reward = 0.0
            else:
                reward = 0.5
        else:
            if verdict == "benign":
                reward = 1.0
            elif verdict == "suspicious":
                reward = 0.0
            else:
                reward = 0.5

        skill_rewards.setdefault(skill_id, []).append(reward)

    # 3. Apply one EMA update per skill per run using mean reward
    updates = []
    for skill_id, rewards in skill_rewards.items():
        mean_reward = sum(rewards) / len(rewards)
        upd = update_skill_score(
            store=store,
            skill_id=skill_id,
            task_type=task_type,
            reward=mean_reward,
            alpha=alpha,
            atlas_graph=atlas_graph,
        )
        updates.append(upd)

    # 4. Set learned = true on all processed Outcome nodes
    for o in unlearned_outcomes:
        store.query(
            run_graph_name,
            f"MATCH (o:{LABEL_OUTCOME} {{id: $oid}}) SET o.learned = true",
            {"oid": o["id"]},
        )

    return updates
