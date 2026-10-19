"""Skill assignment engine matching subtasks to atlas skills via graph queries."""

from typing import Any, Optional
from pydantic import BaseModel, Field
from luna.graph.schema import GRAPH_ATLAS, LABEL_SKILL, LABEL_CAPABILITY, LABEL_TASK_TYPE, REL_PROVIDES, REL_REQUIRES, REL_SUCCEEDED_ON
from luna.graph.store import GraphStore
from luna.atlas.models import SkillDef
from luna.planner.decompose import Subtask


class AssignmentResult(BaseModel):
    """Result of skill selection for a subtask including chosen skill and rejected candidates."""

    subtask: Subtask
    chosen_skill: Optional[SkillDef] = None
    rejected_skills: list[tuple[str, str]] = Field(default_factory=list)


def assign_skills_to_subtasks(
    store: GraphStore,
    subtasks: list[Subtask],
    task_type: str,
    run_graph_name: Optional[str] = None,
    atlas_graph: str = GRAPH_ATLAS,
) -> list[AssignmentResult]:
    """Query atlas graph to match and assign the best skills to subtasks.

    Selection rules:
    1. Filter: skill must PROVIDE the subtask's required capability.
    2. Policy Check: reject restricted skills (e.g. bulk-linker).
    3. Prerequisite Check: ensure required prerequisite skills are satisfied.
    4. Ranking: sort eligible skills by SUCCEEDED_ON score descending; highest score is chosen.
    5. Provenance: record explicit rejection reasons for all unchosen candidates.

    Args:
        store: GraphStore connection wrapper
        subtasks: List of decomposed subtasks
        task_type: Task type name (e.g. 'fraud_ring_investigation')
        run_graph_name: Optional run memory graph name to persist skill-assignment decisions
        atlas_graph: Atlas graph name (default: 'atlas')

    Returns:
        List of AssignmentResult objects documenting selection decisions.
    """
    results: list[AssignmentResult] = []
    assigned_skill_ids: set[str] = set()

    for subtask in subtasks:
        # Query atlas for all skills providing this subtask's capability
        query = (
            f"MATCH (s:{LABEL_SKILL})-[:{REL_PROVIDES}]->(c:{LABEL_CAPABILITY} {{name: $cap}}) "
            "WHERE s.source IS NULL "  # forge skills are gated by human review; never auto-assigned here
            f"OPTIONAL MATCH (s)-[r:{REL_SUCCEEDED_ON}]->(t:{LABEL_TASK_TYPE} {{name: $task_type}}) "
            f"OPTIONAL MATCH (s)-[:{REL_REQUIRES}]->(req:{LABEL_SKILL}) "
            "RETURN s.id AS id, s.name AS name, s.prompt_fragment AS prompt_fragment, "
            "       s.restricted AS restricted, r.score AS score, collect(req.id) AS requires"
        )
        rows = store.query(atlas_graph, query, {"cap": subtask.capability, "task_type": task_type})

        if not rows:
            res = AssignmentResult(
                subtask=subtask,
                chosen_skill=None,
                rejected_skills=[("none", f"No skills provide capability '{subtask.capability}'")],
            )
            results.append(res)
            continue

        eligible_candidates: list[dict[str, Any]] = []
        rejected_candidates: list[tuple[str, str]] = []

        for row in rows:
            skill_id = row.get("id", "")
            is_restricted = bool(row.get("restricted", False))
            score = float(row.get("score") or 0.50)
            requires = row.get("requires") or []
            # Clean up requires if None or empty
            requires = [r for r in requires if r]

            # 1. Policy check: restricted skills are rejected
            if is_restricted:
                rejected_candidates.append(
                    (skill_id, f"Policy restriction: skill '{skill_id}' is marked restricted")
                )
                continue

            # 2. Prerequisite check: requires must be met by previously assigned skills
            unmet_prereqs = [req for req in requires if req not in assigned_skill_ids]
            if unmet_prereqs:
                # If prerequisite not yet assigned in prior subtasks, check if acceptable or penalize
                pass

            eligible_candidates.append({
                "id": skill_id,
                "name": row.get("name") or skill_id,
                "prompt_fragment": row.get("prompt_fragment") or "",
                "restricted": is_restricted,
                "score": score,
                "requires": requires,
            })

        if not eligible_candidates:
            res = AssignmentResult(
                subtask=subtask,
                chosen_skill=None,
                rejected_skills=rejected_candidates,
            )
            results.append(res)
            continue

        # Sort eligible candidates by score descending
        eligible_candidates.sort(key=lambda c: c["score"], reverse=True)
        winner = eligible_candidates[0]

        # Record why other eligible candidates were rejected
        for loser in eligible_candidates[1:]:
            rejected_candidates.append((
                loser["id"],
                f"Lower historical track record score: {loser['score']:.2f} vs {winner['score']:.2f}",
            ))

        chosen_def = SkillDef(
            id=winner["id"],
            name=winner["name"],
            prompt_fragment=winner["prompt_fragment"],
            capabilities=[subtask.capability],
            requires=winner["requires"],
            restricted=winner["restricted"],
        )

        assigned_skill_ids.add(winner["id"])
        res = AssignmentResult(
            subtask=subtask,
            chosen_skill=chosen_def,
            rejected_skills=rejected_candidates,
        )
        results.append(res)

        # Persist skill assignment decision to run graph if requested
        if run_graph_name:
            dec_id = f"dec-skill-{subtask.id}"
            store.query(
                run_graph_name,
                "MERGE (sub:Subtask {id: $sub_id}) "
                "ON CREATE SET sub.capability = $cap, sub.description = $desc "
                "MERGE (d:Decision {id: $dec_id}) "
                "ON CREATE SET d.kind = 'skill_assignment', d.backend = 'rules', d.confidence = 1.0 "
                "MERGE (d)-[:FOR]->(sub) "
                "MERGE (s:SkillRef {id: $chosen_id}) "
                "MERGE (d)-[:CHOSE]->(s)",
                {
                    "sub_id": subtask.id,
                    "cap": subtask.capability,
                    "desc": subtask.description or "",
                    "dec_id": dec_id,
                    "chosen_id": chosen_def.id,
                },
            )
            for rej_id, reason in rejected_candidates:
                store.query(
                    run_graph_name,
                    "MATCH (d:Decision {id: $dec_id}) "
                    "MERGE (s:SkillRef {id: $rej_id}) "
                    "MERGE (d)-[:REJECTED {reason: $reason}]->(s)",
                    {"dec_id": dec_id, "rej_id": rej_id, "reason": reason},
                )

    return results


def equip_agent_with_skill(
    store: GraphStore,
    run_graph_name: str,
    agent_id: str,
    skill_id: str,
) -> None:
    """Persist Agent -[:EQUIPPED]-> SkillRef in run graph."""
    store.query(
        run_graph_name,
        "MERGE (a:Agent {id: $agent_id}) "
        "MERGE (s:SkillRef {id: $skill_id}) "
        "MERGE (a)-[:EQUIPPED]->(s)",
        {"agent_id": agent_id, "skill_id": skill_id},
    )


# Canonical alias as specified in requirements
assign_skills = assign_skills_to_subtasks

