# LUNA Forge MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose LUNA as a Streamable HTTP MCP server. Claude Code and Antigravity connect to it, send a build prompt, and get a skill-graph-planned task DAG. Their subagents fetch skills from FalkorDB, submit results, and receive an assembled report. The Platform page shows all of this live.

**Architecture:** A new `luna/forge/` package holds pure graph-facing units: parse, import, plan, runs, briefing, assemble, events, sessions. A thin FastMCP layer is mounted at `/mcp` on the existing FastAPI app, and `/api/forge/*` REST+SSE routes feed new Agents and Skills tabs on the Platform page. The coding agent does all code writing; LUNA never generates code.

**Tech Stack:** Python 3.12, FastAPI, `mcp` 1.30 (FastMCP, Streamable HTTP), FalkorDB via `GraphStore`, PyYAML, pytest. On the UI side: React 18 + TS, cytoscape + cytoscape-dagre, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-19-luna-forge-mcp-design.md`

## Global Constraints

- Keep the `mcp>=1.0.0,<2.0.0` pin. Use `FastMCP.streamable_http_app()` with `streamable_http_path="/"`, mounted at `/mcp`.
- All Cypher goes through `GraphStore.query`/`read_query` with `$params`. Labels and edge types come from `luna/graph/schema.py` constants. Note that `GraphStore._validate_query_safety` rejects any query containing `{}` or `%s`. Never write an empty map literal; put text content in params only.
- Tool names match `^[a-z_]+$`. Tool parameter types are only `str`, `int`, `bool`, `list[str]` and lists of flat objects. No `Optional`/`Union` in tool signatures; use defaults (`""`, `[]`).
- Limits:
  - `skill_md` ≤ 100 KB.
  - ≤ 20 references, each ≤ 100 KB.
  - Briefing body truncated at 12,000 chars.
  - Lease 15 min (`LUNA_FORGE_LEASE_MIN`).
  - Lease sweep every 60 s.
  - Session shown as disconnected after 5 min idle.
- Submit limits (plan decision implementing spec §10 "size limits on all inputs"): `summary` ≤ 20,000 chars; `files` ≤ 500 entries, each ≤ 300 chars, relative, no `..`, no leading `/` or `\`, no drive letter.
- Skill status values: `approved`, `pending_review`, `rejected`. Sources: `repo` → `approved`; `upload`/`mcp` → `pending_review`.
- Task status values: `pending`, `ready`, `claimed`, `done`, `failed`. `submitted` is transient: submit moves the task straight to `done`, as spec §6 allows.
- Env vars:
  - `LUNA_MCP_TOKEN` (optional bearer).
  - `LUNA_MCP_ALLOWED_HOSTS` (comma list, added to `localhost`, `127.0.0.1`, `localhost:*`, `127.0.0.1:*`).
  - `LUNA_FORGE_LEASE_MIN`.
- Python tests that need FalkorDB use the `live_store` and `tmp_graph` fixtures from `tests/conftest.py` and are marked `@pytest.mark.integration`.
- UI follows existing Hyperstudio tokens and must pass `npm run test:lint` (design-lint) and the axe checks used in `ui/e2e/luna.spec.ts`.

### Spec corrections adopted by this plan (flag in review)

1. **Expansion rule (§5.2).**
   - **Problem:** Literal "add transitive `BEFORE` predecessors" plus the chain `scaffold → database → backend → frontend` would make every website plan include database and backend tasks.
   - **Plan rule:** Capabilities carry a `role` property:
     - `foundation` (`scaffold_project`) is always added when any skill provides it.
     - `finalizer` (`verify_contracts`) is always added last when any skill provides it.
     - All others (`implement_database`, `implement_backend`, `implement_frontend`, `style_ui`) are added only when matched or required.
   - `BEFORE` edges only order tasks that are present, transitively through absent capabilities.
2. **New capability `style_ui`** (for the `ui-styling` starter skill), so styling is its own task, parallel to pages. This matches the spec's example DAG.
   - `BEFORE` edges: `scaffold_project → style_ui → verify_contracts`.
3. **New route `GET /api/forge/connect`.** It returns `mcp_url`, `token_required` and both snippets. The UI needs it to render §9's connect card without hard-coding the port.
4. **New `ForgeDag` component.** The DAG uses it (cytoscape + dagre directly) instead of `GraphCanvas`, whose props are trace-tour specific (`mode`, `stepIndex`, `steps`).

## Review Focus

1. **Windows-authored SKILL.md** (CRLF line endings, UTF-8 BOM) must parse identically to LF files. Covered by `test_parse_crlf_and_bom` in Task 1.
2. **Prompt naming an unknown stack** ("build me a Flutter mobile app") must return `needs_input` listing capabilities, not a plan with unrelated tasks. Covered by `test_plan_unknown_stack_needs_input` in Task 3.
3. **Agent reconnects with a new MCP session mid-run** and calls `luna_get_skill` on its old claimed task. It must get an error naming the lease expiry time; after expiry the new session can claim. Covered by `test_claim_conflict_reports_expiry` in Task 4.
4. **Oversized or hostile submissions** (10,001 files, `../../etc/passwd`, `C:\x`) are rejected with per-field errors, and nothing is written. Covered by `test_submit_rejects_bad_paths_and_limits` in Task 4.
5. **FalkorDB down during a tool call** must return an MCP tool error with the text `LUNA graph store unavailable` instead of a 500 or a hung session. Covered by `test_mcp_store_down_returns_tool_error` in Task 7.

---

## File Structure

**Backend (create):**
- `luna/forge/__init__.py`: public exports.
- `luna/forge/models.py`: Pydantic models shared by all forge units.
- `luna/forge/skill_parse.py`: SKILL.md text → `SkillDoc` (no graph access).
- `luna/forge/vocab.py`: seeds capabilities (with `role`, `aliases`), technology aliases, `BEFORE` edges.
- `luna/forge/skill_import.py`: `SkillDoc` → atlas graph; cycle check; status changes; repo folder import.
- `luna/forge/planner.py`: prompt → `PlanDraft` (reads atlas only).
- `luna/forge/runs.py`: run persistence, lifecycle, leases, run index.
- `luna/forge/briefing.py`: briefing and section payloads.
- `luna/forge/assemble.py`: assembly report and learning.
- `luna/forge/events.py`: `ForgeEventBus`.
- `luna/forge/sessions.py`: `SessionRegistry`.
- `luna/forge/mcp_server.py`: FastMCP tools, `/luna-build` prompt, bearer middleware, ASGI app factory.
- `luna/forge/routes.py`: `register_forge_routes(app, ...)` for `/api/forge/*`.
- `skills/<6 starter skills>/SKILL.md`.

**Backend (modify):**
- `luna/graph/schema.py`: new constants.
- `pyproject.toml`: add `pyyaml>=6.0`.
- `luna/api/app.py`: lifespan for the MCP session manager, mount `/mcp` before the static mount at line ~1270, call `register_forge_routes`, repo skill import at startup.
- `docs/runbook.md`: connect instructions and manual smoke checklist.

**Tests (create):** `tests/test_forge_parse.py`, `test_forge_import.py`, `test_forge_planner.py`, `test_forge_runs.py`, `test_forge_assemble.py`, `test_forge_mcp.py`, `test_forge_routes.py`.

**UI (create):**
- `ui/src/api/mock/forgeMock.ts`
- `ui/src/state/forgeReducer.ts`
- `ui/src/components/forge/`: `ConnectCard.tsx`, `AgentList.tsx`, `RunList.tsx`, `RunView.tsx`, `TaskCard.tsx`, `ForgeDag.tsx`, `AssemblyReportView.tsx`, `AgentsTab.tsx`, `SkillsTab.tsx`, `SkillDetail.tsx`, `SkillUpload.tsx`, `ReviewQueue.tsx`, `forge.css`
- `ui/src/pages/platform/CaseWorkspace.tsx`
- `ui/src/test/forgeReducer.test.ts`, `ui/src/test/forgeAgents.test.tsx`, `ui/src/test/forgeSkills.test.tsx`
- `ui/e2e/forge.spec.ts`

**UI (modify):** `ui/src/api/contract.ts`, `ui/src/api/live.ts`, `ui/src/api/mock/mockApi.ts`, `ui/src/dev/mockApi.ts`, `ui/src/pages/Platform.tsx`.

---

### Task 1: Forge models, schema constants and SKILL.md parser

**Files:**
- Create: `luna/forge/__init__.py`, `luna/forge/models.py`, `luna/forge/skill_parse.py`
- Modify: `luna/graph/schema.py` (append constants), `pyproject.toml` (dependency)
- Test: `tests/test_forge_parse.py`

**Interfaces:**
- Produces, in `luna/graph/schema.py`:
  - `LABEL_SECTION="Section"`, `LABEL_CHECKLIST_ITEM="ChecklistItem"`, `LABEL_RUN="Run"`, `LABEL_ASSIGNMENT="Assignment"`, `LABEL_CANDIDATE="Candidate"`, `LABEL_RESULT="Result"`, `LABEL_FORGE_RUN="ForgeRun"`
  - `REL_BEFORE="BEFORE"`, `REL_HAS_SECTION="HAS_SECTION"`, `REL_HAS_CHECK="HAS_CHECK"`, `REL_PART_OF="PART_OF"`, `REL_ASSIGNED="ASSIGNED"`, `REL_CONSIDERED="CONSIDERED"`, `REL_HAS_RESULT="HAS_RESULT"`
  - `GRAPH_FORGE_INDEX="forge_runs"`
  - `TASK_TYPE_SOFTWARE_BUILD="software_build"`
- Produces, in `luna/forge/models.py` (Pydantic v2):
  - `ChecklistDef(id: str, text: str)`
  - `SectionDef(slug: str, title: str, content: str, order: int)`
  - `SkillDoc(id, name, description, body: str, capabilities: list[str], technologies: list[str], requires: list[str], checklist: list[ChecklistDef], sections: list[SectionDef], content_hash: str)`
  - `ImportResult(skill_id: str, status: str, warnings: list[str], changed: bool)`
  - `PlanTask(task_id: str, title: str, capability: str, skill_id: str, depends_on: list[str], wave: int, status: str)`. `skill_id == ""` means unskilled.
  - `CandidateRecord(skill_id: str, score: float, overlap: int, rejected_reason: str)`
  - `PlanDraft(status: Literal["planned","needs_input"], question: str, matched_capabilities: list[str], matched_technologies: list[str], tasks: list[PlanTask], waves: list[list[str]], candidates: dict[str, list[CandidateRecord]])`
  - `Plan(run_id: str, status, question: str, tasks: list[PlanTask], waves: list[list[str]])`
  - `CheckReport(id: str, passed: bool, note: str = "")`
  - `SubmitResult(accepted: bool, errors: list[str], unlocked_tasks: list[str])`
  - `Briefing(run_id, task_id, task: PlanTask, skill: dict[str,str], sections_index: list[dict], checklist: list[ChecklistDef], upstream: list[dict], rules: list[str], truncated: bool)`
  - `AssemblyReport(run_id, status: Literal["complete","incomplete"], missing: list[str], tasks: list[dict], overlaps: dict[str, list[str]], gaps: list[dict], summary: str)`
  - `class ForgeError(Exception)` with `code: str` (`not_found`, `not_ready`, `claim_conflict`, `invalid`, `store_unavailable`).
- Produces, in `luna/forge/skill_parse.py`:
  - `class SkillParseError(ValueError)`
  - `parse_skill_md(text: str, references: list[tuple[str, str]] | None = None, default_id: str = "") -> SkillDoc`

- [ ] **Step 1: Write failing tests in `tests/test_forge_parse.py`**

```python
SAMPLE = """---
name: React Vite Pages
description: Build pages for a React + Vite site.
capabilities: [implement_frontend]
technologies: [React, Vite]
requires: [project-scaffold]
checklist:
  - id: routes
    text: Every page has a route.
---
Core instructions.

## Routing
Use react-router.

## Layout
Mobile first.
"""

def test_parse_frontmatter_and_sections():
    doc = parse_skill_md(SAMPLE, default_id="react-vite-pages")
    assert doc.id == "react-vite-pages"
    assert doc.name == "React Vite Pages"
    assert doc.capabilities == ["implement_frontend"]
    assert doc.requires == ["project-scaffold"]
    assert doc.checklist[0].id == "routes"
    assert doc.body.strip() == "Core instructions."
    assert [s.slug for s in doc.sections] == ["routing", "layout"]
    assert len(doc.content_hash) == 64

def test_parse_id_slug_from_name_when_no_default():
    assert parse_skill_md(SAMPLE).id == "react-vite-pages"

def test_parse_references_become_sections_after_body_sections():
    doc = parse_skill_md(SAMPLE, references=[("forms.md", "# Forms\nUse zod.")], default_id="x")
    assert doc.sections[-1].slug == "forms" and doc.sections[-1].order == 2

def test_parse_crlf_and_bom():
    crlf = "\ufeff" + SAMPLE.replace("\n", "\r\n")
    assert parse_skill_md(crlf, default_id="x").model_dump() == parse_skill_md(SAMPLE, default_id="x").model_dump()

@pytest.mark.parametrize("bad", ["no frontmatter", "---\ndescription: d\n---\nbody", "---\nname: [unclosed\n---\n"])
def test_parse_rejects_invalid(bad):
    with pytest.raises(SkillParseError):
        parse_skill_md(bad)

def test_parse_rejects_oversize():
    with pytest.raises(SkillParseError, match="100 KB"):
        parse_skill_md(SAMPLE + "x" * 102_401)

def test_parse_rejects_too_many_references():
    refs = [(f"r{i}.md", "x") for i in range(21)]
    with pytest.raises(SkillParseError, match="20"):
        parse_skill_md(SAMPLE, references=refs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_forge_parse.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'luna.forge'`

- [ ] **Step 3: Add the schema constants, the `pyyaml>=6.0` dependency, the models, and `parse_skill_md`**

Parsing details:
- Strip the BOM and normalize CRLF to LF before anything else.
- Frontmatter is the block between the first two `---` lines, parsed with `yaml.safe_load`. A missing block, a missing `name`, or a YAML error raises `SkillParseError`.
- The body is the text before the first `## ` heading. Each `## ` heading starts a `SectionDef`. The slug is lowercase, with non-alphanumerics replaced by `-` and the ends stripped.
- References are appended as sections. The title is the reference's first `# ` line, or else its filename stem; the slug comes from the filename stem.
- `content_hash` is sha256 of the normalized text plus each reference's name and content.
- The id is `default_id`, or else the slug of `name`.
- The size limits come from Global Constraints.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_forge_parse.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add luna/forge luna/graph/schema.py pyproject.toml tests/test_forge_parse.py
git commit -m "feat(forge): add forge models and SKILL.md parser"
```

---

### Task 2: Vocabulary seed and skill importer

**Files:**
- Create: `luna/forge/vocab.py`, `luna/forge/skill_import.py`
- Test: `tests/test_forge_import.py` (integration)

**Interfaces:**
- Consumes: `SkillDoc`, `ImportResult`, `parse_skill_md` (Task 1).
- Produces:
  - `seed_forge_vocabulary(store: GraphStore, atlas_graph: str = GRAPH_ATLAS) -> None`
  - `import_skill(store, doc: SkillDoc, source: Literal["repo","upload","mcp"], atlas_graph: str = GRAPH_ATLAS, llm: LLMClient | None = None) -> ImportResult`
  - `import_skill_dir(store, path: Path, source: str = "repo", atlas_graph: str = GRAPH_ATLAS) -> ImportResult`, which reads `SKILL.md` and `references/*.md`.
  - `set_skill_status(store, skill_id: str, status: Literal["approved","rejected"], atlas_graph: str = GRAPH_ATLAS) -> None`, which raises `ForgeError("not_found")`.
  - `CAPABILITY_ROLES: dict[str, str]`

Vocabulary values:

| Capability | role | aliases |
|---|---|---|
| `scaffold_project` | foundation | scaffold, setup, init, boilerplate |
| `implement_database` | normal | database, db, schema, sql, persistence |
| `implement_backend` | normal | backend, api, server, endpoint, rest |
| `implement_frontend` | normal | website, site, web app, webapp, landing page, page, pages, frontend, ui, portfolio |
| `style_ui` | normal | styling, style, design, theme, css, tailwind, responsive |
| `verify_contracts` | finalizer | test, qa, verify |

- `BEFORE` edges:
  - `scaffold_project→implement_database→implement_backend→implement_frontend→verify_contracts`
  - `scaffold_project→style_ui→verify_contracts`
- Technology aliases: `React`: react, `Vite`: vite, `Next.js`: next, nextjs, next.js, `TailwindCSS`: tailwind, `FastAPI`: fastapi, `Express`: express, `SQLite`: sqlite, `Postgres`: postgres, postgresql, `TypeScript`: typescript, ts, `Python`: python. Keep the existing `BUILD_TECHNOLOGIES` nodes.

- [ ] **Step 1: Write failing tests in `tests/test_forge_import.py`.** Every test is `@pytest.mark.integration` and uses `live_store`, `tmp_graph`, and `seed_forge_vocabulary(live_store, tmp_graph)` in a fixture.

```python
def test_vocab_seed_is_idempotent(live_store, atlas):
    seed_forge_vocabulary(live_store, atlas)
    rows = live_store.query(atlas, "MATCH (c:Capability) RETURN count(c) AS n")
    assert rows[0]["n"] == 6
    roles = live_store.query(atlas, "MATCH (c:Capability {name: $n}) RETURN c.role AS r", {"n": "scaffold_project"})
    assert roles[0]["r"] == "foundation"

def test_import_creates_skill_sections_checks_and_links(live_store, atlas):
    res = import_skill(live_store, parse_skill_md(SAMPLE_FRONTEND, default_id="react-vite-pages"), "repo", atlas)
    assert res.status == "approved" and res.changed and res.warnings == []
    # PROVIDES implement_frontend, TARGETS React+Vite, 2 sections, 1 check

def test_import_unknown_names_warn_without_edges(live_store, atlas):
    res = import_skill(live_store, doc_with(capabilities=["fly"], technologies=["Cobol"], requires=["ghost"]), "repo", atlas)
    assert sorted(res.warnings) == ["unknown capability 'fly'", "unknown required skill 'ghost'", "unknown technology 'Cobol'"]

def test_import_same_hash_is_noop_and_keeps_score(live_store, atlas): ...  # second import changed=False; SUCCEEDED_ON score unchanged

def test_import_changed_hash_replaces_sections(live_store, atlas): ...  # old section slug gone, new one present

def test_import_rejects_requires_cycle(live_store, atlas):
    import_skill(live_store, doc_with(id="a", requires=[]), "repo", atlas)
    import_skill(live_store, doc_with(id="b", requires=["a"]), "repo", atlas)
    with pytest.raises(ForgeError) as e:
        import_skill(live_store, doc_with(id="a", requires=["b"]), "repo", atlas)
    assert e.value.code == "invalid" and "cycle" in str(e.value)

@pytest.mark.parametrize("source,status", [("repo","approved"),("upload","pending_review"),("mcp","pending_review")])
def test_import_status_by_source(live_store, atlas, source, status): ...

def test_set_skill_status_and_missing(live_store, atlas): ...  # approve pending → approved; unknown id → ForgeError not_found
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_forge_import.py -v`
Expected: FAIL with `ImportError` for `luna.forge.vocab`

- [ ] **Step 3: Implement `seed_forge_vocabulary` and the importer**

- Use `MERGE` throughout.
- **Cycle check:** before writing anything, load the existing `REQUIRES` adjacency from atlas, add the new skill's edges in memory, and run a DFS. Raise `ForgeError("invalid", "requires cycle: a -> b -> a")` and write nothing.
- **Changed hash:** delete the skill's old `Section` and `ChecklistItem` nodes, then write new ones. Keep the `SUCCEEDED_ON` edge.
- **Initial score:** create `SUCCEEDED_ON` to `TaskType {name: 'software_build'}` with `score: 0.7, runs: 0` only `ON CREATE`.
- **Status:**
  - A re-import from the same source keeps an existing `approved`/`rejected` status unless the hash changed.
  - A changed hash on `upload`/`mcp` resets it to `pending_review`.
- **Missing LUNA keys:** when `capabilities` is empty and `llm` is given and `llm.info()["reachable"]`, ask `llm.complete_json` to choose from the existing capability and technology names. Append the suggestions as warnings in the form `"suggested capability 'x'"`; never as edges. Wrap the call in try/except so a failure only adds the warning `"llm suggestion unavailable"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_forge_import.py -v`
Expected: all passed (or skipped if FalkorDB is down; start it with `docker compose up -d`)

- [ ] **Step 5: Commit**

```bash
git add luna/forge/vocab.py luna/forge/skill_import.py tests/test_forge_import.py
git commit -m "feat(forge): seed build vocabulary and import skills into atlas"
```

---

### Task 3: Starter skill library and graph-native planner

**Files:**
- Create: `skills/project-scaffold/SKILL.md`, `skills/react-vite-pages/SKILL.md`, `skills/ui-styling/SKILL.md`, `skills/backend-api/SKILL.md`, `skills/database-schema/SKILL.md`, `skills/qa-verification/SKILL.md`, `luna/forge/planner.py`
- Modify: `luna/forge/skill_import.py`, adding `import_repo_skills(store, root: Path = Path("skills"), atlas_graph: str = GRAPH_ATLAS) -> list[ImportResult]`. It imports folders in dependency order: retry the warned `requires` once after all are loaded.
- Test: `tests/test_forge_planner.py` (integration)

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: `build_plan(store, prompt: str, stack_hints: list[str] | None = None, llm: LLMClient | None = None, atlas_graph: str = GRAPH_ATLAS) -> PlanDraft`

Starter skills:

| id | capabilities | technologies | requires | checklist ids |
|---|---|---|---|---|
| project-scaffold | scaffold_project | Vite, React, TypeScript, Node | (none) | `runs`, `readme` |
| react-vite-pages | implement_frontend | React, Vite, TypeScript | project-scaffold | `routes`, `responsive`, `a11y` |
| ui-styling | style_ui | TailwindCSS, React | project-scaffold | `tokens`, `contrast`, `mobile` |
| backend-api | implement_backend | FastAPI, Express, Python, Node | project-scaffold | `endpoints`, `errors`, `cors` |
| database-schema | implement_database | SQLite, Postgres | (none) | `schema`, `seed` |
| qa-verification | verify_contracts | TypeScript, Python | (none) | `build`, `smoke`, `contracts` |

Each skill body is 30–80 lines of concrete, stack-specific instructions, with at least two `##` sections.

Planner algorithm, in order:
1. **Match.** Lowercase `prompt + " " + " ".join(stack_hints)`. Match capability and technology names and aliases with word-boundary regexes (`re.escape`, `\b…\b`).
   - If `llm` is reachable, union in its picks from the closed list. Drop unknown names. Swallow exceptions.
2. **Technology-only fallback.** If no capability matched but technologies did, use the capabilities provided by approved skills that `TARGETS` those technologies.
3. **No match.** If still no capabilities, return `status="needs_input"`. The question is: `"I couldn't map that request to LUNA's skills. Which of these should I plan for: <comma-separated capability names>?"`
4. **Add roles.** Add `foundation` and `finalizer` capabilities that have at least one approved, non-restricted provider.
5. **Assign.** For each capability in sorted order:
   - Candidates are skills with `status='approved'` that are not restricted.
   - Score tuple: `(overlap, succeeded_on_score, -ord-sorted id)`. Choose the max.
   - Record every candidate, plus excluded ones (pending, rejected, restricted), as `CandidateRecord` with `rejected_reason` set to `""`, `"lower score"`, `"pending_review"`, `"rejected"` or `"restricted"`.
   - If there are no candidates, set `skill_id=""`.
6. **Required skills.** For each chosen skill's `REQUIRES` skill whose capability isn't present, add that capability's task with the required skill forced (reason `"required by <skill>"`). Repeat until stable.
7. **Dependencies.**
   - Task A depends on task B if B's capability reaches A's capability via `BEFORE` paths in the full capability graph.
   - Also, if A's skill `REQUIRES` B's skill.
8. **Waves.** Use Kahn's algorithm with ties sorted by capability name. `task_id = capability`. `title = capability.replace("_", " ").capitalize()`.

- [ ] **Step 1: Write failing tests.** The fixture seeds vocabulary into `tmp_graph` and runs `import_repo_skills(live_store, Path("skills"), tmp_graph)`.

```python
def test_repo_skills_import_clean(live_store, atlas):
    results = import_repo_skills(live_store, Path("skills"), atlas)
    assert len(results) == 6 and all(r.status == "approved" and r.warnings == [] for r in results)

def test_plan_portfolio_website(live_store, atlas):
    d = build_plan(live_store, "build me a portfolio website with React", atlas_graph=atlas)
    assert d.status == "planned"
    assert d.waves == [["scaffold_project"], ["implement_frontend"], ["verify_contracts"]]
    assert {t.task_id: t.skill_id for t in d.tasks} == {
        "scaffold_project": "project-scaffold", "implement_frontend": "react-vite-pages", "verify_contracts": "qa-verification"}

def test_plan_styling_runs_parallel_to_pages(live_store, atlas):
    d = build_plan(live_store, "build a website with tailwind styling", atlas_graph=atlas)
    assert d.waves[1] == ["implement_frontend", "style_ui"]

def test_plan_fullstack_orders_db_backend_frontend(live_store, atlas):
    d = build_plan(live_store, "build a todo web app with a FastAPI backend and sqlite database", atlas_graph=atlas)
    assert d.waves == [["scaffold_project"], ["implement_database"], ["implement_backend"], ["implement_frontend"], ["verify_contracts"]]

def test_plan_stack_hints_match(live_store, atlas):
    assert build_plan(live_store, "make something", ["nextjs", "website"], atlas_graph=atlas).status == "planned"

def test_plan_unknown_stack_needs_input(live_store, atlas):
    d = build_plan(live_store, "build me a Flutter mobile app", atlas_graph=atlas)
    assert d.status == "needs_input" and "implement_frontend" in d.question and d.tasks == []

def test_plan_excludes_pending_and_restricted(live_store, atlas):
    import_skill(live_store, better_frontend_doc, "upload", atlas)      # pending_review, higher overlap
    d = build_plan(live_store, "website with React", atlas_graph=atlas)
    assert task(d, "implement_frontend").skill_id == "react-vite-pages"
    assert any(c.rejected_reason == "pending_review" for c in d.candidates["implement_frontend"])

def test_plan_unskilled_task(live_store, atlas): ...   # restrict qa-verification → finalizer not added; restrict react-vite-pages → frontend task skill_id == ""

def test_plan_is_deterministic(live_store, atlas):
    a = build_plan(live_store, "website with React", atlas_graph=atlas)
    b = build_plan(live_store, "website with React", atlas_graph=atlas)
    assert a.model_dump() == b.model_dump()
```

Note: "with React" must not add backend or database. "web app" matches `implement_frontend` only.

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_forge_planner.py -v`
Expected: FAIL with `ImportError: build_plan`

- [ ] **Step 3: Write the six SKILL.md files, `import_repo_skills`, and `build_plan`** following the algorithm above.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_forge_planner.py tests/test_forge_import.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add skills luna/forge/planner.py luna/forge/skill_import.py tests/test_forge_planner.py
git commit -m "feat(forge): starter skill library and graph-native planner"
```

---

### Task 4: Run persistence, lifecycle and briefings

**Files:**
- Create: `luna/forge/runs.py`, `luna/forge/briefing.py`
- Test: `tests/test_forge_runs.py` (integration)

**Interfaces:**
- Consumes: `PlanDraft`, `PlanTask`, `Briefing`, `SubmitResult`, `CheckReport`, `ForgeError` (Task 1); `build_plan` (Task 3).
- Produces in `runs.py` (every function takes `now: datetime | None = None`, defaulting to UTC now):
  - `create_run(store, draft: PlanDraft, prompt: str, session_id: str, run_id: str | None = None) -> Plan`. It writes `run_<id>` (`Run`, `Task`, `DEPENDS_ON`, `Assignment`, `Candidate`) and the index node `(:ForgeRun {run_id, prompt, status, created_at, task_count})` in `GRAPH_FORGE_INDEX`. Wave-0 tasks start `ready`, the rest `pending`.
  - `claim_task(store, run_id, task_id, session_id, agent_label: str = "", lease_minutes: int | None = None, now=None) -> PlanTask`
  - `submit_task(store, run_id, task_id, session_id, summary: str, files: list[str], checks: list[CheckReport], atlas_graph: str = GRAPH_ATLAS, now=None) -> SubmitResult`
  - `expire_leases(store, run_id, now=None) -> list[str]`, which returns the task ids moved back to `ready`.
  - `get_run(store, run_id, now=None) -> dict` with keys `run`, `tasks` (each with `assignment`, `candidates`, `result`, `claimed_by`, `agent_label`, `lease_expires_at`), and `report`. It calls `expire_leases` first.
  - `list_runs(store, limit: int = 50) -> list[dict]`, newest first.
  - `set_run_status(store, run_id, status: str) -> None`
- Produces in `briefing.py`:
  - `build_briefing(store, run_id, task_id, atlas_graph: str = GRAPH_ATLAS) -> Briefing`
  - `get_section(store, skill_id: str, slug: str, atlas_graph: str = GRAPH_ATLAS) -> dict` with keys `title` and `content`.
  - `RULES: list[str]`, the three rules from spec §6.

Error contract (`ForgeError.code`, message):
- **Unknown run or task:** `not_found`, `"run 'x' not found"` / `"task 'y' not found in run 'x'"`.
- **Not ready:** `not_ready`, `"task 'y' is waiting on: scaffold_project (claimed)"`.
- **Held lease:** `claim_conflict`, `"task 'y' is claimed by another session until 2026-10-19T10:15:00+00:00"`.
- **Submit without the claim:** `invalid`, `"task 'y' is not claimed by this session"`.

Validation errors go in `SubmitResult.errors` with `accepted=False`, never as exceptions. They cover unknown check ids, path rules and limits. On any error nothing is written. Checklist items the agent omits count as `passed=False` with note `"not reported"`.

Unskilled briefing: `skill = {"id": "", "name": "Generic <title>", "description": <capability description>, "body": "No skill in the library covers this capability. Work from the capability description and the upstream results."}`

- [ ] **Step 1: Write failing tests (fixed `now` values, lease 15 min)**

```python
def test_create_run_initial_states(live_store, atlas, plan): ...   # wave-0 ready, others pending; ForgeRun index row exists

def test_claim_returns_task_and_renews_for_same_session(...):
    claim_task(store, rid, "scaffold_project", "s1", now=T0)
    t = claim_task(store, rid, "scaffold_project", "s1", now=T0 + timedelta(minutes=10))
    assert t.status == "claimed"
    # lease_expires_at == T0 + 25 min

def test_claim_conflict_reports_expiry(...):
    claim_task(store, rid, "scaffold_project", "s1", now=T0)
    with pytest.raises(ForgeError) as e:
        claim_task(store, rid, "scaffold_project", "s2", now=T0 + timedelta(minutes=1))
    assert e.value.code == "claim_conflict" and (T0 + timedelta(minutes=15)).isoformat() in str(e.value)
    assert claim_task(store, rid, "scaffold_project", "s2", now=T0 + timedelta(minutes=16)).status == "claimed"

def test_claim_not_ready_names_blockers(...):
    with pytest.raises(ForgeError, match="waiting on: scaffold_project"):
        claim_task(store, rid, "implement_frontend", "s1", now=T0)

def test_submit_unlocks_dependents(...):
    claim_task(...); r = submit_task(store, rid, "scaffold_project", "s1", "done", ["package.json"], [CheckReport(id="runs", passed=True)], atlas, now=T0)
    assert r.accepted and r.unlocked_tasks == ["implement_frontend"]

def test_submit_missing_checks_count_as_failed(...): ...   # stored checks include {"id":"readme","passed":False,"note":"not reported"}

@pytest.mark.parametrize("files,checks,err", [
    (["../../etc/passwd"], [], "invalid path"), (["C:\\x"], [], "invalid path"), (["/abs"], [], "invalid path"),
    ([f"f{i}" for i in range(501)], [], "at most 500 files"), (["a"], [CheckReport(id="bogus", passed=True)], "unknown check 'bogus'")])
def test_submit_rejects_bad_paths_and_limits(..., files, checks, err):
    r = submit_task(...); assert not r.accepted and any(err in e for e in r.errors)
    # task still claimed, no Result node

def test_submit_rejects_long_summary(...): ...   # 20_001 chars → "summary exceeds 20000 characters"

def test_submit_by_other_session_raises(...): ...  # ForgeError invalid

def test_briefing_contains_skill_checklist_upstream_and_truncation(...):
    # after scaffold submitted, briefing for implement_frontend: skill.id == "react-vite-pages",
    # upstream[0]["task_id"] == "scaffold_project", checklist ids == ["routes","responsive","a11y"], len(skill["body"]) <= 12000

def test_unskilled_briefing(...): ...
def test_get_section_unknown_slug_not_found(...): ...
def test_get_run_lazily_expires_leases(...): ...   # claim at T0, get_run(now=T0+16min) shows task ready
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_forge_runs.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `runs.py` and `briefing.py`**

- Store timestamps as ISO-8601 UTC strings and compare as `datetime`.
- Do dependency readiness in Python after reading the run's tasks. Run graphs are small.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_forge_runs.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add luna/forge/runs.py luna/forge/briefing.py tests/test_forge_runs.py
git commit -m "feat(forge): run lifecycle with leases and task briefings"
```

---

### Task 5: Assembly and learning

**Files:**
- Create: `luna/forge/assemble.py`
- Test: `tests/test_forge_assemble.py` (integration)

**Interfaces:**
- Consumes: `get_run`, `set_run_status` (Task 4); `update_skill_score(store, skill_id, task_type, reward, alpha, atlas_graph)` from `luna/atlas/learner.py`; `TASK_TYPE_SOFTWARE_BUILD` (Task 1).
- Produces: `assemble_run(store, run_id: str, llm: LLMClient | None = None, atlas_graph: str = GRAPH_ATLAS) -> AssemblyReport`

Report rules:
- `tasks` are in wave order. Each entry is `{task_id, wave, skill_id, status, summary, files, checks_passed, checks_total}`.
- `overlaps` maps each file reported by more than one task to the task ids, sorted.
- `missing` is the sorted ids of tasks not `done`.
- `gaps` entries:
  - `{task_id, kind: "unskilled"}` for each unskilled task;
  - `{task_id, kind: "failed_checks", failed: [...]}` for each task with failed checks;
  - `{task_id, kind: "missing"}` for each task not `done`.
- `summary`: if `llm` is reachable, `complete_text` over a compact JSON of the report. On failure or no LLM, use the template `"{done}/{total} tasks complete across {waves} waves; {n_files} files reported; {n_gaps} gaps."`
- Learning applies only when `status == "complete"` and the `Run` node lacks `learned_at`:
  - For each assigned skill, reward = passed/total, or 1.0 if total = 0. Use `alpha=0.2`.
  - Then set `learned_at` and run status `assembled`, and update the `ForgeRun` index status.
- Store the report JSON on the `Run` node (`report_json`) so `get_run` can return it.

- [ ] **Step 1: Write failing tests**

```python
def test_assemble_incomplete_lists_missing(...):
    rep = assemble_run(store, rid, atlas_graph=atlas)
    assert rep.status == "incomplete" and rep.missing == ["implement_frontend", "scaffold_project", "verify_contracts"]

def test_assemble_complete_overlaps_and_gaps(...):
    # submit all three; scaffold and frontend both report "src/main.tsx"; frontend fails "a11y"
    rep = assemble_run(store, rid, atlas_graph=atlas)
    assert rep.status == "complete"
    assert rep.overlaps == {"src/main.tsx": ["implement_frontend", "scaffold_project"]}
    assert {"task_id": "implement_frontend", "kind": "failed_checks", "failed": ["a11y"]} in rep.gaps
    assert rep.summary.startswith("3/3 tasks complete across 3 waves")

def test_assemble_learning_applies_once(...):
    before = score(atlas, "react-vite-pages")
    assemble_run(...); mid = score(...); assemble_run(...); after = score(...)
    assert mid == pytest.approx(0.8 * before + 0.2 * (2 / 3)) and after == mid

def test_assemble_llm_failure_falls_back_to_template(...): ...  # llm whose complete_text raises
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_forge_assemble.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `assemble_run`**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_forge_assemble.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add luna/forge/assemble.py tests/test_forge_assemble.py
git commit -m "feat(forge): deterministic run assembly with skill learning"
```

---

### Task 6: Event bus and session registry

**Files:**
- Create: `luna/forge/events.py`, `luna/forge/sessions.py`
- Test: `tests/test_forge_events.py` (unit, no FalkorDB)

**Interfaces:**
- Produces:
  - `class ForgeEventBus`
    - `publish(type: str, data: dict) -> dict` returns `{seq: int, ts: str, type, data}`.
    - `wait_after(seq: int, timeout: float) -> list[dict]` blocks until events newer than `seq` exist or the timeout passes.
    - It keeps the last 500 events. It is thread-safe via `threading.Condition`, the same pattern as `RunState` in `luna/api/app.py:84-118`.
  - `class SessionRegistry(bus: ForgeEventBus)`
    - `touch(session_id: str, client_name: str = "", client_version: str = "", now: datetime | None = None) -> None` publishes `agent_connected` for the first sighting and `agent_seen` at most once per 30 s per session after that.
    - `list(now: datetime | None = None) -> list[dict]` returns `{session_id, client_name, client_version, first_seen, last_seen, connected}`. `connected` is `now - last_seen < 5 min`. Newest first.
  - Event type constants in `events.py`: `AGENT_CONNECTED`, `AGENT_SEEN`, `RUN_CREATED`, `TASK_UPDATED`, `TASK_STALLED`, `RUN_ASSEMBLED`, `SKILL_IMPORTED`.

- [ ] **Step 1: Write failing tests**

```python
def test_bus_sequence_and_wait_after():
    bus = ForgeEventBus(); bus.publish("run_created", {"run_id": "r1"})
    assert [e["seq"] for e in bus.wait_after(0, 0.01)] == [1]
    assert bus.wait_after(1, 0.01) == []

def test_bus_ring_buffer_keeps_500(): ...

def test_sessions_connect_seen_throttle_and_disconnect():
    bus = ForgeEventBus(); reg = SessionRegistry(bus)
    reg.touch("s1", "claude-code", "2.1", now=T0); reg.touch("s1", now=T0 + timedelta(seconds=10)); reg.touch("s1", now=T0 + timedelta(seconds=40))
    assert [e["type"] for e in bus.wait_after(0, 0.01)] == ["agent_connected", "agent_seen"]
    assert reg.list(now=T0 + timedelta(minutes=6))[0]["connected"] is False
    assert reg.list(now=T0)[0]["client_name"] == "claude-code"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_forge_events.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement both classes**

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_forge_events.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add luna/forge/events.py luna/forge/sessions.py tests/test_forge_events.py
git commit -m "feat(forge): event bus and agent session registry"
```

---

### Task 7: FastMCP server mounted at `/mcp`

**Files:**
- Create: `luna/forge/mcp_server.py`
- Modify: `luna/api/app.py`
  - Add a FastAPI `lifespan` that runs `mcp.session_manager.run()`, starts the 60 s lease sweep thread, and runs `seed_forge_vocabulary` plus `import_repo_skills` at startup inside try/except with a logged warning.
  - Mount `/mcp` before the static UI mount near line 1270.
  - New `create_app` config keys: `forge_enabled` (default `True`), `forge_skills_dir` (default `"skills"`).
- Test: `tests/test_forge_mcp.py` (integration)

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces:
  - `create_forge_mcp(store: GraphStore, bus: ForgeEventBus, sessions: SessionRegistry, llm_factory: Callable[[], LLMClient | None], atlas_graph: str = GRAPH_ATLAS, allowed_hosts: list[str] | None = None) -> FastMCP`
  - `forge_asgi_app(mcp: FastMCP, token: str | None) -> ASGIApp`, the Streamable HTTP app wrapped in bearer middleware. On a mismatch it returns 401 JSON `{"error": "unauthorized"}`. With no token it passes everything through.
  - `BUILD_PROMPT_NAME = "luna-build"`

Tool implementations:
- Each tool calls `sessions.touch(session_id, client_name, client_version)` first.
  - `session_id` comes from the `mcp-session-id` header on `ctx.request_context.request`.
  - Client info comes from `ctx.session.client_params.clientInfo`, if present.
- Each tool then calls the matching forge function, publishes the matching event, and returns `model_dump()`.
- Events published:
  - `luna_plan` → `run_created {run_id, prompt}`.
  - A claim via `luna_get_skill` → `task_updated {run_id, task_id, status: "claimed", claimed_by, agent_label}`.
  - An accepted `luna_submit` → `task_updated` (`done`, with `result`) for the task, plus one `task_updated` (`ready`) per unlocked task.
  - `luna_assemble` → `run_assembled {run_id, report}`.
  - `luna_add_skill` → `skill_imported {skill_id, status}`.
  - The 60 s sweep thread calls `expire_leases` for each run in `list_runs` whose status is not `assembled`, and publishes `task_stalled {run_id, task_id, status: "ready"}` for each id returned.
- `ForgeError` is re-raised as `ToolError(f"{code}: {message}")` (from `mcp.server.fastmcp.exceptions`).
- Connection errors from FalkorDB (`redis.exceptions.ConnectionError`, `ConnectionError`, `OSError`) become `ToolError("store_unavailable: LUNA graph store unavailable")`.
- `luna_plan` returns `Plan` fields. For `needs_input` it still returns a `run_id` of `""` and no run is created.
- `luna_add_skill`:
  - Parses with `default_id=""`, imports with source `mcp`, and publishes `skill_imported`.
  - Parse errors become `ToolError("invalid: ...")`.
  - The `references` parameter is a list of `{name, content}` objects.
- `luna_get_skill` with a non-empty `section` checks that the task is claimed by this session, then returns `get_section`.
- `luna_search_skills` does case-insensitive substring search over id, name and description. It returns at most `limit`, capped at 50.
- The `/luna-build` prompt takes `request: str` and returns the playbook text from spec §3. It must name both parallel and sequential modes and all four core tools in order.
- Transport security: `TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=[...defaults + env], allowed_origins=["http://localhost:*", "http://127.0.0.1:*"])`.

- [ ] **Step 1: Write failing tests.** These run the real app with uvicorn on a free port in a background thread (fixture `forge_server`, `create_app(store=live_store, config={"atlas_graph": tmp_graph})`) and connect with `mcp.client.streamable_http.streamablehttp_client` plus `ClientSession`.

```python
async def test_mcp_lists_tools_and_prompt(forge_server):
    async with client(forge_server) as s:
        names = sorted(t.name for t in (await s.list_tools()).tools)
        assert names == ["luna_add_skill", "luna_assemble", "luna_get_skill", "luna_plan", "luna_search_skills", "luna_submit"]
        assert "luna-build" in [p.name for p in (await s.list_prompts()).prompts]

async def test_tool_schemas_are_gemini_safe(forge_server):
    # walk every inputSchema: no "anyOf"/"oneOf"/"allOf"; every property type in {"string","integer","boolean","array","object"}

async def test_mcp_end_to_end_build(forge_server):
    async with client(forge_server) as s:
        plan = json_of(await s.call_tool("luna_plan", {"prompt": "build me a portfolio website with React"}))
        for wave in plan["waves"]:
            for tid in wave:
                b = json_of(await s.call_tool("luna_get_skill", {"run_id": plan["run_id"], "task_id": tid}))
                checks = [{"id": c["id"], "passed": True, "note": ""} for c in b["checklist"]]
                r = json_of(await s.call_tool("luna_submit", {"run_id": plan["run_id"], "task_id": tid, "summary": "ok", "files": [f"{tid}.txt"], "checks": checks}))
                assert r["accepted"]
        rep = json_of(await s.call_tool("luna_assemble", {"run_id": plan["run_id"]}))
        assert rep["status"] == "complete" and rep["gaps"] == []

async def test_mcp_errors_are_tool_errors(forge_server): ...   # get_skill on pending task → isError, text starts "not_ready:"
async def test_mcp_add_skill_is_pending(forge_server): ...     # status == "pending_review"; search finds it
async def test_mcp_token_required(forge_server_with_token): ... # no header → 401; correct Bearer → initialize OK
async def test_mcp_rejects_foreign_host(forge_server): ...      # raw POST with Host: evil.example → 421 or 403
async def test_mcp_store_down_returns_tool_error(...): ...      # server built with GraphStore(port=1) → isError, "LUNA graph store unavailable"
async def test_sessions_record_client_name(forge_server): ...   # after initialize with clientInfo name "pytest-agent" and one tool call: app.state.forge_sessions.list()[0]["client_name"] == "pytest-agent"
```

Expose the registry as `app.state.forge_sessions` and the bus as `app.state.forge_bus` for tests and Task 8. Mark every test in the file with `pytest.mark.asyncio` and `pytest.mark.integration`.

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_forge_mcp.py -v`
Expected: FAIL with `ImportError: create_forge_mcp`

- [ ] **Step 3: Implement `mcp_server.py` and wire it into `create_app`**

- Build `FastMCP("luna", streamable_http_path="/", transport_security=...)`.
- `app.mount("/mcp", forge_asgi_app(mcp, os.environ.get("LUNA_MCP_TOKEN") or None))`.
- Because the app had no lifespan before, pass `lifespan=` to the `FastAPI(...)` constructor.

- [ ] **Step 4: Run the new tests and the existing API tests**

Run: `python -m pytest tests/test_forge_mcp.py tests/test_api.py -v`
Expected: all passed. The existing API tests are unchanged and still pass.

- [ ] **Step 5: Commit**

```bash
git add luna/forge/mcp_server.py luna/api/app.py tests/test_forge_mcp.py
git commit -m "feat(forge): mount Streamable HTTP MCP server at /mcp"
```

---

### Task 8: Forge REST and SSE routes

**Files:**
- Create: `luna/forge/routes.py`
- Modify: `luna/api/app.py` (call `register_forge_routes`)
- Test: `tests/test_forge_routes.py` (integration, FastAPI `TestClient`)

**Interfaces:**
- Consumes: Tasks 2–7, `app.state.forge_bus`, `app.state.forge_sessions`.
- Produces: `register_forge_routes(app: FastAPI, store: GraphStore, bus: ForgeEventBus, sessions: SessionRegistry, atlas_graph: str, skills_dir: Path) -> None`

| Route | Response |
|---|---|
| `GET /api/forge/connect` | `{mcp_url, token_required: bool, snippets: {claude_code, antigravity, claude_code_token, antigravity_token}}`. `mcp_url` comes from `request.base_url` + `mcp`. Token variants contain the literal `<token>`, never the real value. |
| `GET /api/forge/agents` | `sessions.list()` |
| `GET /api/forge/runs` | `list_runs(store)` |
| `GET /api/forge/runs/{run_id}` | `get_run`; 404 on `not_found` |
| `GET /api/forge/events?after=<seq>` | SSE via `StreamingResponse`, `text/event-stream`. Each event is `id: <seq>`, `event: <type>`, `data: <json>`. A 15 s keep-alive comment. Honours the `Last-Event-ID` header. |
| `GET /api/forge/skills` | `[{id, name, description, status, source, capabilities, technologies, warnings_count}]` |
| `GET /api/forge/skills/{id}` | Detail plus `sections`, `checklist`, `requires`, `required_by`, and `neighbourhood: {nodes, edges}` (1 hop: capabilities, technologies, skills). 404 if missing. |
| `POST /api/forge/skills/upload` | Multipart field `skill` (SKILL.md) and repeatable field `references`. Source `upload`. 413 over the limits, 422 on a parse error with the message. Publishes `skill_imported`. |
| `POST /api/forge/skills/{id}/approve` and `/reject` | 204; 404 if missing; publishes `skill_imported` with the new status |
| `POST /api/forge/skills/reimport` | `import_repo_skills` results |

- [ ] **Step 1: Write failing tests**

```python
def test_connect_snippets_without_token(client):
    body = client.get("/api/forge/connect").json()
    assert body["token_required"] is False
    assert body["snippets"]["claude_code"] == f"claude mcp add --transport http luna {body['mcp_url']}"
    assert json.loads(body["snippets"]["antigravity"]) == {"mcpServers": {"luna": {"serverUrl": body["mcp_url"]}}}

def test_connect_never_leaks_token(client_with_token):
    text = client_with_token.get("/api/forge/connect").text
    assert "s3cret" not in text and "<token>" in text

def test_upload_approve_flow(client): ...      # upload → pending_review; approve → approved; reject unknown → 404
def test_upload_parse_error_422(client): ...
def test_upload_too_large_413(client): ...
def test_runs_list_and_detail_404(client): ... # after creating a run via build_plan+create_run
def test_skill_detail_neighbourhood(client): ...  # react-vite-pages has edge to implement_frontend and project-scaffold
def test_events_stream_replays_after(client): ... # publish 2 events on app.state.forge_bus; GET ?after=1 reads "id: 2"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_forge_routes.py -v`
Expected: FAIL with 404s for `/api/forge/*`

- [ ] **Step 3: Implement `register_forge_routes` and call it from `create_app`** after the existing routes and before the static mount.

For the SSE test, add a `max_events: int = 0` query param that closes the stream after N events (0 means unlimited), so `TestClient` can finish.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_forge_routes.py tests/test_forge_mcp.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add luna/forge/routes.py luna/api/app.py tests/test_forge_routes.py
git commit -m "feat(forge): REST and SSE routes for the Platform page"
```

---

### Task 9: UI contract, LiveApi, mocks and reducer

**Files:**
- Modify: `ui/src/api/contract.ts`, `ui/src/api/live.ts`, `ui/src/api/mock/mockApi.ts`, `ui/src/dev/mockApi.ts`
- Create: `ui/src/api/mock/forgeMock.ts`, `ui/src/state/forgeReducer.ts`
- Test: `ui/src/test/forgeReducer.test.ts`, plus additions to `ui/src/test/liveApi.test.ts`

**Interfaces:**
- Produces, as types in `contract.ts` mirroring Task 8 JSON in snake_case like the existing types:
  - `ForgeConnectInfo`, `ForgeAgent`, `ForgeRunSummary`, `ForgeTask` (`task_id`, `title`, `capability`, `skill_id`, `depends_on`, `wave`, `status`, `claimed_by`, `agent_label`, `lease_expires_at`, `assignment`, `candidates`, `result`), `ForgeRunDetail` (`run`, `tasks`, `report`), `ForgeReport`, `ForgeEvent` (`seq`, `ts`, `type`, `data`), `ForgeSkillSummary`, `ForgeSkillDetail`.
- Produces, as `Api` methods:
  - `forgeConnect(): Promise<ForgeConnectInfo>`
  - `forgeAgents(): Promise<ForgeAgent[]>`
  - `forgeRuns(): Promise<ForgeRunSummary[]>`
  - `forgeRun(runId: string): Promise<ForgeRunDetail>`
  - `subscribeForge(opts: { lastEventId?: number; onEvent: (e: ForgeEvent) => void; onState: (s: 'open'|'reconnecting'|'closed') => void }): () => void`
  - `forgeSkills(): Promise<ForgeSkillSummary[]>`
  - `forgeSkill(id: string): Promise<ForgeSkillDetail>`
  - `uploadForgeSkill(skill: File, references: File[]): Promise<{ skill_id: string; status: string; warnings: string[] }>`
  - `approveForgeSkill(id: string): Promise<void>`
  - `rejectForgeSkill(id: string): Promise<void>`
  - `reimportForgeSkills(): Promise<{ skill_id: string; status: string; warnings: string[] }[]>`
- Produces in `forgeMock.ts`: `forgeMockMethods: Pick<Api, ...forge methods>`. It has one fixture run (the portfolio-website DAG with scaffold done, frontend claimed and qa pending), two agents (`claude-code` connected, `antigravity` idle), and the six starter skills plus one `pending_review`. `subscribeForge` replays a scripted sequence (`task_updated` frontend → done, qa → ready, `run_assembled`) with `mockEventSource`-style timers. Both mock files spread `...forgeMockMethods`.
- Produces in `forgeReducer.ts`:
  - `ForgeState = { agents: ForgeAgent[]; runs: ForgeRunSummary[]; activeRun: ForgeRunDetail | null; lastSeq: number; connection: 'open'|'reconnecting'|'closed' }`
  - `forgeReducer(state, action)` with actions `{type:'agents', agents}`, `{type:'runs', runs}`, `{type:'run', run}`, `{type:'event', event}`, `{type:'connection', state}`
  - `initialForgeState`

Reducer event rules:
- `agent_connected`/`agent_seen`: upsert the agent by `session_id`.
- `run_created`: prepend a summary.
- `task_updated`/`task_stalled`: patch the matching task in `activeRun` when `data.run_id` matches. The data carries `{run_id, task_id, status, claimed_by?, result?}`.
- `run_assembled`: set `activeRun.report = data.report` and update the run summary status.
- Events with `seq <= lastSeq` are ignored.

- [ ] **Step 1: Write failing tests in `forgeReducer.test.ts`**

```ts
it('patches task status for the active run only', () => { ... expect(task(s, 'implement_frontend').status).toBe('done') });
it('ignores duplicate or older seq', () => { ... });
it('upserts agents by session_id', () => { ... expect(s.agents).toHaveLength(1) });
it('stores report on run_assembled', () => { ... });
```

In `liveApi.test.ts`, add one case each: `forgeRun` GETs `/api/forge/runs/r1`, and `uploadForgeSkill` POSTs multipart with field names `skill` and `references`.

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ui && npx vitest run src/test/forgeReducer.test.ts src/test/liveApi.test.ts`
Expected: FAIL (module not found / method missing)

- [ ] **Step 3: Implement the types, `LiveApi` methods, `forgeMock.ts`, the mock wiring and the reducer**

`subscribeForge` reuses the EventSource reconnect pattern in `live.ts:184-200`, with URL `/api/forge/events?after=<lastEventId>`.

- [ ] **Step 4: Run tests and the type-check**

Run: `cd ui && npx vitest run src/test/forgeReducer.test.ts src/test/liveApi.test.ts && npx tsc --noEmit`
Expected: tests pass; tsc exits 0

- [ ] **Step 5: Commit**

```bash
git add ui/src/api ui/src/dev/mockApi.ts ui/src/state/forgeReducer.ts ui/src/test/forgeReducer.test.ts ui/src/test/liveApi.test.ts
git commit -m "feat(ui): forge API contract, live client, mocks and reducer"
```

---

### Task 10: Platform tabs and Agents tab

**Files:**
- Create: `ui/src/pages/platform/CaseWorkspace.tsx`. Move the current body of `Platform.tsx` here unchanged, as the default export `CaseWorkspace`.
- Create: `ui/src/components/forge/ConnectCard.tsx`, `AgentList.tsx`, `RunList.tsx`, `RunView.tsx`, `TaskCard.tsx`, `ForgeDag.tsx`, `AssemblyReportView.tsx`, `AgentsTab.tsx`, `forge.css`
- Modify: `ui/src/pages/Platform.tsx`, now a tab shell with tablist **Agents | Cases | Skills**. It uses the `?tab=` search param via `useSearchParams` and defaults to `agents`. Use `role="tablist"`/`role="tab"`/`aria-selected`/`role="tabpanel"`.
- Test: `ui/src/test/forgeAgents.test.tsx`; update `ui/src/test/platform.test.tsx` to use `?tab=cases` where it asserts case-workspace content.

**Interfaces:**
- Consumes: Task 9 `Api` methods and `forgeReducer`.
- Produces:
  - `AgentsTab()`: on mount, loads connect info, agents and runs, subscribes to forge events, and selects the newest run.
  - `ForgeDag({ tasks, selectedTaskId, onSelect })`: cytoscape with the `dagre` layout (`rankDir: 'LR'`). Node class is the task status. Edges come from `depends_on`. Colours come from CSS variables in `forge.css` mapped to existing tokens.
  - `TaskCard({ task, now })`: skill id, a "Why this skill?" `<details>` listing candidates with `rejected_reason`, claimer label, lease countdown `mm:ss`, and the submission summary, files and checks.
  - `ConnectCard({ info })`: two code blocks with copy buttons (`navigator.clipboard.writeText`). It shows the token variants only when `token_required`, plus the Antigravity hint text "Agent panel → MCP menu → Manage MCP Servers → View raw config".
- `AgentList` shows "No agents connected yet" when empty.

- [ ] **Step 1: Write failing tests (mock API)**

```tsx
it('defaults to the Agents tab and shows both connect snippets', async () => { ... getByText(/claude mcp add --transport http luna/); getByText(/"serverUrl"/) });
it('lists connected and idle agents', async () => { ... getByText('claude-code'); getByText(/idle/i) });
it('renders the run DAG task cards with skills', async () => { ... getByText('react-vite-pages') });
it('applies live task_updated events', async () => { ... await findByText(/done/) on implement_frontend card });
it('shows assembled report after run_assembled', async () => { ... findByText(/3\/3 tasks complete/) });
it('Cases tab still renders case workspace', async () => { ... });
```

Mock cytoscape in this test file the same way existing graph tests do (see `ui/src/test/traceView.test.tsx`).

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ui && npx vitest run src/test/forgeAgents.test.tsx src/test/platform.test.tsx`
Expected: FAIL

- [ ] **Step 3: Implement the components and the tab shell**

- [ ] **Step 4: Run unit tests, the type-check and design-lint**

Run: `cd ui && npx vitest run && npx tsc --noEmit && npm run test:lint`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add ui/src/pages ui/src/components/forge ui/src/test
git commit -m "feat(ui): Platform tabs with live Agents mission control"
```

---

### Task 11: Skills tab and Playwright e2e

**Files:**
- Create: `ui/src/components/forge/SkillsTab.tsx`, `SkillDetail.tsx`, `SkillUpload.tsx`, `ReviewQueue.tsx`, `ui/e2e/forge.spec.ts`
- Modify: `ui/src/pages/Platform.tsx` (render `SkillsTab`)
- Test: `ui/src/test/forgeSkills.test.tsx`, `ui/e2e/forge.spec.ts`

**Interfaces:**
- Consumes: Task 9 skill methods; `ForgeDag`'s cytoscape setup pattern for the neighbourhood graph.
- Produces:
  - `SkillsTab()`: a table filterable by status, capability and technology (three `<select>`s).
  - The selected row opens `SkillDetail` with sections, checklist, warnings and a neighbourhood graph.
  - `SkillUpload` takes one SKILL.md plus optional reference files, plus a "Re-import repo skills" button.
  - `ReviewQueue` lists `pending_review` skills with Approve and Reject buttons, which refetch after the action.

- [ ] **Step 1: Write failing tests**

```tsx
it('filters skills by status', ...);
it('approving a pending skill moves it out of the review queue', ...);
it('shows upload warnings returned by the API', ...);
```

`ui/e2e/forge.spec.ts`, against `/platform?mock=1`:
- Agents tab visible by default.
- The DAG canvas is present.
- A task card for `react-vite-pages`.
- Switching to Skills shows 7 rows.
- Approve the pending one.
- `new AxeBuilder({ page }).analyze()` has no violations on both tabs, using the same helper as `luna.spec.ts`.
- At a 375 px viewport there is no horizontal scroll: `document.documentElement.scrollWidth <= 375`.

- [ ] **Step 2: Run them to verify they fail**

Run: `cd ui && npx vitest run src/test/forgeSkills.test.tsx && npx playwright test e2e/forge.spec.ts`
Expected: FAIL

- [ ] **Step 3: Implement the Skills components**

- [ ] **Step 4: Run the full UI suite**

Run: `cd ui && npm test && npx playwright test`
Expected: all pass, including the existing `luna.spec.ts`

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/forge ui/src/pages/Platform.tsx ui/src/test/forgeSkills.test.tsx ui/e2e/forge.spec.ts
git commit -m "feat(ui): Skills library tab with upload and review queue"
```

---

### Task 12: Runbook, full regression and manual agent smoke

**Files:**
- Modify: `docs/runbook.md`. Add a "Connect a coding agent" section with both snippets, token setup, the `/luna-build` usage, and a manual smoke checklist table with columns: agent, version, connected, mode used (parallel/sequential), run id, result, notes.
- Modify: `README.md`. Add one line under the API reference and project structure pointing to `luna/forge/` and the runbook section.

- [ ] **Step 1: Run the full Python suite**

Run: `python -m pytest -q`
Expected: all passed. Failures outside `test_forge_*` are pre-existing; compare against `git stash` on `main` before attributing them.

- [ ] **Step 2: Run the full UI suite**

Run: `cd ui && npm test && npx playwright test && npm run build`
Expected: all pass; build succeeds

- [ ] **Step 3: Manual smoke with Claude Code.** Start FalkorDB and the backend as in `docs/runbook.md`. Then:
  1. Run `claude mcp add --transport http luna http://localhost:8000/mcp`.
  2. In a scratch folder, run `/luna-build build me a portfolio website with React`.
  3. Confirm the Platform Agents tab shows `claude-code` connected and the DAG reaching all-done with a report.

  Record the result in the runbook table.

- [ ] **Step 4: Manual smoke with Antigravity**
  1. Add `{"mcpServers": {"luna": {"serverUrl": "http://localhost:8000/mcp"}}}` via Manage MCP Servers → View raw config.
  2. Ask the agent to use the `luna-build` prompt with the same request.
  3. Record whether it used parallel or sequential mode.

- [ ] **Step 5: Commit**

```bash
git add docs/runbook.md README.md
git commit -m "docs(forge): coding agent connection runbook and smoke results"
```
