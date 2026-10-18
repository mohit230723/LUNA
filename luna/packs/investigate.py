"""InvestigatePack — wraps the existing fraud LunaPipeline as a first-class Pack.

This is a thin wrapper: it does NOT rewrite the existing pipeline code.
All investigation logic stays in luna/orchestrator/pipeline.py.
"""

from __future__ import annotations

from typing import Any, Optional

from luna.packs.base import Pack, PackPipeline, Understanding
from luna.graph.schema import GRAPH_ATLAS
from luna.atlas.seed import seed_atlas as _seed_atlas


_INVESTIGATE_CAPABILITIES = [
    "link_entities",
    "detect_communities",
    "rank_influence",
    "explain_connection",
    "detect_amount_anomalies",
    "trace_connections",
]

_INVESTIGATE_KEYWORDS = [
    "fraud", "connected", "ring", "suspicious", "who is", "cust-", "cust_",
    "investigate", "flagged", "bank account", "phone", "network",
    "trace", "link", "related", "customer",
]


class InvestigatePack:
    """Investigate pack: connected-data traversal and fraud ring detection."""

    name: str = "investigate"
    title: str = "Investigate"
    description: str = (
        "Connected-data investigation: traverse the fraud graph, identify rings, "
        "arbitrate conflicting evidence, and return a cited answer with traversal path."
    )
    example_prompts: list[str] = [
        "Who is connected to the fraud involving customer cust-000?",
        "Which customers share a bank account with cust-ring-01?",
        "Is cust-003 part of the same fraud ring?",
    ]
    capabilities: list[str] = _INVESTIGATE_CAPABILITIES

    def seed_atlas(self, store: Any, atlas_graph: str = GRAPH_ATLAS) -> None:
        """Idempotently seed investigate pack skills using existing atlas seed logic.

        Uses MERGE semantics via the existing seed_atlas helper so scores are
        preserved across repeated seeding calls.
        """
        # The existing seed_atlas DELETEs and recreates.  To make it idempotent
        # we check whether the skills already exist and only seed if the atlas
        # is empty, matching the existing test patterns.
        existing = store.query(atlas_graph, "MATCH (s:Skill) RETURN count(s) AS n")
        if existing and int(existing[0].get("n", 0)) > 0:
            return  # Already seeded; skip to preserve scores
        _seed_atlas(store, atlas_graph)

    def seed_data(self, store: Any, domain_graph: str) -> None:
        """Seed domain fraud graph. Delegates to existing luna.domain.seed.seed_domain."""
        from luna.domain.seed import seed_domain
        seed_domain(store, domain_graph)

    def understand(
        self,
        llm: Any,
        prompt: str,
        context: Optional[dict[str, Any]] = None,
    ) -> Understanding:
        """Parse investigate prompt into structured understanding.

        Classifies question into:
          - who_connected
          - is_suspicious
          - list_ring
          - path_between
          - other
        """
        import re

        p_lower = prompt.lower()

        # Classify question type
        if "path between" in p_lower or "path from" in p_lower or "shortest path" in p_lower:
            question_type = "path_between"
        elif "who is" in p_lower or "who's" in p_lower or "who connected" in p_lower or "connected to" in p_lower:
            question_type = "who_connected"
        elif "is " in p_lower and ("suspicious" in p_lower or "part of" in p_lower or "involved" in p_lower):
            question_type = "is_suspicious"
        elif "ring" in p_lower or "share" in p_lower or "which customer" in p_lower or "list" in p_lower:
            question_type = "list_ring"
        elif any(kw in p_lower for kw in _INVESTIGATE_KEYWORDS):
            question_type = "who_connected"
        else:
            question_type = "other"

        # Extract cust-* and cust_* identifiers (including multi-part like cust-ring-01)
        entities = re.findall(r"cust(?:[-_][a-z0-9]+)+", prompt, re.IGNORECASE)
        entities = list(dict.fromkeys(entities))  # dedup, preserve order

        # Pull prior entities from conversation context for follow-ups (D3)
        if context:
            prior_entities = context.get("entities", [])
            for e in prior_entities:
                if e not in entities:
                    entities.append(e)

        # Check if prompt refers to an unknown customer when known_cids is provided in context
        known_cids = context.get("known_cids") if context else None
        if known_cids and entities:
            unknown = [e for e in entities if e not in known_cids]
            if unknown:
                sample_known = ", ".join(list(known_cids)[:4])
                return Understanding(
                    question_type=question_type,
                    entities=entities,
                    needs_input=True,
                    clarification_question=(
                        f"Customer '{unknown[0]}' was not found in the claims database. "
                        f"Did you mean one of the known customers: {sample_known}?"
                    ),
                    context_run_id=context.get("run_id") if context else None,
                )

        return Understanding(
            question_type=question_type,
            entities=entities,
            needs_input=False,
            context_run_id=context.get("run_id") if context else None,
        )

    def build_pipeline(self, store: Any, config: Any) -> PackPipeline:
        """Wrap the existing LunaPipeline for investigate tasks."""
        from luna.orchestrator.pipeline import LunaPipeline
        return LunaPipeline(store, config)
