"""Unit tests for task decomposition and atlas graph skill matching."""

from unittest.mock import MagicMock
from luna.llm.client import MockLLMClient
from luna.planner.decompose import Subtask, decompose_task
from luna.atlas.assign import assign_skills_to_subtasks


def test_decompose_task_with_mock_llm():
    """Verify task decomposition using MockLLMClient."""
    mock_llm = MockLLMClient()
    mock_llm.register_response(
        r"fraud",
        {
            "subtasks": [
                {
                    "id": "sub_1",
                    "description": "Find shared accounts and phone links",
                    "capability": "link_entities",
                },
                {
                    "id": "sub_2",
                    "description": "Cluster connected components to locate fraud ring",
                    "capability": "detect_communities",
                },
            ]
        },
    )

    subtasks = decompose_task(
        task_text="Investigate suspicious claims clustered around provider prov_ring",
        task_type="fraud_ring_investigation",
        llm=mock_llm,
    )

    assert len(subtasks) == 2
    assert subtasks[0].id == "sub_1"
    assert subtasks[0].capability == "link_entities"
    assert subtasks[1].id == "sub_2"
    assert subtasks[1].capability == "detect_communities"


def test_decompose_task_fallback():
    """Verify default fallback subtasks when LLM returns unparseable or empty response."""
    mock_llm = MockLLMClient(default_response="Not a json response")

    subtasks = decompose_task(
        task_text="Investigate provider prov_ring",
        task_type="fraud_ring_investigation",
        llm=mock_llm,
    )

    assert len(subtasks) == 2
    assert subtasks[0].capability == "link_entities"
    assert subtasks[1].capability == "detect_communities"


def test_assign_skills_policy_rejection_and_score_ranking():
    """Verify assign_skills_to_subtasks rejects restricted skills and ranks by score."""
    mock_store = MagicMock()

    # Query responses for subtask 1 (link_entities) and subtask 2 (detect_communities)
    def mock_query(graph_name, query_str, params=None):
        cap = (params or {}).get("cap")
        if cap == "link_entities":
            return [
                {
                    "id": "bulk-linker",
                    "name": "Bulk Linker",
                    "prompt_fragment": "Link all.",
                    "restricted": True,
                    "score": 0.95,
                    "requires": [],
                },
                {
                    "id": "entity-linker",
                    "name": "Entity Linker",
                    "prompt_fragment": "Report shared attributes.",
                    "restricted": False,
                    "score": 0.70,
                    "requires": [],
                },
            ]
        elif cap == "detect_communities":
            return [
                {
                    "id": "ring-detector",
                    "name": "Fraud Ring Detector",
                    "prompt_fragment": "Address-only is clean.",
                    "restricted": False,
                    "score": 0.80,
                    "requires": ["entity-linker"],
                },
                {
                    "id": "ring-detector-lite",
                    "name": "Ring Detector Lite",
                    "prompt_fragment": "Basic components.",
                    "restricted": False,
                    "score": 0.50,
                    "requires": [],
                },
            ]
        return []

    mock_store.query.side_effect = mock_query

    subtasks = [
        Subtask(id="sub_1", description="Link entities", capability="link_entities"),
        Subtask(id="sub_2", description="Detect ring", capability="detect_communities"),
    ]

    assignments = assign_skills_to_subtasks(mock_store, subtasks, "fraud_ring_investigation")

    assert len(assignments) == 2

    # 1. Subtask 1 evaluation: bulk-linker is rejected due to policy restriction; entity-linker wins
    res1 = assignments[0]
    assert res1.chosen_skill is not None
    assert res1.chosen_skill.id == "entity-linker"
    rejected_ids = [rej[0] for rej in res1.rejected_skills]
    assert "bulk-linker" in rejected_ids
    bulk_reason = next(rej[1] for rej in res1.rejected_skills if rej[0] == "bulk-linker")
    assert "Policy restriction" in bulk_reason

    # 2. Subtask 2 evaluation: ring-detector (0.80) beats ring-detector-lite (0.50)
    res2 = assignments[1]
    assert res2.chosen_skill is not None
    assert res2.chosen_skill.id == "ring-detector"
    rejected_ids2 = [rej[0] for rej in res2.rejected_skills]
    assert "ring-detector-lite" in rejected_ids2
    lite_reason = next(rej[1] for rej in res2.rejected_skills if rej[0] == "ring-detector-lite")
    assert "Lower historical track record score" in lite_reason


def test_assign_skills_unknown_capability():
    """Verify handling when no skill provides the required capability."""
    mock_store = MagicMock()
    mock_store.query.return_value = []

    subtasks = [Subtask(id="sub_x", description="Unrecognized task", capability="unknown_capability")]
    assignments = assign_skills_to_subtasks(mock_store, subtasks, "fraud_ring_investigation")

    assert len(assignments) == 1
    assert assignments[0].chosen_skill is None
    assert len(assignments[0].rejected_skills) == 1
    assert "No skills provide capability" in assignments[0].rejected_skills[0][1]
