"""Unit tests for the atlas skill catalog, models, and graph seeder."""

import pytest
from unittest.mock import MagicMock
from luna.atlas.models import CapabilityDef, ToolDef, SkillDef, SkillScore
from luna.atlas.seed import seed_atlas, get_seeded_skills, get_seeded_capabilities, get_seeded_tools


def test_atlas_model_definitions():
    """Verify that atlas models instantiate and validate fields correctly."""
    cap = CapabilityDef(name="link_entities", description="Link entities together")
    assert cap.name == "link_entities"

    tool = ToolDef(name="shared_attribute_links", description="Find shared links")
    assert tool.name == "shared_attribute_links"

    score = SkillScore(task_type="fraud_ring_investigation", score=0.85, runs=3)
    assert score.score == 0.85
    assert score.runs == 3

    skill = SkillDef(
        id="ring-detector",
        name="Fraud Ring Detector",
        prompt_fragment="Look for clusters.",
        capabilities=["detect_communities"],
        requires=["entity-linker"],
        exposes=["connected_components", "ask_graph"],
        restricted=False,
        scores=[score],
    )
    assert skill.id == "ring-detector"
    assert skill.requires == ["entity-linker"]
    assert "ask_graph" in skill.exposes


def test_seeded_catalog_integrity():
    """Verify the 7 core skills and their required capabilities and tool exposures."""
    skills = get_seeded_skills()
    assert len(skills) == 7

    skill_map = {s.id: s for s in skills}
    expected_ids = {
        "entity-linker",
        "bulk-linker",
        "ring-detector",
        "ring-detector-lite",
        "influence-ranker",
        "path-explainer",
        "anomaly-scout",
    }
    assert set(skill_map.keys()) == expected_ids

    # 1. Prerequisite verification: ring-detector requires entity-linker
    assert skill_map["ring-detector"].requires == ["entity-linker"]

    # 2. Policy restriction verification: bulk-linker is restricted
    assert skill_map["bulk-linker"].restricted is True
    assert skill_map["entity-linker"].restricted is False

    # 3. Score verification: bulk-linker (0.95) vs entity-linker (0.70)
    bulk_score = next(s.score for s in skill_map["bulk-linker"].scores if s.task_type == "fraud_ring_investigation")
    assert bulk_score == 0.95

    ring_score = next(s.score for s in skill_map["ring-detector"].scores if s.task_type == "fraud_ring_investigation")
    assert ring_score == 0.80

    lite_score = next(s.score for s in skill_map["ring-detector-lite"].scores if s.task_type == "fraud_ring_investigation")
    assert lite_score == 0.50

    # 4. ask_graph must be exposed to ALL 7 skills
    for s in skills:
        assert "ask_graph" in s.exposes, f"Skill {s.id} does not expose ask_graph"


@pytest.mark.integration
def test_seed_atlas_query_execution(live_store):
    """Verify that seed_atlas populates the real atlas catalog in FalkorDB."""
    seed_atlas(live_store)

    # 1. Verify 7 skills created
    skills = live_store.query("atlas", "MATCH (s:Skill) RETURN s.id AS id")
    assert len(skills) == 7

    # 2. Verify capabilities and tools created
    caps = live_store.query("atlas", "MATCH (c:Capability) RETURN c.name AS name")
    assert len(caps) >= 5

    tools = live_store.query("atlas", "MATCH (t:Tool) RETURN t.name AS name")
    assert len(tools) >= 6

    # 3. Verify relationships exist
    provides = live_store.query("atlas", "MATCH (:Skill)-[:PROVIDES]->(:Capability) RETURN count(*) AS cnt")
    assert provides[0]["cnt"] >= 7


def test_simulated_atlas_skill_matching():
    """Simulate atlas queries matching capabilities and checking requirements and scores."""
    skills = get_seeded_skills()

    # Query: capability 'detect_communities'
    candidates = [s for s in skills if "detect_communities" in s.capabilities]
    assert len(candidates) == 2
    candidate_ids = {s.id for s in candidates}
    assert candidate_ids == {"ring-detector", "ring-detector-lite"}

    # Sort candidates by score descending
    candidates.sort(
        key=lambda s: next(sc.score for sc in s.scores if sc.task_type == "fraud_ring_investigation"),
        reverse=True,
    )
    # ring-detector (0.80) should beat ring-detector-lite (0.50)
    assert candidates[0].id == "ring-detector"
    assert candidates[1].id == "ring-detector-lite"

    # Query: capability 'link_entities'
    link_candidates = [s for s in skills if "link_entities" in s.capabilities]
    assert len(link_candidates) == 2

    # Filter out restricted skills (policy check)
    unrestricted = [s for s in link_candidates if not s.restricted]
    restricted = [s for s in link_candidates if s.restricted]

    assert len(unrestricted) == 1
    assert unrestricted[0].id == "entity-linker"
    assert len(restricted) == 1
    assert restricted[0].id == "bulk-linker"
