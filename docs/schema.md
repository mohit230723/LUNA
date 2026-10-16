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
  - `FOR` (`(:Subtask)-[:FOR]->(:Capability)`)
  - `CHOSE` (`(:Subtask)-[:CHOSE]->(:SkillRef)`)
  - `REJECTED` (`(:Subtask)-[:REJECTED]->(:SkillRef)`)
  - `EQUIPPED` (`(:Agent)-[:EQUIPPED]->(:SkillRef)`)
  - `PRODUCED_BY` (`(:Finding)-[:PRODUCED_BY]->(:Agent)`)
  - `CONFLICTS_WITH` (`(:Finding)-[:CONFLICTS_WITH]->(:Finding)`)
  - `SUPERSEDES` (`(:Decision)-[:SUPERSEDES]->(:Finding)`)
  - `UPHELD` (`(:Decision)-[:UPHELD]->(:Finding)`)
  - `BASED_ON` (`(:Action)-[:BASED_ON]->(:Decision)`)
  - `RESULTED_IN` (`(:Action)-[:RESULTED_IN]->(:Outcome)`)

### 2.4 `agent_<run>_<agent>` (Private Slice)
- Contains an induced subgraph extracted from `domain` using the exact labels and relationships of the extracted neighborhood (`Customer`, `BankAccount`, `Address`, `Phone`, `InsuranceClaim`, etc.).

---

## 3. Finding Data Model Schema (`luna.agents.models.Finding`)

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique finding identifier (e.g. `find-a1b2c3d4`). |
| `agent_id` | `str` | Identifier of the investigating agent. |
| `skill_id` | `str` | ID of the skill equipped by the agent. |
| `target_cid` | `str` | Unique CID of the target customer/entity being evaluated. |
| `verdict` | `Literal["suspicious", "benign"]` | Evaluation verdict. |
| `confidence` | `float` | Confidence score between `0.0` and `1.0`. |
| `reasoning` | `str` | Free-text explanation and justification. |
| `evidence_cids` | `list[str]` | List of genuine entity CIDs supporting the verdict. |
| `timestamp` | `str` | UTC timestamp in ISO 8601 format. |
| `backend` | `Literal["llm", "rules", "scripted"]` | Origin of the finding logic (default: `"llm"`). |
| `fallback_reason`| `str \| None` | Short reason if deterministic rules were used (e.g. `"invalid_json"`, `"timeout"`). |

---

## 4. Atlas Seeded Skill IDs

| Skill ID | Capability Provided | Tool Exposed | Default Score | Notes |
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

Where early plan/spec drafts used alternate names, this table documents the definitive mappings in active code:

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
