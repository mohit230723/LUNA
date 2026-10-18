"""Pydantic and data models for LUNA OS ingestion pipeline."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ParsedChunk(BaseModel):
    """Text chunk extracted from an unstructured or semi-structured source."""
    source_id: str
    source_name: str
    text: str
    char_start: int
    char_end: int
    line_start: int


class ColumnPlan(BaseModel):
    """Mapping role assigned to a tabular column."""
    column: str
    role: str  # id | name | property | date | amount | entity_ref | shared_value | ignore
    ref_table: Optional[str] = None
    ref_column: Optional[str] = None
    value_label: Optional[str] = None


class TableMappingPlan(BaseModel):
    """Mapping specification for a relational or tabular dataset."""
    table: str
    node_label: str
    columns: list[ColumnPlan] = Field(default_factory=list)


class ExtractedEntity(BaseModel):
    """Entity extracted by language model from a text chunk."""
    key: str
    type: str
    name: str
    props: dict[str, str] = Field(default_factory=dict)
    quote: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_id: str
    locator: str
    method: str = "llm"
    model: str = ""


class ExtractedRelation(BaseModel):
    """Relationship extracted by language model from a text chunk."""
    src: str
    dst: str
    rel: str
    quote: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_id: str
    locator: str
    method: str = "llm"
    model: str = ""


class TopEntity(BaseModel):
    cid: str
    name: str
    type: str
    degree: int


class ExtractionStats(BaseModel):
    chunks_total: int = 0
    chunks_ok: int = 0
    entities_kept: int = 0
    entities_dropped: int = 0
    relations_kept: int = 0
    relations_dropped: int = 0
    model: str = ""


class GraphStats(BaseModel):
    nodes: int = 0
    edges: int = 0
    sources: int = 0
    by_label: dict[str, int] = Field(default_factory=dict)
    by_rel: dict[str, int] = Field(default_factory=dict)
    top_entities: list[TopEntity] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    extraction: Optional[ExtractionStats] = None
