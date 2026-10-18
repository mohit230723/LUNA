# LUNA OS — Frozen Schema Naming Contract

> **Specification Authority:** This document defines the exact frozen naming contract across all FalkorDB graphs, node labels, relationship types, data models, and skill IDs in LUNA OS across both the `investigate` and `software-build` packs.

---

## 1. Graph Names

| Graph Category | Name / Expression | Description |
|---|---|---|
| **Atlas Catalog** | `atlas` | Global catalog of skills, capabilities, tools, packs, technologies, and cross-run learning edges. |
| **Domain Graph** | `domain` | The operational knowledge graph (customers, policies, claims, bank accounts, phones, addresses). |
| **Conversation Memory** | `conversations` | Persistent multi-turn chat threads, user/assistant turns, and run references. |
| **Run Memory** | `run_<id>` | Shared audit memory graph for an active or completed orchestration run (tasks, decisions, steps, components). |
| **Agent Private Slice** | `agent_<run>_<agent>` | Private, isolated k-hop induced subgraph slice extracted for a single agent during an investigation. |

---

## 2. Node Labels and Relationship Types

### 2.1 `atlas` Graph (Global Catalog)
- **Node Labels:**
  - `Skill`
  - `Capability`
  - `Tool`
  - `TaskType`
  - `Pack`
  - `Technology`
- **Relationship Types:**
  - `PROVIDES`: `(:Skill)-[:PROVIDES]->(:Capability)`
  - `REQUIRES`: `(:Skill)-[:REQUIRES]->(:Skill)`
  - `EXPOSES`: `(:Skill)-[:EXPOSES]->(:Tool)`
  - `SUCCEEDED_ON`: `(:Skill)-[:SUCCEEDED_ON {score, runs, last_updated}]->(:TaskType)`
  - `IN_PACK`: `(:Skill)-[:IN_PACK]->(:Pack)`
  - `TARGETS`: `(:Skill)-[:TARGETS]->(:Technology)`

---

### 2.2 `domain` Graph (Operational Data)
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
  - `HAS_POLICY` / `HOLDS`: `(:Customer)-[:HAS_POLICY]->(:Policy)`
  - `HAS_ACCOUNT` / `PAYS_FROM`: `(:Customer)-[:HAS_ACCOUNT]->(:BankAccount)`
  - `HAS_PHONE` / `USES_PHONE`: `(:Customer)-[:HAS_PHONE]->(:Phone)`
  - `LIVES_AT`: `(:Customer)-[:LIVES_AT]->(:Address)`
  - `FILED_CLAIM` / `FILED`: `(:Customer)-[:FILED_CLAIM]->(:InsuranceClaim)`
  - `INVOLVED_VEHICLE`: `(:InsuranceClaim)-[:INVOLVED_VEHICLE]->(:Vehicle)`
  - `TREATED_BY`: `(:InsuranceClaim)-[:TREATED_BY]->(:Provider)`
  - `REPORTED_ACCIDENT`: `(:InsuranceClaim)-[:REPORTED_ACCIDENT]->(:AccidentReport)`
- **Domain Operational Properties:**
  - `Customer.flagged`: boolean indicating operational fraud flag.
  - `Customer.flag_run`: run ID string attributing the flagging execution.
  - `Customer.flagged_at`: ISO 8601 UTC timestamp of execution.

---

### 2.3 `conversations` Graph (Case Workspace & Thread Memory)
- **Node Labels:**
  - `Conversation` (Case root node): `id`, `title`, `status` (`'draft'|'building'|'ready'|'stale'|'failed'`), `context_graph`, `build_error`, `created_at`, `updated_at`.
  - `Source`: Raw user input attached to a case (`id`, `name`, `kind` (`'text'|'csv'|'json'|'jsonl'|'xlsx'|'sqlite'|'txt'|'md'`), `bytes`, `status` (`'pending'|'parsed'|'failed'`), `error`, `stats_json`, `path`).
  - `Turn`: Individual message turn (`id`, `idx`, `role`, `blocks_json`, `run_id`, `created_at`).
  - `RunRef`: Lightweight reference linking an executed run to a turn (`run_id`, `pack`, `status`, `created_at`).
- **Relationship Types:**
  - `HAS_SOURCE`: `(:Conversation)-[:HAS_SOURCE]->(:Source)`
  - `HAS_TURN`: `(:Conversation)-[:HAS_TURN]->(:Turn)`
  - `FOLLOWS`: `(:Turn)-[:FOLLOWS]->(:Turn)` (chronological ordering)
  - `TRIGGERED`: `(:Turn)-[:TRIGGERED]->(:RunRef)`

---

### 2.3.1 `ctx_<conversation_id>` Graphs (Context Knowledge Graphs)
- **Node Labels:**
  - Domain Allowlist: `Person`, `Organization`, `Account`, `Phone`, `Email`, `Address`, `Location`, `Device`, `Transaction`, `Event`, `Document`, `Claim`, `Asset`, `Other`, plus validated PascalCase labels from relational table mappings.
  - Source Node: `Source` (`id`, `name`, `kind`).
- **Node Properties:**
  - `cid`: Canonical unique entity identifier (e.g. `person:alice_moreno-8f2a1b`, `table:1`).
  - `name`: Display name.
  - `type`: High-level entity category.
  - `aliases`: List of alternate resolved string names.
  - `source_ids`: List of source IDs contributing evidence to the node.
  - `confidence`: Confidence score in $[0.0, 1.0]$.
  - `props_json`: Serialized JSON dictionary of scalar attributes (dates, amounts, roles).
- **Relationship Types:**
  - `MENTIONED_IN`: `(:Entity)-[:MENTIONED_IN {locator, quote}]->(:Source)`
  - `POSSIBLY_SAME_AS`: `(:Entity)-[:POSSIBLY_SAME_AS {score}]->(:Entity)` (fuzzy resolution 80-91 score threshold)
  - `REFERENCES_<TABLE>`: Deterministic foreign key pointer between relational table rows.
  - `HAS_<VALUE_LABEL>`: Link to shared normalized value nodes (`Phone`, `Email`, `Address`, `Account`).
  - Extracted Verb Phrases: Parameterized uppercase snake-case relations matching `^[A-Z][A-Z0-9_]{1,40}$` with `{source_id, locator, quote, confidence, method}`.

---

### 2.4 `run_<id>` Graph (Run Audit & Artifact Memory)
- **Node Labels:**
  - `Task`: Root task created for the run (`id`, `prompt`, `status`).
  - `Subtask`: Decomposed subtask (`id`, `kind`, `target_cid`, `component_id`).
  - `Agent`: Assigned subagent worker (`id`, `status`).
  - `SkillRef`: Proxy reference to the skill selected from `atlas` (`id`, `name`).
  - `Decision`: Arbitrated verdict, routing, or skill selection (`id`, `kind`, `chosen_verdict`, etc.).
  - `Finding`: Claim produced by an agent (`id`, `verdict`, `confidence`, `reasoning`).
  - `EvidenceRef` / `Entity`: Proxy node representing corroborated evidence (`cid`, `label`).
  - `TraversalStep`: Step-by-step query hop in the investigation graph (`seq`, `tool`, `from_cid`, `to_cid`, `rel`).
  - `Answer`: Synthesized final answer with anti-hallucination citations (`text`, `backend`, `timestamp`).
  - `Component`: Architectural component in a software build (`id`, `name`, `type`, `technology`, `wave`).
  - `Contract`: Inter-component communication interface (`id`, `kind`, `source`, `target`, `spec`).
  - `Artifact`: Generated source code file (`path`, `component`, `sha256`, `size_bytes`).
  - `Action`: Proposed or executed governance action (`id`, `kind`, `status`, `target_cids`).
  - `Outcome`: Record of execution and evaluation metrics (`id`, `success`, `tp`, `fp`, `fn`, `precision`, `recall`).
- **Relationship Types:**
  - `HAS_SUBTASK`: `(:Task)-[:HAS_SUBTASK]->(:Subtask)`
  - `FOR`: `(:Decision)-[:FOR]->(:Subtask)` or `(:Subtask)-[:FOR]->(:Capability)`
  - `CHOSE`: `(:Decision)-[:CHOSE]->(:SkillRef)`
  - `REJECTED`: `(:Decision)-[:REJECTED {reason}]->(:SkillRef)`
  - `EQUIPPED`: `(:Agent)-[:EQUIPPED]->(:SkillRef)`
  - `PRODUCED_BY` / `PROMOTED_FROM`: `(:Finding)-[:PROMOTED_FROM]->(:Agent)`
  - `ASSESSES`: `(:Finding)-[:ASSESSES]->(:Customer)`
  - `SUPPORTED_BY`: `(:Finding)-[:SUPPORTED_BY]->(:Entity)`
  - `CONFLICTS_WITH`: `(:Finding)-[:CONFLICTS_WITH]->(:Finding)`
  - `SUPERSEDES`: `(:Decision)-[:SUPERSEDES]->(:Finding)`
  - `UPHELD`: `(:Decision)-[:UPHELD]->(:Finding)`
  - `ABOUT`: `(:Decision)-[:ABOUT]->(:Customer)`
  - `HAS_STEP`: `(:Task)-[:HAS_STEP]->(:TraversalStep)`
  - `ANSWERED_BY`: `(:Task)-[:ANSWERED_BY]->(:Answer)`
  - `CITES`: `(:Answer)-[:CITES]->(:Customer)`
  - `HAS_COMPONENT`: `(:Task)-[:HAS_COMPONENT]->(:Component)`
  - `DEPENDS_ON`: `(:Component)-[:DEPENDS_ON]->(:Component)`
  - `CONSUMES`: `(:Component)-[:CONSUMES]->(:Contract)`
  - `PRODUCED`: `(:Component)-[:PRODUCED]->(:Artifact)`
  - `BASED_ON`: `(:Action)-[:BASED_ON]->(:Finding)`
  - `RESULTED_IN`: `(:Action)-[:RESULTED_IN]->(:Outcome)`

---

## 3. Core Data Models

### 3.1 Routing Decision (`luna.packs.base.RoutingDecision`)
| Field | Type | Description |
|---|---|---|
| `pack` | `str` | Destination pack: `"investigate"` or `"software-build"`. |
| `confidence` | `float` | Routing confidence score ($0.0 \dots 1.0$). |
| `reasoning` | `str` | Justification for pack classification. |
| `backend` | `Literal["llm", "rules", "scripted"]` | Origin of the routing classification. |

### 3.2 Traversal Step (`luna.orchestrator.traversal.TraversalStep`)
| Field | Type | Description |
|---|---|---|
| `seq` | `int` | Monotonically increasing sequence index. |
| `tool` | `str` | Tool that executed the traversal hop (e.g., `"trace_connections"`). |
| `agent_id` | `str` | Identifier of the exploring agent. |
| `from_cid` | `str` | Origin entity CID. |
| `to_cid` | `str` | Destination entity CID reached in this hop. |
| `rel` | `str` | Relationship type traversed (e.g., `"HAS_ACCOUNT"`, `"LIVES_AT"`). |
| `note` | `str` | Descriptive rationale for the hop. |

### 3.3 Answer Schema (`luna.orchestrator.traversal.Answer`)
| Field | Type | Description |
|---|---|---|
| `text` | `str` | Human-readable synthesis of the investigation findings. |
| `cited_cids` | `list[str]` | List of verified entity CIDs cited in the answer. |
| `backend` | `str` | Generation engine (`"llm"`, `"scripted"`, `"rules"`). |
| `timestamp` | `str` | ISO 8601 UTC timestamp. |

### 3.4 Component Schema (`luna.packs.build.blueprint.Component`)
| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique component identifier (e.g., `"comp-database"`, `"comp-backend"`). |
| `name` | `str` | Display name of the component. |
| `type` | `str` | Architectural role: `"database"`, `"backend"`, `"frontend"`. |
| `technology` | `str` | Primary framework/language (e.g., `"postgres"`, `"express"`, `"react"`). |
| `dependencies`| `list[str]` | IDs of components that must be built prior to this component. |
| `wave` | `int` | Topological execution wave index ($1, 2, 3$). |

### 3.5 Contract Schema (`luna.packs.build.blueprint.Contract`)
| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique contract identifier (e.g., `"cntr-todos-api"`). |
| `kind` | `str` | Protocol/interface type: `"rest"`, `"graphql"`, `"sql_schema"`, `"env"`. |
| `source` | `str` | Providing component ID. |
| `target` | `str` | Consuming component ID. |
| `endpoints` | `list[dict]` | Specification of HTTP methods, paths, and payload schemas. |

### 3.6 Action Schema (`luna.orchestrator.actions.Action`)
| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique action identifier (`act-...`). |
| `kind` | `str` | Canonical action type: `"flag_for_review"` (investigate) or `"run_build_check"` (build). |
| `target_cids` | `list[str]` | Targeted customer CIDs (for fraud review). |
| `command` | `str \| None`| Gated shell command to execute on approval (for build check). |
| `status` | `str` | `"PENDING"`, `"APPROVED"`, `"REJECTED"`, `"EXECUTING"`, `"EXECUTED"`, `"FAILED"`. |
| `approver` | `str \| None`| Identifying handle of the human or system approver. |

---

## 4. Atlas Seeded Skills Catalog

### 4.1 Investigate Pack Skills
| Skill ID | Capability Provided | Tool Exposed | Default Prior | Status |
|---|---|---|---|---|
| `entity-linker` | `link_entities` | `shared_attribute_links`, `ask_graph` | 0.70 | Production |
| `community-analyzer` | `detect_communities` | `connected_components`, `ask_graph` | 0.80 | Production |
| `centrality-ranker` | `rank_influence` | `pagerank_top`, `ask_graph` | 0.60 | Production |
| `path-tracer` | `explain_connection` | `shortest_path`, `ask_graph` | 0.60 | Production |
| `claim-outlier-detector` | `detect_amount_anomalies` | `claim_amount_outliers`, `ask_graph` | 0.60 | Production |
| `connection-tracer` | `trace_connections` | `trace_connections`, `find_suspect_links` | 0.75 | Production |
| `graph-rag-investigator` | `query_natural_language` | `ask_graph` | 0.65 | Production |
| `bulk-linker` | `link_entities` | None | 0.95 | **Restricted** (Policy Rejection) |

### 4.2 Software-Build Pack Skills
| Skill ID | Capability Provided | Target Technology | Default Prior | Status |
|---|---|---|---|---|
| `react-architect` | `scaffold_component` | `react` | 0.85 | Production |
| `vue-architect` | `scaffold_component` | `vue` | 0.80 | Production |
| `express-router` | `scaffold_component` | `express` | 0.85 | Production |
| `fastapi-builder` | `scaffold_component` | `fastapi` | 0.85 | Production |
| `postgres-designer` | `design_schema` | `postgres` | 0.90 | Production |
| `sqlite-designer` | `design_schema` | `sqlite` | 0.85 | Production |
| `mongo-modeler` | `design_schema` | `mongodb` | 0.75 | Production |
| `api-contractor` | `verify_contract` | `rest` | 0.90 | Production |
| `integration-verifier` | `verify_contract` | `fullstack` | 0.90 | Production |
| `workspace-assembler` | `assemble_workspace` | `any` | 0.90 | Production |
| `shell-runner` | `run_build_check` | `shell` | 0.50 | **Restricted** (Policy Rejection) |
| `tailwind-styler` | `scaffold_component` | `tailwind` | 0.80 | Production |
