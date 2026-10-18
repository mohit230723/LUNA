"""Atlas seeding for Software-Build Pack (capabilities, technologies, skills, and TARGETS edges)."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_CAPABILITY,
    LABEL_SKILL,
    LABEL_TECHNOLOGY,
    LABEL_PACK,
    REL_PROVIDES,
    REL_TARGETS,
    REL_IN_PACK,
    REL_SUCCEEDED_ON,
)
from luna.atlas.models import CapabilityDef, SkillDef, SkillScore


class TechnologyDef(BaseModel):
    name: str
    category: str  # "frontend" | "backend" | "database" | "tool"


BUILD_CAPABILITIES: list[CapabilityDef] = [
    CapabilityDef(name="scaffold_project", description="Initialize project structure and configuration files"),
    CapabilityDef(name="implement_backend", description="Implement REST/GraphQL API routes, middleware, and handlers"),
    CapabilityDef(name="implement_frontend", description="Implement UI components, pages, state management, and API clients"),
    CapabilityDef(name="implement_database", description="Design and write database schemas, migrations, and ORM models"),
    CapabilityDef(name="verify_contracts", description="Validate API endpoints, route matches, and contract compliance"),
]

BUILD_TECHNOLOGIES: list[TechnologyDef] = [
    TechnologyDef(name="React", category="frontend"),
    TechnologyDef(name="Vite", category="frontend"),
    TechnologyDef(name="Next.js", category="frontend"),
    TechnologyDef(name="TailwindCSS", category="frontend"),
    TechnologyDef(name="Express", category="backend"),
    TechnologyDef(name="FastAPI", category="backend"),
    TechnologyDef(name="NestJS", category="backend"),
    TechnologyDef(name="Node", category="backend"),
    TechnologyDef(name="Postgres", category="database"),
    TechnologyDef(name="MongoDB", category="database"),
    TechnologyDef(name="SQLite", category="database"),
    TechnologyDef(name="Redis", category="database"),
    TechnologyDef(name="TypeScript", category="tool"),
    TechnologyDef(name="Python", category="tool"),
    TechnologyDef(name="Docker", category="tool"),
]

BUILD_SKILLS: list[dict[str, Any]] = [
    {
        "id": "react-vite-expert",
        "name": "React Vite Expert",
        "prompt_fragment": "Build modern React components with Vite, TypeScript, and clean responsive CSS.",
        "capabilities": ["implement_frontend"],
        "targets": ["React", "Vite", "TypeScript"],
        "restricted": False,
        "score": 0.88,
    },
    {
        "id": "express-builder",
        "name": "Express Backend Builder",
        "prompt_fragment": "Implement modular Express REST APIs with input validation and CORS middleware.",
        "capabilities": ["implement_backend"],
        "targets": ["Express", "Node", "TypeScript"],
        "restricted": False,
        "score": 0.85,
    },
    {
        "id": "postgres-schema-builder",
        "name": "Postgres Schema Builder",
        "prompt_fragment": "Design normalized Postgres schemas with SQL DDL, indexes, and constraints.",
        "capabilities": ["implement_database"],
        "targets": ["Postgres"],
        "restricted": False,
        "score": 0.90,
    },
    {
        "id": "fastapi-backend-builder",
        "name": "FastAPI Backend Builder",
        "prompt_fragment": "Build async Python REST APIs using FastAPI and Pydantic schemas.",
        "capabilities": ["implement_backend"],
        "targets": ["FastAPI", "Python"],
        "restricted": False,
        "score": 0.82,
    },
    {
        "id": "sqlite-schema-builder",
        "name": "SQLite Schema Builder",
        "prompt_fragment": "Create zero-config SQLite schemas and query helpers.",
        "capabilities": ["implement_database"],
        "targets": ["SQLite"],
        "restricted": False,
        "score": 0.80,
    },
    {
        "id": "mongodb-modeler",
        "name": "MongoDB Modeler",
        "prompt_fragment": "Create document schemas and indexes for MongoDB.",
        "capabilities": ["implement_database"],
        "targets": ["MongoDB"],
        "restricted": False,
        "score": 0.78,
    },
    {
        "id": "nextjs-fullstack-builder",
        "name": "Next.js Fullstack Builder",
        "prompt_fragment": "Build Next.js app router pages, layouts, and server actions.",
        "capabilities": ["implement_frontend", "implement_backend"],
        "targets": ["Next.js", "React", "TypeScript"],
        "restricted": False,
        "score": 0.84,
    },
    {
        "id": "tailwind-styler",
        "name": "Tailwind Styler",
        "prompt_fragment": "Craft sleek modern styling with Tailwind utility classes.",
        "capabilities": ["implement_frontend"],
        "targets": ["TailwindCSS"],
        "restricted": False,
        "score": 0.86,
    },
    {
        "id": "project-scaffolder",
        "name": "Project Scaffolder",
        "prompt_fragment": "Generate base configuration files, package.json, and directory trees.",
        "capabilities": ["scaffold_project"],
        "targets": ["TypeScript", "Node", "Docker"],
        "restricted": False,
        "score": 0.92,
    },
    {
        "id": "docker-packager",
        "name": "Docker Packager",
        "prompt_fragment": "Generate optimized multi-stage Dockerfiles and compose setups.",
        "capabilities": ["scaffold_project"],
        "targets": ["Docker"],
        "restricted": False,
        "score": 0.80,
    },
    {
        "id": "integration-verifier",
        "name": "Integration Contract Verifier",
        "prompt_fragment": "Verify that backend routes match API contracts and frontend fetches align.",
        "capabilities": ["verify_contracts"],
        "targets": ["TypeScript"],
        "restricted": False,
        "score": 0.95,
    },
    {
        "id": "shell-runner",
        "name": "Arbitrary Shell Runner",
        "prompt_fragment": "Execute raw shell commands and scripts directly.",
        "capabilities": ["scaffold_project", "implement_backend"],
        "targets": ["Node", "Docker"],
        "restricted": True,  # Policy restricted!
        "score": 0.99,
    },
]


def seed_build_atlas(store: Any, atlas_graph: str = GRAPH_ATLAS) -> None:
    """Idempotently seed Software-Build capabilities, technologies, and skills.

    Uses MERGE to preserve existing skill scores and never delete prior records.
    """
    # 1. Seed Capabilities
    for cap in BUILD_CAPABILITIES:
        store.query(
            atlas_graph,
            f"MERGE (c:{LABEL_CAPABILITY} {{name: $name}}) "
            "ON CREATE SET c.description = $desc "
            "ON MATCH SET c.description = $desc",
            {"name": cap.name, "desc": cap.description},
        )

    # 2. Seed Technologies
    for tech in BUILD_TECHNOLOGIES:
        store.query(
            atlas_graph,
            f"MERGE (t:{LABEL_TECHNOLOGY} {{name: $name}}) "
            "ON CREATE SET t.category = $cat "
            "ON MATCH SET t.category = $cat",
            {"name": tech.name, "cat": tech.category},
        )

    # 3. Seed Pack Node
    store.query(
        atlas_graph,
        f"MERGE (p:{LABEL_PACK} {{name: 'build'}}) "
        "ON CREATE SET p.title = 'Software Build', p.description = 'Autonomous fullstack code generator and contract verifier' "
        "ON MATCH SET p.title = 'Software Build', p.description = 'Autonomous fullstack code generator and contract verifier'",
    )

    # 4. Seed Skills, PROVIDES, TARGETS, and IN_PACK edges
    for s in BUILD_SKILLS:
        store.query(
            atlas_graph,
            f"MERGE (sk:{LABEL_SKILL} {{id: $id}}) "
            "ON CREATE SET sk.name = $name, sk.prompt_fragment = $prompt, sk.restricted = $restricted "
            "ON MATCH SET sk.name = $name, sk.prompt_fragment = $prompt, sk.restricted = $restricted",
            {
                "id": s["id"],
                "name": s["name"],
                "prompt": s["prompt_fragment"],
                "restricted": s["restricted"],
            },
        )

        # Link PROVIDES Capability
        for cap_name in s["capabilities"]:
            store.query(
                atlas_graph,
                f"MATCH (sk:{LABEL_SKILL} {{id: $id}}) "
                f"MATCH (c:{LABEL_CAPABILITY} {{name: $cap}}) "
                f"MERGE (sk)-[:{REL_PROVIDES}]->(c)",
                {"id": s["id"], "cap": cap_name},
            )

        # Link TARGETS Technology
        for tech_name in s["targets"]:
            store.query(
                atlas_graph,
                f"MATCH (sk:{LABEL_SKILL} {{id: $id}}) "
                f"MATCH (t:{LABEL_TECHNOLOGY} {{name: $tech}}) "
                f"MERGE (sk)-[:{REL_TARGETS}]->(t)",
                {"id": s["id"], "tech": tech_name},
            )

        # Link IN_PACK Build
        store.query(
            atlas_graph,
            f"MATCH (sk:{LABEL_SKILL} {{id: $id}}) "
            f"MATCH (p:{LABEL_PACK} {{name: 'build'}}) "
            f"MERGE (sk)-[:{REL_IN_PACK}]->(p)",
            {"id": s["id"]},
        )

        # Initial track record score on software_build task type
        store.query(
            atlas_graph,
            f"MATCH (sk:{LABEL_SKILL} {{id: $id}}) "
            "MERGE (tt:TaskType {name: 'software_build'}) "
            f"MERGE (sk)-[r:{REL_SUCCEEDED_ON}]->(tt) "
            "ON CREATE SET r.score = $score, r.runs = 5",
            {"id": s["id"], "score": s["score"]},
        )
