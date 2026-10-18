"""Seed the atlas graph with the LUNA Forge build vocabulary."""

from __future__ import annotations

from luna.atlas.models import CapabilityDef
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_CAPABILITY,
    LABEL_TECHNOLOGY,
    REL_BEFORE,
)
from luna.packs.build.seed import BUILD_CAPABILITIES, BUILD_TECHNOLOGIES

STYLE_UI = CapabilityDef(
    name="style_ui",
    description="Apply visual design, theming, and responsive styling to the UI",
)

CAPABILITY_ROLES: dict[str, str] = {
    "scaffold_project": "foundation",
    "implement_database": "normal",
    "implement_backend": "normal",
    "implement_frontend": "normal",
    "style_ui": "normal",
    "verify_contracts": "finalizer",
}

CAPABILITY_ALIASES: dict[str, list[str]] = {
    "scaffold_project": ["scaffold", "setup", "init", "boilerplate"],
    "implement_database": ["database", "db", "schema", "sql", "persistence"],
    "implement_backend": ["backend", "api", "server", "endpoint", "rest"],
    "implement_frontend": [
        "website", "site", "web app", "webapp", "landing page", "page", "pages",
        "frontend", "ui", "portfolio",
    ],
    "style_ui": ["styling", "style", "design", "theme", "css", "tailwind", "responsive"],
    "verify_contracts": ["test", "qa", "verify"],
}

CAPABILITY_ORDER: list[tuple[str, str]] = [
    ("scaffold_project", "implement_database"),
    ("implement_database", "implement_backend"),
    ("implement_backend", "implement_frontend"),
    ("implement_frontend", "verify_contracts"),
    ("scaffold_project", "style_ui"),
    ("style_ui", "verify_contracts"),
]

TECHNOLOGY_ALIASES: dict[str, list[str]] = {
    "React": ["react"],
    "Vite": ["vite"],
    "Next.js": ["next", "nextjs", "next.js"],
    "TailwindCSS": ["tailwind"],
    "FastAPI": ["fastapi"],
    "Express": ["express"],
    "SQLite": ["sqlite"],
    "Postgres": ["postgres", "postgresql"],
    "TypeScript": ["typescript", "ts"],
    "Python": ["python"],
}


def seed_forge_vocabulary(store, atlas_graph: str = GRAPH_ATLAS) -> None:
    """Idempotently MERGE capabilities, technologies, roles, aliases and BEFORE edges."""
    for cap in [*BUILD_CAPABILITIES, STYLE_UI]:
        store.query(
            atlas_graph,
            f"MERGE (c:{LABEL_CAPABILITY} {{name: $name}}) "
            "ON CREATE SET c.description = $desc "
            "SET c.role = $role, c.aliases = $aliases",
            {
                "name": cap.name,
                "desc": cap.description,
                "role": CAPABILITY_ROLES[cap.name],
                "aliases": CAPABILITY_ALIASES[cap.name],
            },
        )

    for tech in BUILD_TECHNOLOGIES:
        store.query(
            atlas_graph,
            f"MERGE (t:{LABEL_TECHNOLOGY} {{name: $name}}) "
            "ON CREATE SET t.category = $cat "
            "SET t.aliases = $aliases",
            {
                "name": tech.name,
                "cat": tech.category,
                "aliases": TECHNOLOGY_ALIASES.get(tech.name, []),
            },
        )

    for src, dst in CAPABILITY_ORDER:
        store.query(
            atlas_graph,
            f"MATCH (a:{LABEL_CAPABILITY} {{name: $src}}) "
            f"MATCH (b:{LABEL_CAPABILITY} {{name: $dst}}) "
            f"MERGE (a)-[:{REL_BEFORE}]->(b)",
            {"src": src, "dst": dst},
        )
