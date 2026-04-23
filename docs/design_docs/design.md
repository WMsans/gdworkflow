# Multi-Agent Godot Development Workflow — Design Document

**Status:** Draft v1
**Target:** Solo game developer, Godot 4.x (GDScript), self-hosted
**Timeline:** 2–4 weeks build, then ongoing iteration

---

## 1. Problem statement

Solo game development in Godot is rate-limited by serial attention: one human can only design, implement, test, and review one feature at a time. Existing AI coding tools help with individual tasks but don't coordinate multiple simultaneous work streams, and they don't enforce the discipline — scene isolation, test coverage, human playtest — that keeps a Godot project from degrading into merge-conflict and regression hell.

This workflow turns a single developer into a dispatcher for a small fleet of AI subagents, with the developer's attention reserved for the work only a human can do: writing the game design document, deciding which tasks are worth doing, answering clarifying questions, and playtesting features for feel.

## 2. Goals and non-goals

**Goals**
- Run up to 5 AI subagents in parallel on independent features without merge conflicts.
- Keep the human in the loop at three specific checkpoints: TODO revision, clarifying questions, and playtest approval.
- Produce a tested, screenshotted, human-approved milestone from a GDD with minimal manual coordination.
- Run entirely on self-hosted infrastructure with no vendor lock-in beyond the model API.

**Non-goals**
- Replacing the human designer. The GDD is written by hand; creative decisions stay with the developer.
- Generating art, audio, or other non-code assets.
- Cross-platform CI/CD. Builds are local; deployment is out of scope.
- Handling legacy Godot 3.x projects.
- Surviving reboots mid-run. A reboot aborts the current milestone; work resumes from the last git commit.

## 3. Core design principles

**Scene isolation as the parallelism primitive.** Each new feature is implemented as a self-contained `.tscn` scene owned by exactly one subagent. Subagents never edit existing scenes. The merger agent is the only component that touches parent scenes, and it does so serially. This converts what would be constant `.tscn` merge conflicts into a clean producer/integrator pattern.

**Human in the loop at high-leverage moments, not low-leverage ones.** The developer does not review every commit or every test. They review the GDD-to-TODO translation (catches misunderstood requirements), answer clarifying questions from subagents (catches ambiguity before coding), and playtest features (catches feel problems that tests cannot). Everything else is automated.

**Synchronous blocking with timeouts.** Subagents that need clarification block until the developer answers, but with a configurable timeout that pauses the blocked agent so the batch can continue. This trades some pipeline throughput for much simpler coordination logic.

**No state persistence.** Crash recovery is handled by git — each subagent commits its progress frequently within its worktree, so a reboot resumes from the last commit rather than a custom state store. This keeps infrastructure simple at the cost of losing work-in-progress on restart.

**Open source and self-hostable end to end.** Vanilla OpenCode, GLM-5.1 (MIT-licensed, hosted via Z.ai API or OpenRouter), Godot, gdUnit4, and the custom orchestrator code. Docker Compose for local deployment.

## 4. System architecture

The system is six components plus the Godot project itself, coordinated through a shared git repository and a Discord server.

### 4.1 GDD → TODO generator

A one-shot CLI script invoked manually by the developer after writing or revising the GDD. Reads the GDD markdown, sends it to GLM-5.1 with a structured-output schema, writes a `TODO.md` file with the generated tasks. The developer reviews and edits this file before invoking the orchestrator.

Not part of the runtime pipeline; fully under developer control.

### 4.2 Orchestrator (external script + vanilla OpenCode)

A Python or Go CLI script that:
1. Parses and validates `TODO.md`, builds a dependency DAG, computes the maximum parallel-safe batch (capped at 5).
2. Creates a git worktree for each task (`git worktree add .worktrees/<task-id> -b feat/<task-id>`).
3. Starts a vanilla `opencode serve` process in each worktree directory.
4. Drives each instance via OpenCode's HTTP API: POSTs the task prompt, streams progress via the `/event` SSE endpoint.
5. Detects subagent completion by watching for the `DONE` marker file in the worktree.
6. When a batch completes, dispatches the reviewer agent for each feature, waits for human approval via the Discord bot, and invokes the merger on the approved set.

OpenCode is not modified. All custom logic — DAG computation, parallelism, worktree lifecycle, Discord coordination — lives in the orchestrator script. OpenCode handles what it does best: model API abstraction, tool calling, and context management.

Runs as a long-lived process; one instance per milestone run.

### 4.3 Discord bot

Owns the single Discord gateway connection. Exposes a local HTTP API used by the orchestrator, subagents, reviewer, and merger for:

- `post_update(channel, message)` — non-blocking status posts
- `post_question(agent_id, feature, question) → answer` — blocking Q&A in a feature thread, with configurable timeout
- `request_approval(feature, test_results, screenshot_paths) → approve | reject + reason` — blocks until developer reacts or uses a slash command
- `announce_milestone(tag, summary)` — final milestone post

Also handles inbound slash commands: `/approve <feature>`, `/reject <feature> <reason>`, `/status`, `/cancel <feature>`, `/cancel-run`.

Runs as a long-lived process alongside the orchestrator.

### 4.4 Subagents

Each subagent is a vanilla `opencode serve` process launched by the orchestrator with `--cwd .worktrees/<task-id>`, configured via project-local files in that directory:
- `.opencode/agents/subagent.md` — agent definition with the scene-isolation system prompt, permission settings, and model config
- `.opencode/skills/` — the ported superpowers skills plus the `clarify-via-discord` skill
- The specific task from `TODO.md` is POSTed as the initial prompt via the HTTP API

The `clarify-via-discord` skill is a markdown skill file with an associated shell script that POSTs to the Discord bot's `post_question` endpoint and blocks for the response.

Subagents commit to their worktree branch frequently (every meaningful change) to preserve work across crashes. They signal completion by creating a `DONE` marker file and exiting.

### 4.5 Reviewer agent

A specialized OpenCode agent invoked per feature after the subagent finishes. It reads the feature scene, writes gdUnit4 tests that exercise the scene's public API and behavior, runs those tests headlessly, and captures a scripted screenshot of the scene via a GDScript helper. Posts test results and screenshots to the feature's Discord thread and signals ready-for-approval.

### 4.6 Merger agent

Runs serially at milestone close, after all approvals. For each approved feature, it:
1. Parses the target parent `.tscn` using a Python `.tscn` library (not regex).
2. Adds a scene instance node for the feature, applying any `integration_hints` from the TODO.
3. Saves the updated parent scene.
4. Merges the feature branch into `main`.
5. Runs the full test suite.
6. On failure, reverts the merge, posts to Discord, and halts the milestone.
7. On success, continues to the next approved feature.

After all merges succeed, creates a git tag, optionally exports a release build, and posts a milestone announcement.

### 4.7 Godot project

Lives in a git repository with one long-lived `main` branch and ephemeral feature branches for each subagent's worktree. Feature scenes live under `scenes/features/<feature_name>.tscn`. Shared scripts live under `scripts/`. The `project.godot` file is edited only by the merger agent, and only when a feature requires autoload registration.

## 5. The data contract: TODO schema

Everything downstream depends on `TODO.md` being well-formed. Each task is a markdown section with a YAML frontmatter block:

```yaml
---
id: feat-player-dash
feature_name: Player dash ability
new_scene_path: scenes/features/player_dash.tscn
integration_parent: scenes/player.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect:
    - from: player/input, signal: dash_pressed, to: ./player_dash, method: on_dash_pressed
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: medium
---
```

Followed by a free-form prose description of the feature.

**Validation rules enforced by the orchestrator:**
- `touches_existing_files` must be empty or the task is rejected before dispatch.
- `new_scene_path` must not already exist on `main`.
- `integration_parent` must exist on `main`.
- `depends_on` must reference other `id`s in the same `TODO.md`.
- A batch of parallel tasks cannot share the same `integration_parent` only if `integration_hints.node_type` is `instance` and does not modify parent structure — otherwise they are serialized.

The GDD → TODO generator produces this schema; the developer revises it by hand.

## 6. Interaction flows

### 6.1 Clarifying question flow

1. Subagent hits ambiguity during planning or coding.
2. Subagent invokes `clarify-via-discord` skill with its question.
3. Skill calls Discord bot's `post_question` endpoint, which creates a threaded message in the feature's channel.
4. Bot blocks the skill's HTTP response until the developer replies in the thread or a slash command like `/answer <feature> <text>` fires.
5. Developer reply is returned to the subagent, which continues working.
6. If the timeout fires first (default 30 min), the subagent is paused and marked as blocked; the orchestrator continues monitoring other agents in the batch.
7. When the developer eventually answers, the agent resumes.

### 6.2 Approval flow

1. Reviewer agent posts to the feature thread: test summary, screenshots attached, "Ready for playtest."
2. Developer checks out the feature branch locally and runs the game to playtest.
3. Developer either reacts with ✅ in Discord or runs `/approve feat-player-dash`, or runs `/reject feat-player-dash "dash range too short"`.
4. On approval, the feature is marked ready for merging.
5. On rejection, the feature is re-queued with the rejection reason appended to its task description, a new worktree is created, and a fresh subagent is dispatched (up to a configurable retry limit, default 2).

### 6.3 Milestone close flow

1. Orchestrator detects all features in the current `TODO.md` are either approved or permanently rejected.
2. Orchestrator invokes the merger agent.
3. Merger processes approved features serially (see 4.6).
4. On full success, milestone is tagged and announced.
5. On merger failure, the milestone is halted; the developer intervenes manually.

## 7. Technology choices and rationale

**Orchestrator: external script driving vanilla OpenCode via HTTP.** OpenCode is open-source, self-hostable, model-agnostic, and exposes a full REST API (`opencode serve`) with an SSE event stream. The workflow's custom logic — DAG computation, worktree lifecycle, parallelism, Discord gating — lives in an external Python or Go script that drives OpenCode programmatically via HTTP. OpenCode's plugin system (JS/TS) handles lifecycle hooks (e.g., detecting `DONE` creation). OpenCode's skills system handles subagent instructions (superpowers skills, `clarify-via-discord`). No fork is required; upstream updates can be pulled freely without merge conflicts.

**Skills: obra/superpowers, ported.** The repository contains proven patterns for software engineering agent behavior (git workflow, testing discipline, debugging). Most skills are prompt-based and port cleanly to OpenCode's agent markdown format. A handful of Claude-Code-specific skills (those depending on Claude Code's plugin API) are dropped. One new skill is written: `clarify-via-discord`.

**Test framework: gdUnit4.** Better Godot 4 support than GUT as of 2026; supports headless runs via `godot --headless` and generates JUnit XML that's easy for the reviewer agent to parse.

**Discord bot: Go.** Written in Go to match the OpenCode fork's language and share the build pipeline. Uses `discordgo` library.

**`.tscn` manipulation: Python with `godot-parser`.** The merger agent is the one place where structured `.tscn` editing matters; a proper parser prevents the class of bugs that killed the idea of text-level scene merging.

**Deployment: Docker Compose on a self-hosted machine.** Orchestrator, Discord bot, and subagent runner each in their own container. The Godot project and git worktrees live on a volume mount. No cloud dependencies.

## 8. Risks and mitigations

**Scene integration is subtler than pure instancing.** Merging `feature_a.tscn` as a child of `main.tscn` may require positioning, signal connections, or autoload registration. *Mitigation:* `integration_hints` field in the TODO schema captures these; merger agent applies them during scene update.

**8-hour autonomous runs can go deeply wrong before visible output.** *Mitigation:* Each subagent must post a plan summary to its Discord thread within 5 minutes of starting. Developer can cancel early if the plan is off-track.

**Synchronous clarifying questions can pile up on the developer.** Five simultaneous blocked agents waiting for answers is overwhelming. *Mitigation:* Per-agent timeout (default 30 min) pauses the blocker without halting the batch. Developer answers at their own pace.

**Reviewer agent test quality is unpredictable.** Auto-generated tests may be shallow or fragile. *Mitigation:* Reviewer is instructed to write behavioral tests of the public scene API, not implementation details. Human playtest remains the real quality gate. Tests are a necessary-but-not-sufficient check.

**No state persistence means reboots lose work.** *Mitigation:* Subagents commit frequently to their worktree branches. A reboot loses at worst the last few minutes of uncommitted work per agent.

**Godot scene files contain UIDs that can conflict.** When the merger adds an `ext_resource` for a new feature scene to a parent scene, the `id` must not collide with existing ids. *Mitigation:* `.tscn` parser handles id assignment; never hand-rolled.

## 9. Success criteria

The workflow is considered successful when, over a representative milestone of 5 features:
- At least 4 of 5 features complete without developer code intervention.
- Average developer attention time per feature is under 30 minutes (GDD work excluded).
- Zero merge conflicts reach the developer.
- All merged features pass their generated tests and the developer's playtest.
- Total wall-clock time from TODO revision to milestone tag is under 2 days for a 5-feature milestone.

## 10. Future work, explicitly out of scope for v1

- Asynchronous clarifying questions with agents proceeding on partial information.
- State persistence across reboots (SQLite or similar).
- A web UI for non-Discord approval flows.
- Multi-developer coordination with per-developer approval queues.
- Automated asset generation (sprite placeholders, sound effects).
- CI/CD and release distribution.
- Support for C# Godot projects.
- Self-hosted GLM-5.1 inference.
