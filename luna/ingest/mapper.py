"""Relational and tabular mapping to property graph using LLM and deterministic rules."""

from __future__ import annotations

import re
from typing import Any
from luna.ingest.models import TableMappingPlan, ColumnPlan
from luna.ingest.parsers import TableData
from luna.llm.client import LLMClient

SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,40}$")

MAPPING_SYSTEM_PROMPT = (
    "You map relational tables to a property graph. You receive one table: its name, "
    "columns with inferred types, up to 5 sample rows (values cut to 40 characters), "
    "the row count, distinct-value counts per column, and declared foreign keys. "
    "Return ONLY JSON. Choose a node label for the table (singular, PascalCase, from this list "
    "when it fits: Person, Organization, Account, Transaction, Event, Document, Asset, "
    "Location, Device, Claim, Other). For every column choose exactly one role: id (unique row identifier), "
    "name (human-readable display name), property (scalar kept on the node), date, amount, "
    "entity_ref (points to another table; give ref_table and ref_column), shared_value (a value that links "
    "rows that share it, such as phone, email, address, account number, device id, IP; give value_label from: "
    "Phone, Email, Address, Account, Device, Organization, Location, Other), or ignore. Never invent columns."
)

MAPPING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "table": {"type": "string"},
                    "node_label": {"type": "string"},
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "role": {
                                    "type": "string",
                                    "enum": ["id", "name", "property", "date", "amount", "entity_ref", "shared_value", "ignore"],
                                },
                                "ref_table": {"type": "string"},
                                "ref_column": {"type": "string"},
                                "value_label": {"type": "string"},
                            },
                            "required": ["column", "role"],
                        },
                    },
                },
                "required": ["table", "node_label", "columns"],
            },
        }
    },
    "required": ["tables"],
}


def plan_table_mapping(llm: LLMClient, table: TableData) -> TableMappingPlan:
    """Ask LLM for mapping plan for a single table, then validate against real columns."""
    sample_rows = []
    for r in table.rows[:5]:
        sample_row = {k: (str(v)[:40] if v is not None else "") for k, v in r.items()}
        sample_rows.append(sample_row)

    distinct_counts = {}
    for col in table.columns:
        distinct_counts[col] = len({r.get(col) for r in table.rows[:500]})

    user_prompt = (
        f"Table Name: {table.name}\n"
        f"Total Rows: {table.total_rows}\n"
        f"Columns: {table.columns}\n"
        f"Distinct Value Counts (sampled): {distinct_counts}\n"
        f"Foreign Keys: {table.foreign_keys}\n"
        f"Sample Rows (up to 5):\n{sample_rows}\n"
    )

    res = llm.complete_json(MAPPING_SYSTEM_PROMPT, user_prompt, MAPPING_SCHEMA)
    tables = res.get("tables", [])
    if not tables:
        raise ValueError(f"Mapping plan for table '{table.name}' returned no tables")

    plan_raw = tables[0]
    node_label = plan_raw.get("node_label") or table.name.capitalize()
    if not SAFE_IDENTIFIER_PATTERN.match(node_label):
        node_label = re.sub(r"[^A-Za-z0-9_]", "", node_label.capitalize()) or "Record"

    raw_cols = plan_raw.get("columns", [])
    real_col_set = set(table.columns)

    validated_columns: list[ColumnPlan] = []
    seen_cols = set()
    for col_info in raw_cols:
        col_name = col_info.get("column")
        if col_name in real_col_set and col_name not in seen_cols:
            seen_cols.add(col_name)
            validated_columns.append(
                ColumnPlan(
                    column=col_name,
                    role=col_info.get("role", "property"),
                    ref_table=col_info.get("ref_table"),
                    ref_column=col_info.get("ref_column"),
                    value_label=col_info.get("value_label"),
                )
            )

    # Add any columns missed by the plan as 'property'
    for col_name in table.columns:
        if col_name not in seen_cols:
            validated_columns.append(ColumnPlan(column=col_name, role="property"))

    # Apply SQLite declared foreign keys if plan missed them
    for fk in table.foreign_keys:
        from_col = fk.get("from")
        to_tbl = fk.get("table")
        to_col = fk.get("to")
        for col_plan in validated_columns:
            if col_plan.column == from_col and col_plan.role not in ("entity_ref", "id"):
                col_plan.role = "entity_ref"
                col_plan.ref_table = to_tbl
                col_plan.ref_column = to_col

    return TableMappingPlan(table=table.name, node_label=node_label, columns=validated_columns)
