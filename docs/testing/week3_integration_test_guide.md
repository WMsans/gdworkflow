# Week 3 Integration Test Guide

Goal: Run the full pipeline through approval — TODO → 3 parallel subagents → reviewers → approve one, reject one, approve one. Confirm rejection retry works.

---

## Prerequisites

Before starting, confirm every dependency is operational:

1. **Godot 4.x** — `godot --headless --version` succeeds.
2. **gdUnit4** — Installed in the sandbox project at `sandbox/addons/gdUnit4/`.
3. **OpenCode** — `opencode --version` works; `opencode-go/glm-5.1` model is reachable.
4. **Discord bot** — Running via `docker compose up` (or directly). Confirm `/ping` responds in Discord.
5. **Git worktree support** — `git worktree add` and `git worktree remove` work; you're on `main` with a clean tree.
6. **Sandbox project** — `sandbox/` exists with `project.godot` and `scenes/main.tscn`.

Quick smoke check:

```bash
cd /path/to/gdworkflow

# Godot + gdUnit4
godot --headless --path sandbox/ -s addons/gdUnit4/bin/GdUnitCmdTool.gd -a test/ --ignoreHeadlessMode

# Discord bot
curl -s http://localhost:8080/health
# Expected: {"status": "ok"}

# OpenCode
opencode run --dir . --model opencode-go/glm-5.1 --format json "Say hello"
```

---

## Test Fixture

The test uses `fixtures/gdds/TODO_week3_integration.md`, which defines 3 independent features (no `depends_on`), all `estimated_complexity: low`:

| Task ID | Feature | Scene Type | Purpose |
|---------|---------|-------------|---------|
| `feat-orange-triangle` | Orange Triangle | 2D gameplay | Tests reviewer + screenshot (2D node) |
| `feat-health-bar` | Health Bar | UI | Tests reviewer + screenshot (UI/Control node) |
| `feat-spark-particles` | Spark Particles | 2D effects | Tests reviewer + screenshot (GPUParticles2D) |

These are deliberately simple so subagents finish quickly. All three have empty `depends_on` so they dispatch in a single parallel batch.

---

## Step-by-Step Procedure

### Step 1: Validate the TODO

```bash
cd /path/to/gdworkflow
python -m gdworkflow.validate_todo fixtures/gdds/TODO_week3_integration.md
```

Expected: `Overall: PASS`, `Tasks found: 3`, no errors.

---

### Step 2: Dry-run the orchestrator

```bash
python -m gdworkflow.orchestrate fixtures/gdds/TODO_week3_integration.md --dry-run
```

Expected output:
- `Found 3 tasks`
- `Batch 1:` with all 3 task IDs listed (single batch, no dependencies)
- `[DRY RUN]` footer

---

### Step 3: Run the full pipeline with review + approval

```bash
python -m gdworkflow.orchestrate \
  fixtures/gdds/TODO_week3_integration.md \
  --review \
  --approve \
  --bot-url http://localhost:8080
```

This will:
1. Create 3 git worktrees (`.worktrees/feat-orange-triangle/`, etc.)
2. Dispatch 3 subagents in parallel
3. Wait for each to complete (DONE marker)
4. For each completed task, dispatch a reviewer agent
5. Post review results (verdict, test summary, screenshot) to Discord `#features`
6. Post an approval request to Discord `#features` and block for your response

---

### Step 4: Monitor Discord for subagent completions

Watch the `#features` channel. You should see messages like:

```
feat-orange-triangle: COMPLETED (took 120s)
feat-health-bar: COMPLETED (took 135s)
feat-spark-particles: COMPLETED (took 110s)
```

If a task fails or times out, note the error. You can check `.worktrees/<task-id>/agent.log` for details.

---

### Step 5: Monitor Discord for review results

After each subagent completes, the reviewer agent runs. You should see messages like:

```
📋 Review: feat-orange-triangle
Verdict: PASS
Tests: 5 passed, 0 failed
[Attached: screenshots/orange_triangle.png]
```

The reviewer verdicts will be one of:
- `PASS` — all tests pass, screenshot captured
- `PASS_WITH_NOTES` — tests pass but with quality concerns
- `FAIL` — tests fail or screenshot capture failed

---

### Step 6: Approve and reject features

The orchestrator will post approval requests in `#features`. Each message will have ✅ and ❌ reactions.

**Test the approval flow:**

1. **Approve `feat-orange-triangle`** — Click ✅ on the approval message (or type `/approve feat-orange-triangle`)
2. **Reject `feat-health-bar`** — Click ❌ on the approval message (or type `/reject feat-health-bar Suboptimal layout`)
3. **Approve `feat-spark-particles`** — Click ✅ on the approval message

---

### Step 7: Verify rejection retry

After rejecting `feat-health-bar`:

1. The orchestrator should remove the existing worktree
2. Create a new worktree on the same branch
3. Re-dispatch a subagent with the rejection reason appended to the task description
4. The new subagent prompt will include a `## Retry Note` section with the rejection reason

Check that:
- `.worktrees/feat-health-bar/` is recreated after rejection
- The new task prompt (`.worktrees/feat-health-bar/.task_prompt.md`) contains `## Retry Note` with your rejection reason
- A new review occurs after the retry completes
- You get a second approval request for `feat-health-bar`

You can approve the retry to continue, or reject again (the default max retries is 2).

---

### Step 8: Verify final state

After all approvals/rejections are resolved:

1. **Worktrees** — Approved features should have their worktrees intact with commits
   ```bash
   ls .worktrees/
   git log --oneline -3 .worktrees/feat-orange-triangle/
   ```

2. **Review artifacts** — Each reviewed feature should have:
   - `.worktrees/<task-id>/reports/junit.xml` — Test results
   - `.worktrees/<task-id>/screenshots/<name>.png` — Screenshot
   - `.worktrees/<task-id>/REVIEW.md` — Review verdict and notes

3. **Agent logs** — Each worktree should have `agent.log`:
   ```bash
   cat .worktrees/feat-orange-triangle/agent.log
   ```

4. **Discord** — Check that `#orchestrator` has a final summary with token costs, and `#features` has all review results posted.

5. **Approval states** — Check via the bot API:
   ```bash
   curl -s http://localhost:8080/approval_status | python -m json.tool
   ```
   Should show `approved` for the two approved features and the final state of the rejected-then-retried feature.

---

## Cleanup

After the test, clean up worktrees:

```bash
for wt in .worktrees/feat-orange-triangle .worktrees/feat-health-bar .worktrees/feat-spark-particles; do
  git worktree remove "$wt" --force 2>/dev/null
done

# Also clean up branches
git branch -D feat/feat-orange-triangle feat/feat-health-bar feat/feat-spark-particles 2>/dev/null
```

Or the orchestrator does cleanup automatically at the start of each run (it removes existing worktrees in `.worktrees/`).

---

## What to look for (pass/fail criteria)

| Check | Pass condition |
|-------|---------------|
| TODO validation | `validate_todo` reports PASS, 3 tasks |
| Dry run | Single batch with 3 tasks, no errors |
| Parallel dispatch | 3 worktrees created, 3 subagents start concurrently |
| Subagent completion | All 3 reach DONE state within timeout |
| Reviewer dispatch | Reviewer runs in each worktree after subagent completion |
| gdUnit4 tests | JUnit XML generated with ≥1 test per feature |
| Screenshots | PNG captured for each feature scene |
| Review result posted | Discord `#features` shows verdict + test summary for each feature |
| Approval request posted | Discord `#features` shows approval message with ✅/❌ reactions |
| Approval via ✅ | Orchestrator receives "approved" response and continues |
| Rejection via ❌ | Orchestrator receives "rejected" response, initiates retry |
| Rejection retry | New worktree created, subagent re-dispatched with retry note |
| Cost tracking | Final summary in `#orchestrator` includes token totals |
| Agent logs | `.worktrees/<task>/agent.log` exists and is non-empty for each task |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Subagent timeout | OpenCode API or model issues | Check `OPENCODE_GO_API_KEY` in `.env`; try `opencode run` manually |
| No DONE file | Subagent crashed before writing marker | Check `agent.log`; subagent may have failed to commit |
| Reviewer fails | gdUnit4 not found, Godot not installed | Verify `godot --headless --version`; check `sandbox/addons/gdUnit4/` |
| Screenshot missing | Headless mode can't render 3D | Week 3 test uses only 2D scenes, so this shouldn't happen |
| Discord not posting | Bot not running or wrong URL | `curl http://localhost:8080/health`; check `docker compose ps` |
| Approval hangs | No ✅/❌ reaction or command | Type `/approve <feature_id>` or `/reject <feature_id> <reason>` in Discord |
| Worktree conflict | Stale worktrees from previous run | Remove `.worktrees/` manually or let the orchestrator clean it up |

---

## Automated validation (unit test level)

The file `tests/test_week3_integration.py` contains unit-level checks for:

- `TestJUnitParser` — JUnit XML parsing correctness
- `TestRunTestsScript` — Script existence and required flags
- `TestScreenshotHarness` — GDScript and shell script existence
- `TestReviewerAgent` — Reviewer config, `build_review_prompt`, `ReviewResult` dataclass
- `TestApprovalFlow` — Bot routes, dataclasses, orchestrator flags, rejection retry
- `TestSandboxTestExists` — gdUnit4 test file in sandbox

Run these anytime:

```bash
python -m pytest tests/test_week3_integration.py -v
```

These validate component wiring but do NOT run the full end-to-end pipeline. That's what this guide covers.