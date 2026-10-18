"""Skill briefings: everything a blank subagent needs to do one Forge task."""

from __future__ import annotations

from luna.forge.models import Briefing, ChecklistDef, ForgeError
from luna.forge.runs import read_results, read_task, skill_checklist
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_CAPABILITY,
    LABEL_SECTION,
    LABEL_SKILL,
    REL_HAS_SECTION,
)

__all__ = ["BODY_LIMIT", "RULES", "build_briefing", "get_section"]

BODY_LIMIT = 12_000
TRUNCATION_NOTE = (
    "\n\n[Skill body truncated at {limit} characters. Fetch the full text of any section "
    "listed in sections_index with luna_get_skill(run_id, task_id, section=<slug>).]"
)
UNSKILLED_BODY = (
    "No skill in the library covers this capability. "
    "Work from the capability description and the upstream results."
)
RULES: list[str] = [
    "Work only within this task.",
    "Report all files you created or changed.",
    "Mark every checklist item.",
]


def _truncate(body: str) -> tuple[str, bool]:
    if len(body) <= BODY_LIMIT:
        return body, False
    note = TRUNCATION_NOTE.format(limit=BODY_LIMIT)
    return body[: BODY_LIMIT - len(note)] + note, True


def _capability_description(store, capability: str, atlas_graph: str) -> str:
    rows = store.query(
        atlas_graph,
        f"MATCH (c:{LABEL_CAPABILITY} {{name: $n}}) RETURN c.description AS d",
        {"n": capability},
    )
    return (rows[0].get("d") if rows else "") or capability


def build_briefing(store, run_id: str, task_id: str, atlas_graph: str = GRAPH_ATLAS) -> Briefing:
    task = read_task(store, run_id, task_id)

    skill_rows = []
    if task.skill_id:
        skill_rows = store.query(
            atlas_graph,
            f"MATCH (s:{LABEL_SKILL} {{id: $id}}) "
            "RETURN s.id AS id, s.name AS name, s.description AS description, s.body AS body",
            {"id": task.skill_id},
        )

    truncated = False
    sections_index: list[dict] = []
    checklist: list[ChecklistDef] = []
    if skill_rows:
        s = skill_rows[0]
        body, truncated = _truncate(s.get("body") or "")
        skill = {
            "id": s["id"],
            "name": s.get("name") or s["id"],
            "description": s.get("description") or "",
            "body": body,
        }
        sections_index = [
            {"slug": r["slug"], "title": r.get("title") or "", "chars": len(r.get("content") or "")}
            for r in store.query(
                atlas_graph,
                f"MATCH (:{LABEL_SKILL} {{id: $id}})-[:{REL_HAS_SECTION}]->(x:{LABEL_SECTION}) "
                "RETURN x.slug AS slug, x.title AS title, x.content AS content, x.order AS ord "
                "ORDER BY ord",
                {"id": task.skill_id},
            )
        ]
        checklist = [ChecklistDef(**c) for c in skill_checklist(store, task.skill_id, atlas_graph)]
    else:
        # Unskilled task, or the assigned skill has since been removed from the atlas.
        skill = {
            "id": "",
            "name": f"Generic {task.title}",
            "description": _capability_description(store, task.capability, atlas_graph),
            "body": UNSKILLED_BODY,
        }

    results = read_results(store, run_id)
    upstream = [
        {"task_id": dep, "summary": results[dep]["summary"], "files": results[dep]["files"]}
        for dep in task.depends_on
        if dep in results
    ]

    return Briefing(
        run_id=run_id,
        task_id=task_id,
        task=task,
        skill=skill,
        sections_index=sections_index,
        checklist=checklist,
        upstream=upstream,
        rules=list(RULES),
        truncated=truncated,
    )


def get_section(store, skill_id: str, slug: str, atlas_graph: str = GRAPH_ATLAS) -> dict:
    rows = store.query(
        atlas_graph,
        f"MATCH (:{LABEL_SKILL} {{id: $id}})-[:{REL_HAS_SECTION}]->(x:{LABEL_SECTION} {{slug: $slug}}) "
        "RETURN x.title AS title, x.content AS content",
        {"id": skill_id, "slug": slug},
    )
    if not rows:
        raise ForgeError("not_found", f"section '{slug}' not found in skill '{skill_id}'")
    return {"title": rows[0].get("title") or "", "content": rows[0].get("content") or ""}
