# LUNA OS — 4-Minute Presentation & Demo Script

**Target Audience:** Engineering Executives, AI Architects, and Product Evaluators  
**Total Duration:** Exactly 4 minutes (240 seconds)  
**Live UI URL:** `http://localhost:5173`  
**API / Backend:** `http://localhost:8000`  
**Theme & Design:** Hyperstudio Design Specification (Pitch Black `#0a0b0e`, Terminal Green `#00ff66`, Cyber Cyan `#00ccff`, 0 shadows, 0 blurs, Satoshi + IBM Plex Mono).

---

## Script Breakdown Overview

| Timestamp | Phase / Section | Screen / View | Primary Focus |
|---|---|---|---|
| **00:00 – 00:35** | 1. Introduction & Home | `/` (Home) | Graph-orchestrated architecture & Hyperstudio aesthetic |
| **00:35 – 01:25** | 2. Software-Build Pack | `/platform` (Chat) | Requirement breakdown, Blueprint DAG, 3-wave execution |
| **01:25 – 02:05** | 3. Blueprint Trace & Contracts | `/platform` (Trace Modal) | Cytoscape component graph, deterministic contract checking |
| **02:05 – 02:50** | 4. Investigate Pack | `/platform` (Chat) | Dynamic prompt routing, fraud ring seeds, subagent assignment |
| **02:50 – 03:30** | 5. Traversal Animation | `/platform` (Trace View) | Step scrubber (`1x`/`2x`/`5x`), anti-hallucination citations |
| **03:30 – 04:00** | 6. Governance & "Why?" | `/platform` & `/skills` | Human approval barrier, immutable Decision provenance, learning |

---

## Minute-by-Minute Walkthrough

### Part 1: Introduction & Home (00:00 – 00:35)

**Visual:** Navigate to `http://localhost:5173/`. The screen opens on the dark, high-density LUNA OS Home page. The interactive dot-matrix `ConstellationCanvas` animates subtly behind the headline. The top right displays the green `SYSTEM HEALTH: OPTIMAL` badge.

**Presenter Voiceover:**
> *"Welcome to LUNA OS. Traditional multi-agent frameworks treat autonomous execution like a black box: agents run ad-hoc prompts, hallucinate tool calls, and hide their decision paths.
> 
> LUNA is built on an entirely different premise: **every decision, subtask, skill assignment, graph traversal, and generated artifact must exist as a first-class, auditable property graph in FalkorDB**.
> 
> Notice the interface: built strictly to the Hyperstudio design standard—no fuzzy blurs or drop-shadows, pure high-contrast 1px hairlines, Satoshi typography, and dense, live telemetry. Let's enter the Platform."*

*(Click **"LAUNCH PLATFORM"** button to navigate to `/platform`)*

---

### Part 2: Software-Build Pack (00:35 – 01:25)

**Visual:** The Platform Chat view loads with the left-hand conversation thread, live stage progress list, and central message feed.

**Action:** Type or click the suggested prompt:
> *"Build a fullstack todo app with React frontend, Express backend, and Postgres database"*

**Visual:** The Dynamic Router instantly classifies the prompt into `software-build` (confidence: `0.98`). The UI renders structured blocks:
1. **Routing Block:** Target pack `software-build` with classification rationale.
2. **Requirements Block:** Extracted components: `Postgres Database`, `Express Backend`, `React Frontend`.
3. **Blueprint DAG Block:** Component and Contract graph.
4. **Execution Waves:**
   - *Wave 1:* `comp-database` $\to$ schema SQL and migrations generated.
   - *Wave 2:* `comp-backend` $\to$ Express routes and controllers written.
   - *Wave 3:* `comp-frontend` $\to$ React components and API clients created.

**Presenter Voiceover:**
> *"Behind this single chat box sits our dynamic router. It immediately recognized that this prompt requires the `software-build` pack.
> 
> Rather than letting an LLM generate loose code in a vacuum, LUNA constructs a typed **Blueprint DAG**. It topologically sorts components into three sequential waves: Database first, then Backend, then Frontend.
> 
> Notice how agents assign specialized skills from our Atlas catalog—like `postgres-designer` and `express-router`—and execute skill-fit evaluations before writing a single line of code into their sandboxed workspaces."*

---

### Part 3: Blueprint Trace & Contracts (01:25 – 02:05)

**Visual:** Click the **"VIEW BLUEPRINT TRACE"** button on the Blueprint block. A Cytoscape graph modal opens displaying the component nodes (`comp-database`, `comp-backend`, `comp-frontend`) and connecting `Contract` nodes (`cntr-todos-api`).

**Presenter Voiceover:**
> *"Here is the live architectural graph. Notice the `Contract` node between the backend and frontend.
> 
> Before any code is packaged, LUNA's `integration-verifier` executes deterministic contract checking. It parses the Express route definitions and the React fetch calls via AST, guaranteeing that HTTP endpoints, query params, and JSON schemas match with zero drift.
> 
> Every generated file is SHA-256 hashed and stored within our sandboxed workspace with strict path traversal protections. The complete workspace is instantly downloadable as a clean zip archive."*

*(Close the modal and return to chat)*

---

### Part 4: Investigate Pack (02:05 – 02:50)

**Visual:** In the chat input, submit:
> *"Who is connected to the fraud involving customer cust-000?"*

**Visual:** The Dynamic Router transitions seamlessly to the `investigate` pack.
- Live stages update: `Detecting Seeds` $\to$ `Reputation Scoring` $\to$ `Task Distribution` $\to$ `Parallel Investigation`.
- Agents spawn in private graph slices, querying multi-hop connections without modifying shared state.

**Presenter Voiceover:**
> *"Now let's switch domains entirely—using the exact same chat interface. We ask: 'Who is connected to the fraud involving customer cust-000?'
> 
> The router routes to the `investigate` pack. The orchestrator detects initial seed customers, queries the Atlas for investigator skills like `connection-tracer` and `community-analyzer`, and launches parallel subagents into isolated graph slices.
> 
> Agents independently discover evidence, evaluate claim anomalies, and propose findings. If conflicting claims arise, LUNA's deterministic arbitration engine resolves the verdict based on evidence weight and skill track records."*

---

### Part 5: Traversal Animation & Anti-Hallucination Citations (02:50 – 03:30)

**Visual:** Click the **"INSPECT TRAVERSAL TRACE"** button. The full-screen Traversal Visualizer opens. Cytoscape renders the fraud network. The timeline scrubber shows sequential hops.

**Action:** Click **Play** on the scrubber; set speed to **`2x`**.
The animation highlights the sequence: `cust-000` $\to$ `ba-7712` (Bank Account) $\to$ `cust-003` $\to$ `phone-9011` $\to$ `cust-007`.

**Presenter Voiceover:**
> *"This is LUNA's Traversal Recorder in action. Every query hop executed by an agent is recorded in FalkorDB as a `TraversalStep`.
> 
> You can scrub through the investigation step-by-step at 1x, 2x, or 5x speed to see exactly how the multi-hop connection was uncovered.
> 
> And crucially: look at the final answer block in the chat. Every single customer ID cited—`cust-000`, `cust-003`, `cust-007`—is validated against entities physically discovered during graph traversal. Phantom citations are actively stripped. LUNA will never hallucinate a suspect that wasn't verified in the graph."*

---

### Part 6: Governance, "Why?", and Learning (03:30 – 04:00)

**Visual:** Scroll to the bottom of the chat. The **Action Request Card** is highlighted in warning amber:
- Action: `flag_for_review`
- Targets: `cust-000`, `cust-003`, `cust-007`
- Status: `PENDING APPROVAL`
- Buttons: `[ REJECT ]` and `[ APPROVE & FLAG ]`

**Action:** Click **"EXPLAIN WHY"** to expand the mathematical breakdown (confidence, evidence count, skill prior). Then click **"APPROVE & FLAG"**.

**Visual:** The card turns Terminal Green: `APPROVED & EXECUTED`. A toast confirms: `Domain graph mutated. Cross-run learning recorded on 3 Atlas skills.`

**Presenter Voiceover:**
> *"Autonomous agents should never possess unchecked write authority over production systems.
> 
> LUNA places a hard governance barrier before any domain mutation or build check can run. Notice the Explain 'Why?' feature: it reads an immutable snapshot taken at decision time—meaning explanations remain mathematically verifiable even as the Atlas evolves.
> 
> When I click 'Approve', the domain graph is updated, and the cross-run learner updates the `SUCCEEDED_ON` edges in our Atlas catalog. LUNA gets measurably smarter with every single run.
> 
> That is LUNA OS: autonomous, graph-native, mathematically verified, and governed. Thank you."*

---

## Presenter Quick Reference & Emergency FAQs

- **Q: What if FalkorDB is offline?**  
  *A: The UI includes full offline mock mode toggle in the TopNav (`LIVE API` vs `MOCK MODE`), allowing complete flawless demonstration of all 5 scenarios without network or Docker dependencies.*
- **Q: What models does LUNA support?**  
  *A: Ollama locally (Llama 3.2), OpenAI-compatible APIs (GPT-4o, Groq, DeepSeek), and Anthropic Claude 3.5 Sonnet, with zero external SDK dependencies and zero-leak API key masking.*
- **Q: How does LUNA prevent path traversal in the software builder?**  
  *A: `SandboxWorkspace` strictly checks canonical paths against the component root directory; paths containing `..` or absolute prefixes are rejected immediately with security violations.*
