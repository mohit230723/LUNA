"""End-to-end check of the Cases flow over the REST API: create case -> ingest text -> build graph -> ask.

Usage: python scripts/check_cases_flow.py [--url http://127.0.0.1:8000] [--file demo/silverline_brief.txt]
       [--question "..."] [--timeout 300]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx


def sse(client: httpx.Client, url: str, timeout: float):
    """Yield (event_type, data_dict) from a Server-Sent Events stream until it closes."""
    deadline = time.time() + timeout
    with client.stream("GET", url, timeout=timeout) as resp:
        resp.raise_for_status()
        etype, data = "message", ""
        for line in resp.iter_lines():
            if time.time() > deadline:
                raise TimeoutError(f"stream {url} exceeded {timeout}s")
            if line.startswith("event:"):
                etype = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
            elif line == "" and data:
                try:
                    yield etype, json.loads(data)
                except json.JSONDecodeError:
                    yield etype, {"raw": data}
                etype, data = "message", ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--file", default="demo/silverline_brief.txt")
    ap.add_argument("--question", default="Who is connected to account ACC-9821 and how are they linked to Apex Holdings?")
    ap.add_argument("--timeout", type=float, default=300)
    a = ap.parse_args()
    c = httpx.Client(base_url=a.url, timeout=60)
    t0 = time.time()

    health = c.get("/api/health").json()
    print("health:", health)
    cid = c.post("/api/chat/conversations").json()["id"]
    print("case:", cid)
    text = Path(a.file).read_text(encoding="utf-8")
    c.post(f"/api/chat/conversations/{cid}/sources/text", json={"name": Path(a.file).name, "text": text}).raise_for_status()
    b = c.post(f"/api/chat/conversations/{cid}/build", json={"acknowledge_remote": True})
    b.raise_for_status()
    build_id = b.json()["build_id"]
    for et, d in sse(c, f"/api/chat/conversations/{cid}/build/{build_id}/events", a.timeout):
        print(f"  build[{time.time() - t0:5.1f}s] {et}: {json.dumps(d)[:160]}")
        if et in ("ready", "done", "complete", "failed", "error"):
            break
    case = c.get(f"/api/chat/conversations/{cid}").json()
    print("case status:", case.get("status"), "stats:", json.dumps(case.get("stats"))[:200])
    if case.get("status") != "ready":
        print("BUILD FAILED"); return 1

    m = c.post(f"/api/chat/conversations/{cid}/messages", json={"content": a.question, "options": {}})
    m.raise_for_status()
    run_id = m.json()["run_id"]
    answer = None
    for et, d in sse(c, f"/api/runs/{run_id}/events", a.timeout):
        print(f"  run[{time.time() - t0:5.1f}s] {et}: {json.dumps(d)[:160]}")
        if et in ("answer", "answer_ready"):
            answer = d
        if et in ("completed", "complete", "done", "failed", "cancelled", "needs_input"):
            break
    print("\nANSWER:", json.dumps(answer, indent=2)[:1500] if answer else None)
    print(f"total {time.time() - t0:.1f}s")
    return 0 if answer else 1


if __name__ == "__main__":
    sys.exit(main())
