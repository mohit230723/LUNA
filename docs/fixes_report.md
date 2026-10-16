# LUNA OS — Hardening Fixes Report

## Phase 3 Rule
> **Rule:** `execute_action` must refuse unless the Action status is `APPROVED`. Headless demo calls `approve_action` with `approver="auto"` explicitly (recorded on the Action); there is no bypass flag.

---

## Fixes Log

| Fix ID | Description | Status | Tests Added | Changes & Verification Notes |
|---|---|---|---|---|
| F10 | Freeze naming contract | DONE | `tests/test_schema_contract.py` | Created `docs/schema.md` detailing exact graph names, labels, relationship types, Finding fields, seeded skill IDs, and plan-to-code mapping. Verified via live FalkorDB test that promoted finding produces exactly {Finding, Agent, Customer, Entity} labels and {PROMOTED_FROM, ASSESSES, SUPPORTED_BY} relationships. |
