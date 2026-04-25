---
name: writing-todos
description: Use when creating or editing a TODO.md file for the gdworkflow pipeline, to ensure task definitions conform to the project frontmatter schema and validation rules
---

# Writing TODOs

## Core Principle

A TODO.md in gdworkflow is NOT a checklist or a task tracker. It is a **structured manifest of independent features**, each defined by YAML frontmatter blocks that the orchestrator parses to build a DAG and dispatch subagents. Every field must conform to the JSON schema — a single violation causes the pipeline to fail validation.

**Do NOT use markdown checklists, phases, priorities, or status fields.** Those are not part of the schema and will cause validation failures.

## File Format

```
# TODO — Generated from <gdd-name>.md

---
id: feat-example-feature
feature_name: Example Feature
new_scene_path: scenes/features/example_feature.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: medium
---

Prose description of the feature...

# ---

---
id: feat-another-feature
feature_name: Another Feature
new_scene_path: scenes/features/another_feature.tscn
...
---
```

- **First line** must be `# TODO — Generated from <gdd-name>.md`
- Each task is delimited by `---` on its own line before and after the YAML
- Tasks are separated by `# ---` (a horizontal rule in markdown)
- Each task block has exactly two parts: YAML frontmatter (between `---`), then prose

## Frontmatter Fields

These are the ONLY allowed fields. Do NOT add `status`, `priority`, `description`, `dependencies`, or any other field — they will cause schema validation failure (`additionalProperties not allowed`).

| Field | Required | Format / Rules |
|-------|----------|----------------|
| `id` | Yes | `feat-kebab-case-name` — lowercase letters and hyphens only (kebab-case). Must be a string, not a number. Must be unique across all tasks. |
| `feature_name` | Yes | Human-readable string, e.g. `Player Dash`. No length limit but keep it concise. |
| `new_scene_path` | Yes | `scenes/features/snake_case_name.tscn` — underscores between words (snake_case), NOT hyphens. Must NOT already exist in the repo. |
| `integration_parent` | Yes | Path to an existing `.tscn` file in the repo, e.g. `scenes/main.tscn`. Must point to a committed file. |
| `integration_hints` | No | Object (see below). Always include it even if using defaults. |
| `touches_existing_files` | No | MUST be `[]` for parallel dispatch. Never add file paths here unless serial dispatch is intentional. |
| `depends_on` | No | Array of task IDs. Use `depends_on` (not `dependencies`). Each ID must exist in the file. Default: `[]`. |
| `estimated_complexity` | No | One of `low`, `medium`, `high`. Default: `medium`. |

### Integration Hints

```yaml
# For a regular feature scene (instanced in parent):
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false

# For an autoload singleton (manager, no scene):
integration_hints:
  node_type: script_attach
  position: autoload
  signals_to_connect: []
  autoload: true
```

- `node_type`: `instance` for scene instancing, `script_attach` for script-only autoload features
- `position`: `as_child_of_root` for regular features, `autoload` for singletons
- `signals_to_connect`: each entry needs `from` (source node path), `signal` (signal name), `to` (target node path), `method` (handler method name)
- `autoload`: set to `true` only for managers/singletons like ScoreManager or LevelManager; the `integration_parent` must be a path to a `.godot` project file when true

## Complete Task Block Example

```yaml
---
id: feat-player-dash
feature_name: Player Dash
new_scene_path: scenes/features/player_dash.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: medium
---

Player dash ability activated by pressing Shift while moving. The player character
lunges forward at 3x normal speed for 0.3 seconds. During the dash, the player is
invulnerable. After the dash, there is a 0.5-second cooldown before the ability
can be used again. Emits dash_started and dash_ended signals.
```

## Parallelism Principles

- **Maximize parallelism** — keep `depends_on` minimal and `touches_existing_files` empty
- Each feature should be a **self-contained scene** in `scenes/features/`
- Features that genuinely depend on another feature's scene (e.g., a UI that shows data from a manager) should set `depends_on` but keep `touches_existing_files` empty
- Only managers/singletons should set `autoload: true` — their `integration_parent` must point to a `.godot` project file tracked in the repo
- Never set `touches_existing_files` to anything other than `[]` unless you are certain the task cannot be parallelized

## Validation Rules

The pipeline runs `validate_todo.py` which checks:
1. **Schema compliance** — every field matches the JSON schema types and patterns; no extra fields allowed
2. **depends_on references** — every ID in `depends_on` exists as a task `id` in the file
3. **No dependency cycles** — the DAG must be acyclic
4. **new_scene_path uniqueness** — the path must not already exist in the git repo
5. **integration_parent existence** — the parent path must exist in the git repo
6. **touches_existing_files empty** — must be `[]` for parallel dispatch

## Prose Description

After the frontmatter block, write a paragraph describing the feature in plain prose. This is used as the subagent's task prompt, so include:
- What the feature should do
- Key implementation details (node structure, scripts, signals)
- Any non-obvious behavior or edge cases

Do NOT use markdown checklists (`- [ ]`), sub-headings, or nested lists in the prose. Write a single coherent paragraph or 2-3 short paragraphs.

## Common Mistakes

| Mistake | Fix |
|---------|------|
| Numeric IDs (`id: 1`) | Use string IDs: `id: feat-player-dash` |
| Wrong field names (`dependencies`, `description`, `status`, `priority`) | Use only schema-defined fields: `depends_on`, `feature_name`, etc. |
| Extra unsupported fields | Remove `status`, `priority`, `dependencies`, `phase`, `tags` — only schema fields are allowed |
| ID uses underscores (`feat_player_dash`) | Use hyphens: `feat-player-dash` |
| Scene path uses hyphens (`scenes/features/player-dash.tscn`) | Use underscores: `scenes/features/player_dash.tscn` |
| Missing `integration_hints` | Always include it, even if defaults suffice |
| `integration_parent` is not an existing file | Use a path that exists in the repo (e.g. `scenes/main.tscn`) |
| `new_scene_path` already exists | Pick a different name or path |
| `depends_on` references a nonexistent ID | Only reference IDs that appear elsewhere in the file |
| Circular dependencies (A→B→A) | Break the cycle by removing one edge |
| `touches_existing_files` has entries | Leave it as `[]` unless serial dispatch is intentional |
| Wrong `integration_parent` when `autoload: true` | Must point to a `.godot` project file |
| Autoload uses `node_type: instance` or `position: as_child_of_root` | Use `node_type: script_attach` and `position: autoload` for autoloads |
| Prose is empty or too vague | Write at least 3-5 sentences covering behavior, signals, edge cases |
| Using markdown checklists or task lists | Write prose paragraphs only — no `- [ ]` list items |

## Verification

After writing a TODO.md, validate it with:

```bash
python -m gdworkflow.validate_todo TODO.md
```

The command must report **Overall: PASS** before the TODO can be used with the orchestrator.

## Red Flags - STOP and Fix

- ID is a number, not a string
- ID doesn't match `feat-[a-z0-9]+` pattern
- Scene path is not under `scenes/features/`
- `depends_on` references anything not in the file
- `touches_existing_files` is not `[]`
- `integration_parent` is a path you're not sure exists
- Missing `#` header at top of file
- Tasks not separated by `# ---`
- Any field named `dependencies`, `status`, `priority`, `phase`, `description` in YAML
- Using `- [ ]` or `- [x]` markdown checklists in prose
