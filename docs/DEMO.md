# LUNA demo guide

Two things to show, in this order:

1. **Cases** - turn a messy brief into a graph, ask questions, get answers with evidence you can trace.
2. **Coding agents over MCP** - connect Claude Code (or Antigravity) to LUNA, give it a build request, and watch LUNA plan it from a skill graph while the agent does the work.

Total time: about 7 minutes. The Cases part has the slowest steps (live model calls), so build the case **before** you go on stage.

---

## 1. Before you start (10 minutes ahead)

### Services

| Service | Check | Start if down |
|---|---|---|
| FalkorDB (Docker) | `docker ps` shows `falkordb` on 6379 | `docker compose up -d` |
| OmniRoute | `curl http://localhost:20128/v1/models` lists models | start OmniRoute (port 20128) |
| Backend | `curl http://127.0.0.1:8000/api/health` returns `"status":"ok"` | `python -m uvicorn luna.api.app:app --host 127.0.0.1 --port 8000` |
| UI | open http://localhost:5173 | `cd ui` then `npm run dev` |

The model settings live in `.env` (it is git-ignored, so the key never leaves your machine):

```
LUNA_LLM_PROVIDER=openai_compatible
LUNA_LLM_BASE_URL=http://localhost:20128/v1
LUNA_LLM_MODEL=mohi
LUNA_LLM_API_KEY=<your OmniRoute key>
LUNA_LLM_TIMEOUT_S=120
```

The backend reads `.env` at startup. After you change it, restart the backend.

### Warm-up checklist

- [ ] `/api/health` shows `llm.reachable: true` (the Platform nav badge reads **BACKEND ONLINE**).
- [ ] Run the Cases check once: `python scripts/check_cases_flow.py` (about 1-2 minutes). It prints the answer at the end.
- [ ] Run the MCP check once: `python scripts/forge_smoke.py --url http://127.0.0.1:8000/mcp` (about 10 seconds). It must end with `SMOKE OK`.
- [ ] In the UI, open **Platform -> Cases** and build the Silverline case ahead of time (steps in section 2). Leave it in the sidebar as your safety net.
- [ ] If you will demo a live coding agent, add LUNA to it now (section 3) and confirm it lists the `luna_*` tools.

---

## 2. Demo A - Cases (about 3.5 minutes)

**Setup line:** "A team gets a messy brief about a suspected shell-company network. Normally an analyst reads it and draws the links by hand. Watch LUNA do it, and show its work."

### Steps

1. Open **Platform -> Cases -> New case**.
2. Paste the brief. It is in `demo/silverline_brief.txt` (Marcus Sterling, Apex Holdings, account ACC-9821, BlueStar Shipping, Silverline Advisory). Click **Add to case**, then **Build context graph**.
3. While it builds (about 10-60 seconds), say: "It reads the text, a model proposes people, companies, accounts and the links between them, and every item is checked against the exact quote in the source. Duplicates are merged, then it is written to FalkorDB."
4. When it finishes, point at the summary: nodes, edges, entity types, top entities.
5. Ask the first question: **"Who is connected to account ACC-9821 and how are they linked to Apex Holdings?"**
6. While it runs (about 40-100 seconds) narrate the stages as they light up:
   - **Routed / Planned** - it splits the question into sub-tasks.
   - **Skills assigned** - each sub-task gets a skill chosen by a graph query (the rejected candidates and the reasons are stored too).
   - **Agents working** - separate sub-agents each get their own private slice of the graph, and can only call the tools their skill allows.
   - **Verified** - a finding is kept only if the evidence it cites actually appeared in that agent's tool output.
7. When the answer appears, scroll through it: the answer text, **How they connect**, **Not checked** (it says what it could not verify), and the citation chips.
8. Click **View trace**. The graph shows every hop the agents took. Press play on the step scrubber to replay the investigation, and click a node to see the source quote behind each edge.
9. Click **Why** on the answer to show the evidence chain for one entity.

### Good follow-up questions

- "What do Marcus Sterling and Victor Vance have in common?"
- "Who controls BlueStar Shipping Ltd and where did its money come from?"
- "Show the timeline of money movements."

### What to say if asked

- *Does it hallucinate?* "Every claim has to cite entities that the agents actually saw in their tool output. A claim that cites something unseen is dropped, and the answer lists what it could not check."
- *Which model?* "Any OpenAI-compatible model. Today it routes through OmniRoute using the `mohi` combo."

---

## 3. Demo B - coding agent over MCP (about 3 minutes)

**Setup line:** "Now the other half. LUNA is also a skill library for coding agents. The agent keeps doing the coding; LUNA plans the work and hands out the right expertise."

### Connect an agent (once)

**Claude Code**

```
claude mcp add --transport http luna http://localhost:8000/mcp
```

**Antigravity** - open the Agent panel, then the MCP menu, then **Manage MCP Servers -> View raw config**, and add:

```json
{"mcpServers": {"luna": {"serverUrl": "http://localhost:8000/mcp"}}}
```

Restart the agent session after adding the server. The same snippets are on **Platform -> Agents** with Copy buttons.

### Steps

1. Open **Platform -> Agents** and leave it on screen. Point at the connect card: "This is all it takes to connect an agent."
2. In your coding agent, run the LUNA prompt. In Claude Code it is listed as `/mcp__luna__luna-build` (type `/` and look for **luna**). Use it with: **"build me a portfolio website with React"**.
3. Watch the Agents tab:
   - the agent appears under **Agents** as connected;
   - a new run appears under **Build runs**, with a task graph: *Scaffold project -> Implement frontend -> Verify contracts*;
   - each task card shows the skill LUNA picked and a **Why this skill?** drop-down listing the alternatives it rejected.
4. As the agent works, each task moves **ready -> claimed -> done**, with its summary, the files it reported and the checklist results.
5. When the agent calls assemble, the **Assembly report** appears at the bottom: tasks done, files, and any gaps.
6. Open the **Skills** tab. Show the library (six built-in skills), then the review gate:
   - upload `demo/sample-skill/SKILL.md` - it lands as **pending review**;
   - say: "A skill is text that gets injected into an agent's prompt, so new skills are never used until a person approves them";
   - click **Approve**.

### No live agent? Use the replay

```
python scripts/forge_smoke.py --url http://127.0.0.1:8000/mcp
```

It acts as a coding agent over real MCP: connects, plans, claims every task, submits, assembles. Keep **Platform -> Agents** open while it runs and the whole thing animates live.

### What to say if asked

- *Who writes the code?* "The connected agent. LUNA never generates code; it plans, serves skills, tracks the tasks and assembles the report."
- *Why a graph?* "Skills link to capabilities, technologies and each other. Planning is a graph walk, so it is fast, repeatable and explainable - same request, same plan."
- *Can it run subagents in parallel?* "Yes if the agent supports it. Otherwise the agent works through the same tasks one by one and LUNA sees the same claim and submit sequence."

---

## 4. Closing line

"Cases show LUNA reasoning over your data with evidence. MCP shows LUNA equipping the agents you already use. Both run on one idea: skills and decisions live in a graph you can query and audit."

---

## 5. If something goes wrong

| Symptom | Fix |
|---|---|
| Nav badge says **BACKEND OFFLINE** | Check `curl http://127.0.0.1:8000/api/health`. If the backend is down, start it (section 1). If `llm.reachable` is false, check OmniRoute is running and the key in `.env`. |
| Build or investigation is slow | The model is remote-ish. Show the pre-built case from the sidebar instead, and narrate the stages. |
| Answer says nothing was found | Re-ask with a more specific question that names entities from the brief. |
| Agent does not show the LUNA prompt | Restart the agent session after `claude mcp add`; run `claude mcp list` and confirm **luna** is connected. |
| Agents tab is empty | Agents only appear after they call a LUNA tool. Run the replay command to confirm the server is fine. |
| Port 8000 already in use | Stop the old backend (`Get-NetTCPConnection -LocalPort 8000` in PowerShell, then stop that process). |

## 6. Known limits (say these before someone asks)

- The REST API has no login; it is meant for a developer workstation. The MCP endpoint can require a bearer token (`LUNA_MCP_TOKEN`).
- Live model calls make Cases slower and less predictable than the scripted replay.
- Skill scores learned from MCP runs rely on what the agent reports about its own checks.
