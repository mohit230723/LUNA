"""PackRegistry — a thread-safe catalog of registered packs, seeded into the atlas graph."""

from __future__ import annotations

import threading
from typing import Any, Optional

from luna.packs.base import Pack
from luna.graph.schema import (
    LABEL_PACK,
    LABEL_SKILL,
    REL_IN_PACK,
)


class PackRegistry:
    """Thread-safe registry of registered Pack instances.

    Usage:
        registry = PackRegistry()
        registry.register(InvestigatePack())
        registry.register(BuildPack())
        pack = registry.get("investigate")
    """

    def __init__(self) -> None:
        self._packs: dict[str, Pack] = {}
        self._lock = threading.Lock()

    def register(self, pack: Pack) -> None:
        """Register a pack under its canonical name. Idempotent (last write wins)."""
        with self._lock:
            self._packs[pack.name] = pack

    def get(self, name: str) -> Optional[Pack]:
        """Return a registered pack by name, or None."""
        with self._lock:
            return self._packs.get(name)

    def list(self) -> list[Pack]:
        """Return a snapshot list of all registered packs."""
        with self._lock:
            return list(self._packs.values())

    def names(self) -> list[str]:
        """Return sorted list of registered pack names."""
        with self._lock:
            return sorted(self._packs.keys())

    def seed_all_atlas(self, store: Any, atlas_graph: str) -> None:
        """Idempotently seed every registered pack's skills into the atlas graph.

        Also persists Pack nodes and Skill-[:IN_PACK]->Pack edges so the router
        and UI can query pack membership directly from the graph.
        """
        for pack in self.list():
            pack.seed_atlas(store, atlas_graph)
            _persist_pack_node(store, atlas_graph, pack)

    def seed_all_data(self, store: Any, domain_graph: str) -> None:
        """Seed domain data for packs that support it (investigate only)."""
        for pack in self.list():
            if hasattr(pack, "seed_data") and callable(pack.seed_data):
                pack.seed_data(store, domain_graph)


def _persist_pack_node(store: Any, atlas_graph: str, pack: Pack) -> None:
    """Persist a Pack node and link its owned capabilities' skills via IN_PACK edges."""
    # Upsert the Pack node
    store.query(
        atlas_graph,
        f"MERGE (p:{LABEL_PACK} {{name: $name}}) "
        "ON CREATE SET p.title = $title, p.description = $description "
        "ON MATCH SET p.title = $title, p.description = $description",
        {
            "name": pack.name,
            "title": pack.title,
            "description": pack.description,
        },
    )

    # Link every skill that provides one of this pack's capabilities via IN_PACK
    for cap in pack.capabilities:
        store.query(
            atlas_graph,
            f"MATCH (s:{LABEL_SKILL})-[:PROVIDES]->(c:Capability {{name: $cap}}) "
            f"MATCH (p:{LABEL_PACK} {{name: $pack_name}}) "
            f"MERGE (s)-[:{REL_IN_PACK}]->(p)",
            {"cap": cap, "pack_name": pack.name},
        )


def default_registry() -> PackRegistry:
    """Build and return the default production registry with investigate and build packs.

    Import is deferred to avoid circular imports when either pack isn't available yet.
    """
    registry = PackRegistry()
    try:
        from luna.packs.investigate import InvestigatePack
        registry.register(InvestigatePack())
    except ImportError:
        pass

    try:
        from luna.packs.build.pack import BuildPack
        registry.register(BuildPack())
    except ImportError:
        pass

    return registry
