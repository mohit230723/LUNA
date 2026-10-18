# GSD Runbook

> Operational procedures for debugging, validation, and recovery.

---

## Quick Commands

### Status Check

**PowerShell:**
```powershell
# Current git status
git status

# Recent commits
git log --oneline -10

# Current branch
git branch --show-current
```

**Bash:**
```bash
# Current git status
git status

# Recent commits
git log --oneline -10

# Current branch
git branch --show-current
```

---

## Wave Validation

### Verify Wave Completion

**Before marking a wave complete:**

1. All tasks have commits:
   ```powershell
   git log --oneline -N  # N = number of tasks in wave
   ```

2. All verifications passed (documented in SUMMARY.md)

3. STATE.md updated with current position

4. State snapshot created

### Wave Rollback

**If a wave needs to be reverted:**

```powershell
# Find commit before wave started
git log --oneline -20

# Reset to that commit (keeps changes staged)
git reset --soft <commit-hash>

# Or hard reset (discards changes)
git reset --hard <commit-hash>
```

---

## Debugging Procedures

### 3-Strike Rule

After 3 consecutive failed debug attempts:

1. **Stop** — Don't try a 4th approach in same session

2. **Document** in STATE.md:
   ```markdown
   ## Debug Session
   
   **Problem:** {description}
   
   **Attempts:**
   1. {approach 1} → {result}
   2. {approach 2} → {result}
   3. {approach 3} → {result}
   
   **Hypothesis:** {current theory}
   
   **Recommended next:** {suggested approach}
   ```

3. **Fresh session** — Start new conversation with documented context

### Log Inspection

**Find relevant logs:**

```powershell
# Search for error patterns
Select-String -Path "*.log" -Pattern "error|exception|failed" -CaseSensitive:$false
```

```bash
# Search for error patterns
grep -ri "error\|exception\|failed" *.log
```

---

## Verification Commands

### Build Verification

```powershell
# Node.js
npm run build
if ($LASTEXITCODE -eq 0) { Write-Host "✅ Build passed" }

# Python
python -m py_compile src/**/*.py
```

### Test Verification

```powershell
# Node.js
npm test

# Python
pytest -v

# Go
go test ./...
```

### Lint Verification

```powershell
# Node.js
npm run lint

# Python
ruff check .

# Go
golangci-lint run
```

---

## State Recovery

### From STATE.md

When resuming work:

1. Read STATE.md for current position
2. Check "Last Action" for context
3. Follow "Next Steps" to continue
4. Verify recent commits match documented progress

### From Git History

If STATE.md is outdated:

```powershell
# See recent work
git log --oneline -20

# Check specific commit details
git show <commit-hash> --stat

# View file at specific commit
git show <commit-hash>:path/to/file
```

### Context Pollution Recovery

If quality is degrading mid-session:

1. Create state snapshot immediately
2. Update STATE.md with full context
3. Commit any pending work
4. Start fresh session
5. Run `/resume` to reload context

---

## Search Commands

### Find in Codebase

**PowerShell:**
```powershell
# Find pattern in files
Select-String -Path "src/**/*.ts" -Pattern "TODO" -Recurse

# Find files by name
Get-ChildItem -Recurse -Filter "*.config.*"
```

**Bash:**
```bash
# Find pattern in files (with ripgrep)
rg "TODO" --type ts

# Find pattern in files (with grep)
grep -r "TODO" src/

# Find files by name
find . -name "*.config.*"
```

### Search-First Workflow

Before reading any file:

1. Search for relevant terms:
   ```powershell
   Select-String -Path "**/*.md" -Pattern "architecture" -Recurse
   ```

2. Identify candidate files from results

3. Read only relevant sections:
   ```powershell
   Get-Content file.md | Select-Object -Skip 49 -First 20  # Lines 50-70
   ```

---

## Connect a coding agent

LUNA Forge exposes an MCP server (Streamable HTTP) at `/mcp` so Claude Code or Google Antigravity can plan and build with LUNA's skills. `GET /api/forge/connect` returns the exact snippets for the running backend (the Platform Agents tab shows them with copy buttons).

> Starting the backend seeds forge vocabulary and the starter skills into the real `atlas` graph (MERGE, idempotent). Every `luna_plan` call creates a real run in FalkorDB.

### 1. Start the stack

```bash
docker start luna-falkordb            # or the compose command from README Quickstart
python -m uvicorn luna.api.app:app --port 8000
```

### 2. Optional bearer token

Set `LUNA_MCP_TOKEN` before starting the backend to require `Authorization: Bearer <token>` on `/mcp` (401 otherwise). The `/api/forge/*` routes stay unauthenticated.

### 3. Claude Code

```bash
claude mcp add --transport http luna http://localhost:8000/mcp
# with a token:
claude mcp add --transport http luna http://localhost:8000/mcp --header "Authorization: Bearer <token>"
```

### 4. Antigravity

In the Agent panel open the MCP menu, then Manage MCP Servers, then View raw config, and add:

```json
{"mcpServers": {"luna": {"serverUrl": "http://localhost:8000/mcp"}}}
```

With a token add `"headers": {"Authorization": "Bearer <token>"}` inside the `luna` object. Sources disagree on the file path (`~/.gemini/antigravity/mcp_config.json` vs `~/.gemini/config/mcp_config.json`), so use the menu rather than editing a path.

### 5. Use it

In the agent run the `luna-build` prompt (Claude Code: `/luna-build build me a portfolio website with React`). It calls `luna_plan`, then `luna_get_skill` and `luna_submit` per task wave by wave (parallel subagents if the agent supports them, otherwise sequential), then `luna_assemble`. Watch the run in the Platform page, Agents tab.

### 6. Scripted smoke

```bash
python scripts/forge_smoke.py --url http://127.0.0.1:8000/mcp   # add --token if LUNA_MCP_TOKEN is set
```

Uses the real MCP Python client, exits non-zero on failure, and creates one real run.

### Manual smoke results

| Agent | Version | Connected | Mode used | Run id | Result | Notes |
|-------|---------|-----------|-----------|--------|--------|-------|
| forge_smoke.py (MCP Python client) | mcp client 0.1 | yes | sequential | f6d3372fb1d2 | pass: 6 tools, `luna-build` prompt, 3 tasks in 3 waves done, report `complete`, agent and run listed | 2026-10-19, backend on :8765. Each call was slow (about 5 min total) against the local FalkorDB; lease sweep logged "Query timed out" warnings. A first aborted attempt left run 397a96cbc5d9 in `planned`. |
| Claude Code | pending | pending | pending | pending | pending - run by user | Run `claude mcp add --transport http luna http://localhost:8000/mcp`; in a scratch folder run `/luna-build build me a portfolio website with React`; confirm Agents tab shows `claude-code` connected and the DAG reaches all-done with a report. |
| Antigravity | pending | pending | pending | pending | pending - run by user | Add the raw config above via Manage MCP Servers, ask the agent to use the `luna-build` prompt with the same request, record whether it used parallel or sequential mode. |

---

## Common Issues

### "SPEC.md not FINALIZED"

**Cause:** Planning lock prevents implementation

**Fix:**
1. Open `.gsd/SPEC.md`
2. Complete all required sections
3. Change status to `Status: FINALIZED`
4. Retry command

### "Context degrading"

**Symptoms:** Shorter responses, skipped steps, inconsistency

**Fix:**
1. Create state snapshot
2. Commit current work
3. Start fresh session
4. Run `/resume`

### "Commit failed"

**Causes:** Staged conflicts, hook failures

**Debug:**
```powershell
git status
git diff --staged
```

---

## Checklist Templates

### Pre-Execution Checklist

- [ ] SPEC.md is FINALIZED
- [ ] ROADMAP.md has current phase
- [ ] STATE.md loaded and understood
- [ ] Previous wave verified complete

### Post-Wave Checklist

- [ ] All tasks committed
- [ ] Verifications documented
- [ ] STATE.md updated
- [ ] State snapshot created
- [ ] No uncommitted changes

### Session End Checklist

- [ ] Current work committed
- [ ] STATE.md has "Next Steps"
- [ ] JOURNAL.md updated (if milestone)
- [ ] No loose ends

---

*See PROJECT_RULES.md for canonical rules.*
*See docs/model-selection-playbook.md for model guidance.*
