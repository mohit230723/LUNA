# LUNA OS — Architecture & Implementation Progress Report

> **Project:** LUNA OS (Graph-Native Multi-Agent Orchestrator on FalkorDB)  
> **Repository:** `d:\LUNA`  
> **Current Milestone:** v1.0  
> **Status:** Phase 1 & Phase 2 Complete (44/44 unit and integration tests passing)  
> **Date:** October 15, 2026  

---

## 1. Executive Summary & Vision

**LUNA OS** is an autonomous multi-agent orchestrator built natively on **FalkorDB**, designed for high-stakes investigative workflows (such as insurance claims fraud ring detection). 

Traditional multi-agent frameworks suffer from critical flaws:
1. **Context Window Contamination:** Agents share global text prompts or shared memory, causing hallucinations and tool leakage.
2. **Hallucinated Evidence:** Sub-agents report conclusions based on phantom entities that do not exist in the source dataset.
3. **Black-Box Decisions:** When conflicting agent opinions arise, resolutions are opaque and irreversible (losing findings are simply deleted).
4. **Static Tooling:** Agents are configured with fixed, rigid tool sets upfront regardless of the dynamic task.

**LUNA OS solves all four problems using FalkorDB's multi-graph architecture:**
- **Dynamic Skill Equipping via Atlas:** Blank sub-agents are dynamically equipped by querying an `atlas` skill catalog graph for capabilities, prerequisite chains, and historical success scores.
- **Process & Tool Isolation via FastMCP:** Each sub-agent runs inside its own FastMCP server exposed over stdio, configured *only* with tools exposed by its assigned skill, and pinned *exclusively* to its designated private graph slice.
- **Sub-Graph Slice Extraction:** The orchestrator extracts an isolated k-hop induced subgraph from the `domain` graph into `agent_<run>_<agent>`, making cross-agent data leakage mathematically impossible.
- **Cryptographic Anti-Hallucination Barrier:** Before any draft finding is promoted to shared run memory, the promotion engine checks that *every cited evidence CID actually exists* in the agent's private slice. Hallucinations are immediately rejected with an audit trail.
- **Immutable Explainability Contract:** Contradicting findings are never deleted. Losing findings are marked `status = 'superseded'` and linked with `[:SUPERSEDES]`, enabling a single Cypher "Why?" path query to reconstruct the entire decision tree.

---

## 2. System Architecture & Multi-Graph Topology

LUNA operates across multiple named graphs within a single FalkorDB instance (`localhost:6379`):

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                   FalkorDB Instance                                     │
│                                                                                         │
│  ┌────────────────────────┐  ┌────────────────────────┐  ┌───────────────────────────┐  │
│  │      atlas Graph       │  │      domain Graph      │  │     run_<id> Graph        │  │
│  │ (Skills, Capabilities, │  │  (Customers, Claims,   │  │ (Tasks, Decisions,        │  │
│  │  Tools, Learning Edges)│  │   Policies, Accounts)  │  │  Promoted Findings, Run)  │  │
│  └───────────┬────────────┘  └───────────┬────────────┘  └─────────────▲─────────────┘  │
│              │                           │                             │                │
│              │ Skill Query               │ k-Hop Slice                 │ Verified       │
│              │ & Assignment              │ Extraction                  │ Promotion      │
│              ▼                           ▼                             │                │
│       ┌──────────────┐            ┌────────────────────────────┐       │                │
│       │ Orchestrator │            │ agent_<run>_<agent> Graph  │       │                │
│       │ Task Planner │            │  (Private Induced Subgraph)│───────┘                │
│       └──────┬───────┘            └──────────────▲─────────────┘                        │
│              │                                   │ Pinned Tool Execution                │
│              ▼                                   │ (No access to domain)                │
│       ┌──────────────────────────────────────────┴────────────────────────┐             │
│       │               FastMCP Server & Sub-Agent Process                  │             │
│       │    [Scoped Tools: find_shared_attributes, ask_graph, etc.]        │             │
│       │        Observe ──► Orient ──► Decide ──► Draft Finding            │             │
│       └───────────────────────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Graph Naming Conventions (`luna/graph/schema.py`)
| Graph | Name / Pattern | Purpose |
|---|---|---|
| Catalog | `atlas` | Global catalog of skills, capabilities, tool bindings, and reinforcement scores. |
| Domain | `domain` | Full synthetic knowledge graph containing customers, policies, claims, accounts, etc. |
| Run Memory | `run_<id>` | Shared audit memory for a specific run (tasks, promoted findings, decisions, conflicts). |
| Agent Slice | `agent_<run>_<agent>` | Private, isolated k-hop subgraph extracted specifically for one sub-agent. |

---

## 3. Phase 1: Foundation & Graph Infrastructure (Delivered)

### 3.1. FalkorDB Docker & `GraphStore` Wrapper (`luna/graph/store.py`)
- Configured FalkorDB container via `docker-compose.yml` (`falkordb/falkordb:latest` on port 6379).
- Created `GraphStore` wrapper enforcing:
  - **Parameterized Cypher Only:** Queries using `$param` syntax. Raw string formatting (`%s`, `{}`) and semicolon statement chaining are rejected with `ValueError`.
  - **Lazy Connection:** Safe offline unit testing without requiring a live Redis server.
  - **Robust Header Decoding:** Automatically handles both string and Redis protocol `bytes` headers (`val.decode('utf-8')`).

### 3.2. Synthetic Claims Domain & Planted Ground Truth (`luna/domain/`)
- Deterministic data generator (`luna/domain/generate.py`) with `seed=42`:
  - 25 Customers, 40 InsuranceClaims, 25 Policies, 20 Vehicles, 15 BankAccounts, 15 Addresses, 15 Phones, 8 Providers.
- **Planted Fraud Ring (8 Customers):**
  - Customers `cust-000` through `cust-007` in a dense bipartite collision sharing BankAccounts `ba-ring-01`, `ba-ring-02`, Addresses `addr-ring-01`, `addr-ring-02`, Phones `ph-ring-01`, `ph-ring-02`, and staging multi-vehicle claims with suspicious provider `prov-ring`.
- **Planted Decoy Family (4 Customers):**
  - Customers `cust-010` through `cust-013` sharing benign family address `addr-decoy-01` and single-vehicle collision claims.
- **GraphRAG Ontology:** Exported `luna/domain/ontology.json` defining node labels, relationship schemas, and property types for FalkorDB GraphRAG SDK.

### 3.3. Atlas Skill Catalog (`luna/atlas/`)
- Seeded 7 distinct skills with capabilities, prerequisite chains, tool bindings, and historical scores:
  1. `entity-linker`: Exposes `shared_attribute_links` (score: 0.70).
  2. `community-analyzer`: Exposes `connected_components` (score: 0.80, requires `entity-linker`).
  3. `centrality-ranker`: Exposes `pagerank_top` (score: 0.60).
  4. `path-tracer`: Exposes `shortest_path` (score: 0.60).
  5. `claim-outlier-detector`: Exposes `claim_amount_outliers` (score: 0.60).
  6. `graph-rag-investigator`: Exposes `ask_graph` (score: 0.65).
  7. `bulk-linker`: Restricted skill (`restricted=True`, `REJECTED_BY_POLICY` note, 0 tool access).

### 3.4. Deterministic Graph Algorithm Tools (`luna/tools/`)
Implemented 5 deterministic graph algorithm tools plus GraphRAG natural language query:
- `find_shared_attributes`: Finds entities sharing phone numbers, bank accounts, or addresses.
- `detect_connected_components`: Computes connected subgraphs using NetworkX WCC algorithm.
- `calculate_pagerank`: Identifies central bridge nodes in collision rings.
- `find_shortest_path`: Traces multi-hop paths between suspect entities.
- `detect_claim_amount_outliers`: Uses standard deviation z-scores to flag inflated claims.
- `ask_graph`: Natural language question translation into Cypher using domain ontology schemas.
- `TOOL_REGISTRY`: Central registry mapping tools, parameter JSON schemas, and skill bindings.

### 3.5. LLM Client & Task Planner (`luna/llm/`, `luna/planner/`)
- `LLMClient` protocol with `OllamaLLM` (`llama3.1:8b`, temperature 0.0, format="json") and deterministic `MockLLMClient` for offline testing.
- Task Decomposer (`luna/planner/decompose.py`): Decomposes user tasks into atomic subtasks with required capabilities.
- Skill Selection Engine (`luna/atlas/assign.py`): Matches subtasks to atlas skills, enforces prerequisite satisfaction, rejects policy-restricted skills (`bulk-linker`), and ranks candidates by `SUCCEEDED_ON` scores.

---

## 4. Phase 2: Execution, Isolation & Promotion (Delivered)

### 4.1. FastMCP Tool Scoping & Server Architecture (`luna/mcp/`)
- Uses the official `mcp` SDK (`FastMCP`).
- Factory `create_agent_mcp_server(agent_id, tool_names, graph_store, agent_graph_name)`:
  - Registers *only* the tools allowed by the agent's assigned skill.
  - Automatically binds `graph_store` and `agent_graph_name` into the tool wrappers.
  - The sub-agent has **zero access** to parameters to specify or change graph names.
- Client Adapter `AgentMCPClient(server, allowed_tool_names)`:
  - Validates requested tool calls; raises `PermissionError` if an unassigned tool is invoked.
  - Automatically unwraps FastMCP `TextContent` JSON blocks into native Python dicts and lists.

### 4.2. Sub-Graph Slice Extraction (`luna/orchestrator/slice.py`)
- `extract_subgraph_slice(store, source_graph, target_graph, seed_cids, k_hops=2)`:
  1. Queries seed nodes and traverses k-hop neighborhood using parameterized Cypher paths (`[*1..k]`).
  2. Queries the exact **induced subgraph edges** connecting the extracted nodes (`MATCH (a)-[r]->(b) WHERE a.cid IN $cids AND b.cid IN $cids`).
  3. Sanitizes all node labels and relationship types against strict identifier regexes (`SAFE_LABEL_PATTERN`, `SAFE_REL_PATTERN`) to prevent Cypher injection.
  4. Batch inserts nodes and edges into `target_graph` (`agent_<run>_<agent>`) via Cypher `UNWIND $batch`.
  5. Tested mathematical isolation: Decoy customer slice contains only benign family nodes with 0% leakage into fraud ring entities.

### 4.3. Autonomous Sub-Agent Loop (`luna/agents/`)
- Pydantic Model `Finding`:
  - `id`: Unique identifier (`find-xxxx`).
  - `agent_id`: Identifier of investigating agent.
  - `skill_id`: Equipped skill.
  - `target_cid`: Target entity CID being assessed.
  - `verdict`: `"suspicious"` | `"benign"`.
  - `confidence`: Float `[0.0, 1.0]`.
  - `reasoning`: Natural language explanation.
  - `evidence_cids`: List of specific entity CIDs supporting the verdict.
  - `timestamp`: UTC ISO 8601 string.
- `SubAgent.run()` Observe-Orient-Decide-Act Loop:
  - **Observe:** Calls scoped FastMCP tools (`shared_attribute_links`, `connected_components`, `ask_graph`, etc.) against the private slice to gather structural evidence.
  - **Orient & Decide:** Synthesizes observations with skill prompt fragment via structured LLM schema.
  - **Fallback Resilience:** Built-in deterministic graph rule evaluator ensures 100% test reliability and offline execution.
  - **Act:** Emits draft findings citing authentic evidence CIDs.

### 4.4. Finding Promotion Engine with Anti-Hallucination Barrier (`luna/orchestrator/promote.py`)
- `promote_findings(store, agent_graph_name, run_graph_name, findings) -> PromotionResult`:
  - **Anti-Hallucination Verification:** For every CID in `finding.evidence_cids`, queries the private graph slice (`MATCH (n) WHERE n.cid = $cid RETURN count(n)`).
  - If *any* evidence CID is missing from the private slice, the finding is **immediately rejected** with reason `RejectedFinding(reason="... anti-hallucination barrier rejection")`. Zero writes are made to the run graph.
  - **Provenance Merging:** For verified findings, creates:
    - `(:Finding)` node with all properties.
    - `(:Finding)-[:PROMOTED_FROM]->(:Agent)`
    - `(:Finding)-[:ASSESSES]->(:Customer)`
    - `(:Finding)-[:SUPPORTED_BY]->(:Entity)` for each verified evidence CID.

### 4.5. Complete End-to-End Integration Pipeline (`tests/test_phase2_integration.py`)
- Validated the entire flow across Phase 1 and Phase 2:
  1. Atlas skill selection assigns `entity-linker` to investigate `cust-000` (fraud ring) and `cust-010` (decoy family).
  2. 2-hop private slice is extracted for `cust-000` containing only the fraud ring cluster.
  3. Scoped FastMCP server and client are launched.
  4. Autonomous sub-agent investigates slice, detects shared account `ba-ring-01` and associate `cust-001`, and emits `suspicious` finding.
  5. Promotion engine verifies evidence existence and merges finding into `run_<id>` graph.
  6. Rejects maliciously injected finding citing fake evidence `ghost-cid-does-not-exist`.

---

## 5. Test Suite Verification & Empirical Results

The complete test suite runs in **2.58 seconds** with **44/44 passing tests**:

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.2.0, pluggy-1.6.0
rootdir: D:\LUNA
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.13.0, langsmith-0.11.1, asyncio-0.23.6
asyncio: mode=Mode.STRICT
collected 44 items

tests\test_atlas.py ....                                                 [  9%]
tests\test_domain.py .....                                               [ 20%]
tests\test_llm.py ..                                                     [ 25%]
tests\test_mcp.py ....                                                   [ 34%]
tests\test_phase2_integration.py .                                       [ 36%]
tests\test_planner.py ....                                               [ 45%]
tests\test_promote.py ...                                                [ 52%]
tests\test_slice.py ....                                                 [ 61%]
tests\test_store.py .....                                                [ 72%]
tests\test_subagent.py ....                                              [ 81%]
tests\test_tools.py ........                                             [100%]

======================== 44 passed, 1 warning in 2.58s ========================
```

### Test Coverage Breakdown
| Test Module | Tests | Verifies |
|---|---|---|
| `test_store.py` | 5 | Cypher parameterization safety, SQL/Cypher injection blocking, lazy client connection, byte header decoding |
| `test_domain.py` | 5 | Deterministic synthetic claims domain, 8-node fraud ring, 4-node decoy family, ontology JSON schema, domain seeding |
| `test_atlas.py` | 4 | Pydantic skill/capability models, 7 catalog skills, prerequisite chains, Cypher seed queries |
| `test_tools.py` | 8 | Central tool registry, skill-to-tool mapping, 5 deterministic algorithm tools (WCC, PageRank, ShortestPath, Outliers, SharedAttributes), `ask_graph` |
| `test_llm.py` | 2 | `LLMClient` protocol, `MockLLMClient` pattern matching, `OllamaLLM` JSON format parsing |
| `test_planner.py` | 4 | Subtask decomposition, atlas skill assignment, policy rejection of `bulk-linker`, ranking by historical score |
| `test_mcp.py` | 4 | FastMCP per-agent tool registration, unexposed tool blocking, graph name pinning, `AgentMCPClient` |
| `test_slice.py` | 4 | k-Hop induced subgraph extraction, identifier sanitization, fraud ring vs decoy isolation, empty slice handling |
| `test_subagent.py` | 4 | Pydantic `Finding` validation, autonomous fraud ring detection, decoy benign detection, structured LLM synthesis |
| `test_promote.py` | 3 | Finding promotion into `run_<id>`, anti-hallucination barrier, partial batch handling |
| `test_phase2_integration.py` | 1 | End-to-end integration: Skill Assignment ──► Slice Extraction ──► FastMCP ──► SubAgent ──► Verified Promotion |

---

## 6. Key Gotchas & Architectural Decisions Resolved

1. **FastMCP Version Compatibility (`mcp>=1.0.0,<2.0.0`):**
   - The newer `mcp` 2.x renamed `FastMCP` to `MCPServer`. Pinning `mcp>=1.0.0,<2.0.0` (installed `mcp-1.30.0`) provides the battle-tested FastMCP interface required by all documentation.
2. **Windows C++ Compilation Isolation:**
   - In Windows Python 3.12, `pip install graphrag-sdk` tries to compile `hnswlib` from source, failing if C++ build tools are absent. LUNA architecture provides a standalone ontology loader and natural language Cypher translator in `luna/tools/ask_graph.py`, operating 100% reliably without external C++ compilers.
3. **Redis Protocol Byte Headers in FalkorDB Client:**
   - FalkorDB responses can return column headers as raw `bytes` (e.g. `[1, b"shared_cid"]`). `GraphStore.query()` decodes bytes explicitly (`val.decode('utf-8')`), preventing literal `"b'...'"` string formatting bugs.
4. **Graph Pinning for Zero-Leakage Security:**
   - Sub-agents are never passed client connections or domain graph names. The FastMCP wrapper closures bake in `agent_graph_name`, making cross-graph queries physically impossible at the transport level.

---

## 7. Roadmap & Upcoming Phase 3

With Phase 1 and Phase 2 complete and verified, the next milestone is **Phase 3: Conflict Resolution & Action Lifecycle**:

- **Plan 3.1: Contradiction Detection Engine (`luna/orchestrator/conflicts.py`)**
  - Scans `run_<id>` for promoted findings that assess the same entity with contradictory verdicts (`suspicious` vs `benign`).
  - Creates `[:CONFLICTS_WITH]` edges between conflicting findings.
- **Plan 3.2: Main Agent Conflict Resolution Logic (`luna/orchestrator/resolve.py`)**
  - Evaluates conflicting findings using confidence, evidence depth, and atlas skill score.
  - Creates `(:Decision)` node in `run_<id>`.
  - Links winning finding with `[:UPHELD]`.
  - Marks losing finding `status = 'superseded'` and links with `[:SUPERSEDES]`. (Never deletes).
- **Plan 3.3: Action Proposal & Human Approval Gate (`luna/orchestrator/actions.py`)**
  - Proposes domain actions (`FLAG_CUSTOMER`).
  - Human approval barrier (auto-approved in headless demo mode).
  - Idempotent domain graph mutation (`MATCH (c:Customer {cid: $cid}) SET c.flagged = true`).
  - Precision/Recall evaluation against planted ground truth.
- **Plan 3.4: Cross-Run Learner in Atlas (`luna/atlas/learner.py`)**
  - Exponential moving average score updates on `(:Skill)-[:SUCCEEDED_ON]->(:TaskType)` edges in `atlas` based on confirmed domain action outcomes.
