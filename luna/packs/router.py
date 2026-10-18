"""Prompt router — classifies a user prompt to a registered pack.

Routing decision is persisted as a Decision(kind='routing') node in the run graph.

Strategy:
  1. Keyword rules (backend="rules") — fast, deterministic, always available.
  2. LLM classification (backend="llm") — constrained to registered pack names;
     falls back to rules on failure.
  If confidence < ROUTE_MIN_CONF or no pack matches -> needs_input with a clarifying
  question listing available packs.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from luna.packs.base import RoutingDecision
from luna.graph.schema import (
    LABEL_DECISION,
    LABEL_TASK,
    REL_FOR,
)

# Minimum confidence threshold below which we ask a clarifying question
ROUTE_MIN_CONF: float = 0.6

# Keyword signals for each built-in pack
_PACK_KEYWORDS: dict[str, list[str]] = {
    "investigate": [
        "fraud", "connected", "suspicious", "ring", "investigate", "who is",
        "cust-", "cust_", "customer", "bank account", "phone", "network",
        "trace", "link", "related", "flagged", "traversal",
    ],
    "build": [
        "build", "create", "generate", "make", "write code", "scaffold",
        "frontend", "backend", "database", "react", "vite", "express",
        "fastapi", "postgres", "mongodb", "sqlite", "npm", "node",
        "project", "app", "application", "todo", "dashboard", "api",
        "nextjs", "vue", "nestjs", "fastify",
    ],
}


def _keyword_route(prompt: str, registered_names: list[str]) -> RoutingDecision:
    """Fast deterministic keyword-based routing."""
    p = prompt.lower()
    scores: dict[str, int] = {}
    for pack_name, keywords in _PACK_KEYWORDS.items():
        if pack_name not in registered_names:
            continue
        scores[pack_name] = sum(1 for kw in keywords if kw in p)

    if not scores or max(scores.values()) == 0:
        return RoutingDecision(
            pack=None,
            intent="unknown",
            confidence=0.0,
            reasoning="No keyword signals matched any registered pack.",
            backend="rules",
            needs_input=True,
            clarification_question=_clarification_question(registered_names),
        )

    best = max(scores, key=lambda k: scores[k])
    best_count = scores[best]
    total_signals = sum(scores.values())

    # Confidence: ratio of best pack's signals to total signals, floored at 0.5
    if total_signals > 0:
        confidence = 0.5 + 0.5 * (best_count / total_signals)
    else:
        confidence = 0.5

    if confidence < ROUTE_MIN_CONF:
        return RoutingDecision(
            pack=None,
            intent="ambiguous",
            confidence=confidence,
            reasoning=f"Keyword score {confidence:.2f} below threshold {ROUTE_MIN_CONF}. Signals: {scores}",
            backend="rules",
            needs_input=True,
            clarification_question=_clarification_question(registered_names),
        )

    return RoutingDecision(
        pack=best,
        intent=f"{best}_task",
        confidence=round(confidence, 4),
        reasoning=f"Keyword match: {best} scored {best_count} signals out of {total_signals} total. Scores: {scores}",
        backend="rules",
    )


def _llm_route(
    llm: Any,
    prompt: str,
    registered_names: list[str],
) -> Optional[RoutingDecision]:
    """LLM-based routing with constrained output and one repair attempt."""
    pack_list = ", ".join(f'"{n}"' for n in registered_names)
    system = (
        "You are a routing classifier for LUNA OS. "
        f"Classify the user prompt into exactly one of these packs: [{pack_list}]. "
        "Return JSON: {\"pack\": \"<pack_name>\", \"intent\": \"<1-sentence>\", \"confidence\": <0.0-1.0>}. "
        "pack must be one of the listed names exactly. confidence is your certainty."
    )

    schema = {
        "type": "object",
        "properties": {
            "pack": {"type": "string"},
            "intent": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["pack", "intent", "confidence"],
    }

    for attempt in range(2):
        try:
            result = llm.complete(prompt, system=system, json_schema=schema)
            if not isinstance(result, dict):
                continue

            raw_pack = str(result.get("pack", "")).strip().lower()
            if raw_pack not in registered_names:
                # One repair: try substring match
                matched = next((n for n in registered_names if n in raw_pack), None)
                if not matched:
                    continue
                raw_pack = matched

            confidence = float(result.get("confidence", 0.0))
            intent = str(result.get("intent", ""))

            if confidence < ROUTE_MIN_CONF:
                return RoutingDecision(
                    pack=None,
                    intent=intent,
                    confidence=confidence,
                    reasoning=f"LLM confidence {confidence:.2f} below threshold {ROUTE_MIN_CONF}.",
                    backend="llm",
                    needs_input=True,
                    clarification_question=_clarification_question(registered_names),
                )

            return RoutingDecision(
                pack=raw_pack,
                intent=intent,
                confidence=round(confidence, 4),
                reasoning=f"LLM classified prompt as '{raw_pack}' with confidence {confidence:.2f}.",
                backend="llm",
            )

        except Exception:
            if attempt == 1:
                return None
    return None


def _clarification_question(registered_names: list[str]) -> str:
    """Build a consistent clarification question for ambiguous prompts."""
    packs_str = " or ".join(f'"{n}"' for n in registered_names)
    return (
        f"I'm not sure which task type this is. Available packs: {packs_str}. "
        "Could you clarify — are you investigating connected data (fraud, relationships) "
        "or building a software project?"
    )


def route_prompt(
    llm: Any,
    prompt: str,
    registry: Any,  # PackRegistry
    context: Optional[dict[str, Any]] = None,
    run_graph_name: Optional[str] = None,
    store: Optional[Any] = None,
    task_id: Optional[str] = None,
    scripted: bool = False,
    backend: str = "auto",
) -> RoutingDecision:
    """Classify a user prompt to a registered pack and optionally persist the decision.

    Strategy:
      1. Try LLM classification (unless scripted=True or backend="rules", which forces keyword rules).
      2. On LLM failure, fall back to keyword rules (backend remains "rules").
      3. If confidence < ROUTE_MIN_CONF: return needs_input with clarifying question.
      4. Persist Decision(kind='routing') in run graph if store + run_graph_name given.

    Args:
        llm:              LLMClient instance.
        prompt:           Raw user prompt string.
        registry:         PackRegistry instance.
        context:          Optional prior conversation context dict.
        run_graph_name:   Run graph to persist the routing decision.
        store:            GraphStore for persisting the decision.
        task_id:          Task node ID to link Decision-[:FOR]->Task.
        scripted:         If True, skip LLM and use keyword rules only.
        backend:          "auto" (default, LLM first with rules fallback) or "rules" (rules only).

    Returns:
        RoutingDecision with pack name, intent, confidence, backend, and reasoning.
    """
    registered_names = registry.names()
    if not registered_names:
        return RoutingDecision(
            pack=None,
            intent="no_packs",
            confidence=0.0,
            reasoning="No packs are registered in the registry.",
            backend="rules",
            needs_input=True,
            clarification_question="No task packs are available. Please contact the administrator.",
        )

    decision: Optional[RoutingDecision] = None

    if not scripted and backend != "rules" and llm is not None:
        # Attempt LLM routing first
        decision = _llm_route(llm, prompt, registered_names)

    if decision is None:
        # Fallback: deterministic keyword rules
        decision = _keyword_route(prompt, registered_names)

    # Persist to run graph if requested
    if store is not None and run_graph_name and decision is not None:
        _persist_routing_decision(store, run_graph_name, decision, task_id)

    return decision


def persist_routing_decision(
    store: Any,
    run_graph_name: str,
    decision: RoutingDecision,
    task_id: Optional[str] = None,
) -> str:
    """Persist Decision(kind='routing') node and optionally link to Task. Returns dec_id."""
    import uuid as _uuid
    dec_id = f"dec-route-{_uuid.uuid4().hex[:8]}"

    store.query(
        run_graph_name,
        f"MERGE (d:{LABEL_DECISION} {{id: $dec_id}}) "
        "ON CREATE SET d.kind = 'routing', d.pack = $pack, d.intent = $intent, "
        "              d.confidence = $conf, d.backend = $backend, "
        "              d.needs_input = $needs_input, d.reasoning = $reasoning",
        {
            "dec_id": dec_id,
            "pack": decision.pack or "",
            "intent": decision.intent,
            "conf": decision.confidence,
            "backend": decision.backend,
            "needs_input": decision.needs_input,
            "reasoning": decision.reasoning,
        },
    )

    if task_id:
        store.query(
            run_graph_name,
            f"MATCH (d:{LABEL_DECISION} {{id: $dec_id}}) "
            f"MERGE (t:{LABEL_TASK} {{id: $task_id}}) "
            f"MERGE (d)-[:{REL_FOR}]->(t)",
            {"dec_id": dec_id, "task_id": task_id},
        )

    return dec_id


# Alias for backward compatibility
_persist_routing_decision = persist_routing_decision
