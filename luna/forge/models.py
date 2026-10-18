"""Pydantic models and errors shared across LUNA Forge."""

from typing import Literal

from pydantic import BaseModel, Field


class ForgeError(Exception):
    """Forge failure carrying a machine-readable code.

    Codes: not_found, not_ready, claim_conflict, invalid, store_unavailable.
    """

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


class ChecklistDef(BaseModel):
    id: str
    text: str


class SectionDef(BaseModel):
    slug: str
    title: str
    content: str
    order: int


class SkillDoc(BaseModel):
    id: str
    name: str
    description: str
    body: str
    capabilities: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    checklist: list[ChecklistDef] = Field(default_factory=list)
    sections: list[SectionDef] = Field(default_factory=list)
    content_hash: str


class ImportResult(BaseModel):
    skill_id: str
    status: str
    warnings: list[str] = Field(default_factory=list)
    changed: bool


class PlanTask(BaseModel):
    task_id: str
    title: str
    capability: str
    skill_id: str = ""  # "" means unskilled
    depends_on: list[str] = Field(default_factory=list)
    wave: int = 0
    status: str = "pending"


class CandidateRecord(BaseModel):
    skill_id: str
    score: float
    overlap: int
    rejected_reason: str = ""


class PlanDraft(BaseModel):
    status: Literal["planned", "needs_input"]
    question: str = ""
    matched_capabilities: list[str] = Field(default_factory=list)
    matched_technologies: list[str] = Field(default_factory=list)
    tasks: list[PlanTask] = Field(default_factory=list)
    waves: list[list[str]] = Field(default_factory=list)
    candidates: dict[str, list[CandidateRecord]] = Field(default_factory=dict)


class Plan(BaseModel):
    run_id: str
    status: Literal["planned", "needs_input"]
    question: str = ""
    tasks: list[PlanTask] = Field(default_factory=list)
    waves: list[list[str]] = Field(default_factory=list)


class CheckReport(BaseModel):
    id: str
    passed: bool
    note: str = ""


class SubmitResult(BaseModel):
    accepted: bool
    errors: list[str] = Field(default_factory=list)
    unlocked_tasks: list[str] = Field(default_factory=list)


class Briefing(BaseModel):
    run_id: str
    task_id: str
    task: PlanTask
    skill: dict[str, str] = Field(default_factory=dict)
    sections_index: list[dict] = Field(default_factory=list)
    checklist: list[ChecklistDef] = Field(default_factory=list)
    upstream: list[dict] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    truncated: bool = False


class AssemblyReport(BaseModel):
    run_id: str
    status: Literal["complete", "incomplete"]
    missing: list[str] = Field(default_factory=list)
    tasks: list[dict] = Field(default_factory=list)
    overlaps: dict[str, list[str]] = Field(default_factory=dict)
    gaps: list[dict] = Field(default_factory=list)
    summary: str = ""
