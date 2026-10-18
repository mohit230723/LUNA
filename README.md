# LUNA OS — Autonomous Graph-Orchestrated Chat Platform

[![Architecture: Graph-Native Multi-Agent](https://img.shields.io/badge/Architecture-Graph--Native%20Multi--Agent-00ff66?style=flat-square)](#architecture)
[![Database: FalkorDB](https://img.shields.io/badge/Graph%20DB-FalkorDB%20Docker-blue?style=flat-square)](https://falkordb.com)
[![Frontend: Hyperstudio Spec](https://img.shields.io/badge/UI-Hyperstudio%20%7C%20React%20%2B%20Vite%20%2B%20Cytoscape-black?style=flat-square)](#hyperstudio-ui)
[![Security: Zero-Leak API Keys](https://img.shields.io/badge/Security-Zero--Leak%20API%20Keys-success?style=flat-square)](#security--governance)

**LUNA OS** is an autonomous, graph-orchestrated multi-agent chat platform. Behind a single unified chat interface, LUNA dynamically routes user prompts into domain-specialized **Packs** (`investigate` and `software-build`). Every plan, decision, skill assignment, agent traversal step, evidence link, and generated artifact is persisted directly into **FalkorDB** as an auditable property graph.

---

## Architecture Overview

```mermaid
flowchart TD
    User([User Prompt]) --> ChatBox[Hyperstudio Chat Box / API Gateway]
    ChatBox --> Router{Dynamic Router\nroute_prompt\nLLM + Keyword Fallback}

    subgraph Packs ["Pack Abstraction Layer"]
        Router -->|investigate| InvPack[Investigate Pack\nFraud & Entity Linkage]
        Router -->|software-build| BuildPack[Software-Build Pack\nCodebase Generator]
    end

    subgraph InvestigatePipeline ["Investigate Pack Flow"]
        InvPack --> Seeds[Detect Seeds & Targets]
        Seeds --> RepScore[Atlas Skill Scoring & Assignment]
        RepScore --> SubAgents[Parallel Subagents\nPrivate Graph Slices]
        SubAgents --> TraversalRec[TraversalRecorder\nStep-by-Step Entity Graph Hops]
        TraversalRec --> SideRes[Deterministic Side Resolution]
        SideRes --> CorrGate[Corroboration Gating]
        CorrGate --> AnswerInv[Compose Answer\nStrict Entity Citation Enforcement]
    end

    subgraph BuildPipeline ["Software-Build Pack Flow"]
        BuildPack --> Understand[Requirement Extraction & Tech Check]
        Understand --> BlueprintDAG[Blueprint DAG Generation\nTopological Wave Sorting]
        BlueprintDAG --> Wave1[Wave 1: Database Entities]
        Wave1 --> Wave2[Wave 2: Backend Routes & Logic]
        Wave2 --> Wave3[Wave 3: Frontend Views & Contracts]
        Wave3 --> ContractVerify[Deterministic Contract Verifier\nRoute / Fetch / Schema Check]
        ContractVerify --> Assembly[Sandbox Workspace Assembly\nFile Tree & ZIP Generation]
    end

    subgraph HumanGate ["Human-in-the-Loop Governance"]
        CorrGate --> ActionInv[PENDING: flag_for_review Action]
        Assembly --> ActionBuild[PENDING: run_build_check Action]
        ActionInv --> ApprovalGate{Human Approval\nPOST /api/runs/{id}/approve}
        ActionBuild --> ApprovalGate
        ApprovalGate -->|Approved| ExecDomain[Mutate Domain / Execute Build Check]
        ApprovalGate -->|Approved| LearnAtlas[Cross-Run Atlas Learning\nUpdate SUCCEEDED_ON Edges]
    end

    subgraph FalkorDB ["FalkorDB Property Graphs"]
        AtlasDB[(atlas Graph\nSkills, Capabilities, Tech, Packs)]
        DomainDB[(domain Graph\nCustomers, Claims, Accounts, Policies)]
        RunDB[(run_<id> Graphs\nTasks, Decisions, Findings, Steps, Artifacts)]
        ConvDB[(conversations Graph\nThreads, Turns, Run References)]
    end

    SubAgents -.-> DomainDB
    RepScore -.-> AtlasDB
    LearnAtlas -.-> AtlasDB
    TraversalRec -.-> RunDB
    BlueprintDAG -.-> RunDB
    ChatBox -.-> ConvDB
```

---

## Key Capabilities & Design Pillars

### 1. Two Specialized Packs Behind One Chat Box
* **`investigate` Pack:** Detects fraud rings, traces hidden multi-hop connections between customers and entities, detects claim outliers, resolves conflicting agent claims deterministically, and produces anti-hallucination answers backed strictly by observed graph paths (`(:Answer)-[:CITES]->(:Customer)`).
* **`software-build` Pack:** Generates fullstack software applications from prompt specifications. Deconstructs requirements into a typed component & contract Directed Acyclic Graph (DAG), executes generation across sequential topological waves (Database $\to$ Backend $\to$ Frontend), enforces deterministic contract verification (matching endpoints, fetch paths, and schemas), and packages code safely into sandboxed zip bundles.

### 2. Autonomous Skill Assignment & Skill-Fit Governance
* Agents dynamically query the `atlas` graph for skills matching capabilities and target technologies.
* Subagents execute an internal **skill-fit check** against their assigned subtask before execution. If fit falls below $0.6$, the orchestrator reassigns to the next-ranked skill.
* Policy-restricted skills (such as unauthorized `shell-runner` or `bulk-linker`) are automatically filtered and recorded in provenance logs as `(:Decision)-[:REJECTED {reason: 'policy_restricted'}]->(:SkillRef)`.

### 3. Grounded Traversal & Anti-Hallucination Answers
* Graph queries during investigations are tracked step-by-step in `run_<id>` using `TraversalStep` nodes (`from_cid`, `to_cid`, `rel`, `tool`).
* Every citation in `compose_answer` is validated against CIDs actually observed in the run memory graph. Phantom or hallucinated entity IDs are purged and flagged.

### 4. Pluggable LLM Providers with Zero-Leak Security
* Built-in support for **Ollama** (local/offline default), **OpenAI-compatible endpoints** (vLLM, Groq, DeepSeek, OpenAI), and **Anthropic** (Claude 3.5 Sonnet / Haiku).
* Zero external third-party SDK dependencies (uses Python standard library `urllib.request`).
* Sensitive API keys (`LUNA_LLM_API_KEY`, `ANTHROPIC_API_KEY`) are masked in all logs, audit records, and serialized objects (displaying only the first 3 characters, e.g., `sk-***`).

### 5. Hyperstudio Design Aesthetics
* Rebuilt from the ground up matching the **Hyperstudio Design Specification**:
  * Ultra-strict 12-color palette (Pitch Black `#0a0b0e`, Crisp Neutral White `#ffffff`, Terminal Green `#00ff66`, Amber `#ffaa00`, Signal Red `#ff3344`, Cyber Cyan `#00ccff`).
  * Pure typography pairing: **Satoshi** (geometric display) + **IBM Plex Mono** (technical clarity).
  * Absolutely **zero box-shadows and zero backdrop-filter blurs**; depth is achieved exclusively through 1px border contrasts, hairline rules, and high-density information architecture.
  * Interactive **Cytoscape.js** visualizers with step scrubbers (`1x`, `2x`, `5x`, Play/Pause) for both investigation traversal and blueprint dependency DAGs.

---

## Project Structure

```
d:\LUNA\
├── luna/                       # Core Python Backend Engine
│   ├── api/                    # FastAPI REST & SSE Streaming App
│   ├── atlas/                  # Global Atlas Catalog & Seeding
│   ├── conversation/           # Persistent Graph Memory (conversations)
│   ├── domain/                 # Domain Knowledge Graph & Fraud Generators
│   ├── graph/                  # FalkorDB Client & Frozen Schema Contract
│   ├── llm/                    # Provider Abstraction (Ollama, OpenAI, Anthropic, Mock)
│   ├── orchestrator/           # Orchestrator, Resolution, Actions, Traversal
│   ├── packs/                  # Pack Registry, Router & Implementations
│   │   ├── base.py             # Pack & PackPipeline Protocol
│   │   ├── investigate.py      # Investigate Pack Wrapping LunaPipeline
│   │   ├── registry.py         # Dynamic Pack Registration
│   │   ├── router.py           # Intelligent Prompt Classifier & Fallback
│   │   └── build/              # Software-Build Pack Engine
│   │       ├── blueprint.py    # Component/Contract DAG & Topological Sort
│   │       ├── pack.py         # BuildPack Implementation
│   │       ├── pipeline.py     # 3-Wave Builder & Gated Actions
│   │       ├── sandbox.py      # Sandboxed File Workspace with Path Protection
│   │       ├── seed.py         # Atlas Seeding (Techs, Capabilities, Skills)
│   │       ├── understand.py   # Tech & Requirement Extractor
│   │       └── verifier.py     # Deterministic Route/Fetch Contract Checker
│   ├── planner/                # Task Decomposition & Skill Assignment
│   └── tools/                  # Algorithmic & Graph Tools (PageRank, ShortestPath, etc.)
├── ui/                         # Hyperstudio Frontend (Vite + React + TypeScript)
│   ├── src/
│   │   ├── api/                # LiveApi, MockApi, SSE Client & Type Contract
│   │   ├── components/         # Hyperstudio Primitives, Chat Blocks, Graph Viewers
│   │   ├── pages/              # Home, Skills Atlas, Platform Chat, How It Works
│   │   └── state/              # Pure Reducers & Stage Derivations
│   └── tests/                  # Vitest Unit Tests & Playwright E2E Suites
├── scripts/
│   └── demo_conversations.py   # Headless Runner for Scenarios D1–D5
└── docs/                       # Architectural Specs & Reports
    ├── schema.md               # Frozen Graph Schema Contract
    ├── phase5_report.md        # Comprehensive Rebuild Engineering Report
    └── demo_script.md          # 4-Minute Presentation Script
```

---

## Quickstart Guide

### 1. Prerequisites
- **Python:** 3.12+ (Windows / Linux / macOS)
- **Node.js:** v20+ or v22+
- **Docker:** Docker Desktop running with Compose support

### 2. Start FalkorDB
Start the FalkorDB graph database container:
```bash
docker compose up -d
```
Verify the container is listening on port `6379`:
```bash
docker ps --filter "ancestor=falkordb/falkordb"
```

### 3. Start Backend Server
Install Python dependencies and run the FastAPI server:
```bash
# In repository root:
python -m uvicorn luna.api.app:app --host 0.0.0.0 --port 8000 --reload
```
The REST API will be accessible at `http://localhost:8000`, and OpenAPI documentation at `http://localhost:8000/docs`.

### 4. Start Hyperstudio Frontend
```bash
cd ui
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

### 5. Run Scripted Headless Demo Scenarios
To run all 5 canonical scenarios (D1 Investigate, D2 Build, D3 Context Follow-up, D4 Clarification, D5 Policy Rejection) end-to-end without a browser:
```bash
python scripts/demo_conversations.py
```

---

## LLM Provider Configuration

Configure your LLM backend via environment variables:

| Environment Variable | Allowed Values | Default | Description |
|---|---|---|---|
| `LUNA_LLM_PROVIDER` | `ollama`, `openai`, `anthropic`, `mock` | `ollama` | Active LLM client implementation. |
| `LUNA_LLM_BASE_URL` | URL string | `http://localhost:11434` | Endpoint for Ollama or OpenAI-compatible service. |
| `LUNA_LLM_MODEL` | Model string | `llama3.2` | Global default model identifier. |
| `LUNA_MODEL_INVESTIGATE` | Model string | None | Optional model override for the `investigate` pack. |
| `LUNA_MODEL_BUILD` | Model string | None | Optional model override for the `software-build` pack. |
| `LUNA_LLM_API_KEY` | Secret string | None | API key for OpenAI-compatible providers (vLLM, DeepSeek, OpenAI). |
| `ANTHROPIC_API_KEY` | Secret string | None | API key for Anthropic Claude. |

### Example: Running with Local Ollama
```bash
set LUNA_LLM_PROVIDER=ollama
set LUNA_LLM_MODEL=llama3.2
```

### Example: Running with OpenAI / DeepSeek / vLLM
```bash
set LUNA_LLM_PROVIDER=openai
set LUNA_LLM_BASE_URL=https://api.openai.com/v1
set LUNA_LLM_API_KEY=sk-proj-...
set LUNA_LLM_MODEL=gpt-4o-mini
```

### Example: Running with Anthropic Claude
```bash
set LUNA_LLM_PROVIDER=anthropic
set ANTHROPIC_API_KEY=sk-ant-...
set LUNA_LLM_MODEL=claude-3-5-sonnet-20241022
```

---

## API Reference

### Core Chat & Conversation Endpoints
- `POST /api/chat/conversations`: Create a new conversation thread.
- `GET /api/chat/conversations`: List existing conversation threads.
- `GET /api/chat/conversations/{conv_id}`: Retrieve conversation history, turns, and linked runs.
- `POST /api/chat/conversations/{conv_id}/messages`: Submit a user prompt to a conversation thread. Initiates routing and starts background execution.
- `POST /api/runs/{run_id}/answer`: Submit an answer to a clarification question (`needs_input`), resuming a paused run.
- `POST /api/runs/{run_id}/cancel`: Signal immediate cancellation of an active run.

### Human-in-the-Loop Approval Endpoints
- `POST /api/runs/{run_id}/actions/{action_id}/approve`: Approve a pending governance action (`flag_for_review` or `run_build_check`).
- `POST /api/runs/{run_id}/approve`: Convenient alias to approve the first pending action of a run.
- `POST /api/runs/{run_id}/actions/{action_id}/reject`: Reject a proposed action with audit reasoning.

### Trace & Artifact Endpoints
- `GET /api/runs/{run_id}/trace`: Retrieve Cytoscape-formatted graph trace for visual replay. Returns nodes, edges, ordered traversal steps, and critical path node IDs.
- `GET /api/runs/{run_id}/download`: Download assembled software-build zip archive (`workspaces/<run_id>.zip`).
- `GET /api/runs/{run_id}/artifacts/{file_path:path}`: Stream an individual generated file from the sandboxed workspace.
- `GET /api/atlas/skills`: Retrieve the complete catalog of skills, capabilities, and technologies.

---

## Security & Governance Guarantees

1. **Sandboxed Workspace Protection:** All file writes during software builds are strictly jailed within `workspaces/<run_id>/<component>/`. Paths containing `..`, absolute paths, or symbolic links attempting to escape the component root are actively rejected with security exceptions.
2. **Deterministic Parameterized Cypher:** Every Cypher query executed against FalkorDB uses parameterized queries (`$param`). Raw string concatenation of user prompts into Cypher strings is strictly forbidden.
3. **Zero-Leak Secret Masking:** API keys are never written to logs, graph properties, or frontend responses. Keys are masked during initialization and logged only as `sk-***`.
4. **Approval Barrier Enforcement:** High-impact domain actions (such as mutating production customer records or executing shell build checks) cannot be executed by subagents autonomously; they are proposed in a `PENDING` state and require explicit human review.
5. **Anti-Hallucination Citations:** Generated answers citing entity IDs are verified against nodes physically resident in the run memory graph. Hallucinated IDs are discarded and audited.

---

## License

Apache-2.0. Copyright (c) 2026 LUNA OS Authors.
