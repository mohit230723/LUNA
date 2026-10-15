---
phase: 1
researched_at: 2026-10-15
discovery_level: 2
---

# Phase 1 Research: Foundation & Graph Infrastructure

## Objective
Establish the technical requirements, library APIs, and testing patterns for FalkorDB connection management, domain data generation, atlas skill catalog seeding, deterministic graph algorithm tools, and LLM abstraction.

---

## Key Decisions for Phase 1

### 1. FalkorDB Docker & Client Setup
- **Docker Image**: `falkordb/falkordb:latest` exposed on `localhost:6379`.
- **Python Client**: `falkordb` library.
- **Pattern**:
  ```python
  from falkordb import FalkorDB
  db = FalkorDB(host="localhost", port=6379)
  graph = db.select_graph("atlas")
  res = graph.query("MATCH (s:Skill {id: $id}) RETURN s", {"id": "entity-linker"})
  ```
- **Graph Isolation**: Graphs are named strings (`atlas`, `domain`, `run_<id>`, `agent_<run>_<agent>`). Deleting a graph calls `graph.delete()`.
- **Safety**: Never format queries via f-strings; all values must be passed in query params dictionary.

### 2. Synthetic Domain & Ground Truth
- Seed: `seed=42` for 100% reproducible data generation.
- Entities:
  - `Customer` (~300 nodes, properties: `cid`, `name`, `flagged: bool`)
  - `Provider` (~10 nodes, including suspicious `prov_ring`)
  - `InsuranceClaim` (~500 nodes, properties: `cid`, `amount`, `date`)
  - `Policy` (~300 nodes)
  - `Phone`, `Address`, `BankAccount`
- Planted Clusters:
  - **Fraud Ring** (8 customers): share BankAccount `ba_ring`, phone numbers `ph_ring_1`, `ph_ring_2`, high claims with `prov_ring`.
  - **Decoy Family** (4 customers): share Address `addr_decoy`, legitimate claims, distinct accounts/phones (clean).
- Ground truth returned as a dataclass `GroundTruth(ring_cids=set(...), decoy_cids=set(...))`.
- Ontology exported as `luna/domain/ontology.json` matching FalkorDB GraphRAG SDK format.

### 3. Atlas Catalog Seeding
- Schema:
  - `(:Capability {name})`
  - `(:Skill {id, name, prompt_fragment, restricted: bool})`
  - `(:Tool {name, description})`
  - `(:TaskType {name})`
- Relationships:
  - `(:Skill)-[:PROVIDES]->(:Capability)`
  - `(:Skill)-[:REQUIRES]->(:Skill)`
  - `(:Skill)-[:EXPOSES]->(:Tool)`
  - `(:Skill)-[:SUCCEEDED_ON {score: float, runs: int}]->(:TaskType)`
- Skills seeded:
  1. `entity-linker` (provides: `link_entities`, exposes: `shared_attribute_links`, score: 0.70)
  2. `bulk-linker` (provides: `link_entities`, exposes: `shared_attribute_links`, restricted: true, score: 0.95)
  3. `ring-detector` (provides: `detect_communities`, requires: `entity-linker`, exposes: `connected_components`, score: 0.80)
  4. `ring-detector-lite` (provides: `detect_communities`, exposes: `connected_components`, score: 0.50)
  5. `influence-ranker` (provides: `rank_influence`, exposes: `pagerank_top`, score: 0.60)
  6. `path-explainer` (provides: `explain_connection`, exposes: `shortest_path`, score: 0.60)
  7. `anomaly-scout` (provides: `detect_amount_anomalies`, exposes: `claim_amount_outliers`, score: 0.60)
- All skills additionally expose `ask_graph` (FalkorDB GraphRAG NL query tool).

### 4. Graph Algorithm Tools & GraphRAG Integration
- **Deterministic Tools**:
  - `shared_attribute_links(cid, attribute_types)`: Finds entities sharing Phone, BankAccount, or Address.
  - `connected_components(cids, relationship_types)`: Computes subgraphs of connected entities (NetworkX fallback if server WCC procedure is unavailable).
  - `pagerank_top(limit)`: Finds highest centrality entity in graph.
  - `shortest_path(source_cid, target_cid)`: Traces connection path between entities.
  - `claim_amount_outliers(threshold_std)`: Finds claims > N standard deviations above mean.
- **GraphRAG Tool**:
  - `ask_graph(question, graph_name)`: Uses `graphrag_sdk.KnowledgeGraph` with domain ontology to answer natural language questions via Cypher.

### 5. LLM Client & Mocking Strategy
- Protocol:
  ```python
  class LLMClient(Protocol):
      def complete(self, prompt: str, system: str = "", json_schema: dict | None = None) -> str | dict: ...
  ```
- Implementations:
  - `OllamaLLM`: wraps `langchain_ollama.ChatOllama(model="llama3.1:8b")` with JSON format output.
  - `MockLLMClient`: returns canned deterministic JSON responses for task decomposition, sub-agent investigations, and conflict resolutions during tests.

---

## Anti-Patterns to Avoid
- Running tests that require active network connectivity or unmocked external LLM calls.
- Hardcoding Cypher query string interpolations.
- Attempting cross-graph joins in a single Cypher query.

---

*Last updated: 2026-10-15*
