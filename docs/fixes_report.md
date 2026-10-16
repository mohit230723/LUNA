# LUNA OS — Hardening Fixes Report

## Phase 3 Rule
> **Rule:** `execute_action` must refuse unless the Action status is `APPROVED`. Headless demo calls `approve_action` with `approver="auto"` explicitly (recorded on the Action); there is no bypass flag.

---

## Fixes Log

| Fix ID | Description | Status | Tests Added | Changes & Verification Notes |
|---|---|---|---|---|
| F10 | Freeze naming contract | DONE | `tests/test_schema_contract.py` | Created `docs/schema.md` detailing exact graph names, labels, relationship types, Finding fields, seeded skill IDs, and plan-to-code mapping. Verified via live FalkorDB test that promoted finding produces exactly {Finding, Agent, Customer, Entity} labels and {PROMOTED_FROM, ASSESSES, SUPPORTED_BY} relationships. |
| F6 | Split fake-backed and live tests | DONE | `tests/conftest.py`, live tests in `test_atlas`, `test_domain`, `test_slice`, `test_promote`, `test_tools`, `test_planner`, `test_phase2_integration` | Created session fixture `live_store` (skips if unreachable) and `tmp_graph`. Separated pure-logic unit tests (27 tests) from live FalkorDB integration tests (18 tests). Documented `docker compose up -d` workflow in `README.md`. Bug found on live server: `shortest_path` query in `luna/tools/algorithms.py` threw ResponseError `FalkorDB currently only supports shortestPaths in WITH or RETURN clauses`; fixed query to use `WITH shortestPath(...) AS p`. |
