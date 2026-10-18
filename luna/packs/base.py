"""Pack protocol and supporting data models for LUNA OS multi-agent system."""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, Field


class Understanding(BaseModel):
    """Structured understanding of a user prompt, produced by Pack.understand()."""

    question_type: str  # e.g. "fraud_investigation", "software_build", "other"
    entities: list[str] = Field(default_factory=list)  # resolved seed cids or names
    features: list[str] = Field(default_factory=list)  # requested features (build)
    tech: dict[str, Any] = Field(default_factory=dict)  # {frontend, backend, database, other}
    needs_input: bool = False
    clarification_question: Optional[str] = None
    context_run_id: Optional[str] = None  # prior run for follow-ups


class RoutingDecision(BaseModel):
    """Structured output from route_prompt(), persisted as Decision(kind='routing')."""

    pack: Optional[str] = None  # None means needs_input
    intent: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    backend: str = "rules"  # "llm" | "rules" | "scripted"
    needs_input: bool = False
    clarification_question: Optional[str] = None


class PackPipeline(Protocol):
    """Minimal interface for a runnable pack pipeline."""

    def start(self, task: str, **kwargs: Any) -> Any: ...
    def approve_and_finish(self, **kwargs: Any) -> Any: ...


@runtime_checkable
class Pack(Protocol):
    """Protocol that every LUNA OS task pack must implement.

    A Pack is a self-describing bundle that seeds atlas data,
    understands prompts, and builds a runnable pipeline.
    """

    name: str
    title: str
    description: str
    example_prompts: list[str]
    capabilities: list[str]  # atlas capability names this pack owns

    def seed_atlas(self, store: Any, atlas_graph: str) -> None:
        """Idempotently seed this pack's skills and capabilities into the atlas graph.

        MUST use MERGE, never DELETE. Never resets existing SUCCEEDED_ON scores.
        """
        ...

    def seed_data(self, store: Any, domain_graph: str) -> None:
        """Seed domain graph data (investigate pack only). May be None for other packs."""
        ...

    def understand(self, llm: Any, prompt: str, context: Optional[dict[str, Any]] = None) -> Understanding:
        """Parse the user prompt into a structured Understanding.

        Returns Understanding with needs_input=True and a clarifying_question
        if the prompt is ambiguous or requests unsupported technologies.
        """
        ...

    def build_pipeline(self, store: Any, config: Any) -> PackPipeline:
        """Build and return a runnable pipeline for this pack."""
        ...
