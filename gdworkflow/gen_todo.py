import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

DEFAULT_MODEL = "deepseek/deepseek-v4-flash"

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "todo_frontmatter.json"

SYSTEM_PROMPT = """\
You are a game development task planner. Given a Game Design Document (GDD) in markdown, \
your job is to break it into discrete, parallelizable features suitable for multi-agent \
development in Godot 4.

Each feature becomes a task in a TODO.md file. Each task has YAML frontmatter followed by \
the feature's prose description.

The YAML frontmatter must follow this schema:
- id: feat-kebab-case-name (unique identifier, e.g. feat-player-dash)
- feature_name: Human-readable name for the feature
- new_scene_path: scenes/features/kebab_case_name.tscn (path where the new scene will be created)
- integration_parent: path to the parent .tscn file this feature integrates into
- integration_hints: object with:
    - node_type: "instance" or "script_attach" (default: "instance")
    - position: where to place the instance in the parent tree (e.g. "as_child_of_root")
    - signals_to_connect: list of objects with {from, signal, to, method} (default: [])
    - autoload: boolean, whether to register as autoload in project.godot (default: false)
- touches_existing_files: [] (MUST be empty for parallelizable tasks; non-empty forces serialization)
- depends_on: list of task IDs that must complete before this one starts (default: [])
- estimated_complexity: "low", "medium", or "high" (default: "medium")

IMPORTANT RULES:
1. Maximize parallelism — minimize depends_on edges and keep touches_existing_files empty.
2. Each feature should be a self-contained scene that can be developed independently.
3. Use stable parent scene paths from the GDD or project structure.
4. Separate tasks by # --- delimiters.
5. Each task section starts with --- on its own line, then the YAML frontmatter (between --- markers), then the prose description.

Output format — a sequence of task blocks separated by horizontal rules:

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

Prose description of the feature taken from or paraphrased from the GDD...

---
id: feat-another-feature
...
---

Another feature description...

Respond ONLY with the task blocks. Do not include any preamble, explanation, or commentary.
"""


def load_schema() -> dict:
    if SCHEMA_PATH.exists():
        with open(SCHEMA_PATH) as f:
            return json.load(f)
    return {}


def generate_todo(gdd_content: str, model: str) -> str:
    schema = load_schema()

    user_msg = f"Here is the Game Design Document. Break it into discrete, parallelizable feature tasks:\n\n{gdd_content}"

    prompt = f"{SYSTEM_PROMPT}\n\n{user_msg}"

    if schema:
        prompt += (
            f"\n\nJSON Schema for reference:\n```json\n{json.dumps(schema, indent=2)}\n```\n\n"
            f"Respond with a JSON object having a single key \"tasks\" whose value is an array of task objects conforming to this schema. "
            f"Also include a \"description\" field in each task object with the prose description for that feature."
        )

    cmd = ["opencode", "run", "--model", model, prompt]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        print("Error: 'opencode' not found. Install it from https://opencode.ai", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Error: opencode run timed out after 300s.", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"Error: opencode run failed (exit {result.returncode}): {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    content = result.stdout.strip()

    if not content:
        print("Error: Empty response from the model.", file=sys.stderr)
        sys.exit(1)

    if schema:
        return _json_response_to_todo(content)

    return content


def _json_response_to_todo(content: str) -> str:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return content.strip()

    tasks = parsed.get("tasks", [])
    if not tasks and isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                tasks = v
                break

    parts = []
    for task in tasks:
        description = task.pop("description", "")
        frontmatter = yaml.dump(task, default_flow_style=False, sort_keys=False).strip()
        block = f"---\n{frontmatter}\n---\n\n{description.strip()}\n"
        parts.append(block)

    return "\n# ---\n\n".join(parts)


def dry_run(gdd_path: Path) -> str:
    gdd_content = gdd_path.read_text()
    lines = gdd_content.splitlines()
    features = []
    current_section = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
        elif stripped.startswith("- ") and current_section:
            feature_text = stripped.lstrip("- ").strip()
            kebab = feature_text.lower().replace(" ", "-").replace(".", "")
            kebab = "".join(c for c in kebab if c.isalnum() or c == "-").strip("-")
            if not kebab:
                kebab = "unnamed-feature"
            features.append(
                {
                    "id": f"feat-{kebab}",
                    "feature_name": feature_text,
                    "new_scene_path": f"scenes/features/{kebab.replace('-', '_')}.tscn",
                    "integration_parent": "scenes/main.tscn",
                    "integration_hints": {
                        "node_type": "instance",
                        "position": "as_child_of_root",
                        "signals_to_connect": [],
                        "autoload": False,
                    },
                    "touches_existing_files": [],
                    "depends_on": [],
                    "estimated_complexity": "medium",
                }
            )
            current_section = None

    if not features:
        features.append(
            {
                "id": "feat-placeholder",
                "feature_name": "Placeholder Feature",
                "new_scene_path": "scenes/features/placeholder.tscn",
                "integration_parent": "scenes/main.tscn",
                "integration_hints": {
                    "node_type": "instance",
                    "position": "as_child_of_root",
                    "signals_to_connect": [],
                    "autoload": False,
                },
                "touches_existing_files": [],
                "depends_on": [],
                "estimated_complexity": "medium",
            }
        )

    parts = []
    for feat in features:
        fm = yaml.dump(feat, default_flow_style=False, sort_keys=False).strip()
        block = f"---\n{fm}\n---\n\n{feat['feature_name']} — replace with detailed description from GDD.\n"
        parts.append(block)

    return "\n# ---\n\n".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a TODO.md from a Game Design Document using opencode"
    )
    parser.add_argument("gdd", help="Path to the GDD markdown file")
    parser.add_argument("--output", help="Output path for TODO.md (default: TODO.md in GDD directory)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Model to use in provider/model format (default: {DEFAULT_MODEL}). "
                             f"Configure API keys via 'opencode auth login'.")
    parser.add_argument("--dry-run", action="store_true", help="Print a template TODO.md without making API calls")
    args = parser.parse_args()

    gdd_path = Path(args.gdd).resolve()
    if not gdd_path.exists():
        print(f"Error: GDD file not found: {gdd_path}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        result = dry_run(gdd_path)
    else:
        gdd_content = gdd_path.read_text()
        result = generate_todo(gdd_content, args.model)

    header = f"# TODO — Generated from {gdd_path.name}\n\n"
    output = header + result + "\n"

    print(output)

    output_path = Path(args.output) if args.output else gdd_path.parent / "TODO.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output)
    print(f"\nWritten to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()