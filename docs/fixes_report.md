# LUNA OS — Hardening Fixes Report

## Phase 3 Rule
> **Rule:** `execute_action` must refuse unless the Action status is `APPROVED`. Headless demo calls `approve_action` with `approver="auto"` explicitly (recorded on the Action); there is no bypass flag.

---

## Fixes Log

| Fix ID | Description | Status | Tests Added | Changes & Verification Notes |
|---|---|---|---|---|
| F10 | Freeze naming contract | DONE | `tests/test_schema_contract.py` | Created `docs/schema.md` detailing exact graph names, labels, relationship types, Finding fields, seeded skill IDs, and plan-to-code mapping. Verified via live FalkorDB test that promoted finding produces exactly {Finding, Agent, Customer, Entity} labels and {PROMOTED_FROM, ASSESSES, SUPPORTED_BY} relationships. |
| F6 | Split fake-backed and live tests | DONE | `tests/conftest.py`, live tests in `test_atlas`, `test_domain`, `test_slice`, `test_promote`, `test_tools`, `test_planner`, `test_phase2_integration` | Created session fixture `live_store` (skips if unreachable) and `tmp_graph`. Separated pure-logic unit tests (27 tests) from live FalkorDB integration tests (18 tests). Documented `docker compose up -d` workflow in `README.md`. Bug found on live server: `shortest_path` query in `luna/tools/algorithms.py` threw ResponseError `FalkorDB currently only supports shortestPaths in WITH or RETURN clauses`; fixed query to use `WITH shortestPath(...) AS p`. |
| F1 | Read-only guard for ask_graph | DONE | `tests/test_cypher_guard.py` (11 tests: 10 unit + 1 integration) | Created `luna/tools/cypher_guard.py` with `UnsafeCypherError` and `validate_read_only`. Enforces single statement, blocks mutating keywords (CREATE, MERGE, SET, DELETE, DETACH, REMOVE, DROP, LOAD, FOREACH, CALL) outside string literals, and enforces/lowers LIMIT to max_rows. Added `GraphStore.read_query` using FalkorDB's native `ro_query` (FalkorDB `GRAPH.RO_QUERY`). Updated `ask_graph` to validate read-only and return `{"error": "unsafe_query"}` on violation. Verified pinned graph scoping on MCP wrapper. |
| F2 | Stronger provenance in promotion | DONE | `tests/test_provenance.py` (6 tests: 1 unit + 5 integration) | Created `luna/agents/provenance.py` with `ToolCallLog` recording tool outputs and extracting nested strings via `observed_strings()`. Wired `SubAgent` to record all tool calls into `self.tool_log`. Extended `promote_findings` with `observed: set[str] | None`, `require_observed: bool`, and `max_hops: int | None`. Enforces check order: 1) existence in slice (`evidence_not_in_slice`), 2) observation in tool outputs (`evidence_not_observed`, target CID exempt), 3) connectivity within max_hops via shortestPath (`evidence_not_connected`). Wired `test_phase2_integration.py` with `observed=tool_log.observed_strings(), require_observed=True, max_hops=3`. |
