"""Task decomposition engine breaking high-level tasks into capability-aligned subtasks."""

from typing import Any
from pydantic import BaseModel
from luna.llm.client import LLMClient


class Subtask(BaseModel):
    """A discrete unit of work requiring a specific capability."""

    id: str
    description: str
    capability: str


def decompose_task(
    task_text: str,
    task_type: str,
    llm: LLMClient,
) -> list[Subtask]:
    """Decompose high-level task text into capability-aligned subtasks using LLM.

    Args:
        task_text: Human-submitted task instruction
        task_type: Categorical task type (e.g. 'fraud_ring_investigation')
        llm: LLMClient instance for structured generation

    Returns:
        List of Subtasks with assigned capabilities.
    """
    system_prompt = (
        "You are the main orchestrator for LUNA OS. "
        "Your role is to break down investigation tasks into discrete subtasks. "
        "Each subtask must specify one required capability from the skill catalog:\n"
        "- link_entities: link entities sharing bank accounts, phone numbers, or addresses\n"
        "- detect_communities: detect connected component clusters and isolate fraud rings\n"
        "- rank_influence: rank node centrality and hub importance\n"
        "- explain_connection: trace shortest evidence paths between entities\n"
        "- detect_amount_anomalies: flag statistical outliers in transaction amounts\n"
        "Return structured JSON matching the requested schema."
    )

    schema = {
        "type": "object",
        "properties": {
            "subtasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                        "capability": {"type": "string"},
                    },
                    "required": ["id", "description", "capability"],
                },
            }
        },
        "required": ["subtasks"],
    }

    user_prompt = (
        f"Task Type: {task_type}\n"
        f"Task Instruction: {task_text}\n\n"
        "Break down this task into ordered subtasks with required capabilities."
    )

    response = llm.complete(user_prompt, system=system_prompt, json_schema=schema)

    subtasks_data: list[dict[str, Any]] = []
    if isinstance(response, dict) and "subtasks" in response and isinstance(response["subtasks"], list):
        subtasks_data = response["subtasks"]
    elif isinstance(response, list):
        subtasks_data = response

    if not subtasks_data:
        # Deterministic default decomposition for fraud_ring_investigation
        if task_type == "fraud_ring_investigation":
            return [
                Subtask(
                    id="subtask_1",
                    description="Link customers sharing bank accounts, phone numbers, or addresses",
                    capability="link_entities",
                ),
                Subtask(
                    id="subtask_2",
                    description="Analyze connected clusters to detect the organized fraud ring and separate decoys",
                    capability="detect_communities",
                ),
            ]
        return [
            Subtask(
                id="subtask_1",
                description=f"Investigate task: {task_text}",
                capability="link_entities",
            )
        ]

    subtasks: list[Subtask] = []
    for item in subtasks_data:
        subtasks.append(
            Subtask(
                id=item.get("id", f"subtask_{len(subtasks) + 1}"),
                description=item.get("description", ""),
                capability=item.get("capability", "link_entities"),
            )
        )
    return subtasks
