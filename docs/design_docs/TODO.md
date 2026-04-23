# Build TODO — Multi-Agent Godot Workflow

This is the build plan for the workflow itself, not for a game. Items are grouped by week and ordered within each week by dependency. A `[ ]` item is not started, `[~]` is in progress, `[x]` is done. Each item has a rough effort estimate in hours.

Items marked **CRITICAL PATH** block later work if they slip. Items marked **PARALLELIZABLE** can be done out of order if you're feeling unblocked on them.

---

## Week 0 — Prerequisites and environment

Set up before touching any workflow code.

- [x] **Install Godot 4.x stable** and confirm `godot --headless --version` works from the shell. (0.5h)
- [x] **Install gdUnit4** as a Godot addon in a throwaway test project, confirm `godot --path sandbox/ -s addons/gdUnit4/bin/GdUnitCmdTool.gd -a test/ --ignoreHeadlessMode` produces output. (1h)
- [x] **Set up an OpenCode Go subscription** at https://opencode.ai/auth. Subscribe to Go, copy your API key, store it in `.env` as `OPENCODE_GO_API_KEY`. Confirm that `opencode` can use model `opencode-go/glm-5.1` via the Go provider. (0.5h)
- [x] **Create a Discord server** for the workflow. Create application and bot in the Discord Developer Portal. Invite bot to the server with the `bot` and `applications.commands` scopes. Store token in `.env`. (1h)
- [x] **Create channels**: `#orchestrator` for status, `#features` for per-feature threads, `#milestones` for announcements. (0.25h)
- [x] **Install OpenCode** (binary or `npm i -g opencode-ai`), confirm `opencode --version` works and `opencode serve` starts cleanly. Confirm it can call GLM-5.1 via OpenCode Go (`opencode-go/glm-5.1`). (0.5h)
- [x] **Install Docker and Docker Compose**, confirm both work. (0.5h)
- [x] **Create a throwaway Godot project** (`sandbox/`) for testing the workflow. Will be used end-to-end for validation. (0.5h)

Total: ~4.5 hours.

---

## Week 1 — Foundation: TODO generator, orchestrator scaffold, minimal Discord bot

Goal by end of week: you can hand-craft a TODO, run the orchestrator, and it dispatches a single subagent that completes and posts a result to Discord.

### GDD → TODO generator **CRITICAL PATH**

- [x] **Design the TODO schema YAML structure**, write example TODOs by hand to validate it's expressive enough. (2h)
- [x] **Write a JSON schema** for the TODO frontmatter. This becomes the structured output target and the validator. (1h)
- [x] **Write `gen-todo` CLI tool** (Python or Go, your call). Reads a GDD markdown file, sends to GLM-5.1 with schema, writes `TODO.md`. (3h)
- [x] **Write a TODO validator** as a standalone CLI that checks schema compliance, file existence, dependency sanity, and no-shared-parent rules. (2h)
- [x] **Write 3 example GDDs** of varying complexity and generate TODOs for each. Hand-revise and save as fixtures. (2h)

### Orchestrator scaffold (external script + vanilla OpenCode) **CRITICAL PATH**

- [x] **Explore the OpenCode HTTP API**: start `opencode serve`, read the OpenAPI docs at `/doc`, and write a minimal test client that creates a session, posts a prompt, and reads the SSE event stream. (1.5h)
- [x] **Write the `orchestrate` CLI script** (Python or Go) with a skeleton that reads a TODO file via the validator from above and prints a dry-run of what would be dispatched. Include a `--dry-run` flag. (2h)
- [x] **Implement worktree creation**: for each task, run `git worktree add .worktrees/<task-id> -b feat/<task-id>` and copy the project-local `.opencode/` config into the new worktree. (2h)
- [x] **Implement single-subagent dispatch**: start `opencode serve --cwd .worktrees/<task-id>`, then POST the task description as the initial prompt via the HTTP API. Do not yet parallelize. (3h)
- [x] **Implement subagent completion detection**: poll for the `DONE` marker file in the worktree; on detection, gracefully shut down the `opencode serve` process. (1.5h)

### Minimal Discord bot **CRITICAL PATH**

- [x] **Scaffold a Go Discord bot** using `discordgo`, connect to gateway, respond to a `/ping` slash command. (2h)
- [x] **Implement `post_update` HTTP endpoint**: POST `{channel, message}` → posts to Discord. (1.5h)
- [x] **Implement `announce_milestone` endpoint**. (1h)
- [x] **Containerize the bot** with a Dockerfile, test it runs from `docker compose up`. (1.5h)

### End-of-week integration test

- [ ] **Run the full Week 1 pipeline**: hand-craft a trivial TODO ("create a scene with a red square"), run orchestrator, confirm worktree created, `opencode serve` starts, subagent runs, completion detected, update posted to Discord. (2h)

Total: ~26 hours. This is a full week if you're not also doing day-job work.

---

## Week 2 — Parallelism, clarifying questions, superpowers port

Goal by end of week: 3 subagents run in parallel on different tasks, can ask clarifying questions via Discord, and use ported skills.

### Parallelism in the orchestrator **CRITICAL PATH**

- [ ] **Implement DAG construction** from `depends_on` fields. Validate no cycles. (2h)
- [ ] **Implement batch computation**: topologically sort, group independent tasks, cap each batch at 5. (2h)
- [ ] **Implement concurrent subagent dispatch** within a batch: start one `opencode serve` process per worktree concurrently, POST each task prompt, and track completion via DONE file polling. Use goroutines/channels (Go) or asyncio (Python) in the orchestrator script. (3h)
- [ ] **Implement batch-wait semantics**: orchestrator advances to next batch only when all tasks in current batch complete or permanently fail. (2h)
- [ ] **Add per-agent logging** that captures stdout/stderr to `.worktrees/<task-id>/agent.log`. (1h)
- [ ] **Add a cost tracker** that sums token usage across all agents and reports to Discord at milestone end. (2h)

### Clarifying question flow **CRITICAL PATH**

- [ ] **Implement `post_question` endpoint** in Discord bot: POST `{agent_id, feature, question}` creates a thread and blocks the HTTP response until an answer arrives. (4h — this is the trickiest concurrency in the bot)
- [ ] **Implement answer capture**: thread message from developer → resolve the blocking request. Also handle `/answer <feature> <text>` slash command as fallback. (2h)
- [ ] **Implement per-request timeout** with pause semantics: on timeout, return a `PAUSED` sentinel; agent checkpoints and exits. (2h)
- [ ] **Write the `clarify-via-discord` skill**: a SKILL.md file in `.opencode/skills/` plus a companion shell script that POSTs to the Discord bot's `post_question` endpoint and blocks for the response. The skill invokes the shell script via the `bash` tool. (2h)
- [ ] **Test with a toy agent** that deliberately asks a question, confirm the whole round-trip works. (1.5h)

### Superpowers port **PARALLELIZABLE**

- [ ] **Clone `obra/superpowers`**, read every SKILL.md, classify each as (a) drop in as-is (OpenCode reads `.claude/skills/` natively), (b) port with edits (rewrite Claude-Code-specific tool references), (c) skip. (3h)
- [ ] **Drop the "as-is" skills** into `.opencode/skills/` (or symlink `.claude/skills/`). Expect 5–8 skills. (1h)
- [ ] **Port the "port with edits" skills**, rewriting tool references to match OpenCode's available tools and permission model. (3h)
- [ ] **Write a new skill** `gdscript-conventions.md` covering Godot-specific norms (signals over polling, composition via scene instancing, no `get_node` string paths when a `@export` works). (1.5h)
- [ ] **Write a new skill** `scene-isolation.md` that reminds every subagent of the "new scene, never touch existing scenes" rule. (1h)
- [ ] **Test each ported skill** on a toy task to verify GLM-5.1 interprets it correctly. (2h)

### Subagent agent config and harness

- [ ] **Write `.opencode/agents/subagent.md`**: agent definition covering scene-isolation rule, plan-summary-within-5-minutes requirement, commit-frequently rule, permission settings (`bash: allow`, `edit: allow`, `webfetch: deny`), and skill list. (2h)
- [ ] **Verify skill loading**: confirm that OpenCode loads all skills from `.opencode/skills/` when the subagent config is active. Run a toy task that deliberately invokes one skill. (1h)
- [ ] **Implement commit-frequency enforcement**: either via a skill that reminds the agent, or a wrapper that commits on file changes with a generic message. (2h)

### End-of-week integration test

- [ ] **Run 3 parallel tasks** on the sandbox Godot project. At least one task should ask a clarifying question. Confirm all three complete and commit to their branches. (3h)

Total: ~36 hours. If this overruns, defer the superpowers port; a minimal skill set is enough for Week 3's work.

---

## Week 3 — Reviewer agent, screenshots, test pipeline

Goal by end of week: features are automatically tested and screenshotted after subagent completion, results posted to Discord for approval.

### gdUnit4 integration **CRITICAL PATH**

- [ ] **Install gdUnit4 in the sandbox project** and write a hand-crafted test for an existing feature to confirm the command line works. (1.5h)
- [ ] **Write a reusable test runner script** `run_tests.sh` that invokes `godot --headless` with gdUnit4 and writes JUnit XML to a known path. (1.5h)
- [ ] **Write a JUnit XML parser** in Go or Python that extracts pass/fail counts and failure messages. (1h)

### Screenshot harness **CRITICAL PATH**

- [ ] **Write a GDScript helper** `capture_scene.gd` that loads a given scene path, positions a camera, lets the scene run for N frames, and saves a PNG to a given output path. (3h)
- [ ] **Decide screenshot conventions**: camera framing, lighting, how many frames to let pass before capture. Document in a README. (1h)
- [ ] **Test on 3 different feature scenes** of varying type (UI, 2D gameplay, 3D gameplay if applicable). (2h)

### Reviewer agent **CRITICAL PATH**

- [ ] **Design the reviewer agent's system prompt**: write gdUnit4 tests for the feature scene, focus on behavioral tests of public API, run the tests, capture a screenshot, post results. (2h)
- [ ] **Implement reviewer invocation** in the orchestrator: after subagent `DONE`, start a second `opencode serve` in the same worktree with the reviewer agent config and POST the review task prompt. (2h)
- [ ] **Implement result posting to Discord** via new bot endpoint `post_review_result(feature, test_summary, screenshot_paths)`. Attach screenshots as Discord attachments. (3h)
- [ ] **Test the reviewer end-to-end** on a completed subagent's output. (2h)

### Approval flow **CRITICAL PATH**

- [ ] **Implement `request_approval` endpoint** in Discord bot. Blocks until ✅ reaction, `/approve`, or `/reject` fires. (3h)
- [ ] **Implement rejection retry logic** in orchestrator: on reject, delete worktree, create new one on same branch, re-dispatch with rejection reason added to task description. Cap at 2 retries. (2h)
- [ ] **Implement approval state tracking**: keep a map `feature_id → approved | rejected | pending` in memory, persisted nowhere (consistent with no-state-persistence rule). (1h)

### End-of-week integration test

- [ ] **Run the pipeline through approval**: TODO → 3 parallel subagents → reviewers → you approve one, reject one, approve one. Confirm rejection retry works. (3h)

Total: ~28 hours.

---

## Week 4 — Merger, milestone tagging, polish

Goal by end of week: approved features are automatically merged into `main`, milestone is tagged and announced, system is stable enough to use on a real project.

### Merger agent **CRITICAL PATH**

- [ ] **Install `godot-parser` Python library** in the merger's container. Confirm it round-trips a `.tscn` file without data loss. (1.5h)
- [ ] **Write the scene-integration function**: given parent `.tscn` path, feature `.tscn` path, and `integration_hints`, produce an updated parent scene with the feature instanced. (4h)
- [ ] **Handle signal connections** specified in `integration_hints`: add the appropriate `[connection]` entries in the parent `.tscn`. (2h)
- [ ] **Handle autoload registration** when `integration_hints.autoload: true`: update `project.godot`'s `[autoload]` section. (2h)
- [ ] **Implement merge loop**: for each approved feature, integrate, commit, merge feature branch into `main`, run full test suite, revert on failure. (3h)
- [ ] **Implement milestone tagging**: on full success, `git tag milestone-<timestamp>`. (0.5h)
- [ ] **Implement release build export** (optional): `godot --headless --export-release`. (1.5h)
- [ ] **Implement milestone announcement**: summary of merged features, token cost, test counts, posted to `#milestones`. (1.5h)

### System polish and robustness **PARALLELIZABLE**

- [ ] **Add graceful shutdown** to orchestrator: on SIGTERM, signal all subagents to commit and exit cleanly. (2h)
- [ ] **Add a `/status` slash command** showing active agents, their state, current batch, and progress. (2h)
- [ ] **Add a `/cancel <feature>` slash command** that terminates a specific agent and marks the feature as failed. (1.5h)
- [ ] **Add a `/cancel-run` slash command** that aborts the entire milestone. (1h)
- [ ] **Write a Docker Compose file** that runs orchestrator, Discord bot, and subagent runner as a single stack. (2h)
- [ ] **Write a README** covering setup, common commands, and troubleshooting. (3h)

### Real-project validation **CRITICAL PATH**

- [ ] **Pick a small real game idea** (a single-screen arcade game is ideal). Write its GDD. (2h — and probably a creatively rewarding afternoon)
- [ ] **Generate, revise, and run a TODO** with 5 features. (1h of active time, plus however long the agents take)
- [ ] **Run the full milestone through to completion**. Take notes on every friction point. (varies; plan for a full day of observing)
- [ ] **Do a retrospective**: what worked, what didn't, what to change first. (1h)

Total: ~30 hours active, plus observation time during the real-project run.

---

## Stretch / post-v1 items

These are not week-4 items. Keep them in a backlog and prioritize after you've actually used v1 for a couple of milestones.

- [ ] **Asynchronous clarifying questions** with agents proceeding on partial information. (Substantial rework of the Q&A skill.)
- [ ] **State persistence across reboots** via SQLite. (Only worth it if you find yourself losing significant work to crashes.)
- [ ] **Web UI** for approvals, as an alternative to Discord. (Nice-to-have; the Discord flow may be enough.)
- [ ] **Automatic visual regression detection** on milestone screenshots. (Compare against previous milestone's screenshots; flag drift.)
- [ ] **Custom Godot asset import hooks** so agents can request placeholder assets via Discord. (Non-trivial; requires art pipeline integration.)
- [ ] **Multi-developer mode** with per-developer approval queues. (Only worth it if the workflow grows beyond solo use.)
- [ ] **Budget caps** that halt a milestone when cumulative token cost exceeds a configured threshold. (Cheap to add; surprisingly useful.)
- [ ] **Flaky-test detection** in the reviewer: run generated tests 3× and flag instability. (Valuable if test quality becomes a problem.)
- [ ] **Support for editing existing scenes** when strictly necessary, via a serialization lock. (Only if you consistently hit limits of scene-isolation.)

---

## Total effort summary

| Week | Focus | Active hours |
|------|-------|--------------|
| 0 | Prerequisites | ~4.5 |
| 1 | TODO generator, orchestrator scaffold, minimal Discord bot | ~26 |
| 2 | Parallelism, clarifying questions, superpowers port | ~36 |
| 3 | Reviewer, screenshots, approvals | ~28 |
| 4 | Merger, polish, real-project validation | ~30 |
| — | **Total** | **~124.5 hours** |

At 20 hours/week of focused work, this is ~6–7 weeks of calendar time. At 40 hours/week, it's the stated 3–4 weeks. The "2–4 weeks" estimate from the architecture discussion assumed roughly full-time focus; adjust to your actual availability.

If you start slipping, cut in this order:
1. Stretch items (already deferred).
2. Week 4 polish and /status commands (nice, not essential).
3. Full superpowers port (a minimal 3-skill subset is enough for v1).
4. Merger agent (can merge manually for a while; painful but safe).
5. Reviewer agent (can manually write tests; loses a lot of workflow value).

Never cut: the TODO schema validator, the worktree management, the clarifying-question flow, the approval flow. Those are the workflow.