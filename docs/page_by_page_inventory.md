# LUNA OS: Complete Page-by-Page Website Inventory

**Document Purpose:** Complete catalog of all pages, layout shells, components, interactive blocks, modals, and drawers across the LUNA OS website (`d:\LUNA\ui\`), structured so each page can be inspected, styled, and refined one by one.

---

## Table of Contents
1. [Global Layout & Shell](#1-global-layout--shell)
2. [Page 1: Home Page (`/`)](#2-page-1-home-page-)
3. [Page 2: How It Works Page (`/how-it-works`)](#3-page-2-how-it-works-page-how-it-works)
4. [Page 3: Skill Atlas Page (`/skills`)](#4-page-3-skill-atlas-page-skills)
5. [Page 4: Platform Chat Page (`/platform` & `/platform/:conversationId`)](#5-page-4-platform-chat-page-platform--platformconversationid)
6. [Page 5: Trace View Page (`/platform/:conversationId/trace/:runId`)](#6-page-5-trace-view-page-platformconversationidtracerunid)
7. [Page 6: 404 Not Found Page (`*`)](#7-page-6-404-not-found-page-)
8. [Interactive Modals & Slide-out Drawers](#8-interactive-modals--slide-out-drawers)
9. [Component Checklist for "One-by-One" Fixes](#9-component-checklist-for-one-by-one-fixes)

---

## 1. Global Layout & Shell

### 1.1 TopNav Component
- **File:** `ui/src/components/layout/TopNav.tsx` & `TopNav.module.css`
- **Location:** Present at the top of every page.
- **Elements & Structure:**
  - **Left Wordmark:** `"LUNA"` in Satoshi weight 400 with a subtle gold accent dot, links to `/`.
  - **Center Navigation Links:**
    - `HOME` (`/`)
    - `HOW IT WORKS` (`/how-it-works`)
    - `SKILL ATLAS` (`/skills`)
    - `PLATFORM` (`/platform`)
    - Active link is highlighted in Chalk (`#f3f3f3`), inactive links in Smoke (`#9c9c9c`).
  - **Right Utility Area:**
    - **Mode Badge / Toggle:** Displays `LIVE` (Pulse Green dot) or `MOCK` (Iron tag). Clicking toggles connection mode between offline mock and live backend.
    - **Primary Action Button:** Filled white pill button (`Button variant="pill"`) with text `"TRY THE PLATFORM"`, uppercase 14px, linking to `/platform`.

### 1.2 Footer Component
- **File:** `ui/src/components/layout/Footer.tsx` & `Footer.module.css`
- **Location:** Anchored at the bottom of standard content pages (`/`, `/how-it-works`, `/skills`).
- **Elements & Structure:**
  - Hairline top border (`1px solid var(--color-graphite)`).
  - Wordmark `"LUNA"` with tagline `"Graph-orchestrated multi-agent operating system."`.
  - Links column: Home, How It Works, Skill Atlas, Platform.
  - System status indicators: FalkorDB, MCP tool isolation, Parameterized Cypher.
  - Copyright and synthetic data disclaimer.

### 1.3 PageShell & SkipLink
- **Files:** `ui/src/components/layout/PageShell.tsx` & `SkipLink.tsx`
- **Purpose:** Consistent 1200px max-width centered container, skip navigation link for keyboard accessibility (WCAG AA).

---

## 2. Page 1: Home Page (`/`)
- **Route:** `/`
- **Page File:** `ui/src/pages/Home.tsx`
- **Components Directory:** `ui/src/components/home/`

### 2.1 Hero Section (`Hero.tsx` & `Hero.module.css`)
- **Headline:** Display typography (63px, letter-spacing -0.69px, weight 400):  
  `"Agents that act on connected data."`
- **Sub-headline:** 21px Smoke body text:  
  `"An orchestrator that assigns skills to sub-agents by graph query, isolates their work in graph slices, and returns an answer you can trace."`
- **Status Badge:** Status dot badge reading `"BACKEND ONLINE"` (with Pulse Green dot) or `"BACKEND OFFLINE"` (Smoke dot) fetched live from `/api/health`.
- **CTA Buttons:**
  - White Pill Button: `"TRY THE PLATFORM"` (links to `/platform`).
  - Ghost Button: `"HOW IT WORKS"` (links to `/how-it-works`).

### 2.2 Hero Constellation Canvas (`ConstellationCanvas.tsx`)
- **Type:** Procedural HTML5 2D Canvas animation.
- **Visuals:** Network of small Chalk nodes connected by hairline Graphite lines, with a slow, subtle Pulse Green signal path tracing through nodes.
- **Accessibility:** Detects `prefers-reduced-motion` and renders a clean, stationary constellation graph.

### 2.3 Feature Grid ("What it does") (`FeatureGrid.tsx`)
- **Layout:** 2x2 bordered grid with 1px Graphite borders.
- **Cards (with Compass Gold icons):**
  1. **Skills assigned by graph query:** Sub-agents start blank; skills are matched dynamically from the Skill Atlas graph based on requested capabilities and technologies.
  2. **Isolated agent graphs:** Agents work strictly in isolated sub-graph slices; writes are scoped via MCP sandboxes.
  3. **Evidence-checked findings:** Contradictory findings are arbitrated with mathematical confidence scoring; unobserved entities are flagged and stripped.
  4. **Approval-gated actions:** External side-effects (flagging accounts, running terminal commands) remain PENDING until an authorized approver signs off.

### 2.4 Use Cases ("Two ways to use it") (`UseCases.tsx`)
- **Investigate Card:**
  - Tag: `PACK: INVESTIGATE`
  - Prompt text: `"Who is connected to the fraud involving customer cust-000?"`
  - Mini Graph Preview (`MiniGraph.tsx`): 5-node graph showing traversal path.
  - Button: `"Try this prompt"` (opens `/platform` with prompt pre-filled).
- **Build Card:**
  - Tag: `PACK: BUILD`
  - Prompt text: `"Build a todo app with an npm project: React + Vite frontend, Express backend, Postgres database."`
  - Mini Graph Preview (`MiniGraph.tsx`): Blueprint DAG showing component dependencies.
  - Button: `"Try this prompt"` (opens `/platform` with prompt pre-filled).

### 2.5 Request Flow ("How a request flows") (`FlowSteps.tsx`)
- **Numbered Steps (Horizontal row / Stack on mobile):**
  - `01`: Route Prompt (LLM classification with keyword fallback).
  - `02`: Plan Graph (DAG decomposition of subtasks or components).
  - `03`: Assign Skills (Match skills to blank agents by graph query).
  - `04`: Work in Isolation (Execute tools inside per-agent graph slices).
  - `05`: Verify and Answer (Arbitrate evidence, check contracts, output traceable answer).

### 2.6 System Manifesto (`Manifesto.tsx`)
- **Layout:** Centered wireframe card (max-width 600px).
- **Content:** Core engineering thesis explaining why graphs are required for reliable multi-agent coordination (cycle rejection, scoped context, auditable provenance).

### 2.7 Under The Hood (`UnderTheHood.tsx`)
- **Cards:**
  - **FalkorDB Graph Engine:** Low-latency graph operations and Cypher queries.
  - **MCP Tool Scoping:** Per-agent stdio MCP servers restricting file and graph access.
  - **Parameterized Cypher:** 100% parameterized queries, zero dynamic string interpolation.
  - **Provenance Arbitration:** Mathematical scoring of conflicting findings.
  - **Human-in-the-Loop Barrier:** Explicit approval gate with no bypass flags.

### 2.8 Final CTA (`FinalCta.tsx`)
- Centered section with button: `"LAUNCH PLATFORM"`.

---

## 3. Page 2: How It Works Page (`/how-it-works`)
- **Route:** `/how-it-works`
- **Page File:** `ui/src/pages/HowItWorks.tsx` & `HowItWorks.module.css`

### 3.1 Pack Switcher Tabs
- Two options: `[Investigate Walkthrough]` and `[Build Walkthrough]`.
- Switching tabs reloads the corresponding scenario and graph simulation.

### 3.2 Five-Stage Walkthrough Stepper
- **Investigation Scenario Steps:**
  1. *Prompt Routing:* Route `"Who is connected to fraud customer cust-000?"` to `investigate` pack (confidence 0.96).
  2. *Slice Isolation:* Extract sub-graph slice for `cust-000` with 2-hop radius.
  3. *Traversal Walk:* Agents walk phone numbers and bank accounts, discovering shared ring entities.
  4. *Evidence Arbitration:* Discrepancies between suspicious signals arbitrated with confidence scoring.
  5. *Answer & Approval:* Plain-language answer generated with cited CIDs and proposed flag action PENDING.
- **Build Scenario Steps:**
  1. *Requirement Extraction:* Parse prompt into React, Vite, Express, and Postgres requirements.
  2. *Blueprint DAG:* Generate Component and Contract graph with topological build order.
  3. *Skill Matching:* Graph query assigns `frontend-react-vite`, `backend-express`, and `db-postgres`; rejects `shell-runner`.
  4. *Sandboxed Generation:* Sub-agents write files to `workspaces/<run_id>/`; remediation fixes route mismatches.
  5. *Contract Verification:* Verifier checks routes against endpoints; proposes `run_build_check` PENDING.

### 3.3 Progressive Graph Visualizer (Cytoscape)
- As the user clicks `"Next Step"` or `"Previous Step"`, new nodes and edges appear with smooth transitions, showing exactly what happened at each step.

---

## 4. Page 3: Skill Atlas Page (`/skills`)
- **Route:** `/skills`
- **Page File:** `ui/src/pages/SkillAtlas.tsx` & `SkillAtlas.module.css`

### 4.1 Header & Filter Controls
- **Page Title:** `"Skill Atlas"`
- **Subtitle:** `"Registered capabilities and specialized agent skills queryable by the orchestrator."`
- **Search Input:** Filter skills by name, capability, or technology.
- **Pack Filter Pills:** `[All Packs]`, `[investigate]`, `[build]`.
- **View Mode Switcher:** `[List View]` vs. `[Graph View]`.

### 4.2 List View Table
- **Columns:**
  - **Skill Name:** Monospace font, status dot, and `POLICY RESTRICTED` badge if applicable.
  - **Pack:** Badge (`investigate` or `build`).
  - **Primary Capability:** Monospace capability identifier.
  - **Target Technologies:** Inline technology tags (e.g. `react`, `vite`, `postgres`).
  - **Score:** Visual progress bar and percentage (e.g. `95%`).
  - **Runs:** Number of executions (e.g. `14 runs`).
  - **Actions:** Ghost button `"Inspect"`.
- Clicking any row opens the Slide-out Drawer.

### 4.3 Graph View Canvas
- Interactive Cytoscape graph displaying:
  - Skills (Iron hexagons)
  - Capabilities (Carbon ellipses)
  - Technologies (Card Slate rectangles)
  - Packs (Chalk diamonds)
- Zoom controls: `[+]`, `[-]`, `[Fit]`.

### 4.4 Skill Detail Slide-out Drawer
- Slides out from the right when a skill is clicked.
- **Header:** Skill Name, Pack, Policy Badge (`ALLOWED` vs. `RESTRICTED`).
- **Prompt Fragment:** Wireframe code container displaying the agent prompt.
- **Capabilities & Technologies:** Badges for all mapped entities.
- **Exposed MCP Tools:** List of tools this skill gives sub-agents access to.
- **Performance Track Record:** Score percentage and historical run count.
- **Policy Reason:** Clear explanation of policy restrictions (e.g. why `shell-runner` is blocked).

---

## 5. Page 4: Platform Chat Page (`/platform` & `/platform/:conversationId`)
- **Route:** `/platform` (new chat) and `/platform/:conversationId` (existing thread)
- **Page File:** `ui/src/pages/Platform.tsx` & `Platform.module.css`
- **Components Directory:** `ui/src/components/chat/`

### 5.1 Left Sidebar (`Sidebar.tsx`)
- `"NEW CHAT"` white pill button.
- Mode indicator: `MOCK DATA` or `LIVE BACKEND`.
- Speed multiplier control for mock runs (1x, 2x, 5x, 10x).
- Conversation session history list with timestamps and delete buttons.

### 5.2 Center Chat Thread (`Thread.tsx`)

#### Empty State View:
- Displayed when no messages have been sent yet.
- Centered headline: `"What should the agents work on?"`.
- Four prompt suggestion chips:
  1. `"Who is connected to the fraud involving customer cust-000?"` (Investigate)
  2. `"Build a todo app: React + Vite, Express, Postgres"` (Build)
  3. `"What about cust-003?"` (Investigate multi-turn)
  4. `"Build a dashboard with Svelte and Fastify"` (Build clarification)

#### Message History View:
- **`UserMessage.tsx`:** Right-aligned hairline card with prompt text and timestamp.
- **`AssistantMessage.tsx`:** Left-aligned response container composed of:
  - **Live Run Card (`RunCard.tsx`):**
    - Visible while a run is executing.
    - Vertical `StageList.tsx`:
      - `Routed` (Done / Active dot / Pending)
      - `Planned` (Done / Active dot / Pending)
      - `Skills assigned` (Done / Active dot / Pending)
      - `Agents working` (Done / Active dot / Pending)
      - `Verified` (Done / Active dot / Pending)
      - `Answer` (Done / Active dot / Pending)
    - Under *Agents working*, individual `AgentRow.tsx` rows:
      - Agent ID (e.g. `agent-01`)
      - Skill equipped
      - Tool call badge (e.g. `trace_connections(cust-000)`)
      - Status dot & Backend tag (`llm`, `rules`, or `scripted`)
  - **Block Renderers (`ui/src/components/chat/blocks/`):**
    1. **`RoutingBlock.tsx`:** Selected pack, intent, confidence %, reasoning, backend tag.
    2. **`PlanBlock.tsx`:** Subtask list (Investigate) or Component DAG (Build).
    3. **`SkillsBlock.tsx`:** Chosen skills, rejected candidate skills with reasons, skill-fit scores.
    4. **`FindingsBlock.tsx`:** Table of findings with verdict, confidence, status, and evidence CIDs.
    5. **`FilesBlock.tsx`:** File tree of generated artifacts, text file preview viewer, and `"DOWNLOAD .ZIP"` button.
    6. **`ActionRequestBlock.tsx`:** Approval gate card:
       - Displays target entities or npm commands to execute.
       - `"APPROVE"` button (opens `ApproverModal`).
       - `"REJECT"` ghost button.
       - Upon approval, transitions to `ACTION EXECUTED` card with precision, recall, and F1 metrics.
    7. **`NeedsInputBlock.tsx`:** Clarification prompt with clickable option buttons (e.g. selecting alternative supported technologies like React or Vue).
    8. **`WarningBlock.tsx`:** Amber alert banner for non-critical warnings or fallback modes.
    9. **`AnswerBlock.tsx`:** Final markdown text, clickable cited CID chips, and `"VIEW TRACE"` button.

### 5.3 Bottom Composer (`Composer.tsx`)
- Auto-growing multi-line textarea (Enter sends, Shift+Enter for newline).
- `"Options"` popover button:
  - Pack selector (`Auto`, `Investigate`, `Build`).
  - Mode selector (`Scripted`, `Live`).
  - `Strict LLM` toggle.
  - `Parallel Agents` slider (1 to 5).
- Send button (filled white pill).
- Disabled state with clear notification when run is awaiting human input (`needs_input`).

### 5.4 Right Details Drawer (`DetailsDrawer.tsx`)
- Collapsible inspector panel with 5 tabs:
  - `[Skills]`: Selected skills, candidate rankings, fit scores, and rejection provenance.
  - `[Agents]`: Agent execution logs, tool invocations, and slice metrics.
  - `[Findings]`: Evidence findings table with corroboration status.
  - `[Why]`: Full explainability chain (`/why` and `/explain`).
  - `[Files]`: Artifact file explorer and size summary.

---

## 6. Page 5: Trace View Page (`/platform/:conversationId/trace/:runId`)
- **Route:** `/platform/:conversationId/trace/:runId` (Also accessible as a full-screen overlay modal from the chat thread).
- **Page File:** `ui/src/pages/TracePage.tsx` & `ui/src/components/graph/TraceView.tsx`

### 6.1 Top Control Bar
- `"Back to Chat"` navigation button.
- Run ID and Pack Mode badge (`INVESTIGATE` or `BUILD`).
- CID search input (centers and zooms to matching node).
- Utility buttons:
  - `"COPY PATH"` (copies path text to clipboard).
  - `"EXPORT PNG"` (downloads canvas snapshot).
  - `"LEGEND"` (opens shape and color vocabulary guide).

### 6.2 Main Cytoscape Graph Canvas (`GraphCanvas.tsx`)
- **Visual Encoding:**
  - Customer nodes: Smoke diamond with Iron border.
  - Entity nodes (Phone, Account, Address): Carbon ellipse with Graphite border.
  - Finding nodes: Chalk round-rectangle.
  - Agent nodes: Card Slate hexagon.
  - SkillRef nodes: Iron tag shape.
  - Action nodes: Transparent with Compass Gold border.
  - Component nodes: Card Slate rectangle.
  - Contract nodes: Carbon barrel with Chalk border.
  - Artifact nodes: Graphite rectangle.
  - Active traversal path: Highlighted in Signal White with moving Pulse Green marker.
  - Context nodes (1-hop): Dimmed to 30% opacity.
- **Interactions:** Zoom, pan, node click (opens details in right panel), double-click to expand neighbors.

### 6.3 Left Step Scrubber Panel (`StepList.tsx`)
- Chronological list of traversal steps:
  - Step number (`Step 01`, `Step 02`, etc.).
  - From CID -> Relationship -> To CID.
  - Tool used and Agent ID.
  - Hovering a step highlights the edge on the canvas; clicking focuses the node.

### 6.4 Bottom Playback Scrubber Bar (`Scrubber.tsx`)
- Play / Pause button.
- Step backward / Step forward buttons.
- Progress scrubber slider with step indicators.
- Speed multiplier pills (`1x`, `2x`, `5x`).
- `"Show All"` toggle.

### 6.5 Right Node Detail Drawer (`NodeDetail.tsx`)
- Node CID / ID, label, and metadata properties.
- Incident edges and linked findings.
- Provenance trail explaining why this node was investigated.

---

## 7. Page 6: 404 Not Found Page (`*`)
- **Route:** Any unmatched route (`*`).
- **Page File:** `ui/src/pages/NotFound.tsx` & `NotFound.module.css`
- **Elements:**
  - Large monospace `"404"`.
  - Wireframe error card with message: `"The requested graph path or page could not be resolved."`.
  - White pill button: `"RETURN HOME"`, links to `/`.

---

## 8. Interactive Modals & Slide-out Drawers

| Component | File Path | Trigger / Location | Purpose |
| :--- | :--- | :--- | :--- |
| **Approver Modal** | `ui/src/components/chat/ApproverModal.tsx` | Click `"APPROVE"` on `ActionRequestBlock` | Prompts for Approver Name and optional notes; submits approval to backend. |
| **Graph Legend Modal** | `ui/src/components/graph/Legend.tsx` | Click `"LEGEND"` in Trace View toolbar | Explains node shapes (diamond, ellipse, hexagon) and relationship edge styles. |
| **Skill Drawer** | `ui/src/pages/SkillAtlas.tsx` | Click any row or node in Skill Atlas | Shows complete skill capabilities, prompt fragment, and policy restriction details. |
| **Details Drawer** | `ui/src/components/chat/DetailsDrawer.tsx` | Click `"INSPECT"` in Platform Chat | 5-tab deep-dive inspector for Skills, Agents, Findings, Why, and Files. |
| **Node Detail Panel** | `ui/src/components/graph/NodeDetail.tsx` | Click any node in Trace View | Displays node properties, connected hops, and evidence citations. |

---

## 9. Component Checklist for "One-by-One" Fixes

Use this checklist when inspecting, styling, or debugging pages one by one:

- [ ] **TopNav & Footer:** Verify active link color, mode toggle responsiveness, and mobile hamburger/stack layout.
- [ ] **Home Page - Hero:** Check headline scaling on mobile (`< 768px`), button hover states, and health badge status.
- [ ] **Home Page - Constellation:** Confirm canvas animation pauses when reduced motion is preferred (`prefers-reduced-motion: reduce`).
- [ ] **Home Page - Feature Grid & Use Cases:** Verify 1px Graphite border alignment and pre-filled prompt transitions to `/platform`.
- [ ] **How It Works Page:** Verify step forward/backward buttons, progressive Cytoscape graph layout, and scenario switcher.
- [ ] **Skill Atlas Page - List View:** Verify search bar filter, pack filter tabs, and score bar rendering.
- [ ] **Skill Atlas Page - Graph View:** Verify zoom controls, Cytoscape node layouts, and drawer open on click.
- [ ] **Platform Chat - Empty State:** Verify clicking prompt chips pre-populates composer with correct pack.
- [ ] **Platform Chat - Live Run Card:** Confirm stage list updates only on events and agent rows display tool calls.
- [ ] **Platform Chat - Blocks:** Test collapsible state on Routing, Plan, Skills, Findings, and Files blocks.
- [ ] **Platform Chat - Action Approval:** Test `ApproverModal` input, approve flow, and verify execution metrics appear.
- [ ] **Platform Chat - Needs Input:** Verify clicking an option button calls `/answer` and clears the composer disabled state.
- [ ] **Platform Chat - Details Drawer:** Test tab switching (`Skills`, `Agents`, `Findings`, `Why`, `Files`).
- [ ] **Trace View - Scrubber:** Test Play/Pause, step scrubber slider, and 1x/2x/5x speed multipliers.
- [ ] **Trace View - Cytoscape:** Verify node shape mapping, white traversal path highlighting, and CID search.
- [ ] **NotFound Page:** Confirm layout and return home link.
