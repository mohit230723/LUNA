"""Parse SKILL.md text (YAML frontmatter + markdown) into a SkillDoc."""

import hashlib
import re

import yaml

from luna.forge.models import ChecklistDef, SectionDef, SkillDoc

MAX_SKILL_BYTES = 102_400
MAX_REFERENCES = 20
MAX_REFERENCE_BYTES = 102_400


class SkillParseError(ValueError):
    """Raised when a SKILL.md cannot be parsed or violates limits."""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _normalize(text: str) -> str:
    return text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")


def _str_list(value, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    raise SkillParseError(f"frontmatter '{field}' must be a list")


def _checklist(value) -> list[ChecklistDef]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SkillParseError("frontmatter 'checklist' must be a list")
    items = []
    for i, item in enumerate(value):
        if isinstance(item, dict) and "text" in item:
            items.append(ChecklistDef(id=str(item.get("id") or f"check-{i + 1}"), text=str(item["text"])))
        elif isinstance(item, str):
            items.append(ChecklistDef(id=f"check-{i + 1}", text=item))
        else:
            raise SkillParseError("checklist items need 'text'")
    return items


def parse_skill_md(
    text: str,
    references: list[tuple[str, str]] | None = None,
    default_id: str = "",
) -> SkillDoc:
    references = references or []
    text = _normalize(text)
    if len(text.encode("utf-8")) > MAX_SKILL_BYTES:
        raise SkillParseError("SKILL.md exceeds the 100 KB limit")
    if len(references) > MAX_REFERENCES:
        raise SkillParseError(f"too many references (max {MAX_REFERENCES})")
    refs = []
    for name, content in references:
        content = _normalize(content)
        if len(content.encode("utf-8")) > MAX_REFERENCE_BYTES:
            raise SkillParseError(f"reference '{name}' exceeds the 100 KB limit")
        refs.append((name, content))

    m = re.match(r"---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", text, re.DOTALL)
    if not m:
        raise SkillParseError("missing YAML frontmatter")
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise SkillParseError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(meta, dict):
        raise SkillParseError("frontmatter must be a mapping")
    name = str(meta.get("name") or "").strip()
    if not name:
        raise SkillParseError("frontmatter is missing 'name'")

    parts = re.split(r"(?m)^## (.*)$", text[m.end():])
    body = parts[0]
    sections: list[SectionDef] = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        sections.append(SectionDef(
            slug=_slug(title), title=title, content=parts[i + 1].strip("\n"), order=len(sections)))
    for fname, content in refs:
        stem = fname.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        t = re.search(r"(?m)^# (.*)$", content)
        sections.append(SectionDef(
            slug=_slug(stem), title=t.group(1).strip() if t else stem,
            content=content, order=len(sections)))

    digest = hashlib.sha256(text.encode("utf-8"))
    for fname, content in refs:
        digest.update(fname.encode("utf-8"))
        digest.update(content.encode("utf-8"))

    return SkillDoc(
        id=default_id or _slug(name),
        name=name,
        description=str(meta.get("description") or ""),
        body=body,
        capabilities=_str_list(meta.get("capabilities"), "capabilities"),
        technologies=_str_list(meta.get("technologies"), "technologies"),
        requires=_str_list(meta.get("requires"), "requires"),
        checklist=_checklist(meta.get("checklist")),
        sections=sections,
        content_hash=digest.hexdigest(),
    )
