"""BuildPack — autonomous fullstack code generator and contract verifier conforming to Pack protocol."""

from __future__ import annotations

from typing import Any, Optional

from luna.packs.base import Pack, PackPipeline, Understanding
from luna.packs.build.seed import seed_build_atlas, BUILD_CAPABILITIES
from luna.packs.build.understand import understand_build_prompt
from luna.packs.build.pipeline import BuildPipeline, BuildPipelineConfig
from luna.graph.schema import GRAPH_ATLAS


class BuildPack:
    """Software-Build pack: decomposes fullstack requirements, generates contracts, and verifies code."""

    name: str = "build"
    title: str = "Software Build"
    description: str = (
        "Autonomous fullstack code generation: constructs contract DAGs, "
        "assigns technology-specialized skills, builds isolated components in waves, "
        "and deterministically verifies routes, fetches, and schemas."
    )
    example_prompts: list[str] = [
        "Build a fullstack todo app with React frontend, Express backend, and Postgres database",
        "Create an analytics dashboard with Next.js and SQLite",
        "Build a chat service with FastAPI backend and MongoDB",
    ]
    capabilities: list[str] = [c.name for c in BUILD_CAPABILITIES]

    def seed_atlas(self, store: Any, atlas_graph: str = GRAPH_ATLAS) -> None:
        """Seed build skills, capabilities, and technologies into the atlas graph."""
        seed_build_atlas(store, atlas_graph)

    def seed_data(self, store: Any, domain_graph: str) -> None:
        """Domain graph seeding is not required for the software-build pack."""
        pass

    def understand(
        self,
        llm: Any,
        prompt: str,
        context: Optional[dict[str, Any]] = None,
    ) -> Understanding:
        """Parse build prompt into project requirements and validate tech stack."""
        return understand_build_prompt(llm, prompt, context)

    def build_pipeline(self, store: Any, config: Any) -> PackPipeline:
        """Build and return a runnable BuildPipeline instance."""
        if not isinstance(config, BuildPipelineConfig):
            b_cfg = BuildPipelineConfig(
                run_id=getattr(config, "run_id", "build_run"),
                atlas_graph=getattr(config, "atlas_graph", GRAPH_ATLAS),
                event_callback=getattr(config, "event_callback", None),
            )
        else:
            b_cfg = config
        return BuildPipeline(store, b_cfg)
