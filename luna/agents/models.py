"""Pydantic data models for sub-agent execution and findings."""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, Field


class Finding(BaseModel):
    """Structured evaluation emitted by a sub-agent after investigating a private graph slice."""

    id: str = Field(default_factory=lambda: f"find-{uuid4().hex[:8]}")
    agent_id: str
    skill_id: str
    target_cid: str
    verdict: Literal["suspicious", "benign"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    evidence_cids: list[str] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SubAgentRunConfig(BaseModel):
    """Configuration for an autonomous sub-agent execution run."""

    agent_id: str
    skill_id: str
    prompt_fragment: str
    target_cids: list[str]
    private_graph_name: str
