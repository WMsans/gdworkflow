"""Merger module: integrate approved feature scenes into their parent scenes,
handle signal connections, autoload registration, merge branches, and create milestones."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from gdworkflow.tscn_parser import (
    TscnFile,
    Connection,
    parse_tscn,
    update_load_steps,
)

DONE_MARKER = "DONE"


@dataclass
class IntegrationResult:
    task_id: str
    success: bool
    message: str = ""
    merged_branch: str = ""
    files_modified: list[str] = field(default_factory=list)


def integrate_scene(
    parent_path: Path,
    feature_path: Path,
    integration_hints: dict,
) -> IntegrationResult:
    """Integrate a feature scene into its parent scene.

    Reads the parent .tscn, adds the feature as an instanced child node,
    adds any signal connections, and writes back the modified parent.
    """
    try:
        parent_tscn = parse_tscn(parent_path)
    except Exception as exc:
        return IntegrationResult(
            task_id="",
            success=False,
            message=f"Failed to parse parent scene {parent_path}: {exc}",
        )

    feature_name = feature_path.stem
    feature_res_path = f"res://{feature_path}"

    node_type = integration_hints.get("node_type", "instance")
    position = integration_hints.get("position", "as_child_of_root")
    signals_to_connect = integration_hints.get("signals_to_connect", [])

    ext_id = parent_tscn.generate_ext_resource_id()

    existing_paths = {er.path for er in parent_tscn.ext_resources}
    if feature_res_path in existing_paths:
        for er in parent_tscn.ext_resources:
            if er.path == feature_res_path:
                ext_id = er.id
                break
    else:
        parent_tscn.add_ext_resource(
            type_="PackedScene",
            uid="",
            path=feature_res_path,
            id_=ext_id,
        )

    parent_tscn.header = update_load_steps(parent_tscn.header, delta=1)

    if node_type == "instance":
        parent_str = "."
        if position == "as_child_of_root":
            parent_str = "."
        elif position.startswith("as_child_of_"):
            parent_str = position[len("as_child_of_"):]

        new_node = parent_tscn.add_node_instance(
            name=feature_name,
            parent=parent_str,
            instance_id=ext_id,
        )

        parent_tscn.nodes.append(new_node)
    elif node_type == "script_attach":
        pass

    for sig in signals_to_connect:
        from_path = sig.get("from", feature_name)
        signal_name = sig.get("signal", "")
        to_path = sig.get("to", ".")
        method = sig.get("method", "")
        if signal_name and method:
            parent_tscn.add_connection(
                signal=signal_name,
                from_path=from_path,
                to_path=to_path,
                method=method,
            )

    try:
        parent_tscn.write(parent_path)
    except Exception as exc:
        return IntegrationResult(
            task_id="",
            success=False,
            message=f"Failed to write parent scene {parent_path}: {exc}",
        )

    return IntegrationResult(
        task_id="",
        success=True,
        message=f"Integrated {feature_name} into {parent_path}",
        files_modified=[str(parent_path)],
    )


def connect_signals(
    parent_path: Path,
    signals: list[dict],
) -> IntegrationResult:
    """Add signal connection entries to a parent .tscn file."""
    try:
        parent_tscn = parse_tscn(parent_path)
    except Exception as exc:
        return IntegrationResult(
            task_id="",
            success=False,
            message=f"Failed to parse parent scene {parent_path}: {exc}",
        )

    modified = False
    for sig in signals:
        from_path = sig.get("from", "")
        signal_name = sig.get("signal", "")
        to_path = sig.get("to", "")
        method = sig.get("method", "")
        flags = sig.get("flags")

        if not signal_name or not method:
            continue

        duplicate = any(
            c.signal == signal_name
            and c.from_path == from_path
            and c.to_path == to_path
            and c.method == method
            for c in parent_tscn.connections
        )
        if not duplicate:
            parent_tscn.add_connection(
                signal=signal_name,
                from_path=from_path,
                to_path=to_path,
                method=method,
                flags=flags,
            )
            modified = True

    if modified:
        try:
            parent_tscn.write(parent_path)
        except Exception as exc:
            return IntegrationResult(
                task_id="",
                success=False,
                message=f"Failed to write parent scene {parent_path}: {exc}",
            )

    return IntegrationResult(
        task_id="",
        success=True,
        message=f"Added {len(signals)} signal connection(s) to {parent_path}",
        files_modified=[str(parent_path)] if modified else [],
    )


def register_autoload(
    project_path: Path,
    name: str,
    script_path: str,
    singleton: bool = True,
) -> IntegrationResult:
    """Register an autoload in project.godot.

    Adds a line like: FeatureName="*res://path/to/feature.gd" to [autoload].
    The * prefix indicates a singleton.
    """
    content = project_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    autoload_line = f'{name}="{"*" if singleton else ""}{script_path}"'

    in_autoload = False
    autoload_section_idx = -1
    max_beyond_autoload = len(lines)

    for i, line in enumerate(lines):
        if line.strip() == "[autoload]":
            in_autoload = True
            autoload_section_idx = i
            continue
        if in_autoload and line.strip().startswith("["):
            max_beyond_autoload = i
            break
        if in_autoload and line.strip().startswith(f"{name}="):
            lines[i] = autoload_line
            project_path.write_text("\n".join(lines), encoding="utf-8")
            return IntegrationResult(
                task_id="",
                success=True,
                message=f"Updated autoload {name}",
                files_modified=[str(project_path)],
            )

    if autoload_section_idx == -1:
        autoload_idx = _find_insert_index(lines, "autoload")
        lines.insert(autoload_idx, "[autoload]")
        lines.insert(autoload_idx + 1, autoload_line)
        lines.insert(autoload_idx + 2, "")
        project_path.write_text("\n".join(lines), encoding="utf-8")
        return IntegrationResult(
            task_id="",
            success=True,
            message=f"Created [autoload] section and added {name}",
            files_modified=[str(project_path)],
        )

    insert_idx = min(max_beyond_autoload, autoload_section_idx + 1)
    while insert_idx < len(lines) and lines[insert_idx].strip() and not lines[insert_idx].strip().startswith("["):
        insert_idx += 1

    if insert_idx < len(lines):
        lines.insert(insert_idx, autoload_line)
    else:
        lines.append(autoload_line)

    project_path.write_text("\n".join(lines), encoding="utf-8")
    return IntegrationResult(
        task_id="",
        success=True,
        message=f"Added autoload {name}",
        files_modified=[str(project_path)],
    )


def _find_insert_index(lines: list[str], section: str) -> int:
    section_header = f"[{section}]"
    existing_sections = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            existing_sections.append((i, stripped))

    target = f"[{section}]"
    for idx, header in existing_sections:
        if header > target:
            return idx

    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            return i + 1

    return len(lines)


def merge_feature_branch(
    task_id: str,
    worktree_path: Path,
    git_root: Path,
    base_branch: str = "main",
) -> IntegrationResult:
    """Merge a feature branch into the base branch."""
    branch_name = f"feat/{task_id}"

    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        capture_output=True, text=True, cwd=str(git_root),
    )
    if result.returncode != 0:
        return IntegrationResult(
            task_id=task_id,
            success=False,
            message=f"Branch {branch_name} not found",
        )

    result = subprocess.run(
        ["git", "checkout", base_branch],
        capture_output=True, text=True, cwd=str(git_root),
    )
    if result.returncode != 0:
        return IntegrationResult(
            task_id=task_id,
            success=False,
            message=f"Failed to checkout {base_branch}: {result.stderr}",
        )

    result = subprocess.run(
        ["git", "merge", "--no-ff", branch_name, "-m", f"Merge {branch_name} into {base_branch}"],
        capture_output=True, text=True, cwd=str(git_root),
    )
    if result.returncode != 0:
        subprocess.run(["git", "merge", "--abort"], capture_output=True, cwd=str(git_root))
        return IntegrationResult(
            task_id=task_id,
            success=False,
            message=f"Merge conflict for {branch_name}: {result.stderr}",
        )

    return IntegrationResult(
        task_id=task_id,
        success=True,
        message=f"Merged {branch_name} into {base_branch}",
        merged_branch=branch_name,
    )


def revert_merge(git_root: Path, base_branch: str = "main") -> bool:
    """Revert the last merge commit on base_branch."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=str(git_root),
    )
    if result.returncode != 0:
        return False

    result = subprocess.run(
        ["git", "reset", "--hard", "HEAD~1"],
        capture_output=True, text=True, cwd=str(git_root),
    )
    return result.returncode == 0


def run_test_suite(git_root: Path, project_dir: Optional[Path] = None) -> bool:
    """Run the full test suite and return True if all tests pass."""
    test_dir = project_dir or git_root / "sandbox"
    script_path = git_root / "scripts" / "run_tests.sh"

    result = subprocess.run(
        ["bash", str(script_path), "--project-dir", str(test_dir)],
        capture_output=True, text=True, cwd=str(git_root),
    )
    return result.returncode == 0


def merge_approved_features(
    approved_tasks: list[dict],
    worktrees_dir: Path,
    git_root: Path,
    base_branch: str = "main",
    run_tests: bool = True,
    bot_url: str = "http://localhost:8080",
    no_discord: bool = False,
) -> list[IntegrationResult]:
    """Merge all approved features into the base branch.

    For each approved task:
    1. Merge the feature branch into base
    2. Integrate the feature scene into its parent
    3. Connect signals if specified
    4. Register autoloads if specified
    5. Commit integration changes
    6. Run tests (optional)
    7. Revert on test failure
    """
    from gdworkflow.orchestrate import Task, parse_todo, post_update_to_discord

    results: list[IntegrationResult] = []

    subprocess.run(["git", "checkout", base_branch], capture_output=True, cwd=str(git_root))

    for task_info in approved_tasks:
        task_id = task_info.get("id", task_info.get("task_id", ""))
        feature_name = task_info.get("feature_name", task_id)
        new_scene_path = task_info.get("new_scene_path", "")
        integration_parent = task_info.get("integration_parent", "")
        integration_hints = task_info.get("integration_hints", {})

        if not no_discord:
            post_update_to_discord("features", f"**{task_id}**: Merging {feature_name}", bot_url)

        merge_result = merge_feature_branch(task_id, worktrees_dir / task_id, git_root, base_branch)
        if not merge_result.success:
            results.append(merge_result)
            continue

        if integration_parent and new_scene_path:
            parent_path = git_root / integration_parent
            feature_path = Path(new_scene_path)

            if parent_path.exists():
                worktree_path = worktrees_dir / task_id

                integrate_result = integrate_scene(
                    parent_path, feature_path, integration_hints
                )
                if not integrate_result.success:
                    revert_merge(git_root, base_branch)
                    results.append(IntegrationResult(
                        task_id=task_id,
                        success=False,
                        message=f"Scene integration failed: {integrate_result.message}",
                    ))
                    continue

                if integrate_result.files_modified:
                    subprocess.run(
                        ["git", "add"] + integrate_result.files_modified,
                        capture_output=True, cwd=str(git_root),
                    )
                    subprocess.run(
                        ["git", "commit", "-m", f"integrate {task_id} into {integration_parent}"],
                        capture_output=True, cwd=str(git_root),
                    )

            signals = integration_hints.get("signals_to_connect", [])
            if signals and integration_parent:
                parent_path = git_root / integration_parent
                if parent_path.exists():
                    signal_result = connect_signals(parent_path, signals)
                    if signal_result.files_modified:
                        subprocess.run(
                            ["git", "add"] + signal_result.files_modified,
                            capture_output=True, cwd=str(git_root),
                        )
                        subprocess.run(
                            ["git", "commit", "-m", f"connect signals for {task_id}"],
                            capture_output=True, cwd=str(git_root),
                        )

            if integration_hints.get("autoload", False):
                project_godot = git_root / "sandbox" / "project.godot"
                if not project_godot.exists():
                    project_godot = git_root / "project.godot"

                script_path_autoload = f"res://{new_scene_path.replace('.tscn', '.gd')}"
                autoload_name = feature_name.replace(" ", "").replace("-", "_")

                autoload_result = register_autoload(
                    project_godot, autoload_name, script_path_autoload
                )
                if autoload_result.files_modified:
                    subprocess.run(
                        ["git", "add"] + autoload_result.files_modified,
                        capture_output=True, cwd=str(git_root),
                    )
                    subprocess.run(
                        ["git", "commit", "-m", f"register autoload {autoload_name}"],
                        capture_output=True, cwd=str(git_root),
                    )

        if run_tests:
            test_passed = run_test_suite(git_root)
            if not test_passed:
                if not no_discord:
                    post_update_to_discord(
                        "features",
                        f"**{task_id}**: Tests failed after merge, reverting",
                        bot_url,
                    )
                revert_merge(git_root, base_branch)
                results.append(IntegrationResult(
                    task_id=task_id,
                    success=False,
                    message="Tests failed after merge, reverted",
                ))
                continue

        results.append(IntegrationResult(
            task_id=task_id,
            success=True,
            message=f"Merged and integrated {task_id}",
            merged_branch=f"feat/{task_id}",
        ))

        if not no_discord:
            post_update_to_discord("features", f"**{task_id}**: Merge complete", bot_url)

    return results


def create_milestone_tag(git_root: Path) -> str:
    """Create a git tag for the milestone at the current HEAD."""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    tag_name = f"milestone-{timestamp}"

    result = subprocess.run(
        ["git", "tag", "-a", tag_name, "-m", f"Milestone {tag_name}"],
        capture_output=True, text=True, cwd=str(git_root),
    )
    if result.returncode != 0:
        return ""

    return tag_name


def export_release(git_root: Path, project_dir: Optional[Path] = None, preset: str = "default") -> bool:
    """Export a release build using Godot's headless mode.

    Returns True if export succeeds.
    """
    project = project_dir or git_root / "sandbox"
    godot_bin = os.environ.get("GODOT_BIN", "godot")

    result = subprocess.run(
        [godot_bin, "--headless", "--path", str(project), "--export-release", preset],
        capture_output=True, text=True, cwd=str(git_root),
    )
    return result.returncode == 0


def announce_milestone(
    bot_url: str,
    tag: str,
    merged_features: list[IntegrationResult],
    cost_records: Optional[list] = None,
    test_results: Optional[dict] = None,
    no_discord: bool = False,
) -> bool:
    """Post a milestone announcement to Discord."""
    if no_discord:
        return True

    import httpx

    lines = [
        f"**Milestone: {tag}**",
        "",
        "**Merged Features:**",
    ]
    for r in merged_features:
        status = "✅" if r.success else "❌"
        lines.append(f"  {status} {r.task_id}: {r.message}")

    if cost_records:
        total_tokens = sum(cr.total_tokens for cr in cost_records)
        total_prompt = sum(cr.prompt_tokens for cr in cost_records)
        total_completion = sum(cr.completion_tokens for cr in cost_records)
        lines.extend([
            "",
            "**Token Usage:**",
            f"  Prompt: {total_prompt:,}",
            f"  Completion: {total_completion:,}",
            f"  Total: {total_tokens:,}",
        ])

    if test_results:
        lines.extend([
            "",
            "**Test Results:**",
            f"  Passed: {test_results.get('passed', '?')}",
            f"  Failed: {test_results.get('failed', '?')}",
        ])

    lines.append("")
    lines.append(f"Tag: `{tag}`")

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{bot_url}/announce_milestone",
                json={"tag": tag, "summary": "\n".join(lines)},
            )
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def write_orchestrator_state(state: dict, worktrees_dir: Path) -> None:
    """Write orchestrator state to a JSON file for status queries."""
    state_path = worktrees_dir / "orchestrator_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def read_orchestrator_state(worktrees_dir: Path) -> dict:
    """Read orchestrator state from JSON file."""
    state_path = worktrees_dir / "orchestrator_state.json"
    if not state_path.exists():
        return {"status": "unknown"}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"status": "unknown"}


def check_cancel_signal(task_id: str, worktrees_dir: Path) -> bool:
    """Check if a cancel signal file exists for a specific task."""
    return (worktrees_dir / f"cancel_{task_id}").exists()


def check_cancel_run_signal(worktrees_dir: Path) -> bool:
    """Check if a cancel-run signal file exists."""
    return (worktrees_dir / "cancel_run").exists()


def write_cancel_signal(task_id: str, worktrees_dir: Path) -> None:
    """Write a cancel signal file for a specific task."""
    signal_path = worktrees_dir / f"cancel_{task_id}"
    signal_path.parent.mkdir(parents=True, exist_ok=True)
    signal_path.write_text(f"cancel {task_id}", encoding="utf-8")


def write_cancel_run_signal(worktrees_dir: Path) -> None:
    """Write a cancel-run signal file."""
    signal_path = worktrees_dir / "cancel_run"
    signal_path.parent.mkdir(parents=True, exist_ok=True)
    signal_path.write_text("cancel_run", encoding="utf-8")


def clear_cancel_signal(task_id: str, worktrees_dir: Path) -> None:
    """Remove the cancel signal file for a task."""
    signal_path = worktrees_dir / f"cancel_{task_id}"
    if signal_path.exists():
        signal_path.unlink()


def clear_cancel_run_signal(worktrees_dir: Path) -> None:
    """Remove the cancel-run signal file."""
    signal_path = worktrees_dir / "cancel_run"
    if signal_path.exists():
        signal_path.unlink()