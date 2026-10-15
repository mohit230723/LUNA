# SPEC.md — Project Specification

> **Status**: `FINALIZED`
>
> ⚠️ **Planning Lock**: No code may be written until this spec is marked `FINALIZED`.

## Vision

LUNA OS is a graph-native multi-agent orchestrator built on FalkorDB where a main orchestrator agent equips blank sub-agents by querying an `atlas` skill graph, sub-agents explore connected datasets within private graph slices using the FalkorDB GraphRAG SDK and deterministic graph algorithm tools, validated findings are promoted into a shared run memory graph with automated conflict detection and resolution, actions require human approval before idempotent domain mutation, and every decision is fully traceable via graph-native "Why?" path queries rendered in an interactive Hyperstudio/Obsidian-aesthetic dashboard.

## Goals

1. **Graph-Native Dynamic Skill Assignment** — Blank sub-agents are equipped at runtime by querying the `atlas` skill graph based on task decomposition, recording selected skills and explicit rejection reasons.
2. **Isolated Private Graph Slices & GraphRAG Exploration** — Sub-agents investigate private domain graph slices (`agent_<run>_<agent>`) using deterministic graph algorithms (PageRank, connected components, shortest path, outlier detection) and the FalkorDB GraphRAG SDK (`ask_graph`) without contaminating shared memory or other agents' views.
3. **Validated Promotion & Conflict Resolution** — The orchestrator validates reported evidence against an agent's private slice, promotes findings to the shared `run_<id>` graph, detects contradictions (`CONFLICTS_WITH`), and performs transparent conflict resolution where superseded findings are preserved for auditability.
4. **Human-in-the-Loop Action Execution & Cross-Run Learning** — High-stakes actions require human approval before idempotent domain mutation; execution outcomes update skill track records in the atlas graph (`SUCCEEDED_ON`), creating cross-run memory.
5. **Full Explainability via "Why?" Path Queries** — The entire decision chain (`Action` ← `Finding` ← `EvidenceRef`, plus skill selection and conflict resolution) is queryable with a single Cypher path query and visualized in an interactive graph dashboard.

## Non-Goals (Out of Scope for Core v1.0)

- **Tribunal Multi-Agent Debate** — Prosecutor, Defender, and Judge adversarial loop is reserved for v2.0 (hooks retained in schema).
- **Counterfactual Graph Forks** — What-if graph simulation branches are reserved for v2.0 (retaining `GraphStore.copy` hook).
- **Self-Growing Dynamic Skills** — Autonomous LLM generation of new skills is out of scope; skills are curated in `atlas`.
- **Multi-Tenancy & Production Auth** — Single-user developer workstation architecture with local FalkorDB and Ollama.
- **Real Customer / Production Data** — Strictly synthetic datasets with mathematically seeded ground truth.

## Users

- **AI & Graph Engineers** building explainable agentic workflows on top of knowledge graphs.
- **Fraud & Risk Analysts** investigating complex entity clusters requiring verifiable audit trails.
- **Hackathon Judges & Evaluators** assessing graph-native context management, multi-agent coordination, and FalkorDB capabilities.

## Constraints

- **Hackathon Deadline**: Submissions close **October 18, 2026 at 11:59 PM IST (GMT+5:30)**.
- **Single Graph Engine**: FalkorDB (port 6379) is the sole graph store. All cross-graph operations are explicit orchestrator logic.
- **Query Safety**: Cypher queries must be 100% parameterized (`$param`). No string interpolation. Graph names and labels strictly defined in `luna/graph/schema.py`.
- **Execution & Language**: Python 3.11+, package name `luna`.
- **LLM Layer**: Ollama local inference running `llama3.1:8b` via LangChain `ChatOllama` behind an `LLMClient` protocol with deterministic mock fallback for offline tests.
- **Tool Scoping**: Tool access strictly controlled via the official `mcp` Python SDK (FastMCP + stdio client) exposing only equipped skills.
- **UI Design System**: React + Vite + Cytoscape.js adhering to the Hyperstudio/Obsidian aesthetic (dark mode `#0d0d0f`, `#16161a`, Satoshi + IBM Plex Mono typography, neon accent edges).

## Success Criteria

- [ ] Synthetic insurance claims domain graph (~300 customers, 8 ring members, 4 decoy members) generated with deterministic ground truth.
- [ ] Atlas skill catalog seeded with 7 skills, capabilities, dependencies, and 6 tools (`ask_graph` + 5 deterministic algorithms).
- [ ] Sub-agent equipped with `ring-detector` identifies fraud ring, while over-eager `entity-linker` false positive on decoy family is flagged as `CONFLICTS_WITH`.
- [ ] Main agent resolves contradiction, superseding the false positive while preserving history.
- [ ] Human approval gate halts execution until explicitly confirmed; action execution flags exactly the 8 planted fraud ring members (100% precision & recall) while leaving the decoy family untouched.
- [ ] Skill performance score `SUCCEEDED_ON` updates in `atlas` upon successful action outcome.
- [ ] Graph-native "Why?" path query executes in <50ms and visualizes complete justification trace in the Cytoscape.js dashboard.
- [ ] Full end-to-end run completes in under ~90 seconds with local Ollama, with an automated test suite passing in CI.

## User Stories

### As a Fraud Analyst
- I want to submit an investigation task to LUNA OS and inspect the sub-agent breakdown.
- So that I can verify which specialized skills were selected or rejected before execution.

### As a Compliance Auditor
- I want to query the exact "Why?" chain from any flagged customer back to original claims, shared attributes, agent findings, and skill decisions.
- So that every automated action is completely explainable, defensible, and transparent.

### As an AI Architect
- I want agents to work in isolated private graph slices rather than directly modifying production data.
- So that hallucinations or flawed reasoning cannot corrupt the shared domain state or mislead other agents.

## Technical Requirements

| Requirement | Priority | Notes |
|-------------|----------|-------|
| FalkorDB Docker Compose & GraphStore | Must-have | Connection management, parameterized queries, copy & delete |
| Domain Generator & GraphRAG Ontology | Must-have | Synthetic claims generator with ring/decoy labels & ontology JSON |
| Atlas Catalog Seeding | Must-have | 7 skills, capabilities, tool mappings, initial scores |
| Tool Registry & GraphRAG SDK ask_graph | Must-have | PageRank, WCC, Shortest Path, Outliers, Shared Links + NL→Cypher |
| Ollama LLMClient & Mock Fallback | Must-have | `ChatOllama` wrapper with structured output and testing mocks |
| Task Decomposer & Skill Matcher | Must-have | Graph-driven skill query with explicit rejection logging |
| Per-Agent FastMCP Server | Must-have | Dynamic tool isolation via stdio transport |
| Private Slice Extraction & Agent Runner | Must-have | k-hop neighborhood copy into `agent_<run>_<agent>` graph |
| Finding Promotion & Evidence Validator | Must-have | Promotes draft findings to `run_<id>` after verifying evidence cids |
| Conflict Detector & Resolution Engine | Must-have | Generates `CONFLICTS_WITH`, updates finding status to `superseded` |
| Human Approval & Cross-Run Learner | Must-have | Action gate, idempotent domain tagging, `SUCCEEDED_ON` score update |
| Why? Path Query Engine | Must-have | Cypher traversal returning full decision graph |
| FastAPI Backend & SSE Streamer | Must-have | Real-time orchestrator state broadcast |
| Cytoscape.js Obsidian-Themed Dashboard | Must-have | Dark glassmorphism UI with interactive graph inspection |

---

*Last updated: 2026-10-15*
