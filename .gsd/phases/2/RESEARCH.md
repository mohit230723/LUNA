---
phase: 2
researched_at: 2026-10-15
discovery_level: 2
---

# Phase 2 Research: Execution, Isolation & Promotion

## Objective
Establish the technical requirements, architecture, and testing patterns for per-agent FastMCP tool isolation, k-hop sub-graph slice extraction in FalkorDB, sub-agent execution loops with draft findings, and finding promotion with evidence provenance barrier (existence, observation, and connectivity checks) into shared run graphs.

---

## Key Technical Decisions for Phase 2

### 1. FastMCP Tool Scoping & Server Architecture
- **Package**: `mcp>=1.0.0,<2.0.0` (using `from mcp.server.fastmcp import FastMCP`).
- **Isolation Guarantee**: Each equipped sub-agent has a unique FastMCP server instance created via:
  ```python
  def create_agent_mcp_server(
      agent_id: str,
      tool_names: list[str],
      graph_store: GraphStore,
      agent_graph_name: str,
  ) -> FastMCP: ...
  ```
- **Graph Pinning**: Tools registered on the agent's FastMCP server are bound to `graph_name=agent_graph_name`. The sub-agent cannot specify or access `domain`, `atlas`, or another agent's graph.
- **Client Session Transport**: FastMCP provides stdio process execution for headless / subprocess use, and in-memory tool caller interface (`AgentMCPClient` / direct schema binding) for fast, robust unit and integration testing.

### 2. Sub-Graph Slice Extraction (k-Hop Neighborhoods)
- **Problem**: Sub-agents must not query the full domain graph directly; they need private scoped slices (`agent_<run>_<agent>`).
- **Cypher k-Hop Traversal**:
  In FalkorDB, we extract a k-hop neighborhood from `domain` using parameterized Cypher:
  ```cypher
  MATCH path = (c:Customer)-[*1..2]-(m)
  WHERE c.cid IN $cids
  UNWIND nodes(path) AS n
  RETURN DISTINCT labels(n) AS labels, properties(n) AS props
  ```
  And edges:
  ```cypher
  MATCH path = (c:Customer)-[*1..2]-(m)
  WHERE c.cid IN $cids
  UNWIND relationships(path) AS r
  RETURN DISTINCT type(r) AS rel_type, startNode(r).cid AS from_cid, endNode(r).cid AS to_cid, properties(r) AS props
  ```
- **Atomic Clone into Private Graph**: The orchestrator iterates the collected nodes and edges, creating them in `agent_<run>_<agent>` via parameterized batch queries.
- **Node Caching & Identity**: All nodes retain their domain `cid` properties so evidence references remain verifiable.

### 3. Sub-Agent Execution Loop & Draft Findings
- **Data Models** (`luna/agents/models.py`):
  ```python
  class Finding(BaseModel):
      id: str = Field(default_factory=lambda: f"find-{uuid4().hex[:8]}")
      agent_id: str
      target_cid: str
      verdict: Literal["suspicious", "benign"]
      confidence: float = Field(ge=0.0, le=1.0)
      reasoning: str
      evidence_cids: list[str] = Field(default_factory=list)
      skill_id: str
      timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
  ```
- **Loop Flow**:
  1. Initialize with: `agent_id`, `skill` (name, prompt fragment), `private_graph_name`, `target_cids`, `mcp_client`, `llm_client`.
  2. Sub-agent queries its FastMCP tools (e.g. `shared_attribute_links`, `detect_connected_components`, `ask_graph`).
  3. Synthesizes observations with LLM prompt using structured schema or heuristic parser.
  4. Yields one or more draft `Finding` objects citing specific `evidence_cids`.

### 4. Finding Promotion Engine & Evidence Verification
- **Anti-Hallucination Barrier**:
  Before any finding is promoted to the shared `run_<id>` graph:
  1. For each `cid` in `finding.evidence_cids`:
     Execute `MATCH (n {cid: $cid}) RETURN count(n) AS cnt` against the agent's private graph `agent_<run>_<agent>`.
  2. If count == 0 for ANY evidence CID:
     **REJECT** the finding immediately with `PromotionError(f"Evidence {cid} not found in agent slice")`.
  3. If all evidence CIDs exist:
     **PROMOTE**: Write finding node to `run_<id>` graph:
     ```cypher
     CREATE (f:Finding {
         id: $id,
         target_cid: $target_cid,
         verdict: $verdict,
         confidence: $confidence,
         reasoning: $reasoning,
         skill_id: $skill_id,
         agent_id: $agent_id,
         status: 'promoted',
         timestamp: $timestamp
     })
     MERGE (a:Agent {id: $agent_id})
     CREATE (f)-[:PROMOTED_FROM]->(a)
     ```
     For each `evidence_cid`:
     ```cypher
     MERGE (e:Entity {cid: $evidence_cid})
     CREATE (f)-[:SUPPORTED_BY]->(e)
     ```

---

## Anti-Patterns to Avoid
1. Letting sub-agents pass arbitrary graph names into tools.
2. Allowing sub-agents to access tools outside their assigned skill.
3. Accepting findings with unverifiable or hallucinated evidence CIDs.
4. Mutating domain graph during slice exploration.

---

*Last updated: 2026-10-15*
