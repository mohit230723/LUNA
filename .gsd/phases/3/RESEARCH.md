---
phase: 3
researched_at: 2026-10-15
discovery_level: 2
---

# Phase 3 Research: Conflict Resolution & Action Lifecycle

## Objective
Establish the technical requirements, Cypher queries, data models, and testing patterns for automated contradiction detection, main-agent conflict resolution with append-only by convention: losing findings are marked superseded, never deleted, human approval gates, idempotent domain graph mutations, and cross-run exponential moving average skill score updates.

---

## Key Technical Decisions for Phase 3

### 1. Contradiction Detection (`luna/orchestrator/conflicts.py`)
- **Condition**: In `run_<id>`, two findings assessing the same target entity (`f1-[:ASSESSES]->(c)<-[:ASSESSES]-f2`) have contradictory verdicts (`f1.verdict != f2.verdict`, e.g. `"suspicious"` vs `"benign"`).
- **Graph Mutation**:
  Create a bidirectional or directed contradiction link:
  ```cypher
  MATCH (f1:Finding)-[:ASSESSES]->(c:Customer)<-[:ASSESSES]-(f2:Finding)
  WHERE f1.id < f2.id AND f1.verdict <> f2.verdict
  MERGE (f1)-[r:CONFLICTS_WITH]-(f2)
  SET r.detected_at = $timestamp
  RETURN f1.id AS f1_id, f2.id AS f2_id, c.cid AS target_cid, f1.verdict AS v1, f2.verdict AS v2
  ```
- **Auditing**: Returns a list of detected contradiction pairs `[(Finding1, Finding2, target_cid)]`.

### 2. Main-Agent Conflict Resolution (`luna/orchestrator/resolve.py`)
- **Principle**: Zero Deletion. Under the Explainability Contract (DECISION-005), losing findings are marked `status = 'superseded'` and explicitly connected via `[:SUPERSEDES]`.
- **Resolution Strategy**:
  - Compare confidence scores, evidence count, and skill historical success score from `atlas`.
  - Main agent synthesizes rationalization (via LLM or deterministic rule-based arbitrator).
  - Graph Mutations:
    ```cypher
    CREATE (d:Decision {
        id: $decision_id,
        target_cid: $target_cid,
        chosen_verdict: $chosen_verdict,
        confidence: $confidence,
        reasoning: $reasoning,
        resolved_at: $timestamp
    })
    MATCH (winner:Finding {id: $winner_id}), (loser:Finding {id: $loser_id})
    SET loser.status = 'superseded'
    CREATE (d)-[:UPHELD]->(winner)
    CREATE (d)-[:SUPERSEDES]->(loser)
    ```

### 3. Human Approval Gate & Idempotent Domain Mutation (`luna/orchestrator/actions.py`)
- **Action Proposal**:
  When a decision or unanimous finding concludes an entity is `"suspicious"`:
  An `ActionProposal` is generated:
  - `action_type`: `"FLAG_CUSTOMER"` | `"ESCALATE_CLAIM"` | `"CLEAR_CUSTOMER"`
  - `target_cid`: entity CID
  - `recommended_by_decision_id`: Decision or Finding ID
  - `status`: `"pending"` | `"approved"` | `"rejected"`
- **Approval Gate**:
  - Headless demo mode supports `auto_approve=True`.
  - Interactive mode / API exposes approval endpoints (`approve_action(action_id)`).
- **Idempotency Guarantee**:
  - When approved: `MATCH (c:Customer {cid: $cid}) SET c.flagged = true, c.flagged_at = $timestamp`
  - Re-running the execution does not duplicate nodes or fail.
- **Ground Truth Evaluation**:
  - Computes Precision, Recall, and F1 score against `GroundTruth(ring_cids, decoy_cids)`.
  - Ring customers (`cust-000` to `cust-007`) flagged = True Positives.
  - Decoy customers (`cust-010` to `cust-013`) unflagged = True Negatives.

### 4. Cross-Run Learning in Atlas (`luna/atlas/learner.py`)
- **Formula**: Exponential moving average:
  $$S_{new} = \alpha \cdot R + (1 - \alpha) \cdot S_{old}$$
  where $\alpha = 0.2$ (learning rate), $R = 1.0$ if the skill's promoted finding contributed to a correct domain outcome, or $R = 0.0$ if it contributed to a false positive / false negative.
- **Cypher Update on Atlas Graph**:
  ```cypher
  MATCH (s:Skill {id: $skill_id})-[r:SUCCEEDED_ON]->(t:TaskType {name: $task_type})
  SET r.score = (1.0 - $alpha) * r.score + $alpha * $reward,
      r.runs = r.runs + 1,
      r.last_updated = $timestamp
  RETURN s.id AS skill_id, r.score AS new_score, r.runs AS total_runs
  ```

---

## Anti-Patterns to Avoid
1. Deleting losing findings from `run_<id>` (breaks the single-path "Why?" explanation graph query).
2. Applying mutations to the `domain` graph without passing through the approval gate state.
3. Mutating domain entities with hardcoded string parameters instead of parameterized Cypher.
4. Overwriting atlas scores abruptly instead of smooth EMA updating.

---

*Last updated: 2026-10-15*
