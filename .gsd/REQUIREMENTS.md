---
milestone: v1.0
updated: 2026-10-15T22:15:00+05:30
---

# Requirements

## Overview

Requirements derived from `SPEC.md` for full traceability, test verification, and phase coverage tracking in LUNA OS.

---

## Functional Requirements

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-01 | **FalkorDB GraphStore**: Multi-graph connection manager supporting parameterized queries, graph isolation, clone, and teardown. | SPEC Goal 1, 2 | 1 | Pending |
| REQ-02 | **Synthetic Domain Generator**: Generates ~300 customers, claims, policies, providers, with 1 planted fraud ring (8 members) and 1 decoy family (4 members) with known ground truth. | SPEC Goal 2 | 1 | Pending |
| REQ-03 | **Domain Ontology**: Export domain schema to JSON ontology compatible with FalkorDB GraphRAG SDK. | SPEC Goal 2 | 1 | Pending |
| REQ-04 | **Atlas Catalog Seeding**: Seed `atlas` graph with Capabilities, Skills, Tools, TaskTypes, prerequisite edges, and initial track record scores. | SPEC Goal 1 | 1 | Pending |
| REQ-05 | **Graph Algorithm Tools**: 5 deterministic Cypher/Python tools (`shared_attribute_links`, `connected_components`, `pagerank_top`, `shortest_path`, `claim_amount_outliers`). | SPEC Goal 2 | 1 | Pending |
| REQ-06 | **GraphRAG ask_graph Tool**: NL→Cypher querying tool powered by FalkorDB GraphRAG SDK against target graph. | SPEC Goal 2 | 1 | Pending |
| REQ-07 | **LLMClient Protocol & Ollama Provider**: Unified LLM client abstraction supporting LangChain `ChatOllama` (`llama3.1:8b`) with JSON output and deterministic `MockLLMClient` for tests. | SPEC Goal 1, 3 | 1 | Pending |
| REQ-08 | **Task Decomposition & Skill Selection**: Main agent decomposes tasks into subtasks and queries `atlas` to assign best skills while logging chosen and rejected candidates. | SPEC Goal 1 | 1 | Pending |
| REQ-09 | **Per-Agent FastMCP Server**: Spawns isolated FastMCP server over stdio exposing strictly the tools registered to the agent's equipped skill. | SPEC Goal 1, 2 | 2 | Pending |
| REQ-10 | **Sub-Graph Slice Extraction**: Extracts k-hop neighborhood from `domain` and clones nodes/edges into private `agent_<run>_<agent>` graph. | SPEC Goal 2 | 2 | Pending |
| REQ-11 | **Sub-Agent Execution Loop**: Blank agent equipped with prompt fragment and MCP client executes investigation in private slice and drafts findings. | SPEC Goal 2 | 2 | Pending |
| REQ-12 | **Finding Promotion & Validation**: Validates that evidence `cid`s exist in agent's private slice before promoting findings into shared `run_<id>` graph. | SPEC Goal 3 | 2 | Pending |
| REQ-13 | **Contradiction Detection**: Detects contradictory verdicts on the same subject node and links them with `[:CONFLICTS_WITH]`. | SPEC Goal 3 | 3 | Pending |
| REQ-14 | **Conflict Resolution**: Main agent evaluates conflicting findings, records decision, and marks losing findings as `superseded` via `[:SUPERSEDES]`. | SPEC Goal 3 | 3 | Pending |
| REQ-15 | **Human Approval Gate & Action Execution**: Generates proposed Action, halts for human approval, executes idempotent domain tagging, and records Outcome. | SPEC Goal 4 | 3 | Pending |
| REQ-16 | **Cross-Run Learning**: Successful action outcome increments `SUCCEEDED_ON` score in `atlas` graph, updating future skill selection probabilities. | SPEC Goal 4 | 3 | Pending |
| REQ-17 | **Why? Path Query Engine**: Single Cypher path query traversing Action ← Finding ← EvidenceRef ← Decision ← Skill to explain complete chain of reasoning. | SPEC Goal 5 | 4 | Pending |
| REQ-18 | **FastAPI Backend & SSE Streaming**: REST API and Server-Sent Events stream orchestrator execution phases, graph events, and human approval requests. | SPEC Goal 5 | 4 | Pending |
| REQ-19 | **Cytoscape.js Obsidian-Themed Dashboard**: Interactive visualization of multi-graph topologies, real-time agent execution stream, and "Why?" path inspection. | SPEC Goal 5 | 5 | Pending |

---

## Non-Functional Requirements

| ID | Requirement | Category | Phase | Status |
|----|-------------|----------|-------|--------|
| NFR-01 | **Execution Speed**: Full orchestrator run completes in under ~90 seconds with local Ollama `llama3.1:8b`. | Performance | 4, 5 | Pending |
| NFR-02 | **Deterministic Testing**: 100% of test suite runs without external network access or running LLM via `MockLLMClient`. | Reliability | All | Pending |
| NFR-03 | **Query Safety**: All Cypher queries use parameterized values (`$param`) without raw string formatting. | Security | All | Pending |
| NFR-04 | **Explainability Completeness**: Every promoted finding has >=1 valid `EvidenceRef` pointing to verified data nodes. | Quality | 2, 3 | Pending |
| NFR-05 | **Visual Polish**: Dashboard UI follows Hyperstudio/Obsidian aesthetic (dark mode `#0d0d0f`, Satoshi typography, neon accents). | UX | 5 | Pending |

---

## Constraints

| ID | Constraint | Source | Impact |
|----|------------|--------|--------|
| CON-01 | Single FalkorDB instance on port 6379 | Hackathon architecture | Multi-graph isolation via named graphs (`atlas`, `domain`, `run_<id>`, `agent_<run>_<agent>`) |
| CON-02 | Submission Deadline Oct 18, 2026 11:59 PM IST | Hackathon rules | Strict 3-day solo critical path prioritization |
| CON-03 | Zero Production PII / Synthetic Only | Compliance & Ethics | Seeded domain generator ensures safe, reproducible demonstrations |
| CON-04 | Append-Only Decision History | Auditability | Losing decisions and findings are marked `superseded`, never deleted |

---

## Traceability Matrix

| Requirement | Phase | Core Modules | Planned Verification |
|-------------|-------|--------------|----------------------|
| REQ-01, REQ-02, REQ-03 | Phase 1 | `luna.graph.store`, `luna.domain` | Unit & integration tests in `tests/test_store.py`, `tests/test_domain.py` |
| REQ-04, REQ-05, REQ-06 | Phase 1 | `luna.atlas`, `luna.tools` | `tests/test_atlas.py`, `tests/test_tools.py` |
| REQ-07, REQ-08 | Phase 1 | `luna.llm`, `luna.planner` | `tests/test_llm.py`, `tests/test_planner.py` |
| REQ-09, REQ-10, REQ-11 | Phase 2 | `luna.mcp`, `luna.agent` | `tests/test_mcp.py`, `tests/test_agent.py` |
| REQ-12, REQ-13, REQ-14 | Phase 2, 3 | `luna.orchestrator` | `tests/test_promotion.py`, `tests/test_conflicts.py` |
| REQ-15, REQ-16 | Phase 3 | `luna.action`, `luna.learning` | `tests/test_action.py`, `tests/test_learning.py` |
| REQ-17, REQ-18 | Phase 4 | `luna.explain`, `luna.api` | `tests/test_explain.py`, `tests/test_api.py` |
| REQ-19 | Phase 5 | `luna-ui` (React + Cytoscape) | End-to-end browser verification and demo flow |

---

## Status Definitions

| Status | Meaning |
|--------|---------|
| Pending | Not yet started |
| In Progress | Being implemented |
| Complete | Implemented and verified |
| Blocked | Cannot proceed |
| Deferred | Moved to later milestone |

---

*Last updated: 2026-10-15*
