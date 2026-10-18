"""Forge run persistence and task lifecycle: create, claim with lease, submit, expire.

Each run lives in its own FalkorDB graph (``run_graph_name(run_id)``) holding
``Run``, ``Task``, ``Assignment``, ``Candidate`` and ``Result`` nodes. A small
``ForgeRun`` row per run is kept in ``GRAPH_FORGE_INDEX`` for listing; it is
also the existence check, so lookups of unknown runs never create empty graphs.

Unskilled tasks (``skill_id == ""``) get no ``Assignment`` node.
Timestamps are ISO-8601 UTC strings; ``""`` means "unset".
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from luna.forge.models import CheckReport, ForgeError, Plan, PlanDraft, PlanTask, SubmitResult
from luna.graph.schema import (
    GRAPH_ATLAS,
    GRAPH_FORGE_INDEX,
    LABEL_ASSIGNMENT,
    LABEL_CANDIDATE,
    LABEL_CHECKLIST_ITEM,
    LABEL_FORGE_RUN,
    LABEL_RESULT,
    LABEL_RUN,
    LABEL_SKILL,
    LABEL_TASK,
    REL_ASSIGNED,
    REL_CONSIDERED,
    REL_DEPENDS_ON,
    REL_HAS_CHECK,
    REL_HAS_RESULT,
    REL_PART_OF,
    run_graph_name,
)

__all__ = [
    "claim_task",
    "create_run",
    "expire_leases",
    "get_run",
    "list_runs",
    "read_results",
    "read_task",
    "set_run_status",
    "skill_checklist",
    "submit_task",
]

DEFAULT_LEASE_MIN = 15
MAX_SUMMARY_CHARS = 20_000
MAX_FILES = 500
MAX_PATH_CHARS = 300
_DRIVE = re.compile(r"^[A-Za-z]:")


def _now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _lease_minutes(lease_minutes: int | None) -> int:
    if lease_minutes is not None:
        return int(lease_minutes)
    try:
        return int(os.environ.get("LUNA_FORGE_LEASE_MIN", DEFAULT_LEASE_MIN))
    except ValueError:
        return DEFAULT_LEASE_MIN


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    return _now(datetime.fromisoformat(value))


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def _require_run(store, run_id: str) -> dict:
    rows = store.query(
        GRAPH_FORGE_INDEX,
        f"MATCH (f:{LABEL_FORGE_RUN} {{run_id: $id}}) RETURN f",
        {"id": run_id},
    )
    if not rows:
        raise ForgeError("not_found", f"run '{run_id}' not found")
    return rows[0]["f"]


def _tasks(store, run_id: str) -> dict[str, dict]:
    rows = store.query(run_graph_name(run_id), f"MATCH (t:{LABEL_TASK}) RETURN t")
    tasks = {r["t"]["id"]: r["t"] for r in rows}
    return dict(sorted(tasks.items(), key=lambda kv: (kv[1].get("order", 0), kv[0])))


def _to_plan_task(t: dict) -> PlanTask:
    return PlanTask(
        task_id=t["id"],
        title=t.get("title") or "",
        capability=t.get("capability") or "",
        skill_id=t.get("skill_id") or "",
        depends_on=list(t.get("depends_on") or []),
        wave=int(t.get("wave") or 0),
        status=t.get("status") or "pending",
    )


def read_task(store, run_id: str, task_id: str) -> PlanTask:
    """Return one task of an existing run, raising ``not_found`` for unknown ids."""
    _require_run(store, run_id)
    t = _tasks(store, run_id).get(task_id)
    if t is None:
        raise ForgeError("not_found", f"task '{task_id}' not found in run '{run_id}'")
    return _to_plan_task(t)


def read_results(store, run_id: str) -> dict[str, dict]:
    """Submitted results keyed by task id (no lease expiry, no existence check)."""
    results: dict[str, dict] = {}
    for r in store.query(
        run_graph_name(run_id),
        f"MATCH (t:{LABEL_TASK})-[:{REL_HAS_RESULT}]->(x:{LABEL_RESULT}) RETURN t.id AS id, x",
    ):
        x = r["x"]
        results[r["id"]] = {
            "summary": x.get("summary", ""),
            "files": list(x.get("files") or []),
            "checks": json.loads(x.get("checks_json") or "[]"),
            "submitted_at": x.get("submitted_at", ""),
            "session_id": x.get("session_id", ""),
        }
    return results


def skill_checklist(store, skill_id: str, atlas_graph: str = GRAPH_ATLAS) -> list[dict]:
    """Checklist items (``id``, ``text``) of a skill in order; empty for ``""``."""
    if not skill_id:
        return []
    rows = store.query(
        atlas_graph,
        f"MATCH (s:{LABEL_SKILL} {{id: $id}})-[:{REL_HAS_CHECK}]->(c:{LABEL_CHECKLIST_ITEM}) "
        "WHERE s.source IS NOT NULL "
        "RETURN c.check_id AS id, c.text AS text, c.order AS ord ORDER BY ord",
        {"id": skill_id},
    )
    return [{"id": r["id"], "text": r.get("text") or ""} for r in rows]


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_run(
    store,
    draft: PlanDraft,
    prompt: str,
    session_id: str,
    run_id: str | None = None,
    now: datetime | None = None,
) -> Plan:
    run_id = run_id or uuid.uuid4().hex[:12]
    ts = _now(now).isoformat()
    exists = store.query(
        GRAPH_FORGE_INDEX,
        f"MATCH (f:{LABEL_FORGE_RUN} {{run_id: $id}}) RETURN f.run_id AS id",
        {"id": run_id},
    )
    if exists:
        raise ForgeError("invalid", f"run '{run_id}' already exists")

    g = run_graph_name(run_id)
    status = draft.status
    store.query(
        g,
        f"CREATE (:{LABEL_RUN} {{id: $id, prompt: $prompt, status: $status, "
        "agent_session: $session, created_at: $ts, question: $question})",
        {
            "id": run_id, "prompt": prompt, "status": status, "session": session_id,
            "ts": ts, "question": draft.question,
        },
    )

    tasks: list[PlanTask] = []
    for order, t in enumerate(draft.tasks):
        task = t.model_copy(update={"status": "ready" if t.wave == 0 else "pending"})
        tasks.append(task)
        store.query(
            g,
            f"MATCH (r:{LABEL_RUN} {{id: $run}}) "
            f"CREATE (t:{LABEL_TASK} {{id: $id, title: $title, capability: $cap, skill_id: $skill, "
            "wave: $wave, status: $status, depends_on: $deps, order: $ord, claimed_by: '', "
            "agent_label: '', lease_expires_at: ''})"
            f"-[:{REL_PART_OF}]->(r)",
            {
                "run": run_id, "id": task.task_id, "title": task.title, "cap": task.capability,
                "skill": task.skill_id, "wave": task.wave, "status": task.status,
                "deps": list(task.depends_on), "ord": order,
            },
        )

        records = draft.candidates.get(task.capability, [])
        chosen = next((c for c in records if task.skill_id and c.skill_id == task.skill_id), None)
        if task.skill_id:
            store.query(
                g,
                f"MATCH (t:{LABEL_TASK} {{id: $id}}) "
                f"CREATE (t)-[:{REL_ASSIGNED}]->(:{LABEL_ASSIGNMENT} "
                "{skill_id: $skill, score: $score, overlap: $overlap, reason: $reason})",
                {
                    "id": task.task_id, "skill": task.skill_id,
                    "score": chosen.score if chosen else 0.0,
                    "overlap": chosen.overlap if chosen else 0,
                    "reason": (chosen.rejected_reason if chosen and chosen.rejected_reason else "best match"),
                },
            )
        for c in records:
            if task.skill_id and c.skill_id == task.skill_id:
                continue
            store.query(
                g,
                f"MATCH (t:{LABEL_TASK} {{id: $id}}) "
                f"CREATE (t)-[:{REL_CONSIDERED}]->(:{LABEL_CANDIDATE} "
                "{skill_id: $skill, score: $score, overlap: $overlap, rejected_reason: $reason})",
                {
                    "id": task.task_id, "skill": c.skill_id, "score": c.score,
                    "overlap": c.overlap, "reason": c.rejected_reason,
                },
            )

    for task in tasks:
        for dep in task.depends_on:
            store.query(
                g,
                f"MATCH (a:{LABEL_TASK} {{id: $a}}), (b:{LABEL_TASK} {{id: $b}}) "
                f"CREATE (a)-[:{REL_DEPENDS_ON}]->(b)",
                {"a": task.task_id, "b": dep},
            )

    store.query(
        GRAPH_FORGE_INDEX,
        f"CREATE (:{LABEL_FORGE_RUN} {{run_id: $id, prompt: $prompt, status: $status, "
        "created_at: $ts, task_count: $n})",
        {"id": run_id, "prompt": prompt, "status": status, "ts": ts, "n": len(tasks)},
    )
    return Plan(
        run_id=run_id, status=status, question=draft.question, tasks=tasks, waves=draft.waves
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def expire_leases(store, run_id: str, now: datetime | None = None) -> list[str]:
    """Return claimed tasks whose lease has passed to ``ready``; return their ids."""
    _require_run(store, run_id)
    current = _now(now)
    g = run_graph_name(run_id)
    expired: list[str] = []
    for tid, t in _tasks(store, run_id).items():
        if t.get("status") != "claimed":
            continue
        lease = _parse_ts(t.get("lease_expires_at") or "")
        if lease is not None and lease > current:
            continue
        rows = store.query(
            g,
            f"MATCH (t:{LABEL_TASK} {{id: $id}}) "
            "WHERE t.status = 'claimed' AND t.lease_expires_at = $lease "
            "SET t.status = 'ready', t.claimed_by = '', t.agent_label = '', t.lease_expires_at = '' "
            "RETURN t.id AS id",
            {"id": tid, "lease": t.get("lease_expires_at") or ""},
        )
        if rows:
            expired.append(tid)
    return expired


def claim_task(
    store,
    run_id: str,
    task_id: str,
    session_id: str,
    agent_label: str = "",
    lease_minutes: int | None = None,
    now: datetime | None = None,
) -> PlanTask:
    current = _now(now)
    expire_leases(store, run_id, now=current)
    tasks = _tasks(store, run_id)
    t = tasks.get(task_id)
    if t is None:
        raise ForgeError("not_found", f"task '{task_id}' not found in run '{run_id}'")

    status = t.get("status")
    if status == "claimed" and t.get("claimed_by") != session_id:
        raise ForgeError(
            "claim_conflict",
            f"task '{task_id}' is claimed by another session until {t.get('lease_expires_at')}",
        )
    if status == "pending":
        blockers = [
            f"{d} ({tasks[d].get('status') if d in tasks else 'missing'})"
            for d in t.get("depends_on") or []
            if d not in tasks or tasks[d].get("status") != "done"
        ]
        if blockers:
            raise ForgeError("not_ready", f"task '{task_id}' is waiting on: {', '.join(blockers)}")
        # Every dependency is done but no submit promoted it (lost race): claim it
        # directly; the conditional write below matches on status 'pending'.
    if status not in ("ready", "claimed", "pending"):
        raise ForgeError("invalid", f"task '{task_id}' is already {status}")

    lease = (current + timedelta(minutes=_lease_minutes(lease_minutes))).isoformat()
    # Conditional write: only succeeds if nobody changed the task since we read it.
    rows = store.query(
        run_graph_name(run_id),
        f"MATCH (t:{LABEL_TASK} {{id: $id}}) "
        "WHERE t.status = $status AND t.claimed_by = $prev "
        "SET t.status = 'claimed', t.claimed_by = $sid, t.agent_label = $label, "
        "t.lease_expires_at = $lease, t.claimed_at = $ts "
        "RETURN t",
        {
            "id": task_id, "status": status, "prev": t.get("claimed_by") or "",
            "sid": session_id, "label": agent_label or (t.get("agent_label") or ""),
            "lease": lease, "ts": current.isoformat(),
        },
    )
    if not rows:
        latest = _tasks(store, run_id).get(task_id) or {}
        raise ForgeError(
            "claim_conflict",
            f"task '{task_id}' is claimed by another session until {latest.get('lease_expires_at', '')}",
        )
    return _to_plan_task(rows[0]["t"])


def _validate_submission(
    summary: str, files: list[str], checks: list[CheckReport], known_checks: list[str]
) -> list[str]:
    errors: list[str] = []
    if len(summary) > MAX_SUMMARY_CHARS:
        errors.append(f"summary exceeds {MAX_SUMMARY_CHARS} characters")
    if len(files) > MAX_FILES:
        errors.append(f"at most {MAX_FILES} files allowed, got {len(files)}")
    else:
        for p in files:
            parts = re.split(r"[\\/]", p) if isinstance(p, str) else []
            if isinstance(p, str) and len(p) > MAX_PATH_CHARS:
                errors.append(f"invalid path '{p[:40]}...': exceeds {MAX_PATH_CHARS} characters")
            elif (
                not isinstance(p, str)
                or not p.strip()
                or p.startswith(("/", "\\"))
                or _DRIVE.match(p)
                or ".." in parts
                or "\x00" in p
            ):
                errors.append(f"invalid path '{p}': use a relative path without '..'")
    seen: set[str] = set()
    for c in checks:
        if c.id not in known_checks:
            errors.append(f"unknown check '{c.id}'")
        elif c.id in seen:
            errors.append(f"duplicate check '{c.id}'")
        seen.add(c.id)
    return errors


def submit_task(
    store,
    run_id: str,
    task_id: str,
    session_id: str,
    summary: str,
    files: list[str],
    checks: list[CheckReport],
    atlas_graph: str = GRAPH_ATLAS,
    now: datetime | None = None,
) -> SubmitResult:
    """Record a task result.

    Leases are not expired here: a session still holding its claim may submit
    late as long as no expiry pass has released the task.
    """
    current = _now(now)
    _require_run(store, run_id)
    tasks = _tasks(store, run_id)
    t = tasks.get(task_id)
    if t is None:
        raise ForgeError("not_found", f"task '{task_id}' not found in run '{run_id}'")
    if t.get("status") != "claimed" or t.get("claimed_by") != session_id:
        raise ForgeError("invalid", f"task '{task_id}' is not claimed by this session")

    checklist = skill_checklist(store, t.get("skill_id") or "", atlas_graph)
    known = [c["id"] for c in checklist]
    errors = _validate_submission(summary, files, checks, known)
    if errors:
        return SubmitResult(accepted=False, errors=errors)

    reported = {c.id: c for c in checks}
    stored_checks = [
        {"id": cid, "passed": reported[cid].passed, "note": reported[cid].note}
        if cid in reported
        else {"id": cid, "passed": False, "note": "not reported"}
        for cid in known
    ]
    g = run_graph_name(run_id)
    rows = store.query(
        g,
        f"MATCH (t:{LABEL_TASK} {{id: $id}}) "
        "WHERE t.status = 'claimed' AND t.claimed_by = $sid "
        "SET t.status = 'done', t.lease_expires_at = '', t.done_at = $ts "
        f"CREATE (t)-[:{REL_HAS_RESULT}]->(:{LABEL_RESULT} "
        "{summary: $summary, files: $files, checks_json: $checks, submitted_at: $ts, session_id: $sid}) "
        "RETURN t.id AS id",
        {
            "id": task_id, "sid": session_id, "ts": current.isoformat(), "summary": summary,
            "files": list(files), "checks": json.dumps(stored_checks),
        },
    )
    if not rows:
        raise ForgeError("invalid", f"task '{task_id}' is not claimed by this session")

    # Re-read after our write so a concurrent submit of a sibling dependency
    # (which read a stale snapshot) cannot leave a dependent stuck in pending.
    tasks = _tasks(store, run_id)
    unlocked: list[str] = []
    for tid, other in tasks.items():
        if other.get("status") != "pending":
            continue
        deps = other.get("depends_on") or []
        if all(tasks.get(d, {}).get("status") == "done" for d in deps):
            moved = store.query(
                g,
                f"MATCH (t:{LABEL_TASK} {{id: $id}}) WHERE t.status = 'pending' "
                "SET t.status = 'ready' RETURN t.id AS id",
                {"id": tid},
            )
            if moved:
                unlocked.append(tid)
    return SubmitResult(accepted=True, unlocked_tasks=sorted(unlocked))


# ---------------------------------------------------------------------------
# Run views
# ---------------------------------------------------------------------------


def get_run(store, run_id: str, now: datetime | None = None) -> dict:
    expire_leases(store, run_id, now=now)
    g = run_graph_name(run_id)
    run_rows = store.query(g, f"MATCH (r:{LABEL_RUN}) RETURN r")
    run = dict(run_rows[0]["r"]) if run_rows else {}
    report_json = run.pop("report_json", None)
    run_view = {"run_id": run.pop("id", run_id), **run}

    assignments = {
        r["id"]: r["a"]
        for r in store.query(
            g, f"MATCH (t:{LABEL_TASK})-[:{REL_ASSIGNED}]->(a:{LABEL_ASSIGNMENT}) RETURN t.id AS id, a"
        )
    }
    candidates: dict[str, list[dict]] = {}
    for r in store.query(
        g,
        f"MATCH (t:{LABEL_TASK})-[:{REL_CONSIDERED}]->(c:{LABEL_CANDIDATE}) RETURN t.id AS id, c",
    ):
        candidates.setdefault(r["id"], []).append(r["c"])
    results = read_results(store, run_id)

    tasks = []
    for tid, t in _tasks(store, run_id).items():
        pt = _to_plan_task(t)
        cands = sorted(
            candidates.get(tid, []), key=lambda c: (-(c.get("overlap") or 0), -(c.get("score") or 0.0), c.get("skill_id", ""))
        )
        tasks.append(
            {
                **pt.model_dump(),
                "claimed_by": t.get("claimed_by") or "",
                "agent_label": t.get("agent_label") or "",
                "lease_expires_at": t.get("lease_expires_at") or "",
                "assignment": assignments.get(tid),
                "candidates": cands,
                "result": results.get(tid),
            }
        )
    return {
        "run": run_view,
        "tasks": tasks,
        "report": json.loads(report_json) if report_json else None,
    }


def list_runs(store, limit: int = 50) -> list[dict]:
    rows = store.query(
        GRAPH_FORGE_INDEX,
        f"MATCH (f:{LABEL_FORGE_RUN}) RETURN f.run_id AS run_id, f.prompt AS prompt, "
        "f.status AS status, f.created_at AS created_at, f.task_count AS task_count "
        "ORDER BY created_at DESC, run_id DESC LIMIT $limit",
        {"limit": max(0, int(limit))},
    )
    return [dict(r) for r in rows]


def set_run_status(store, run_id: str, status: str) -> None:
    _require_run(store, run_id)
    store.query(
        run_graph_name(run_id), f"MATCH (r:{LABEL_RUN}) SET r.status = $status", {"status": status}
    )
    store.query(
        GRAPH_FORGE_INDEX,
        f"MATCH (f:{LABEL_FORGE_RUN} {{run_id: $id}}) SET f.status = $status",
        {"id": run_id, "status": status},
    )
