"""Validate a TODO.md file against the TODO frontmatter JSON schema."""

import json
import re
import subprocess
import sys
from pathlib import Path

import jsonschema
import yaml

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "todo_frontmatter.json"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL | re.MULTILINE)


def load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def parse_todo(path: Path) -> list[tuple[dict, str]]:
    content = path.read_text(encoding="utf-8")
    tasks = []
    for match in FRONTMATTER_RE.finditer(content):
        frontmatter_str = match.group(1)
        frontmatter = yaml.safe_load(frontmatter_str)
        if frontmatter is None:
            continue
        after = content[match.end():]
        next_block = after.find("\n---")
        if next_block == -1:
            prose = after.strip()
        else:
            prose = after[:next_block].strip()
        lines = prose.splitlines()
        cleaned = []
        for line in lines:
            if line.strip() == "":
                break
            cleaned.append(line)
        prose = "\n".join(cleaned).strip()
        tasks.append((frontmatter, prose))
    return tasks


def check_schema_validation(tasks: list[tuple[dict, str]], schema: dict) -> list[str]:
    errors = []
    validator = jsonschema.Draft7Validator(schema)
    for i, (fm, _) in enumerate(tasks):
        task_id = fm.get("id", f"<task {i}>")
        for error in sorted(validator.iter_errors(fm), key=lambda e: list(e.path)):
            path = ".".join(str(p) for p in error.path) if error.path else "(root)"
            errors.append(f"  {task_id}: {path}: {error.message}")
    return errors


def check_depends_on_references(tasks: list[tuple[dict, str]]) -> list[str]:
    errors = []
    valid_ids = {fm["id"] for fm, _ in tasks}
    for fm, _ in tasks:
        for dep in fm.get("depends_on", []):
            if dep not in valid_ids:
                errors.append(f"  {fm['id']}: depends_on '{dep}' does not exist in this file")
    return errors


def check_dependency_cycles(tasks: list[tuple[dict, str]]) -> list[str]:
    adjacency = {}
    for fm, _ in tasks:
        adjacency[fm["id"]] = fm.get("depends_on", [])

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in adjacency}
    cycle_members = set()

    def dfs(node, path):
        color[node] = GRAY
        path.append(node)
        for neighbor in adjacency[node]:
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                for n in path[cycle_start:]:
                    cycle_members.add(n)
            elif color[neighbor] == WHITE:
                dfs(neighbor, path)
        color[node] = BLACK
        path.pop()

    for nid in adjacency:
        if color[nid] == WHITE:
            dfs(nid, [])

    if cycle_members:
        return [f"  Dependency cycle detected among: {', '.join(sorted(cycle_members))}"]
    return []


def _git_file_exists(filepath: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", filepath],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _is_git_repo() -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_new_scene_paths(tasks: list[tuple[dict, str]]) -> list[str]:
    errors = []
    if not _is_git_repo():
        return errors
    for fm, _ in tasks:
        path = fm.get("new_scene_path", "")
        if _git_file_exists(path):
            errors.append(f"  {fm['id']}: new_scene_path '{path}' already exists in the repo")
    return errors


def check_integration_parents(tasks: list[tuple[dict, str]]) -> list[str]:
    errors = []
    if not _is_git_repo():
        return [f"  SKIPPED: not in a git repo, integration_parent existence cannot be checked"]
    for fm, _ in tasks:
        path = fm.get("integration_parent", "")
        if not _git_file_exists(path):
            errors.append(f"  {fm['id']}: integration_parent '{path}' does not exist in the repo")
    return errors


def check_touches_existing_files(tasks: list[tuple[dict, str]]) -> list[str]:
    errors = []
    for fm, _ in tasks:
        touches = fm.get("touches_existing_files", [])
        if touches:
            errors.append(
                f"  {fm['id']}: touches_existing_files is non-empty {touches}; "
                f"must be empty for parallel dispatch"
            )
    return errors


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m gdworkflow.validate_todo <path/to/TODO.md>", file=sys.stderr)
        sys.exit(1)

    todo_path = Path(sys.argv[1])
    if not todo_path.exists():
        print(f"FAIL: file not found: {todo_path}", file=sys.stderr)
        sys.exit(1)

    schema = load_schema()
    tasks = parse_todo(todo_path)

    if not tasks:
        print("FAIL: no frontmatter blocks found in", todo_path)
        sys.exit(1)

    all_pass = True
    results = {}

    checks = [
        ("Schema validation", lambda: check_schema_validation(tasks, schema)),
        ("depends_on references", lambda: check_depends_on_references(tasks)),
        ("Dependency cycles", lambda: check_dependency_cycles(tasks)),
        ("new_scene_path existence", lambda: check_new_scene_paths(tasks)),
        ("integration_parent existence", lambda: check_integration_parents(tasks)),
        ("touches_existing_files empty", lambda: check_touches_existing_files(tasks)),
    ]

    for name, check_fn in checks:
        errors = check_fn()
        if not errors:
            results[name] = ("PASS", [])
        elif len(errors) == 1 and errors[0].strip().startswith("SKIPPED"):
            results[name] = ("SKIP", errors)
        else:
            results[name] = ("FAIL", errors)
            all_pass = False

    print(f"Validating: {todo_path}")
    print(f"Tasks found: {len(tasks)}")
    print()
    for name, (status, errors) in results.items():
        print(f"  [{status}] {name}")
        for err in errors:
            print(err)

    print()
    if all_pass:
        print("Overall: PASS")
        sys.exit(0)
    else:
        print("Overall: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()