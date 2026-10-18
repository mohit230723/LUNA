"""Tests for the Forge SKILL.md parser."""

import pytest

from luna.forge.skill_parse import SkillParseError, parse_skill_md

SAMPLE = """---
name: React Vite Pages
description: Build pages for a React + Vite site.
capabilities: [implement_frontend]
technologies: [React, Vite]
requires: [project-scaffold]
checklist:
  - id: routes
    text: Every page has a route.
---
Core instructions.

## Routing
Use react-router.

## Layout
Mobile first.
"""


def test_parse_frontmatter_and_sections():
    doc = parse_skill_md(SAMPLE, default_id="react-vite-pages")
    assert doc.id == "react-vite-pages"
    assert doc.name == "React Vite Pages"
    assert doc.capabilities == ["implement_frontend"]
    assert doc.requires == ["project-scaffold"]
    assert doc.checklist[0].id == "routes"
    assert doc.body.strip() == "Core instructions."
    assert [s.slug for s in doc.sections] == ["routing", "layout"]
    assert len(doc.content_hash) == 64


def test_parse_id_slug_from_name_when_no_default():
    assert parse_skill_md(SAMPLE).id == "react-vite-pages"


def test_parse_references_become_sections_after_body_sections():
    doc = parse_skill_md(SAMPLE, references=[("forms.md", "# Forms\nUse zod.")], default_id="x")
    assert doc.sections[-1].slug == "forms" and doc.sections[-1].order == 2


def test_parse_crlf_and_bom():
    crlf = "\ufeff" + SAMPLE.replace("\n", "\r\n")
    assert parse_skill_md(crlf, default_id="x").model_dump() == parse_skill_md(SAMPLE, default_id="x").model_dump()


@pytest.mark.parametrize("bad", ["no frontmatter", "---\ndescription: d\n---\nbody", "---\nname: [unclosed\n---\n"])
def test_parse_rejects_invalid(bad):
    with pytest.raises(SkillParseError):
        parse_skill_md(bad)


def test_parse_rejects_oversize():
    with pytest.raises(SkillParseError, match="100 KB"):
        parse_skill_md(SAMPLE + "x" * 102_401)


def test_parse_rejects_too_many_references():
    refs = [(f"r{i}.md", "x") for i in range(21)]
    with pytest.raises(SkillParseError, match="20"):
        parse_skill_md(SAMPLE, references=refs)


def test_parse_empty_slug_fallback():
    text = "---\nname: X\n---\nbody\n\n## !!!\nstuff\n\n## Real\nmore\n"
    doc = parse_skill_md(text, default_id="x")
    assert [s.slug for s in doc.sections] == ["section-0", "real"]


def test_parse_duplicate_slugs_suffixed():
    text = "---\nname: X\n---\nbody\n\n## Setup\na\n\n## Setup\nb\n\n## Setup\nc\n"
    doc = parse_skill_md(text, references=[("setup.md", "# Setup\nd")], default_id="x")
    assert [s.slug for s in doc.sections] == ["setup", "setup-2", "setup-3", "setup-4"]
