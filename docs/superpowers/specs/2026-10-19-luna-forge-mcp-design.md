# LUNA Forge — Skill-Graph MCP Server for Coding Agents

**Date:** 2026-10-19
**Status:** Draft — awaiting review
**Package:** `luna/forge/` (working name)

## 1. Intent

### What the user asked for
- LUNA acts as an MCP server that any coding agent can connect to. Claude Code and Google Antigravity must both work.
- The coding agent sends a prompt such as "build me a website …". LUNA's orchestrator fetches skills from a skill directory, assigns them to empty waiting subagents, and merges their work into one output.
- Skills live in FalkorDB as a hyperconnected graph. A subagent gets its expertise by connecting to that graph.
- Users can add new skills.
- The Platform page shows this as soon as it opens.

### Decisions made during brainstorming
| Question | Decision |
|---|---|
| Who runs the subagents? | **The coding agent.** LUNA plans, serves skills, tracks and assembles. It never writes code or calls an LLM to generate code. |
| How are skills authored? | **SKILL.md folders** (the Claude Code / Antigravity skill format), imported into FalkorDB. |
| What does the Platform page show? | **Agent mission control** as the default tab. Cases stays as a second tab; Skills is a third. |
| How is a prompt turned into tasks? | **Graph-native planning.** Prompt → Capability/Technology nodes → expand graph edges → task DAG. An LLM is optional and limited to the existing vocabulary. |

### Success criteria
1. Claude Code and Antigravity each connect to LUNA with one documented config step.
2. From either agent, the prompt "build me a portfolio website with React" produces:
   - a task DAG with one assigned skill per task;
   - subagents (or sequential turns) that each fetch their skill, do the work and submit;
   - an assembled report back in the agent.
3. Every skill choice, including rejected candidates, can be explained from `run_<id>`.
4. The Platform Agents tab shows connection status and the run's DAG updating live.
5. A new SKILL.md can be added (folder, upload or MCP tool) and is assignable after it is approved.

### Out of scope (v1)
- LUNA running its own LLM workers to generate code.
- Verifying files on the agent's disk. LUNA records what the agent reports.
- Multi-user support. Auth beyond an optional bearer token on `/mcp`.
- Removing the existing build pack (`luna/packs/build/`). It stays until Forge replaces it in the UI.

## 2. Architecture

```
Claude Code / Antigravity ──Streamable HTTP──▶ FastAPI app (luna/api/app.py)
                                               ├── /mcp        Forge MCP server (luna/forge/mcp_server.py)
                                               ├── /api/forge/* REST + SSE for the Platform page
                                               └── existing /api/* routes (unchanged)
                                                       │
                                                       ▼
                                             FalkorDB
                                               atlas     skill graph (extended)
                                               run_<id>  tasks, assignments, results
```

One process serves both the agent and the UI, so connection and run events reach the Platform page through the same event bus.

### Units

| Module | Responsibility | Depends on |
|---|---|---|
| `luna/forge/skill_import.py` | Parse a SKILL.md folder into a `SkillDoc`; validate; write nodes and edges into `atlas`; reject `REQUIRES`/`BEFORE` cycles. | `GraphStore`, schema |
| `luna/forge/planner.py` | `plan(prompt, hints) -> Plan`: match, expand, wave-sort, assign skills, record candidates. | `GraphStore`, optional `LLMClient` |
| `luna/forge/runs.py` | Task lifecycle state machine: claim with lease, submit, status queries, lease expiry. Persists in `run_<id>`. | `GraphStore` |
| `luna/forge/briefing.py` | Build the `luna_get_skill` payload: skill body, section index, upstream results, checklist. | `GraphStore` |
| `luna/forge/assemble.py` | Deterministic merge of results into a report; overlap detection; optional LLM summary; EMA score updates. | `GraphStore`, `atlas.learner`, optional `LLMClient` |
| `luna/forge/events.py` | In-process pub/sub for forge events (agent connected, run created, task changed). | none |
| `luna/forge/mcp_server.py` | FastMCP server: tools, `/luna-build` prompt, session tracking. Thin layer over the units above. | all of the above |
| `luna/api/app.py` | Mount `/mcp`; add `/api/forge/*` routes and `/api/forge/events` SSE. | `luna/forge` |
| `skills/` (repo root) | Starter skill library (trusted). | none |
| `ui/src/pages/Platform.tsx` + `ui/src/components/forge/*` | Agents and Skills tabs. | `/api/forge/*` |

Each unit is testable without the MCP layer.

## 3. MCP surface

Transport: **Streamable HTTP** at `/mcp` via `FastMCP.streamable_http_app()`. The installed `mcp` 1.30.0 supports it, so the `mcp<2.0` pin stays.

Tool schemas use only strings, integers, booleans, lists of strings and lists of flat objects. No unions or `anyOf`, for Gemini compatibility. Tool names match `^[a-z_]+$`.

| Tool | Input | Output |
|---|---|---|
| `luna_plan` | `prompt: str`, `stack_hints: list[str] = []` | `run_id`, `status` (`planned` or `needs_input`), `question?`, `tasks[]` (`task_id`, `title`, `capability`, `skill_id`, `depends_on[]`, `wave`), `waves[][]` |
| `luna_get_skill` | `run_id`, `task_id`, `agent_label: str = ""`, `section: str = ""` | No `section`: claims the task and returns the briefing (see §5). With `section`: returns that section only (task must already be claimed by this session). |
| `luna_submit` | `run_id`, `task_id`, `summary: str`, `files: list[str]`, `checks: list[{id, passed, note}]` | `accepted: bool`, `errors[]`, `unlocked_tasks[]` |
| `luna_assemble` | `run_id` | Report (see §7) |
| `luna_add_skill` | `skill_md: str`, `references: list[{name, content}] = []` | `skill_id`, `status: pending_review`, `warnings[]` |
| `luna_search_skills` | `query: str`, `limit: int = 10` | `skills[]` (`id`, `name`, `description`, `capabilities[]`, `technologies[]`, `status`) |

### `/luna-build` MCP prompt (the playbook)
Argument: `request`. The prompt tells the host agent to:
1. Call `luna_plan` with the request. If the result is `needs_input`, ask the user the returned question and re-plan.
2. For each wave, take every task in it:
   - **Parallel mode** (the host can spawn subagents): spawn one subagent per task. The subagent's only instruction is: "Call `luna_get_skill(run_id, task_id)` first and work only from its briefing; when finished call `luna_submit`."
   - **Sequential mode** (otherwise): handle each task yourself, in order. Treat each briefing as a fresh assignment and do not carry assumptions across tasks.
3. Move to the next wave only after every task in the current wave is submitted.
4. Call `luna_assemble` and present the report to the user.

### Connection snippets (shown in the UI and in `docs/runbook.md`)
- **Claude Code:** `claude mcp add --transport http luna http://localhost:8000/mcp`
  - With a token, add `--header "Authorization: Bearer <token>"`.
- **Antigravity:** `{"mcpServers": {"luna": {"serverUrl": "http://localhost:8000/mcp"}}}`
  - With a token, add `"headers": {"Authorization": "Bearer <token>"}`.
  - Edit via Agent panel → MCP menu → Manage MCP Servers → View raw config. Sources disagree between `~/.gemini/antigravity/mcp_config.json` and `~/.gemini/config/mcp_config.json`, so the UI points at the menu rather than a path.

### Session tracking
On MCP `initialize`, record `clientInfo.name`/`version` and the session id. Update `last_seen` on every call. Emit `agent_connected` and `agent_seen` events. A session is shown as disconnected after 5 minutes without calls. This is in memory only; it is not persisted.

## 4. Skill graph

### SKILL.md format
```markdown
---
name: react-vite-pages
description: Build pages and components for a React + Vite + TypeScript site.
# Optional LUNA keys
capabilities: [implement_frontend]
technologies: [React, Vite, TypeScript]
requires: [project-scaffold]
checklist:
  - id: routes
    text: Every page in the plan has a route.
  - id: responsive
    text: Layout works at 375px width.
---
Core instructions…

## Routing
…
```
- `references/*.md` files are imported as extra sections.
- `id` is the folder name, or a slug of `name` for `luna_add_skill`.

### Nodes (in `atlas`)
| Label | Key properties |
|---|---|
| `Skill` (existing, extended) | `id`, `name`, `description`, `body`, `source` (`repo`/`upload`/`mcp`), `status` (`approved`/`pending_review`/`rejected`), `restricted`, `content_hash`, `imported_at` |
| `Section` (new) | `id` (`<skill>#<slug>`), `title`, `content`, `order` |
| `ChecklistItem` (new) | `id` (`<skill>#<item>`), `text` |
| `Capability` (existing) | `name`, `description`, `aliases[]` (new) |
| `Technology` (existing) | `name`, `category`, `aliases[]` (new) |

### Edges
| Edge | Meaning |
|---|---|
| `(Skill)-[:PROVIDES]->(Capability)` | existing |
| `(Skill)-[:TARGETS]->(Technology)` | existing |
| `(Skill)-[:REQUIRES]->(Skill)` | new; a prerequisite skill whose task must run first |
| `(Capability)-[:BEFORE]->(Capability)` | new; ordering, e.g. `scaffold_project` before `implement_frontend` |
| `(Skill)-[:HAS_SECTION]->(Section)`, `(Skill)-[:HAS_CHECK]->(ChecklistItem)` | new |
| `(Skill)-[:SUCCEEDED_ON]->(TaskType {name:'software_build'})` | existing score edge |

### Import rules
- **Idempotent `MERGE` by `id`.** Re-importing an unchanged `content_hash` is a no-op. A changed hash replaces the sections and checklist, while scores are kept.
- **Unknown names.** A capability, technology or required skill that doesn't exist yields a warning and no edge. Capabilities and technologies are never auto-created from skill files.
- **Cycles.** If adding the skill's `REQUIRES` edges creates a cycle, the import is rejected.
- **Missing LUNA keys.** If an LLM is reachable, it proposes capability and technology links chosen only from existing names. The proposals are stored as warnings for the user to accept in the UI, not as edges. Otherwise the skill is "unlinked".
- **Trust.**
  - Repo `skills/` imports become `approved`. They are imported at app startup and by `POST /api/forge/skills/reimport`.
  - Upload and `luna_add_skill` imports become `pending_review`.
  - Only `approved`, non-restricted skills are assignable.
- **Limits.** `skill_md` ≤ 100 KB; ≤ 20 references, each ≤ 100 KB.

### Starter library (`skills/`)
`project-scaffold`, `react-vite-pages`, `ui-styling`, `backend-api`, `database-schema`, `qa-verification`. Each has capabilities, technologies, `requires` and a checklist.

The seed also adds capability `BEFORE` edges: `scaffold_project → implement_database → implement_backend → implement_frontend → verify_contracts`, and adds aliases (e.g. "website", "site", "landing page" → `implement_frontend`).

## 5. Planning (`luna_plan`)
1. **Match.**
   - Lowercase the prompt plus `stack_hints`, then match Capability and Technology names and aliases on word boundaries.
   - If an LLM is reachable, also ask it to choose from the full list of existing capability and technology names. Unknown names in its answer are dropped. The union of both results is used.
   - If no Capability matches, but Technologies matched, use the capabilities that skills targeting those technologies provide.
   - If still nothing matches, return `needs_input` with a question listing the available capabilities.
2. **Expand.**
   - Each matched capability becomes a task.
   - Add the transitive `BEFORE` predecessors that some approved skill provides, e.g. scaffolding.
   - After assignment, add tasks for each chosen skill's `REQUIRES` skills that are not already covered.
3. **Order.**
   - Dependencies come from `BEFORE` between task capabilities and from `REQUIRES` between chosen skills.
   - Topological sort into waves; ties are ordered by capability name for determinism.
4. **Assign.**
   - Candidates are skills that `PROVIDES` the capability, have `status='approved'` and are not restricted.
   - Score = matched-technology overlap count, then `SUCCEEDED_ON` score, then id.
   - The best candidate wins. If there is no candidate, the task is `unskilled`.
5. **Persist** to `run_<id>`:
   - `(:Run {id, prompt, status, agent_session, created_at})`
   - `(:Task {id, title, capability, wave, status})-[:PART_OF]->(:Run)`
   - `(:Task)-[:DEPENDS_ON]->(:Task)`
   - `(:Assignment {skill_id, score, reason})` linked from the task
   - `(:Candidate {skill_id, score, rejected_reason})` for each losing or excluded candidate
   - Emit `run_created`.

The same prompt, hints and graph state always yield the same plan when no LLM is used.

## 6. Task lifecycle and briefings

States: `pending` → `ready` (all `DEPENDS_ON` tasks `done`) → `claimed` → `submitted` → `done`; or `failed`.

- **Claim.** The first `luna_get_skill` without `section` claims a `ready` task for the calling session, with `lease_expires_at = now + 15 min` (configurable via `LUNA_FORGE_LEASE_MIN`).
  - Calling again from the same session re-sends the briefing and renews the lease.
  - A claim from another session on an unexpired lease is refused.
  - Expired leases return to `ready` and emit `task_stalled`. Expiry is checked lazily on any run access and by a 60 s background sweep.
- **Not ready.** The error lists the blocking task ids and their states.
- **Briefing payload:**
  - `task`;
  - `skill` (`id`, `name`, `description`, `body`);
  - `sections_index[]` (`title`, `chars`);
  - `checklist[]`;
  - `upstream[]` (each finished dependency's `task_id`, `summary`, `files`);
  - `rules`: "work only within this task; report all files you created or changed; mark every checklist item".
  - The body is truncated at 12,000 characters with a note to fetch sections.
  - An `unskilled` task gets a generic briefing built from the capability description.
- **Submit.**
  - The task must be `claimed` by the calling session.
  - Every check `id` must belong to the skill's checklist; missing items count as not passed.
  - `files` must be relative paths without `..`.
  - On success: the task becomes `done`, a `(:Result {summary, files, checks_json, submitted_at})` is linked, and dependent tasks may become `ready`. `task_updated` is emitted.
  - A task with zero passed checks out of ≥1 is still `done`, but is flagged in the report.
- **Failure.** There is no failure tool in v1. A task that is never submitted stays stalled and is reported as missing in assembly.

## 7. Assembly (`luna_assemble`)
Callable at any time; the report says whether the run is complete. The report contains:
- **status:** `complete`, or `incomplete` with the missing task ids;
- **tasks:** in wave order, with skill, summary, files, and checks passed/total;
- **overlaps:** files reported by more than one task;
- **gaps:** `unskilled` tasks and tasks with failed checks;
- **summary:** an LLM-written paragraph if an LLM is reachable, otherwise a template sentence.

When the run is complete and assembled for the first time:
- Each assigned skill's `SUCCEEDED_ON` score is updated with `atlas.learner.update_skill_score`, using reward = passed/total checks (1.0 if the skill has no checklist).
- The run becomes `assembled`, and `run_assembled` is emitted.

Re-assembly does not re-apply learning.

## 8. REST and SSE for the Platform page
| Route | Purpose |
|---|---|
| `GET /api/forge/agents` | Connected sessions |
| `GET /api/forge/runs`, `GET /api/forge/runs/{run_id}` | Run list; run detail with tasks, assignments, candidates, results, report |
| `GET /api/forge/events` | SSE: `agent_connected`, `agent_seen`, `run_created`, `task_updated`, `task_stalled`, `run_assembled`, `skill_imported` |
| `GET /api/forge/skills`, `GET /api/forge/skills/{id}` | Library list; detail with sections, checklist and graph neighbourhood |
| `POST /api/forge/skills/upload` | Multipart SKILL.md (+ references) → `pending_review` |
| `POST /api/forge/skills/{id}/approve`, `POST /api/forge/skills/{id}/reject` | Review gate |
| `POST /api/forge/skills/reimport` | Re-import the repo `skills/` folder |

## 9. Platform UI
- `Platform.tsx` gets a tab bar: **Agents** (default), **Cases** (current workspace, unchanged), **Skills**. The tab is kept in the URL (`?tab=`).
- **Agents tab:**
  - Connect card with copy buttons for both snippets (and the token variants when `LUNA_MCP_TOKEN` is set; the token itself is never shown).
  - Connected agents list.
  - Runs list.
  - Live run view: task DAG on the existing `GraphCanvas`, with nodes coloured by status and edges for dependencies. Each task card shows the skill (with a "Why this skill?" popover listing candidates), the claimer, a lease countdown and the submission. The assembled report is shown below.
- **Skills tab:**
  - Library table filterable by status, capability and technology.
  - Detail panel with sections, checklist, warnings and a neighbourhood graph.
  - Upload control.
  - Pending-review queue with approve and reject buttons.
- Follows the existing Hyperstudio tokens and passes `design-lint` and the axe checks.
- `ui/src/api` gets matching `LiveApi` and `MockApi` methods plus mock fixtures, so the UI runs without a backend.

## 10. Security
- **Host checks.** `/mcp` uses FastMCP transport security, with allowed hosts `localhost`/`127.0.0.1` plus `LUNA_MCP_ALLOWED_HOSTS`.
- **Optional token.** If `LUNA_MCP_TOKEN` is set, `/mcp` requires `Authorization: Bearer <token>` and answers 401 otherwise. The `/api/forge/*` routes follow the existing API stance (no auth, CORS allowlist); that remains a known gap.
- **Untrusted skills.** Skills from upload and MCP can't be assigned until approved, because skill text is injected into agents' prompts.
- **Parameterized Cypher.** All Cypher is parameterized; labels and edge types come from `luna/graph/schema.py` constants.
- **Bounds.** Size limits on all inputs. `files` paths are validated, never opened.

## 11. Error handling summary
| Situation | Behaviour |
|---|---|
| FalkorDB unreachable | Tools return an MCP error "LUNA graph store unavailable"; `/api/health` already reports it. |
| LLM unreachable | Planning and import continue with keywords only; the summary uses the template. |
| Unknown `run_id`/`task_id` | Error naming the id. |
| Claim conflict, not ready, bad submit | Error with the specific reason (§6). |
| Import invalid (no frontmatter, no `name`, cycle, too large) | Rejected with reasons; nothing written. |

## 12. Testing
- **Unit:** use pytest markers that match the current suite.
  - `test_forge_import.py`: frontmatter parse, sections and references, unknown names → warnings, cycle rejection, hash no-op, trust status by source.
  - `test_forge_planner.py`:
    - fixed DAG and waves for "build me a portfolio website with React";
    - prerequisite expansion;
    - restricted and pending skills excluded;
    - `needs_input` on no match;
    - determinism.
  - `test_forge_runs.py`: claim and lease renewal, cross-session refusal, expiry back to ready, not-ready errors, submit validation, unlocking.
  - `test_forge_assemble.py`: complete vs incomplete, overlaps, gaps, learning applied once.
- **Integration:** `test_forge_mcp.py` runs the app in-process, connects with `mcp.client.streamable_http` and runs plan → get_skill → submit for all tasks → assemble against live FalkorDB. It also covers the token on and off.
- **UI:**
  - Vitest for the forge reducer and the Agents and Skills components.
  - Playwright e2e for the Agents tab rendering a mock run, and for the Skills approve flow.
  - Design-lint and axe pass.
- **Manual smoke:** Claude Code and Antigravity each connect and complete `/luna-build` for a small site. Record the results in `docs/runbook.md`.

## 13. Open risks
- **Antigravity subagents.** It is unconfirmed whether Antigravity can spawn subagents within one conversation. Sequential mode covers this; the manual smoke test confirms which mode it uses.
- **Self-reported checks.** Checklist results come from the agent, so the learning signal is weak.
- **Host compliance.** Agents may ignore the playbook. LUNA's lifecycle errors keep the graph consistent, but can't force the order of work.
