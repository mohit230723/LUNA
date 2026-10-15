"""Data models for skills, capabilities, tools, and track record scores in the atlas catalog."""

from pydantic import BaseModel, Field


class CapabilityDef(BaseModel):
    """A distinct capability that can be provided by skills."""

    name: str
    description: str = ""


class ToolDef(BaseModel):
    """A callable tool that can be exposed by skills."""

    name: str
    description: str = ""


class SkillScore(BaseModel):
    """Historical performance score of a skill on a specific task type."""

    task_type: str
    score: float = Field(ge=0.0, le=1.0)
    runs: int = Field(default=1, ge=1)


class SkillDef(BaseModel):
    """Definition of an equipable agent skill."""

    id: str
    name: str
    prompt_fragment: str
    capabilities: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    exposes: list[str] = Field(default_factory=list)
    restricted: bool = False
    scores: list[SkillScore] = Field(default_factory=list)
