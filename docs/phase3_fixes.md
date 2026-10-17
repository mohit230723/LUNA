# LUNA OS — Phase 3 Hardening Fixes Report

## Hardening Fixes Status

| Fix ID | Description | Status | Tests Added | Implementation Details |
|---|---|---|---|---|
| H1 | CORROBORATION: `CORROBORATION_MIN_SKILLS=2`, `CORROBORATION_CONF=0.8` module constants; customer targeted only if active suspicious findings come from >=2 distinct skill_ids OR best confidence >= 0.8 | DONE | `tests/test_h1_corroboration.py` (4 tests) | Defined constants and `check_corroboration()` helper in `luna/orchestrator/actions.py`. Grouped active suspicious findings per customer in `propose_actions()` and filtered action generation strictly to corroborated targets. Verified lone 0.65 finding is NOT targeted, multi-skill 0.65 IS targeted, single-skill >=0.8 IS targeted, and superseded findings do not corroborate. |
| H2 | PER-CUSTOMER SIDE RESOLUTION: Side scoring $S = 0.5 \cdot \text{conf} + 0.2 \cdot \frac{\min(\text{evid}, 5)}{5} + 0.3 \cdot \text{skill}$; conservative tie-break (benign wins); `ABOUT` edge; snapshot fields on Decision | PENDING | — | — |
| H3 | SINGLE BATCH ACTION: One Action per run `{kind: 'flag_for_review', status, target_cids}`; `BASED_ON` links to active suspicious findings on targets | PENDING | — | — |
| H4 | EXECUTION SAFETY: `NotApprovedError(PermissionError)`; conditional status update (`APPROVED->EXECUTING`); domain `flag_run`; idempotent outcome | PENDING | — | — |
| H5 | RUN-SCOPED METRICS: `evaluate_outcomes` scoped to `c.flag_run == run_id`; metrics on Outcome; `reset_flags(store, domain, run_id=None)` | PENDING | — | — |
| H6 | LEARNER: Outcome-gated (`learned=true`); grades all findings against truth; one EMA per skill; missing skill merged at 0.5 | PENDING | — | — |
| H7 | COMPREHENSIVE TESTS: 3-finding conflict, tie-break, benign clearance, double execution, full demo ring flagging, learner idempotency | PENDING | — | — |
| H8 | CLEANUP: Remove deprecated actions; update `docs/schema.md` and schema tests; precise technical wording | PENDING | — | — |
