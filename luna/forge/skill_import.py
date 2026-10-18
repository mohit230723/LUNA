"""Import parsed skills into the atlas graph as Skill/Section/ChecklistItem nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from luna.forge.models import ForgeError, ImportResult, SkillDoc
from luna.forge.skill_parse import SkillParseError, parse_skill_md
from luna.forge.vocab import CAPABILITY_ROLES
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_CAPABILITY,
    LABEL_CHECKLIST_ITEM,
    LABEL_SECTION,
    LABEL_SKILL,
    LABEL_TASK_TYPE,
    LABEL_TECHNOLOGY,
    REL_HAS_CHECK,
    REL_HAS_SECTION,
    REL_PROVIDES,
    REL_REQUIRES,
    REL_SUCCEEDED_ON,
    REL_TARGETS,
    TASK_TYPE_SOFTWARE_BUILD,
)

__all__ = [
    "CAPABILITY_ROLES",
    "import_skill",
    "import_skill_dir",
    "set_skill_status",
]

INITIAL_SCORE = 0.7


def _find_cycle(store, atlas_graph: str, doc: SkillDoc) -> list[str] | None:
    rows = store.query(
        atlas_graph,
        f"MATCH (a:{LABEL_SKILL})-[:{REL_REQUIRES}]->(b:{LABEL_SKILL}) RETURN a.id AS a, b.id AS b",
    )
    adj: dict[str, list[str]] = {}
    for r in rows:
        adj.setdefault(r["a"], []).append(r["b"])
    adj[doc.id] = list(doc.requires)

    def dfs(node: str, path: list[str]) -> list[str] | None:
        for nxt in adj.get(node, []):
            if nxt == doc.id:
                return [*path, nxt]
            if nxt in path:
                continue
            found = dfs(nxt, [*path, nxt])
            if found:
                return found
        return None

    return dfs(doc.id, [doc.id])


def _names(store, atlas_graph: str, label: str) -> dict[str, str]:
    rows = store.query(atlas_graph, f"MATCH (n:{label}) RETURN n.name AS name")
    return {r["name"].lower(): r["name"] for r in rows if r.get("name")}


def _suggest(llm, caps: dict[str, str], techs: dict[str, str], doc: SkillDoc) -> list[str]:
    try:
        if not llm.info().get("reachable"):
            return []
        schema = {
            "type": "object",
            "properties": {
                "capabilities": {"type": "array", "items": {"type": "string"}},
                "technologies": {"type": "array", "items": {"type": "string"}},
            },
        }
        system = (
            "Choose which capabilities and technologies a coding skill covers. "
            "Only use names from the provided lists. Return JSON."
        )
        user = (
            f"Skill: {doc.name}\nDescription: {doc.description}\n\n{doc.body[:2000]}\n\n"
            f"Capabilities: {sorted(caps.values())}\nTechnologies: {sorted(techs.values())}"
        )
        out = llm.complete_json(system, user, schema) or {}
        warnings = []
        for c in out.get("capabilities") or []:
            if str(c).lower() in caps:
                warnings.append(f"suggested capability '{caps[str(c).lower()]}'")
        for t in out.get("technologies") or []:
            if str(t).lower() in techs:
                warnings.append(f"suggested technology '{techs[str(t).lower()]}'")
        return warnings
    except Exception:
        return ["llm suggestion unavailable"]


def import_skill(
    store,
    doc: SkillDoc,
    source: Literal["repo", "upload", "mcp"],
    atlas_graph: str = GRAPH_ATLAS,
    llm=None,
) -> ImportResult:
    cycle = _find_cycle(store, atlas_graph, doc)
    if cycle:
        raise ForgeError("invalid", "requires cycle: " + " -> ".join(cycle))

    existing = store.query(
        atlas_graph,
        f"MATCH (s:{LABEL_SKILL} {{id: $id}}) RETURN s.content_hash AS h, s.status AS st",
        {"id": doc.id},
    )
    changed = not existing or existing[0]["h"] != doc.content_hash
    if not changed and existing[0].get("st"):
        status = existing[0]["st"]
    else:
        status = "approved" if source == "repo" else "pending_review"

    store.query(
        atlas_graph,
        f"MERGE (s:{LABEL_SKILL} {{id: $id}}) "
        "SET s.name = $name, s.description = $desc, s.prompt_fragment = $desc, "
        "s.body = $body, s.content_hash = $hash, s.source = $source, "
        "s.status = $status, s.restricted = false",
        {
            "id": doc.id, "name": doc.name, "desc": doc.description, "body": doc.body,
            "hash": doc.content_hash, "source": source, "status": status,
        },
    )

    if changed:
        for rel, label in ((REL_HAS_SECTION, LABEL_SECTION), (REL_HAS_CHECK, LABEL_CHECKLIST_ITEM)):
            store.query(
                atlas_graph,
                f"MATCH (s:{LABEL_SKILL} {{id: $id}})-[:{rel}]->(x:{label}) DETACH DELETE x",
                {"id": doc.id},
            )
        for sec in doc.sections:
            store.query(
                atlas_graph,
                f"MATCH (s:{LABEL_SKILL} {{id: $id}}) "
                f"MERGE (x:{LABEL_SECTION} {{id: $sid}}) "
                "SET x.slug = $slug, x.title = $title, x.content = $content, x.order = $order "
                f"MERGE (s)-[:{REL_HAS_SECTION}]->(x)",
                {
                    "id": doc.id, "sid": f"{doc.id}#{sec.slug}", "slug": sec.slug,
                    "title": sec.title, "content": sec.content, "order": sec.order,
                },
            )
        for i, chk in enumerate(doc.checklist):
            store.query(
                atlas_graph,
                f"MATCH (s:{LABEL_SKILL} {{id: $id}}) "
                f"MERGE (x:{LABEL_CHECKLIST_ITEM} {{id: $cid}}) "
                "SET x.check_id = $check_id, x.text = $text, x.order = $order "
                f"MERGE (s)-[:{REL_HAS_CHECK}]->(x)",
                {
                    "id": doc.id, "cid": f"{doc.id}#{chk.id}", "check_id": chk.id,
                    "text": chk.text, "order": i,
                },
            )

    # Refresh outgoing links so vocabulary added later is picked up on re-import.
    for rel in (REL_PROVIDES, REL_TARGETS, REL_REQUIRES):
        store.query(
            atlas_graph,
            f"MATCH (s:{LABEL_SKILL} {{id: $id}})-[r:{rel}]->() DELETE r",
            {"id": doc.id},
        )

    caps = _names(store, atlas_graph, LABEL_CAPABILITY)
    techs = _names(store, atlas_graph, LABEL_TECHNOLOGY)
    warnings: list[str] = []

    for c in doc.capabilities:
        real = caps.get(c.lower())
        if not real:
            warnings.append(f"unknown capability '{c}'")
            continue
        store.query(
            atlas_graph,
            f"MATCH (s:{LABEL_SKILL} {{id: $id}}) MATCH (c:{LABEL_CAPABILITY} {{name: $n}}) "
            f"MERGE (s)-[:{REL_PROVIDES}]->(c)",
            {"id": doc.id, "n": real},
        )
    for t in doc.technologies:
        real = techs.get(t.lower())
        if not real:
            warnings.append(f"unknown technology '{t}'")
            continue
        store.query(
            atlas_graph,
            f"MATCH (s:{LABEL_SKILL} {{id: $id}}) MATCH (t:{LABEL_TECHNOLOGY} {{name: $n}}) "
            f"MERGE (s)-[:{REL_TARGETS}]->(t)",
            {"id": doc.id, "n": real},
        )
    for req in doc.requires:
        found = store.query(
            atlas_graph, f"MATCH (r:{LABEL_SKILL} {{id: $rid}}) RETURN r.id AS id", {"rid": req}
        )
        if not found:
            warnings.append(f"unknown required skill '{req}'")
            continue
        store.query(
            atlas_graph,
            f"MATCH (s:{LABEL_SKILL} {{id: $id}}) MATCH (r:{LABEL_SKILL} {{id: $rid}}) "
            f"MERGE (s)-[:{REL_REQUIRES}]->(r)",
            {"id": doc.id, "rid": req},
        )

    if not doc.capabilities and llm is not None:
        warnings.extend(_suggest(llm, caps, techs, doc))

    store.query(
        atlas_graph,
        f"MATCH (s:{LABEL_SKILL} {{id: $id}}) "
        f"MERGE (tt:{LABEL_TASK_TYPE} {{name: $tt}}) "
        f"MERGE (s)-[r:{REL_SUCCEEDED_ON}]->(tt) "
        "ON CREATE SET r.score = $score, r.runs = 0",
        {"id": doc.id, "tt": TASK_TYPE_SOFTWARE_BUILD, "score": INITIAL_SCORE},
    )

    return ImportResult(skill_id=doc.id, status=status, warnings=warnings, changed=changed)


def import_skill_dir(
    store,
    path: Path,
    source: str = "repo",
    atlas_graph: str = GRAPH_ATLAS,
) -> ImportResult:
    path = Path(path)
    skill_file = path / "SKILL.md"
    if not skill_file.is_file():
        raise ForgeError("not_found", f"no SKILL.md in {path}")
    refs: list[tuple[str, str]] = []
    ref_dir = path / "references"
    if ref_dir.is_dir():
        for f in sorted(ref_dir.glob("*.md")):
            refs.append((f.name, f.read_text(encoding="utf-8")))
    try:
        doc = parse_skill_md(
            skill_file.read_text(encoding="utf-8"), references=refs, default_id=path.name
        )
    except SkillParseError as exc:
        raise ForgeError("invalid", str(exc)) from exc
    return import_skill(store, doc, source, atlas_graph)  # type: ignore[arg-type]


def set_skill_status(
    store,
    skill_id: str,
    status: Literal["approved", "rejected"],
    atlas_graph: str = GRAPH_ATLAS,
) -> None:
    rows = store.query(
        atlas_graph, f"MATCH (s:{LABEL_SKILL} {{id: $id}}) RETURN s.id AS id", {"id": skill_id}
    )
    if not rows:
        raise ForgeError("not_found", f"skill '{skill_id}' not found")
    store.query(
        atlas_graph,
        f"MATCH (s:{LABEL_SKILL} {{id: $id}}) SET s.status = $status",
        {"id": skill_id, "status": status},
    )
