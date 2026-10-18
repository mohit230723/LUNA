"""Scripted smoke test for the LUNA Forge MCP server.

Connects with the real MCP Python client, builds a small site end to end
(plan -> get_skill/submit wave by wave -> assemble) and checks the REST views.
Creates one real run in the running backend. Exits non-zero on failure.

Usage: python scripts/forge_smoke.py [--url http://127.0.0.1:8000/mcp] [--token T]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Implementation

PROMPT = "build me a portfolio website with React"
CLIENT_NAME = "forge-smoke"


def _json(result) -> dict:
    if result.isError:
        raise RuntimeError(result.content[0].text)
    return json.loads(result.content[0].text)


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


async def run(url: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    summary: dict = {}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        info = Implementation(name=CLIENT_NAME, version="0.1")
        async with ClientSession(read, write, client_info=info) as s:
            await s.initialize()
            tools = sorted(t.name for t in (await s.list_tools()).tools)
            _check(len(tools) == 6, f"expected 6 tools, got {tools}")
            prompts = [p.name for p in (await s.list_prompts()).prompts]
            _check("luna-build" in prompts, f"luna-build prompt missing: {prompts}")
            pr = await s.get_prompt("luna-build", {"request": PROMPT})
            _check(PROMPT in pr.messages[0].content.text, "prompt does not embed the request")
            summary["tools"] = tools

            plan = _json(await s.call_tool("luna_plan", {"prompt": PROMPT}))
            _check(plan["status"] == "planned" and plan["run_id"], f"plan failed: {plan}")
            run_id = plan["run_id"]
            summary["run_id"] = run_id
            summary["waves"] = [len(w) for w in plan["waves"]]
            done = 0
            for wave in plan["waves"]:
                for tid in wave:
                    b = _json(await s.call_tool("luna_get_skill", {"run_id": run_id, "task_id": tid}))
                    checks = [{"id": c["id"], "passed": True, "note": ""} for c in b["checklist"]]
                    r = _json(await s.call_tool("luna_submit", {
                        "run_id": run_id, "task_id": tid, "summary": "smoke ok",
                        "files": [f"{tid}.txt"], "checks": checks,
                    }))
                    _check(r["accepted"], f"submit {tid} rejected: {r.get('errors')}")
                    done += 1
            summary["tasks_done"] = done
            rep = _json(await s.call_tool("luna_assemble", {"run_id": run_id}))
            _check(rep["status"] == "complete" and rep["gaps"] == [], f"assemble: {rep}")
            summary["report_status"] = rep["status"]

    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    with httpx.Client(base_url=base, timeout=30) as h:
        conn = h.get("/api/forge/connect").json()
        _check(conn["mcp_url"].endswith("/mcp") and "claude_code" in conn["snippets"], f"connect: {conn}")
        agents = h.get("/api/forge/agents").json()
        _check(any(a.get("client_name") == CLIENT_NAME for a in agents), f"agent not listed: {agents}")
        runs = h.get("/api/forge/runs").json()
        _check(any(r.get("run_id") == run_id for r in runs), "run not listed")
    summary["agent_listed"] = CLIENT_NAME
    summary["run_listed"] = True
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    ap.add_argument("--token", default=os.environ.get("LUNA_MCP_TOKEN", ""))
    args = ap.parse_args()
    try:
        summary = asyncio.run(run(args.url, args.token))
    except BaseException as e:  # noqa: BLE001
        while isinstance(e, BaseExceptionGroup) and e.exceptions:
            e = e.exceptions[0]
        print(f"SMOKE FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print("SMOKE OK")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
