# LUNA OS - 4-minute feature demo video script

Goal: show every working part of LUNA, live, in 4:00. Pace of narration: about 2.3 words per second (calm, no hype).

Recording notes:
- Record at 1920x1080 on http://localhost:5173. Hide bookmarks, close other windows.
- A live Cases run takes 40-100 seconds. Record it in full, then speed it up 3-4x (or cut to "Agents working" and "Answer") so the segment fits its time.
- Build the Silverline case once before recording as a safety net, and record a second take for the build and the question.
- Run the MCP part with a real Claude Code session. If that is not available, use `python scripts/forge_smoke.py --url http://127.0.0.1:8000/mcp` while the Agents tab is open.

| Time | Section |
|---|---|
| 0:00-0:15 | Hook: Home page |
| 0:15-0:50 | Cases 1: paste a brief, build the graph |
| 0:50-1:40 | Cases 2: ask a question, live pipeline |
| 1:40-2:20 | Cases 3: answer, citations, trace, Why |
| 2:20-2:40 | Skill Atlas |
| 2:40-3:25 | Coding agents over MCP: connect and live build |
| 3:25-3:50 | Assembly report and the skill review gate |
| 3:50-4:00 | Close |

---

## 0:00-0:15 - Hook (Home)

**Screen:** Open `/`. The constellation animates. Slow scroll to the two cards: "Investigate connected data" and "Give your coding agent skills".

**Narration:** "LUNA OS is a graph-native platform for AI agents. It does two things: it investigates connected data and shows its evidence, and it equips the coding agents you already use with skills. Let me show both working."

**Action:** Click **Open the platform**.

---

## 0:15-0:50 - Cases 1: paste a brief, build the graph

**Screen:** Platform, **Cases** tab, **New case**.

**Actions:**
1. Paste the Silverline brief (`demo/silverline_brief.txt`) into the text box. Click **Add to case**.
2. Click **Build context graph**. Show the four steps lighting up: Parse, Extract, Resolve, Load.
3. When it finishes, show the summary: 14 nodes, 17 edges, 1 source, the top entities, and the types.

**Narration:** "A case starts with raw text. This is a messy brief about a suspected shell-company network. I paste it and build the graph. LUNA parses the text, a model proposes people, companies, accounts and links, and every item is checked against the exact quote in the source. Duplicates are merged, and the result is written to FalkorDB. Fourteen entities, seventeen links, each one traceable to the text."

---

## 0:50-1:40 - Cases 2: ask a question, live pipeline

**Screen:** The case thread with suggested questions.

**Actions:**
1. Type: "Who is connected to account ACC-9821 and how are they linked to Apex Holdings?" and press Enter.
2. Show the live pipeline: Routed, Planned, Skills assigned, Agents working (agent rows with tool-call counts), Verified, Answer.
3. Point at the Execution plan and "Skills assigned" cards.

**Narration:** "Now I ask a question. The planner splits it into sub-tasks, and each sub-task gets a skill chosen by a graph query. These agents are blank until they are equipped. Each one works on its own private slice of the graph and can only call the tools its skill allows. You can see the tool calls count up as they work. Then comes verification: a finding is kept only if the evidence it cites actually appeared in that agent's own tool output."

---

## 1:40-2:20 - Cases 3: answer, citations, trace, Why

**Screen:** The answer in the thread.

**Actions:**
1. Scroll the answer: summary, "How they connect", "Not checked", confidence, citation chips.
2. Click **View trace**. Press play on the step scrubber and let the path draw. Click a node, then a step, to show the source quote.
3. Back in the thread, click **Why** on a finding to show the evidence chain.

**Narration:** "The answer comes back with its evidence. It also says what it did not check. Every citation is a real entity in the graph. View trace replays the investigation hop by hop, and every edge carries the quote from the source text that supports it. Why shows the chain of evidence behind a single finding. Nothing here is a black box."

---

## 2:20-2:40 - Skill Atlas

**Screen:** Click **Skill Atlas** in the nav. Filter by pack (Investigate, Build).

**Actions:** Open one skill to show its capabilities, technologies, tools, track record and policy status. Point at the restricted skill.

**Narration:** "Where do skills come from? The Skill Atlas. Each skill is a node in the graph, linked to the capabilities it provides, the technologies it targets, and a track record that updates after approved runs. Restricted skills are blocked by policy and are never assigned."

---

## 2:40-3:25 - Coding agents over MCP: connect and live build

**Screen:** **Platform -> Agents** tab (connect card visible). Split screen if possible: Claude Code terminal on the left, Agents tab on the right.

**Actions:**
1. Point at the connect card. In the terminal run `claude mcp add --transport http luna http://localhost:8000/mcp`.
2. Show the agent appearing under Agents as connected.
3. In Claude Code run the LUNA prompt (`/mcp__luna__luna-build`) with: "build me a portfolio website with React".
4. On the Agents tab: the new run appears, the task graph (Scaffold project, Implement frontend, Verify contracts), skills assigned, task states moving ready, claimed (live dot), done.
5. Open **Why this skill?** on one task to show the rejected alternatives.

**Narration:** "The second half: your coding agent. One command connects Claude Code, or Antigravity, to LUNA over MCP. I give it a build request. LUNA plans the work as a task graph and hands each task a skill from the graph. The coding agent claims a task, pulls its skill, does the work, and reports back. Here you can watch it live: ready, claimed, done. And for any task I can ask why this skill, and see the candidates that were rejected."

---

## 3:25-3:50 - Assembly report and the skill review gate

**Screen:** The finished run on the Agents tab, then the **Skills** tab.

**Actions:**
1. Show the Assembly report: "3/3 tasks complete across 3 waves, 3 files reported, 0 gaps".
2. Open the **Skills** tab. Upload `demo/sample-skill/SKILL.md`. It appears as **pending review**.
3. Click **Approve**.

**Narration:** "When the agent finishes, LUNA assembles one report: tasks, files, checklist results, and any gaps. New skills are different. A skill is text that gets injected into an agent's prompt, so anything uploaded or added over MCP waits as pending review. It is never assigned until a person approves it. I approve it here, and now it is part of the library."

---

## 3:50-4:00 - Close

**Screen:** Back to Home, or the side-by-side of the trace graph and the task graph.

**Narration:** "Cases show LUNA reasoning over your data, with evidence. MCP shows LUNA equipping the agents you already use. One graph for skills and decisions that you can query and audit. This is LUNA OS."

---

## Cheat sheet

| Feature shown | Where | Proof point |
|---|---|---|
| Text to graph | Cases | 14 nodes, 17 edges, each checked against a source quote |
| Planner and skill assignment | Cases thread | Skills chosen by graph query, rejected candidates stored |
| Private agent slices | Pipeline | Only the tools a skill allows |
| Anti-hallucination check | Verified stage | A finding survives only if its evidence appeared in tool output |
| Trace and Why | View trace, Why | Replayable path, source quote per edge |
| Skill library | Skill Atlas | Capabilities, technologies, scores, restricted skills |
| MCP server | Agents tab | One command connects Claude Code or Antigravity |
| Task lifecycle | Agents tab | ready, claimed, done, assembled report |
| Skill governance | Skills tab | Pending review until a person approves |

## Voiceover word count

About 470 words in total, which fits 4:00 at a calm pace with room for the screen actions.
