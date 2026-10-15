# RESEARCH.md — Technology & Architecture Research

> **Project**: LUNA OS
> **Researched at**: 2026-10-15
> **Discovery Level**: Level 2 (Architecture & Integration Verification)

## Objective
Establish the definitive technical foundation for LUNA OS, verifying compatibility across FalkorDB, the FalkorDB GraphRAG SDK, local Ollama inference, the Model Context Protocol (FastMCP), and the Cytoscape.js visualization layer.

---

## Key Decisions

### Decision 1: Graph Engine & Multi-Graph Isolation
- **Question**: How do we manage agent isolation and multi-agent shared memory on FalkorDB?
- **Options Considered**:
  1. *Single graph with label prefixes / namespaces*: Complex queries, high risk of data leakage between agents.
  2. *Separate FalkorDB instances*: High container overhead, slow setup, difficult cross-graph orchestration.
  3. *Single FalkorDB instance with multiple named graphs (`atlas`, `domain`, `run_<id>`, `agent_<run>_<agent>`) (Selected)*: FalkorDB queries see one named graph at a time, providing mathematical isolation. Cross-graph data movement is explicit orchestrator code.
- **Decision**: Option 3. Single instance, multiple named graphs.
- **Confidence**: High.

### Decision 2: LLM Inference & Local Operation
- **Question**: How to run agent reasoning locally without external API dependencies or costs?
- **Options Considered**:
  1. *Anthropic/OpenAI Cloud APIs*: Fast and capable, but incurs API costs, requires network access, and risks rate limits during hackathon testing.
  2. *LangChain ChatOllama with `llama3.1:8b` behind unified `LLMClient` protocol (Selected)*: Zero cost, 100% offline, privacy-preserving, supports JSON structured output and tool binding. A `MockLLMClient` is used for deterministic unit testing.
- **Decision**: Option 2. Ollama `llama3.1:8b` via `langchain_ollama.ChatOllama`.
- **Confidence**: High.

### Decision 3: Graph Exploration & Query Strategy
- **Question**: How should sub-agents query their private graph slices?
- **Options Considered**:
  1. *Raw Cypher generation only*: Prone to hallucinated schema or invalid query syntax with 8B models.
  2. *Natural language search only (vector similarity)*: Misses multi-hop structural graph insights (e.g., shared attributes, rings).
  3. *Dual Query Strategy (Deterministic Cypher Tools + FalkorDB GraphRAG SDK `ask_graph`) (Selected)*: Sub-agents have deterministic graph algorithm tools (PageRank, WCC, Shortest Path, Outliers) for structured analysis, plus FalkorDB GraphRAG SDK (`Ontology.from_json()`) for flexible natural language exploration.
- **Decision**: Option 3. Dual query strategy.
- **Confidence**: High.

### Decision 4: Agent Tool Isolation via MCP
- **Question**: How to enforce that sub-agents only access tools permitted by their equipped skills?
- **Options Considered**:
  1. *In-process dictionary of functions*: Fragile, tight coupling, hard to audit.
  2. *Official `mcp` Python SDK (FastMCP + stdio client) (Selected)*: Each equipped agent spawns an isolated FastMCP server over stdio exposing only the tools registered to its assigned skill in the `atlas` catalog. Standardized, secure, and extensible.
- **Decision**: Option 2. FastMCP stdio tool isolation.
- **Confidence**: High.

---

## Findings & Verification Checklist (Part B)

1. **FalkorDB Python Client (`falkordb`)**:
   - Install: `pip install falkordb`
   - Connection: `FalkorDB(host='localhost', port=6379)`
   - Queries must be parameterized: `graph.query("MATCH (c:Customer {cid: $cid}) RETURN c", {"cid": cid})`
   - Graph deletion: `graph.delete()`
   - Graph cloning / slice initialization: Done via Cypher batch copy or node/edge replication.

2. **Graph Algorithms on FalkorDB**:
   - PageRank and Shortest Path are supported via Cypher or procedures.
   - For connected components / WCC: If server-side procedure is unavailable or varies by image version, fallback to deterministic Python NetworkX or iterative Cypher component labeling ensures 100% test reliability.

3. **FalkorDB GraphRAG SDK (`graphrag_sdk`)**:
   - Schema defined in `luna/domain/ontology.json` and loaded via `Ontology.from_json()`.
   - Generates Cypher queries against target knowledge graphs from natural language prompts.
   - Initialized per agent slice for the `ask_graph` tool.

4. **Structured Output with `llama3.1:8b`**:
   - `langchain_ollama.ChatOllama` supports `format="json"` or Pydantic structured output.
   - Tool calling via `.bind_tools()` maps cleanly to FastMCP tool definitions.

5. **Cytoscape.js & Obsidian UI**:
   - Fast, GPU-accelerated canvas graph rendering.
   - Dark theme palette: Deep charcoal `#0d0d0f`, surface `#16161a`, neon green/amber accents, IBM Plex Mono monospace tokens.

---

## Patterns to Follow

- **Parameterized Cypher Everywhere**: Never concatenate values into Cypher strings. Always pass parameters dict.
- **Append-Only Run Memory**: Decision losing in conflict resolution is marked `status='superseded'` and linked with `[:SUPERSEDES]`; never delete.
- **Idempotent Actions**: Actions require explicit approval state and can be re-executed safely without duplicate domain writes.
- **Ground Truth Seeding**: Seeded random generator (`seed=42`) guarantees consistent fraud ring generation and verifiable precision/recall benchmarks.

## Anti-Patterns to Avoid

- **Cross-Graph Cypher**: Never attempt `MATCH (a:Graph1), (b:Graph2)`. FalkorDB connects to one graph at a time.
- **Direct Domain Mutation by Sub-Agents**: Sub-agents only write findings to their private slice; only the main orchestrator mutates domain after human approval.
- **Unverified Evidence**: Findings are rejected during promotion if referenced entity `cid`s do not exist in the agent's assigned slice.

## Dependencies Identified

| Package | Version | Purpose |
|---------|---------|---------|
| `falkordb` | latest (>=1.0.0) | FalkorDB Python client |
| `graphrag_sdk` | latest | FalkorDB GraphRAG ontology & NL-to-graph engine |
| `langchain_ollama` | latest | LangChain wrapper for Ollama local models |
| `mcp` | latest (>=1.0.0) | Model Context Protocol SDK (FastMCP + stdio) |
| `pydantic` | >=2.0 | Schema validation and structured outputs |
| `fastapi` | >=0.110 | Backend web API |
| `uvicorn` | >=0.28 | ASGI server |
| `pytest` | >=8.0 | Test runner |
| `networkx` | >=3.0 | Fallback graph algorithms & slice extraction |

---

*Last updated: 2026-10-15*
