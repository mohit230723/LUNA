# LUNA OS — Frozen Schema Naming Contract

> **Specification Authority:** This document defines the exact frozen naming contract across all FalkorDB graphs, node labels, relationship types, data models, and skill IDs in LUNA OS.

---

## 1. Graph Names

| Graph Category | Name / Expression | Description |
|---|---|---|
| **Atlas Catalog** | `atlas` | Global catalog of skills, capabilities, tool exposures, and cross-run learning edges. |
| **Domain Graph** | `domain` | The full operational knowledge graph (customers, policies, claims, accounts, etc.). |
| **Run Memory** | `run_<id>` | Shared audit memory graph for an active or completed orchestration run. |
| **Agent Private Slice** | `agent_<run>_<agent>` | Private, isolated k-hop induced subgraph slice extracted for a single agent. |

---

## 2. Node Labels and Relationship Types

### 2.1 `atlas` Graph
- **Node Labels:**
  - `Skill`
  - `Capability`
  - `Tool`
  - `TaskType`
- **Relationship Types:**
  - `PROVIDES` (`(:Skill)-[:PROVIDES]->(:Capability)`)
  - `REQUIRES` (`(:Skill)-[:REQUIRES]->(:Skill)`)
  - `EXPOSES` (`(:Skill)-[:EXPOSES]->(:Tool)`)
  - `SUCCEEDED_ON` (`(:Skill)-[:SUCCEEDED_ON {score, runs, last_updated}]->(:TaskType)`)

### 2.2 `domain` Graph
- **Node Labels:**
  - `Customer`
  - `Provider`
  - `InsuranceClaim`
  - `Policy`
  - `Vehicle`
  - `BankAccount`
  - `Address`
  - `Phone`
  - `AccidentReport`
- **Relationship Types:**
  - `HAS_POLICY` (`(:Customer)-[:HAS_POLICY]->(:Policy)`)
  - `HAS_ACCOUNT` (`(:Customer)-[:HAS_ACCOUNT]->(:BankAccount)`)
  - `HAS_PHONE` (`(:Customer)-[:HAS_PHONE]->(:Phone)`)
  - `LIVES_AT` (`(:Customer)-[:LIVES_AT]->(:Address)`)
  - `FILED_CLAIM` (`(:Customer)-[:FILED_CLAIM]->(:InsuranceClaim)`)
  - `INVOLVED_VEHICLE` (`(:InsuranceClaim)-[:INVOLVED_VEHICLE]->(:Vehicle)`)
  - `TREATED_BY` (`(:InsuranceClaim)-[:TREATED_BY]->(:Provider)`)
  - `REPORTED_ACCIDENT` (`(:InsuranceClaim)-[:REPORTED_ACCIDENT]->(:AccidentReport)`)
  - Aliases in schema: `HOLDS`, `FILED`, `USES_PHONE`, `PAYS_FROM`
- **Domain Operational Properties:**
  - `Customer.flagged`: boolean indicating operational flag status.
  - `Customer.flag_run`: run ID string attributing the flagging execution.
  - `Customer.flagged_at`: ISO 8601 UTC timestamp of execution.

### 2.3 `run_<id>` Graph
- **Node Labels:**
  - `Task`
  - `Subtask`
  - `Agent`
  - `SkillRef`
  - `Decision`
  - `Finding`
  - `EvidenceRef`
  - `Action`
  - `Outcome`
  - `Customer` (Target proxy)
  - `Entity` (Evidence proxy)
- **Relationship Types:**
  - `PROMOTED_FROM` (`(:Finding)-[:PROMOTED_FROM]->(:Agent)`)
  - `ASSESSES` (`(:Finding)-[:ASSESSES]->(:Customer)`)
  - `SUPPORTED_BY` (`(:Finding)-[:SUPPORTED_BY]->(:Entity)`)
  - `HAS_SUBTASK` (`(:Task)-[:HAS_SUBTASK]->(:Subtask)`)
  - `FOR` (`(:Decision)-[:FOR]->(:Subtask)` / `(:Subtask)-[:FOR]->(:Capability)`)
  - `CHOSE` (`(:Decision)-[:CHOSE]->(:SkillRef)`)
  - `REJECTED` (`(:Decision)-[:REJECTED {reason}]->(:SkillRef)`)
  - `EQUIPPED` (`(:Agent)-[:EQUIPPED]->(:SkillRef)`)
  - `PRODUCED_BY` (`(:Finding)-[:PRODUCED_BY]->(:Agent)`)
  - `CONFLICTS_WITH` (`(:Finding)-[:CONFLICTS_WITH]->(:Finding)`)
  - `SUPERSEDES` (`(:Decision)-[:SUPERSEDES]->(:Finding)`)
  - `UPHELD` (`(:Decision)-[:UPHELD]->(:Finding)`)
  - `ABOUT` (`(:Decision)-[:ABOUT]->(:Customer)`)
  - `BASED_ON` (`(:Action)-[:BASED_ON]->(:Finding)`) — Linked to active suspicious findings on targets; never to Decision.
  - `RESULTED_IN` (`(:Action)-[:RESULTED_IN]->(:Outcome)`)

### 2.4 `agent_<run>_<agent>` (Private Slice)
- Contains an induced subgraph extracted from `domain` using the exact labels and relationships of the extracted neighborhood (`Customer`, `BankAccount`, `Address`, `Phone`, `InsuranceClaim`, etc.).

---

## 3. Core Data Model Schemas

### 3.1 Finding Schema (`luna.agents.models.Finding`)

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique finding identifier (e.g. `find-a1b2c3d4`). |
| `agent_id` | `str` | Identifier of the investigating agent. |
| `skill_id` | `str` | ID of the skill equipped by the agent. |
| `target_cid` | `str` | Unique CID of the target customer/entity being evaluated. |
| `verdict` | `Literal["suspicious", "benign"]` | Evaluation verdict. |
| `confidence` | `float` | Confidence score between `0.0` and `1.0`. |
| `reasoning` | `str` | Text explanation and justification. |
| `evidence_cids` | `list[str]` | List of genuine entity CIDs supporting the verdict. |
| `timestamp` | `str` | UTC timestamp in ISO 8601 format. |
| `backend` | `Literal["llm", "rules", "scripted"]` | Origin of the finding logic (default: `"llm"`). |
| `fallback_reason`| `str \| None` | Short reason if deterministic rules were used (e.g. `"invalid_json"`, `"timeout"`). |

### 3.2 Decision Schema (`luna.orchestrator.resolve.Decision`)

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique decision identifier (e.g. `dec-a1b2c3d4`). |
| `target_cid` | `str` | Target customer CID being arbitrated. |
| `chosen_verdict` | `Literal["suspicious", "benign"]` | Winning verdict for the customer. |
| `confidence` | `float` | Confidence score of the best winning finding. |
| `reasoning` | `str` | Arbitration synthesis and explanation. |
| `winning_finding_id` | `str` | ID of the best winning finding upheld. |
| `superseded_finding_ids` | `list[str]` | IDs of all losing-side findings marked superseded. |
| `resolved_at` | `str` | UTC timestamp in ISO 8601 format. |
| `backend` | `str` | Arbitration engine (`"rule"`). |
| `component_scores` | `str \| None` | JSON string snapshot of side scores and component breakdown. |
| `weights` | `str \| None` | JSON string snapshot of arbitration weights (`w_conf`, `w_evid`, `w_skill`). |
| `skill_scores_json` | `str \| None` | JSON string snapshot of skill scores read prior to learning. |

### 3.3 Action Schema (`luna.orchestrator.actions.Action`)

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique action identifier (e.g. `act-a1b2c3d4`). |
| `kind` | `str` | Canonical action type (`"flag_for_review"`). |
| `action_type` | `str` | Backward-compatible alias for `kind`. |
| `target_cids` | `list[str]` | List of corroborated customer CIDs targeted by the run action. |
| `target_cid` | `str \| None` | Backward-compatible alias for single target customer. |
| `status` | `str` | Execution state: `"PENDING"`, `"APPROVED"`, `"REJECTED"`, `"EXECUTING"`, `"EXECUTED"`, `"FAILED"`. |
| `finding_ids` | `list[str]` | IDs of active suspicious findings supporting this action. |
| `reasoning` | `str` | Rationale for the proposed action. |
| `created_at` | `str` | Creation UTC timestamp in ISO 8601 format. |
| `approved_at` | `str \| None` | Timestamp when approved by human or auto authority. |
| `executed_at` | `str \| None` | Timestamp when domain execution finished. |
| `approver` | `str \| None` | Identifier of approving authority. |
| `rejection_reason` | `str \| None` | Reason provided if action was rejected. |
| `failure_reason` | `str \| None` | Failure exception message if execution failed. |

### 3.4 Outcome Schema & Run Metrics (`luna.orchestrator.actions.Outcome`)

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique outcome identifier (e.g. `out-a1b2c3d4`). |
| `action_id` | `str` | Identifier of executed Action node. |
| `target_cid` | `str` | Primary customer CID target. |
| `target_cids` | `list[str]` | All customer CIDs targeted and mutated. |
| `success` | `bool` | Execution status flag. |
| `details` | `str` | Human-readable outcome description. |
| `recorded_at` | `str` | ISO 8601 UTC timestamp of execution record. |
| `learned` | `bool` | Idempotency flag; `true` once cross-run learner has processed the outcome. |

#### Outcome Graph Node Metrics Properties (Scoped to `flag_run == run_id`)
When evaluated against ground truth, the `Outcome` node stores:
- `tp`: True positive customer count (ring members correctly flagged).
- `fp`: False positive customer count (non-ring customers flagged).
- `fn`: False negative customer count (ring members not flagged).
- `precision`: Precision float score ($tp / (tp + fp)$).
- `recall`: Recall float score ($tp / (tp + fn)$).
- `f1`: Harmonic mean F1 score ($2 \cdot (P \cdot R) / (P + R)$).
*(All metric properties are set to null when evaluation is performed without ground truth).*

---

## 4. Atlas Seeded Skill IDs

| Skill ID | Capability Provided | Tool Exposed | Default Prior | Notes |
|---|---|---|---|---|
| `entity-linker` | `link_entities` | `shared_attribute_links`, `ask_graph` | 0.70 | Base attribute linkage |
| `community-analyzer` | `detect_communities` | `connected_components`, `ask_graph` | 0.80 | Requires `entity-linker` |
| `centrality-ranker` | `rank_influence` | `pagerank_top`, `ask_graph` | 0.60 | PageRank centrality |
| `path-tracer` | `explain_connection` | `shortest_path`, `ask_graph` | 0.60 | Path traversal |
| `claim-outlier-detector` | `detect_amount_anomalies` | `claim_amount_outliers`, `ask_graph` | 0.60 | Claim z-score outliers |
| `graph-rag-investigator` | `query_natural_language`| `ask_graph` | 0.65 | Natural language GraphRAG |
| `bulk-linker` | `link_entities` | None | 0.95 | `restricted=True`, rejected by policy |

---

## 5. Plan-to-Code Name Map

| Plan / Spec Term | Code Implementation Term | Context |
|---|---|---|
| `clean` | `benign` | `Finding.verdict` allowed values: `{"suspicious", "benign"}` |
| `subject_cid` | `target_cid` | `Finding.target_cid` and SubAgent target entities |
| `PRODUCED_BY` | `PROMOTED_FROM` | Edge from promoted `Finding` to `Agent` in `run_<id>` |
| `ring-detector` | `community-analyzer` | Seeded skill ID for community detection |
| `ring-detector-lite` | (Variant) | Lightweight community detection without prerequisites |
| `anomaly-scout` | `claim-outlier-detector` | Seeded skill ID for statistical claim amount outliers |
| `influence-ranker` | `centrality-ranker` | Seeded skill ID for PageRank centrality analysis |
| `path-explainer` | `path-tracer` | Seeded skill ID for shortest path calculation |
