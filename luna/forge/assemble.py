"""Deterministic run assembly: merge task results into a report and nudge skill scores."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from luna.atlas.learner import update_skill_score
from luna.forge.models import AssemblyReport
from luna.forge.runs import get_run, set_run_status
from luna.graph.schema import GRAPH_ATLAS, LABEL_RUN, TASK_TYPE_SOFTWARE_BUILD, run_graph_name

__all__ = ["assemble_run"]

LEARNING_ALPHA = 0.2
_SYSTEM = (
    "You summarise the outcome of a multi-task software build. Given a JSON assembly "
    "report, write a short plain-text summary (at most 4 sentences) covering what was "
    "completed, overlapping files and remaining gaps. Do not invent facts."
)


def _template_summary(done: int, total: int, waves: int, n_files: int, n_gaps: int) -> str:
    return (
        f"{done}/{total} tasks complete across {waves} waves; "
        f"{n_files} files reported; {n_gaps} gaps."
    )


LLM_TIMEOUT_S = 10.0
SUMMARY_FLAG = "LUNA_FORGE_LLM_SUMMARY"


def _llm_summary(llm, report: dict) -> str | None:
    """Opt-in LLM summary (env LUNA_FORGE_LLM_SUMMARY=1), bounded to a 10 s call."""
    if llm is None or os.getenv(SUMMARY_FLAG, "").strip() != "1":
        return None
    try:
        if not llm.info().get("reachable"):
            return None
        text = llm.complete_text(_SYSTEM, json.dumps(report, sort_keys=True), timeout=LLM_TIMEOUT_S)
    except Exception:
        return None
    text = (text or "").strip() if isinstance(text, str) else ""
    return text or None


def assemble_run(
    store, run_id: str, llm=None, atlas_graph: str = GRAPH_ATLAS
) -> AssemblyReport:
    view = get_run(store, run_id)
    tasks = sorted(view["tasks"], key=lambda t: t["wave"])  # stable: keeps plan order in a wave

    entries: list[dict] = []
    file_owners: dict[str, set[str]] = {}
    gaps: list[dict] = []
    missing: list[str] = []
    for t in tasks:
        result = t.get("result") or {}
        checks = result.get("checks") or []
        files = list(result.get("files") or [])
        passed = sum(1 for c in checks if c.get("passed"))
        done = t["status"] == "done"
        entries.append(
            {
                "task_id": t["task_id"],
                "wave": t["wave"],
                "skill_id": t["skill_id"],
                "status": t["status"],
                "summary": result.get("summary", ""),
                "files": files,
                "checks_passed": passed,
                "checks_total": len(checks),
            }
        )
        for f in files:
            file_owners.setdefault(f, set()).add(t["task_id"])
        if not t["skill_id"]:
            gaps.append({"task_id": t["task_id"], "kind": "unskilled"})
        failed = [c["id"] for c in checks if not c.get("passed")]
        if failed:
            gaps.append({"task_id": t["task_id"], "kind": "failed_checks", "failed": failed})
        if not done:
            missing.append(t["task_id"])
            gaps.append({"task_id": t["task_id"], "kind": "missing"})

    overlaps = {f: sorted(ids) for f, ids in sorted(file_owners.items()) if len(ids) > 1}
    missing.sort()
    status = "incomplete" if missing else "complete"
    total = len(entries)
    n_waves = len({e["wave"] for e in entries})
    template = _template_summary(total - len(missing), total, n_waves, len(file_owners), len(gaps))

    report = AssemblyReport(
        run_id=run_id, status=status, missing=missing, tasks=entries,
        overlaps=overlaps, gaps=gaps, summary=template,
    )
    llm_text = _llm_summary(llm, report.model_dump())
    if llm_text:
        report.summary = llm_text

    g = run_graph_name(run_id)
    store.query(
        g, f"MATCH (r:{LABEL_RUN}) SET r.report_json = $report",
        {"report": json.dumps(report.model_dump())},
    )

    if status == "complete":
        # Claim learning atomically so concurrent or repeated assembly applies it once.
        claimed = store.query(
            g,
            f"MATCH (r:{LABEL_RUN}) WHERE r.learned_at IS NULL "
            "SET r.learned_at = $ts RETURN r.id AS id",
            {"ts": datetime.now(timezone.utc).isoformat()},
        )
        if claimed:
            try:
                for e in entries:
                    if not e["skill_id"]:
                        continue
                    total_checks = e["checks_total"]
                    reward = e["checks_passed"] / total_checks if total_checks else 1.0
                    update_skill_score(
                        store, e["skill_id"], TASK_TYPE_SOFTWARE_BUILD, reward,
                        LEARNING_ALPHA, atlas_graph,
                    )
            except BaseException:
                # Release the claim so the next assemble retries learning.
                store.query(g, f"MATCH (r:{LABEL_RUN}) REMOVE r.learned_at")
                raise
        set_run_status(store, run_id, "assembled")
    return report
