"""Requirement extraction and tech-stack validation for Software-Build Pack."""

from __future__ import annotations

import re
from typing import Any, Optional
from luna.packs.base import Understanding


SUPPORTED_FRONTENDS = {"react", "vite", "nextjs", "next.js"}
SUPPORTED_BACKENDS = {"express", "fastapi", "nestjs", "node"}
SUPPORTED_DATABASES = {"postgres", "postgresql", "mongodb", "sqlite"}

UNSUPPORTED_TECH_MAP = {
    "svelte": ("frontend", "React/Vite"),
    "angular": ("frontend", "React/Vite"),
    "vue": ("frontend", "React/Vite"),
    "django": ("backend", "FastAPI"),
    "rails": ("backend", "Express"),
    "ruby": ("backend", "Express"),
    "cobol": ("backend", "Express"),
    "mysql": ("database", "Postgres"),
}


def understand_build_prompt(
    llm: Any,
    prompt: str,
    context: Optional[dict[str, Any]] = None,
) -> Understanding:
    """Parse software-build prompt, extracting project requirements and validating tech stack.

    If an unsupported technology is requested, sets needs_input=True and suggests
    supported alternatives (matching Scenario D4).
    """
    p = prompt.lower()

    # 1. Check for unsupported technologies
    for unsupp, (cat, alt) in UNSUPPORTED_TECH_MAP.items():
        if unsupp in p:
            # Check if user is saying "switch to React instead of Svelte"
            if "instead of" in p or "switch to" in p or "use react" in p:
                continue
            return Understanding(
                question_type="software_build",
                features=[],
                tech={cat: unsupp},
                needs_input=True,
                clarification_question=(
                    f"We noticed you requested {unsupp.title()}. Currently, our software-build pack "
                    f"supports {alt} for {cat}. Would you like us to proceed with {alt} instead?"
                ),
                context_run_id=context.get("run_id") if context else None,
            )

    # 2. Extract tech stack
    tech: dict[str, str] = {}
    if "nextjs" in p or "next.js" in p:
        tech["frontend"] = "nextjs"
    elif "react" in p or "vite" in p:
        tech["frontend"] = "react"

    if "fastapi" in p:
        tech["backend"] = "fastapi"
    elif "nestjs" in p:
        tech["backend"] = "nestjs"
    elif "express" in p or "node" in p:
        tech["backend"] = "express"

    if "postgres" in p or "postgresql" in p:
        tech["database"] = "postgres"
    elif "mongodb" in p or "mongo" in p:
        tech["database"] = "mongodb"
    elif "sqlite" in p:
        tech["database"] = "sqlite"

    # Fill defaults if unspecified
    if "frontend" not in tech:
        tech["frontend"] = "react"
    if "backend" not in tech:
        tech["backend"] = "express"
    if "database" not in tech:
        tech["database"] = "postgres"

    # 3. Extract features and project name
    features: list[str] = []
    if "todo" in p:
        features = ["create todo", "list todos", "mark completed", "delete todo"]
        project_name = "todo-app"
    elif "chat" in p:
        features = ["send message", "list messages", "user channels"]
        project_name = "chat-app"
    elif "dashboard" in p:
        features = ["analytics view", "data charts", "export report"]
        project_name = "analytics-dashboard"
    else:
        features = ["core CRUD operations", "status check endpoint"]
        project_name = "web-application"

    return Understanding(
        question_type="software_build",
        features=features,
        tech=tech,
        needs_input=False,
        context_run_id=context.get("run_id") if context else None,
    )
