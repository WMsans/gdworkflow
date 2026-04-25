# gdworkflow — Multi-Agent Godot Workflow

Automated multi-agent workflow for Godot 4.x game development. An orchestrator dispatches AI subagents to implement features in isolated worktrees, runs reviewers, collects approvals via Discord, and merges approved features into `main`.

## Architecture

```
TODO.md → Orchestrator → Subagents (opencode) → Reviewers → Approval (Discord) → Merger → main branch
                                  ↕                              ↕
                           Clarifying Questions           /approve, /reject
                              (Discord)                   /status, /cancel
```

### Components

| Component | Purpose |
|-----------|---------|
| `gdworkflow.gen_todo` | Generate TODO.md from a GDD |
| `gdworkflow.validate_todo` | Validate TODO.md schema and dependencies |
| `gdworkflow.orchestrate` | Dispatch subagents, manage worktrees, run reviews, merge |
| `gdworkflow.bot.main` | Discord bot for updates, questions, and approvals |
| `gdworkflow.merger` | Scene integration, signal wiring, autoloads, branch merging |
| `gdworkflow.tscn_parser` | Parse and write Godot .tscn scene files |
| `gdworkflow.junit_parser` | Parse JUnit XML test results |

## Quick Start

### Prerequisites

- **Python 3.12+**
- **Git** with worktree support
- **Godot 4.x** (headless mode for tests and exports)
- **OpenCode** CLI (`opencode`) — install from https://opencode.ai
- **API keys** for your chosen model provider (see provider setup below)

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Provider setup

Configure one or more LLM providers via the opencode CLI. This stores your API keys locally — no env vars needed:

```bash
# Interactive login — selects provider and prompts for API key
opencode auth login

# List configured providers
opencode auth list
```

Supported providers include Anthropic, OpenAI, OpenCode Go, and many more. Run `opencode models` to see available models after logging in.

### 3. Configure environment

Copy `.env.example` to `.env` and fill in:

```env
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_GUILD_ID=your_guild_id
BOT_HTTP_PORT=8080
```

### 4. Create Discord channels

- `#orchestrator` — status messages
- `#features` — per-feature threads, reviews, approvals
- `#milestones` — milestone announcements

### 5. Generate a TODO from a GDD

```bash
# Using the default model (deepseek/deepseek-v4-flash)
python -m gdworkflow.gen_todo docs/my_game_gdd.md --output TODO.md

# Using a different provider/model
python -m gdworkflow.gen_todo docs/my_game_gdd.md --model anthropic/claude-sonnet-4-20250514 --output TODO.md
```

Or use `--dry-run` for a template without API calls:

```bash
python -m gdworkflow.gen_todo docs/my_game_gdd.md --dry-run
```

### 6. Validate the TODO

```bash
python -m gdworkflow.validate_todo TODO.md
```

### 7. Run the Discord bot

```bash
python -m gdworkflow.bot.main
```

Or via Docker:

```bash
docker compose up bot
```

### 8. Run the orchestrator

```bash
# Dry run (print plan, don't execute)
python -m gdworkflow.orchestrate TODO.md --dry-run

# Full run with review and approval
python -m gdworkflow.orchestrate TODO.md --review --approve

# With a custom model provider
python -m gdworkflow.orchestrate TODO.md --model anthropic/claude-sonnet-4-20250514 --review --approve

# With merging enabled
python -m gdworkflow.orchestrate TODO.md --review --approve --merge --milestone-tag

# Sequential (not parallel) within each batch
python -m gdworkflow.orchestrate TODO.md --sequential

# No Discord (for local testing)
python -m gdworkflow.orchestrate TODO.md --no-discord
```

Or via Docker:

```bash
docker compose up
```

## CLI Reference

### `orchestrate` flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Print dispatch plan without executing |
| `--base-branch` | Base branch for worktrees (default: `main`) |
| `--model` | Model for subagents in `provider/model` format (default: `deepseek/deepseek-v4-flash`). Configure API keys via `opencode auth login` |
| `--max-batch` | Max parallel tasks per batch (default: 5) |
| `--timeout` | Timeout per subagent in seconds (default: 1800) |
| `--bot-url` | Discord bot URL (default: `http://localhost:8080`) |
| `--no-discord` | Skip all Discord updates |
| `--sequential` | Run tasks sequentially within each batch |
| `--review` | Run reviewer agent after each subagent |
| `--review-timeout` | Reviewer timeout in seconds (default: 600) |
| `--approve` | Request Discord approval after review (requires `--review`) |
| `--approval-timeout` | Approval request timeout in seconds (default: 3600) |
| `--max-retries` | Max retries on rejection (default: 2) |
| `--merge` | Merge approved features into base branch |
| `--skip-tests` | Skip test suite during merge |
| `--export-release` | Export a release build after merge |
| `--milestone-tag` | Create a git milestone tag after merge |

## Discord Commands

| Command | Description |
|---------|-------------|
| `/ping` | Health check |
| `/answer <question_id> <text>` | Answer a clarifying question |
| `/approve <feature_id>` | Approve a feature |
| `/reject <feature_id> [reason]` | Reject a feature |
| `/status` | Show orchestrator status, active agents, progress |
| `/cancel <feature_id>` | Cancel a specific agent and mark as failed |
| `/cancel-run` | Abort the entire milestone |

Bot approval also works via emoji reactions: ✅ to approve, ❌ to reject.

## TODO Schema

Each task in `TODO.md` uses YAML frontmatter:

```yaml
---
id: feat-player-dash
feature_name: Player Dash
new_scene_path: scenes/features/player_dash.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect:
    - from: player_dash
      signal: dash_started
      to: "."
      method: _on_dash_started
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: medium
---
Feature description in markdown...
```

## Testing

### Unit tests

```bash
python -m pytest tests/ -v
```

### Integration tests by week

```bash
# Week 1
python -m pytest tests/test_week1_integration.py -v

# Week 2
python -m pytest tests/test_week2_integration.py -v

# Week 3
python -m pytest tests/test_week3_integration.py -v

# Week 4
python -m pytest tests/test_week4_integration.py -v
```

### Running gdUnit4 tests on the sandbox project

```bash
bash scripts/run_tests.sh --project-dir sandbox --output reports/junit.xml
```

### Capturing screenshots

```bash
bash scripts/capture_screenshot.sh --scene res://scenes/main.tscn --output screenshots/main.png --project-dir sandbox
```

## Merger Pipeline

When `--merge` is enabled, approved features go through:

1. **Branch merge**: `feat/<task_id>` → `main` (non-fast-forward)
2. **Scene integration**: Feature `.tscn` instanced into parent scene
3. **Signal wiring**: `[connection]` entries added to parent `.tscn`
4. **Autoload registration**: If `autoload: true`, `project.godot` updated
5. **Integration commit**: Changes committed on `main`
6. **Test run**: Full gdUnit4 suite executed
7. **Revert on failure**: If tests fail, merge is reverted
8. **Milestone tag**: `milestone-<timestamp>` tag created (with `--milestone-tag`)
9. **Release export**: Optional (with `--export-release`)

## Troubleshooting

### "godot binary not found"

Set `GODOT_BIN` to your Godot executable:

```bash
export GODOT_BIN=/path/to/godot
```

### "opencode not found"

Install OpenCode: https://opencode.ai

### "No API key configured for provider"

Run `opencode auth login` to configure your provider's API key. Keys are stored in `~/.local/share/opencode/auth.json`.

```bash
# List configured providers
opencode auth list

# See available models
opencode models
```

### Discord bot not connecting

- Verify `DISCORD_BOT_TOKEN` in `.env`
- Check bot has `bot` and `applications.commands` scopes
- Ensure channels `#orchestrator`, `#features`, `#milestones` exist

### Subagent timeouts

Increase `--timeout` (default 30 minutes):

```bash
python -m gdworkflow.orchestrate TODO.md --timeout 3600
```

### Git worktree conflicts

Remove stale worktrees:

```bash
rm -rf .worktrees/*
git worktree prune
```

### Cancel a running milestone

Use Discord `/cancel-run` or create the signal file manually:

```bash
touch .worktrees/cancel_run
```

### Check orchestrator status

Use Discord `/status` or read the state file:

```bash
cat .worktrees/orchestrator_state.json
```

## Docker

```bash
# Build and run everything
docker compose up

# Just the bot
docker compose up bot

# Run orchestrator with merge
docker compose run orchestrator TODO.md --review --approve --merge
```