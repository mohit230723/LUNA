"""Graph-native planner: map a build request onto capabilities and assign one skill per task."""

from __future__ import annotations

import re

from luna.forge.models import CandidateRecord, ForgeError, PlanDraft, PlanTask
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_CAPABILITY,
    LABEL_SKILL,
    LABEL_TASK_TYPE,
    LABEL_TECHNOLOGY,
    REL_BEFORE,
    REL_PROVIDES,
    REL_REQUIRES,
    REL_SUCCEEDED_ON,
    REL_TARGETS,
    TASK_TYPE_SOFTWARE_BUILD,
)

__all__ = ["build_plan"]

NEEDS_INPUT_QUESTION = (
    "I couldn't map that request to LUNA's skills. Which of these should I plan for: {names}?"
)


class _Graph:
    """Snapshot of the atlas data the planner needs, loaded with a handful of queries."""

    def __init__(self, store, g: str):
        q = store.query
        self.capabilities: dict[str, dict] = {
            r["name"]: {"role": r.get("role") or "normal", "aliases": list(r.get("aliases") or [])}
            for r in q(g, f"MATCH (c:{LABEL_CAPABILITY}) RETURN c.name AS name, c.role AS role, c.aliases AS aliases")
            if r.get("name")
        }
        self.technologies: dict[str, list[str]] = {
            r["name"]: list(r.get("aliases") or [])
            for r in q(g, f"MATCH (t:{LABEL_TECHNOLOGY}) RETURN t.name AS name, t.aliases AS aliases")
            if r.get("name")
        }
        self.skills: dict[str, dict] = {}
        for r in q(
            g,
            f"MATCH (s:{LABEL_SKILL}) "
            f"OPTIONAL MATCH (s)-[r:{REL_SUCCEEDED_ON}]->(:{LABEL_TASK_TYPE} {{name: $tt}}) "
            "RETURN s.id AS id, s.status AS status, s.restricted AS restricted, r.score AS score",
            {"tt": TASK_TYPE_SOFTWARE_BUILD},
        ):
            if r.get("id"):
                self.skills[r["id"]] = {
                    "status": r.get("status") or "",
                    "restricted": bool(r.get("restricted")),
                    "score": float(r["score"]) if r.get("score") is not None else 0.0,
                }
        self.provides: dict[str, set[str]] = {}  # skill -> capabilities
        self.providers: dict[str, set[str]] = {}  # capability -> skills
        for r in q(g, f"MATCH (s:{LABEL_SKILL})-[:{REL_PROVIDES}]->(c:{LABEL_CAPABILITY}) RETURN s.id AS s, c.name AS c"):
            self.provides.setdefault(r["s"], set()).add(r["c"])
            self.providers.setdefault(r["c"], set()).add(r["s"])
        self.targets: dict[str, set[str]] = {}  # skill -> technologies
        for r in q(g, f"MATCH (s:{LABEL_SKILL})-[:{REL_TARGETS}]->(t:{LABEL_TECHNOLOGY}) RETURN s.id AS s, t.name AS t"):
            self.targets.setdefault(r["s"], set()).add(r["t"])
        self.requires: dict[str, set[str]] = {}
        for r in q(g, f"MATCH (a:{LABEL_SKILL})-[:{REL_REQUIRES}]->(b:{LABEL_SKILL}) RETURN a.id AS a, b.id AS b"):
            self.requires.setdefault(r["a"], set()).add(r["b"])
        self.before: dict[str, set[str]] = {}
        for r in q(g, f"MATCH (a:{LABEL_CAPABILITY})-[:{REL_BEFORE}]->(b:{LABEL_CAPABILITY}) RETURN a.name AS a, b.name AS b"):
            self.before.setdefault(r["a"], set()).add(r["b"])

    def eligible(self, skill_id: str) -> bool:
        s = self.skills.get(skill_id)
        return bool(s) and s["status"] == "approved" and not s["restricted"]

    def reaches(self, src: str, dst: str) -> bool:
        seen, stack = {src}, [src]
        while stack:
            for nxt in self.before.get(stack.pop(), ()):
                if nxt == dst:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return False


def _matches(text: str, terms: list[str]) -> bool:
    return any(t and re.search(r"\b" + re.escape(t.lower()) + r"\b", text) for t in terms)


def _llm_picks(llm, text: str, graph: _Graph) -> tuple[set[str], set[str]]:
    try:
        if llm is None or not llm.info().get("reachable"):
            return set(), set()
        schema = {
            "type": "object",
            "properties": {
                "capabilities": {"type": "array", "items": {"type": "string"}},
                "technologies": {"type": "array", "items": {"type": "string"}},
            },
        }
        system = (
            "Map a software build request onto capabilities and technologies. "
            "Only use names from the provided lists. Return JSON."
        )
        user = (
            f"Request: {text}\n\nCapabilities: {sorted(graph.capabilities)}\n"
            f"Technologies: {sorted(graph.technologies)}"
        )
        out = llm.complete_json(system, user, schema) or {}
        caps = {c.lower(): c for c in graph.capabilities}
        techs = {t.lower(): t for t in graph.technologies}
        picked_caps = {caps[str(c).lower()] for c in out.get("capabilities") or [] if str(c).lower() in caps}
        picked_techs = {techs[str(t).lower()] for t in out.get("technologies") or [] if str(t).lower() in techs}
        return picked_caps, picked_techs
    except Exception:
        return set(), set()


def _assign(graph: _Graph, capability: str, techs: set[str]) -> tuple[str, list[CandidateRecord]]:
    eligible: list[tuple[int, float, str]] = []
    excluded: list[CandidateRecord] = []
    for sid in sorted(graph.providers.get(capability, ())):
        info = graph.skills.get(sid)
        if info is None:
            continue
        overlap = len(graph.targets.get(sid, set()) & techs)
        if graph.eligible(sid):
            eligible.append((overlap, info["score"], sid))
            continue
        if info["restricted"]:
            reason = "restricted"
        elif info["status"] == "rejected":
            reason = "rejected"
        else:
            reason = "pending_review"
        excluded.append(CandidateRecord(skill_id=sid, score=info["score"], overlap=overlap, rejected_reason=reason))
    # Max of (overlap, score); ties go to the lexicographically smallest id.
    eligible.sort(key=lambda c: (-c[0], -c[1], c[2]))
    records = [
        CandidateRecord(skill_id=sid, score=score, overlap=ov, rejected_reason="" if i == 0 else "lower score")
        for i, (ov, score, sid) in enumerate(eligible)
    ]
    return (eligible[0][2] if eligible else ""), records + excluded


def _forced(
    graph: _Graph, capability: str, skill_id: str, required_by: str, techs: set[str]
) -> list[CandidateRecord]:
    """Candidates for a capability pulled in by REQUIRES: the required skill is chosen."""
    _, records = _assign(graph, capability, techs)
    forced = CandidateRecord(
        skill_id=skill_id, score=graph.skills[skill_id]["score"],
        overlap=len(graph.targets.get(skill_id, set()) & techs),
        rejected_reason=f"required by {required_by}",
    )
    others = [
        r.model_copy(update={"rejected_reason": r.rejected_reason or "lower score"})
        for r in records if r.skill_id != skill_id
    ]
    return [forced, *others]


def build_plan(
    store,
    prompt: str,
    stack_hints: list[str] | None = None,
    llm=None,
    atlas_graph: str = GRAPH_ATLAS,
) -> PlanDraft:
    graph = _Graph(store, atlas_graph)
    text = (prompt + " " + " ".join(stack_hints or [])).lower()

    # 1. Match capability / technology names and aliases.
    caps = {c for c, info in graph.capabilities.items() if _matches(text, [c, *info["aliases"]])}
    techs = {t for t, aliases in graph.technologies.items() if _matches(text, [t, *aliases])}
    llm_caps, llm_techs = _llm_picks(llm, text, graph)
    caps |= llm_caps
    techs |= llm_techs

    # 2. Technology-only fallback.
    if not caps and techs:
        for sid, targeted in graph.targets.items():
            if graph.skills.get(sid, {}).get("status") == "approved" and targeted & techs:
                caps |= graph.provides.get(sid, set())

    # 3. No match.
    if not caps:
        return PlanDraft(
            status="needs_input",
            question=NEEDS_INPUT_QUESTION.format(names=", ".join(sorted(graph.capabilities))),
            matched_technologies=sorted(techs),
        )
    matched_caps = sorted(caps)

    # 4. Foundation / finalizer roles with at least one eligible provider.
    for c, info in graph.capabilities.items():
        if info["role"] in ("foundation", "finalizer") and any(
            graph.eligible(s) for s in graph.providers.get(c, ())
        ):
            caps.add(c)

    # 5. Assign one skill per capability.
    assigned: dict[str, str] = {}
    candidates: dict[str, list[CandidateRecord]] = {}
    for c in sorted(caps):
        assigned[c], candidates[c] = _assign(graph, c, techs)

    # 6. Pull in capabilities for required skills until stable. An ineligible
    #    (pending/rejected/restricted) required skill is never forced; its
    #    capability is assigned normally instead.
    changed = True
    while changed:
        changed = False
        for c in sorted(assigned):
            owner = assigned[c]
            for req in sorted(graph.requires.get(owner, ())):
                req_caps = graph.provides.get(req, set())
                if not req_caps or req_caps & assigned.keys():
                    continue
                for rc in sorted(req_caps):
                    if graph.eligible(req):
                        assigned[rc] = req
                        candidates[rc] = _forced(graph, rc, req, owner, techs)
                    else:
                        assigned[rc], candidates[rc] = _assign(graph, rc, techs)
                changed = True

    # 7. Dependencies: BEFORE reachability plus skill REQUIRES.
    skill_task = {}
    for c in sorted(assigned):
        if assigned[c]:
            skill_task.setdefault(assigned[c], c)
    deps: dict[str, set[str]] = {c: set() for c in assigned}
    for a in assigned:
        for b in assigned:
            if a != b and graph.reaches(b, a):
                deps[a].add(b)
        for req in graph.requires.get(assigned[a], ()):
            b = skill_task.get(req)
            if b and b != a:
                deps[a].add(b)

    # 8. Waves via Kahn's algorithm, ties sorted by capability name.
    remaining = {c: set(d) for c, d in deps.items()}
    waves: list[list[str]] = []
    while remaining:
        ready = sorted(c for c, d in remaining.items() if not d)
        if not ready:
            raise ForgeError("invalid", "dependency cycle among: " + ", ".join(sorted(remaining)))
        waves.append(ready)
        for c in ready:
            del remaining[c]
        for d in remaining.values():
            d.difference_update(ready)

    tasks = [
        PlanTask(
            task_id=c,
            title=c.replace("_", " ").capitalize(),
            capability=c,
            skill_id=assigned[c],
            depends_on=sorted(deps[c]),
            wave=i,
        )
        for i, wave in enumerate(waves)
        for c in wave
    ]
    return PlanDraft(
        status="planned",
        matched_capabilities=matched_caps,
        matched_technologies=sorted(techs),
        tasks=tasks,
        waves=waves,
        candidates={c: candidates[c] for c in sorted(candidates)},
    )
