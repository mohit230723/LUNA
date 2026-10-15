# DECISIONS.md — Architecture Decision Records

> **Purpose**: Log significant technical decisions and their rationale for LUNA OS.

---

## Decisions

### [DECISION-001] FalkorDB Single Instance with Separate Named Graphs

**Date**: 2026-10-15  
**Status**: Accepted  

#### Context
LUNA OS requires isolated workspaces for sub-agents to explore hypotheses without contaminating the domain data or other agents' views, while sharing an atlas skill catalog and promoting validated findings into a shared run graph.

#### Decision
Use a single FalkorDB server instance running multiple named graphs:
- `atlas`: static catalog of skills, capabilities, tools, and cross-run track records.
- `domain`: synthetic ground truth dataset of insurance entities.
- `run_<id>`: shared run memory holding promoted findings, decisions, and action outcomes.
- `agent_<run_id>_<agent_id>`: temporary private graph slice assigned to a specific sub-agent.

#### Rationale
FalkorDB naturally scopes queries to one named graph at a time, providing strong mathematical isolation with minimal memory and compute overhead compared to spinning up multiple database instances. Cross-graph data flow is enforced explicitly in orchestrator Python code.

#### Consequences
Queries cannot join across graphs directly. All slice creation and finding promotion must be explicit data transfers executed by the orchestrator.

#### Alternatives Considered
- Single graph with node labels/prefixes: High risk of accidental data leakage or query bugs.
- Multiple FalkorDB Docker containers: Impractical overhead for local laptop development and CI testing.

---

### [DECISION-002] Local LLM Inference via Ollama `llama3.1:8b` with Mock Fallback

**Date**: 2026-10-15  
**Status**: Accepted  

#### Context
The system requires an LLM for task decomposition, sub-agent reasoning, conflict evaluation, and natural language graph queries. We need zero API cost, offline development capability, and predictable hackathon demos.

#### Decision
Implement an `LLMClient` protocol backed by `langchain_ollama.ChatOllama` pointed at `llama3.1:8b`. Provide a `MockLLMClient` with pre-canned deterministic responses for fast, 100% offline unit and integration tests.

#### Rationale
`llama3.1:8b` running locally on Ollama delivers fast JSON structured responses and tool calling without external network dependencies, privacy risks, or API costs. The `MockLLMClient` ensures CI and tests never flake due to LLM variability.

#### Consequences
Prompt templates must be concise and structured with explicit JSON schemas to avoid syntax failures with 8B models.

#### Alternatives Considered
- Cloud LLMs (Claude/OpenAI): Higher reasoning quality, but introduces API token costs, latency, and internet requirement.

---

### [DECISION-003] Per-Agent FastMCP Server for Tool Access Scoping

**Date**: 2026-10-15  
**Status**: Accepted  

#### Context
Sub-agents must be strictly restricted to the tools granted by their equipped skills from the `atlas` catalog. An agent equipped with `entity-linker` must not be able to run `connected_components` or write directly to shared memory.

#### Decision
Use the official Python `mcp` SDK to construct an isolated FastMCP server per sub-agent over stdio, registering only the specific tools matching the agent's equipped skill.

#### Rationale
MCP provides a standardized, interoperable protocol for tool definition and execution. Constructing per-agent FastMCP servers enforces architectural boundaries at the protocol level.

#### Consequences
Slight subprocess / stdio startup overhead per sub-agent, which is negligible for our targeted sub-agent count (2-4 agents per run).

#### Alternatives Considered
- Direct Python function passing: No formal isolation; agents could theoretically access unauthorized globals or store handles.

---

### [DECISION-004] Dual Query Strategy (Deterministic Tools + GraphRAG `ask_graph`)

**Date**: 2026-10-15  
**Status**: Accepted  

#### Context
Sub-agents need both precise graph metrics (PageRank, connected components, shortest paths) and flexible natural language exploration of entity properties.

#### Decision
Provide a dual query toolkit: 5 deterministic algorithm tools implemented with parameterized Cypher/Python, plus a 6th `ask_graph` tool powered by the FalkorDB GraphRAG SDK using an `Ontology.from_json()` schema definition.

#### Rationale
Combines the speed and mathematical certainty of graph algorithms with the flexibility of GraphRAG NL querying.

#### Consequences
Requires defining and maintaining `ontology.json` representing the domain graph schema.

#### Alternatives Considered
- Pure NL-to-Cypher for everything: Often generates suboptimal or invalid Cypher for complex graph algorithms like PageRank.

---

### [DECISION-005] Append-Only Run History with Superseded States

**Date**: 2026-10-15  
**Status**: Accepted  

#### Context
When conflicting findings arise (e.g., an over-eager agent falsely accusing a clean decoy entity), resolving the conflict could either delete the flawed finding or preserve it.

#### Decision
Never delete findings or decisions from `run_<id>`. When a conflict is resolved, the losing finding is marked `status='superseded'` and linked to the resolution `Decision` via `[:SUPERSEDES]`.

#### Rationale
Total transparency and explainability. A compliance auditor or human reviewer can inspect not only what was accepted, but what was considered, challenged, and overridden, and why.

#### Consequences
Run graph size increases monotonically; queries for active findings must filter by `status <> 'superseded'`.

---

*Last updated: 2026-10-15*
