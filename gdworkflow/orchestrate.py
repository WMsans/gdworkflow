"""Orchestrate multi-agent workflow: read TODO, create worktrees, dispatch subagents."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "todo_frontmatter.json"
DONE_MARKER = "DONE"


@dataclass
class Task:
    id: str
    feature_name: str
    new_scene_path: str
    integration_parent: str
    integration_hints: dict = field(default_factory=dict)
    touches_existing_files: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    estimated_complexity: str = "medium"
    prose: str = ""


@dataclass
class DispatchResult:
    task_id: str
    worktree: Path
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    token_usage: dict = field(default_factory=dict)


@dataclass
class CostRecord:
    task_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    duration: float = 0.0


def parse_todo(path: Path) -> list[Task]:
    import re

    content = path.read_text(encoding="utf-8")
    tasks: list[Task] = []

    frontmatter_re = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL | re.MULTILINE)
    positions = [(m.start(), m.end(), m.group(1)) for m in frontmatter_re.finditer(content)]

    for i, (start, end, fm_str) in enumerate(positions):
        fm = yaml.safe_load(fm_str)
        if fm is None:
            continue

        prose_start = end
        if i + 1 < len(positions):
            prose_end = positions[i + 1][0]
        else:
            prose_end = len(content)
        prose = content[prose_start:prose_end].strip()
        lines = prose.splitlines()
        cleaned = []
        for line in lines:
            if line.strip() == "" and not cleaned:
                continue
            cleaned.append(line)
        prose = "\n".join(cleaned).strip()
        header_lines = [l for l in cleaned if l.startswith("#")]
        if header_lines:
            cleaned = [l for l in cleaned if not l.startswith("#")]
            prose = "\n".join(cleaned).strip()

        task = Task(
            id=fm.get("id", ""),
            feature_name=fm.get("feature_name", ""),
            new_scene_path=fm.get("new_scene_path", ""),
            integration_parent=fm.get("integration_parent", ""),
            integration_hints=fm.get("integration_hints", {}),
            touches_existing_files=fm.get("touches_existing_files", []),
            depends_on=fm.get("depends_on", []),
            estimated_complexity=fm.get("estimated_complexity", "medium"),
            prose=prose,
        )
        tasks.append(task)

    return tasks


def build_dag(tasks: list[Task]) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {t.id: [] for t in tasks}
    task_map = {t.id: t for t in tasks}
    for t in tasks:
        for dep in t.depends_on:
            if dep in task_map:
                adjacency[dep].append(t.id)
    return adjacency


def detect_cycle(tasks: list[Task]) -> list[str] | None:
    adjacency = {}
    for t in tasks:
        adjacency[t.id] = t.depends_on

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in adjacency}
    cycle_members: set[str] = set()

    def dfs(node: str, path: list[str]):
        color[node] = GRAY
        path.append(node)
        for neighbor in adjacency.get(node, []):
            if neighbor not in color:
                continue
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
        return sorted(cycle_members)
    return None


def compute_batches(tasks: list[Task], max_batch: int = 5) -> list[list[str]]:
    cycle = detect_cycle(tasks)
    if cycle:
        print(f"ERROR: Dependency cycle detected among: {', '.join(cycle)}", file=sys.stderr)
        return []

    task_map = {t.id: t for t in tasks}
    in_degree: dict[str, int] = {t.id: 0 for t in tasks}

    for t in tasks:
        for dep in t.depends_on:
            in_degree[t.id] += 1

    batches: list[list[str]] = []
    completed: set[str] = set()
    remaining = {t.id for t in tasks}

    while remaining:
        ready = []
        for tid in sorted(remaining):
            task = task_map[tid]
            if all(dep in completed for dep in task.depends_on):
                ready.append(tid)

        if not ready:
            print(f"ERROR: Could not resolve dependencies for: {', '.join(sorted(remaining))}", file=sys.stderr)
            break

        batch = ready[:max_batch]
        batches.append(batch)
        for tid in batch:
            completed.add(tid)
            remaining.discard(tid)

    return batches


def create_worktree(task_id: str, base_branch: str = "main") -> Path:
    git_root = get_git_root()
    worktree_path = git_root / ".worktrees" / task_id
    branch_name = f"feat/{task_id}"

    if worktree_path.exists():
        print(f"  Worktree {worktree_path} already exists, removing...")
        subprocess.run(["git", "worktree", "remove", str(worktree_path), "--force"],
                        capture_output=True, text=True, cwd=str(git_root))

    result = subprocess.run(
        ["git", "branch", "-D", branch_name],
        capture_output=True, text=True, cwd=str(git_root),
    )

    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "-b", branch_name, base_branch],
        capture_output=True, text=True, cwd=str(git_root),
    )
    if result.returncode != 0:
        print(f"  git worktree add failed: {result.stderr.strip()}", file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

    opencode_dir = git_root / ".opencode"
    if opencode_dir.exists():
        dest = worktree_path / ".opencode"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(opencode_dir, dest)

    return worktree_path


def remove_worktree(task_id: str) -> None:
    git_root = get_git_root()
    worktree_path = git_root / ".worktrees" / task_id
    if worktree_path.exists():
        subprocess.run(["git", "worktree", "remove", str(worktree_path), "--force"],
                        capture_output=True, cwd=str(git_root))
        subprocess.run(["git", "branch", "-D", f"feat/{task_id}"],
                        capture_output=True, cwd=str(git_root))


def build_task_prompt(task: Task) -> str:
    parts = [
        f"# Task: {task.feature_name}",
        "",
        f"**Task ID**: {task.id}",
        f"**Scene Path**: {task.new_scene_path}",
        f"**Integration Parent**: {task.integration_parent}",
        "",
    ]

    if task.integration_hints:
        parts.append("## Integration Hints")
        for key, val in task.integration_hints.items():
            if isinstance(val, list) and val:
                parts.append(f"- **{key}**:")
                for item in val:
                    parts.append(f"  - {item}")
            elif isinstance(val, dict):
                parts.append(f"- **{key}**: {json.dumps(val)}")
            else:
                parts.append(f"- **{key}**: {val}")
        parts.append("")

    if task.touches_existing_files:
        parts.append("## Files to Modify")
        for f in task.touches_existing_files:
            parts.append(f"- {f}")
        parts.append("")

    if task.depends_on:
        parts.append(f"## Depends On: {', '.join(task.depends_on)}")
        parts.append("")

    parts.append("## Description")
    parts.append("")
    parts.append(task.prose)

    parts.append("")
    parts.append("## Automated Session")
    parts.append("You are running in an automated session inside a worktree created by the orchestrator. No human is chatting with you directly.")
    parts.append("- Do NOT load the using-superpowers skill. Skip it entirely.")
    parts.append("- Your worktree is already set up — do NOT create a new worktree or branch.")
    parts.append("- When complete, create a file called DONE in the worktree root.")
    parts.append("")
    parts.append("## Workflow — Follow These Skills In Order")
    parts.append("")
    parts.append("1. **brainstorming** — Explore the project, ask clarifying questions via Discord, present a design. Do NOT wait for explicit approval — proceed after presenting the design.")
    parts.append("2. **writing-plans** — Create a detailed implementation plan from the design.")
    parts.append("3. **subagent-driven-development** — Execute the plan task by task with review gates.")
    parts.append("")
    parts.append("## Clarifying Questions — ASK EARLY AND OFTEN")
    parts.append("Use the `clarify-via-discord` skill whenever anything is unclear. Do NOT guess. Do NOT assume. Ask via:")
    parts.append("  bash .opencode/skills/clarify-via-discord.sh \"<YOUR_TASK_ID>\" \"<YOUR_FEATURE_NAME>\" \"<YOUR_QUESTION>\"")
    parts.append("Ask ONE question at a time. Wait for the answer. Then proceed or ask the next question.")
    parts.append("")
    parts.append("## Rules")
    parts.append("- Create your scene as a NEW scene file. Do NOT modify existing scenes.")
    parts.append("- Commit frequently with descriptive messages.")
    parts.append("- This is a Godot 4.x project using GDScript.")

    return "\n".join(parts)


def _parse_token_usage(output: str) -> dict:
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            usage = data.get("usage", {})
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        if isinstance(data, list):
            total_prompt = 0
            total_completion = 0
            total_total = 0
            for item in data:
                if isinstance(item, dict):
                    u = item.get("usage", {})
                    total_prompt += u.get("prompt_tokens", 0)
                    total_completion += u.get("completion_tokens", 0)
                    total_total += u.get("total_tokens", 0)
            return {"prompt_tokens": total_prompt, "completion_tokens": total_completion, "total_tokens": total_total}
    except (json.JSONDecodeError, TypeError):
        pass
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _write_agent_log(worktree: Path, task_id: str, stdout: str, stderr: str,
                     exit_code: int, duration: float, token_usage: dict) -> None:
    log_path = worktree / "agent.log"
    lines = [
        f"=== Agent Log: {task_id} ===",
        f"Exit code: {exit_code}",
        f"Duration: {duration:.1f}s",
        f"Token usage: prompt={token_usage.get('prompt_tokens', 0)}, "
        f"completion={token_usage.get('completion_tokens', 0)}, "
        f"total={token_usage.get('total_tokens', 0)}",
        "",
        "=== STDOUT ===",
        stdout,
        "",
        "=== STDERR ===",
        stderr,
    ]
    log_path.write_text("\n".join(lines), encoding="utf-8")


def dispatch_subagent(task: Task, worktree: Path, model: str = "opencode-go/glm-5.1",
                       timeout: int = 1800) -> DispatchResult:
    prompt = build_task_prompt(task)

    prompt_file = worktree / ".task_prompt.md"
    prompt_file.write_text(prompt)

    done_file = worktree / DONE_MARKER

    cmd = [
        "opencode", "run",
        "--dir", str(worktree.resolve()),
        "--model", model,
        "--format", "json",
        prompt,
    ]

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PATH": os.environ.get("PATH", "")},
        )
        duration = time.time() - start
        token_usage = _parse_token_usage(result.stdout)
        dr = DispatchResult(
            task_id=task.id,
            worktree=worktree,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration=duration,
            token_usage=token_usage,
        )
        _write_agent_log(worktree, task.id, result.stdout, result.stderr,
                         result.returncode, duration, token_usage)
        return dr
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        dr = DispatchResult(
            task_id=task.id,
            worktree=worktree,
            exit_code=-1,
            stdout="",
            stderr=f"Subagent timed out after {timeout}s",
            duration=duration,
            token_usage={},
        )
        _write_agent_log(worktree, task.id, "", f"Subagent timed out after {timeout}s",
                         -1, duration, {})
        return dr


def poll_done_file(worktree: Path, task_id: str, poll_interval: float = 10.0,
                    max_wait: float = 3600) -> bool:
    done_file = worktree / DONE_MARKER
    start = time.time()
    while time.time() - start < max_wait:
        if done_file.exists():
            return True
        time.sleep(poll_interval)
    return False


def post_update_to_discord(channel: str, message: str, bot_url: str = "http://localhost:8080") -> bool:
    import httpx

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{bot_url}/post_update",
                json={"channel": channel, "message": message},
            )
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def post_cost_summary(cost_records: list[CostRecord], bot_url: str) -> bool:
    total_prompt = sum(r.prompt_tokens for r in cost_records)
    total_completion = sum(r.completion_tokens for r in cost_records)
    total_tokens = sum(r.total_tokens for r in cost_records)
    lines = [
        "**Cost Summary**",
        f"Total tasks: {len(cost_records)}",
        f"Prompt tokens: {total_prompt:,}",
        f"Completion tokens: {total_completion:,}",
        f"Total tokens: {total_tokens:,}",
        "",
    ]
    for r in cost_records:
        lines.append(f"  {r.task_id}: {r.total_tokens:,} tokens ({r.duration:.0f}s)")
    return post_update_to_discord("orchestrator", "\n".join(lines), bot_url)


async def _dispatch_task_async(task: Task, worktree: Path, model: str,
                                timeout: int, loop: asyncio.AbstractEventLoop) -> DispatchResult:
    def _run():
        return dispatch_subagent(task, worktree, model, timeout)
    return await loop.run_in_executor(None, _run)


async def _run_batch_async(batch: list[str], task_map: dict[str, Task],
                            model: str, timeout: int, base_branch: str,
                            bot_url: str, no_discord: bool) -> list[DispatchResult]:
    loop = asyncio.get_event_loop()
    coros = []
    for tid in batch:
        task = task_map[tid]
        worktree = create_worktree(task.id, base_branch)
        if not no_discord:
            post_update_to_discord("features", f"**{task.id}**: Starting — {task.feature_name}", bot_url)
        coros.append(_dispatch_task_async(task, worktree, model, timeout, loop))
    results = await asyncio.gather(*coros, return_exceptions=True)
    dispatch_results: list[DispatchResult] = []
    for i, r in enumerate(results):
        tid = batch[i]
        task = task_map[tid]
        if isinstance(r, Exception):
            worktree = Path(get_git_root()) / ".worktrees" / tid
            dr = DispatchResult(task_id=tid, worktree=worktree, exit_code=-1,
                                stdout="", stderr=str(r), duration=0.0)
            dispatch_results.append(dr)
        else:
            dispatch_results.append(r)
    return dispatch_results


def get_git_root() -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if result.returncode != 0:
        return Path.cwd()
    return Path(result.stdout.strip())


def main():
    parser = argparse.ArgumentParser(description="Orchestrate multi-agent workflow from a TODO.md file")
    parser.add_argument("todo_file", help="Path to the TODO.md file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print dispatch plan without executing")
    parser.add_argument("--base-branch", default="main",
                        help="Base branch for worktrees (default: main)")
    parser.add_argument("--model", default="opencode-go/glm-5.1",
                        help="Model for subagents (default: opencode-go/glm-5.1)")
    parser.add_argument("--max-batch", type=int, default=5,
                        help="Maximum parallel tasks per batch (default: 5)")
    parser.add_argument("--timeout", type=int, default=1800,
                        help="Timeout per subagent in seconds (default: 1800)")
    parser.add_argument("--bot-url", default="http://localhost:8080",
                        help="Discord bot HTTP URL (default: http://localhost:8080)")
    parser.add_argument("--no-discord", action="store_true",
                        help="Skip Discord updates (for testing)")
    parser.add_argument("--sequential", action="store_true",
                        help="Run tasks sequentially within each batch instead of in parallel")
    args = parser.parse_args()

    todo_path = Path(args.todo_file)
    if not todo_path.exists():
        print(f"ERROR: TODO file not found: {todo_path}", file=sys.stderr)
        sys.exit(1)

    tasks = parse_todo(todo_path)
    if not tasks:
        print("ERROR: No tasks found in TODO file", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(tasks)} tasks in {todo_path}")
    task_map = {t.id: t for t in tasks}

    cycle = detect_cycle(tasks)
    if cycle:
        print(f"ERROR: Dependency cycle detected among: {', '.join(cycle)}", file=sys.stderr)
        sys.exit(1)

    batches = compute_batches(tasks, args.max_batch)
    if not batches:
        print("ERROR: Could not compute batches (possible unresolved dependencies)", file=sys.stderr)
        sys.exit(1)

    print(f"\nDispatch plan ({len(batches)} batches):")
    for i, batch in enumerate(batches):
        batch_tasks = [task_map[tid] for tid in batch]
        print(f"\n  Batch {i + 1}:")
        for t in batch_tasks:
            deps = f" (depends: {', '.join(t.depends_on)})" if t.depends_on else ""
            print(f"    - {t.id}: {t.feature_name}{deps}")

    if args.dry_run:
        print("\n[DRY RUN] No worktrees created, no subagents dispatched.")
        return

    git_root = get_git_root()
    os.chdir(git_root)

    worktrees_dir = git_root / ".worktrees"
    if worktrees_dir.exists():
        for wt in worktrees_dir.iterdir():
            if wt.is_dir():
                task_id = wt.name
                print(f"  Removing existing worktree: {task_id}")
                subprocess.run(["git", "worktree", "remove", str(wt), "--force"],
                                capture_output=True)
                subprocess.run(["git", "branch", "-D", f"feat/{task_id}"],
                                capture_output=True)
    else:
        worktrees_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[DispatchResult] = []
    cost_records: list[CostRecord] = []
    failed_permanently: set[str] = set()

    for i, batch in enumerate(batches):
        print(f"\n{'='*60}")
        print(f"Batch {i + 1}/{len(batches)}: {len(batch)} task(s)")
        print(f"{'='*60}")

        if not args.no_discord:
            post_update_to_discord(
                "orchestrator",
                f"Starting batch {i + 1}/{len(batches)}: {len(batch)} task(s)",
                args.bot_url,
            )

        if args.sequential:
            batch_results: list[DispatchResult] = []
            for tid in batch:
                task = task_map[tid]
                print(f"\n--- Dispatching: {task.id} ({task.feature_name}) ---")
                worktree = create_worktree(task.id, args.base_branch)
                print(f"  Worktree: {worktree}")
                if not args.no_discord:
                    post_update_to_discord("features", f"**{task.id}**: Starting — {task.feature_name}", args.bot_url)
                result = dispatch_subagent(task, worktree, args.model, args.timeout)
                batch_results.append(result)
        else:
            print(f"\n--- Dispatching {len(batch)} tasks in parallel ---")
            batch_results = asyncio.run(
                _run_batch_async(batch, task_map, args.model, args.timeout,
                                 args.base_branch, args.bot_url, args.no_discord)
            )

        for result in batch_results:
            done_file = result.worktree / DONE_MARKER
            if result.exit_code == 0 and done_file.exists():
                status = "COMPLETED"
            elif result.exit_code == 0:
                status = "NO_DONE_FILE"
                print(f"  WARNING: {result.task_id} exited cleanly but no DONE marker found")
            elif result.exit_code == -1:
                status = "TIMEOUT"
            else:
                status = f"FAILED (exit code {result.exit_code})"

            print(f"  {result.task_id}: {status} (took {result.duration:.1f}s)")

            if not args.no_discord:
                post_update_to_discord(
                    "features",
                    f"**{result.task_id}**: {status} (took {result.duration:.0f}s)",
                    args.bot_url,
                )

            tu = result.token_usage
            cost_records.append(CostRecord(
                task_id=result.task_id,
                prompt_tokens=tu.get("prompt_tokens", 0),
                completion_tokens=tu.get("completion_tokens", 0),
                total_tokens=tu.get("total_tokens", 0),
                model=args.model,
                duration=result.duration,
            ))

            if status != "COMPLETED":
                failed_permanently.add(result.task_id)

        all_results.extend(batch_results)

        failed_in_batch = [r for r in batch_results if r.exit_code != 0 or not (r.worktree / DONE_MARKER).exists()]
        if failed_in_batch:
            for r in failed_in_batch:
                print(f"\n  FAILED: {r.task_id}")
                print(f"    stderr: {r.stderr[:500]}")

        completed_in_batch = [r for r in batch_results if r.exit_code == 0 and (r.worktree / DONE_MARKER).exists()]
        print(f"\nBatch {i + 1} complete: {len(completed_in_batch)} succeeded, {len(failed_in_batch)} failed")

    print(f"\n{'='*60}")
    print("Workflow complete!")
    print(f"{'='*60}")

    completed = [r for r in all_results if r.exit_code == 0 and (r.worktree / DONE_MARKER).exists()]
    failed = [r for r in all_results if r.exit_code != 0 or not (r.worktree / DONE_MARKER).exists()]

    print(f"\n  Completed: {len(completed)}")
    for r in completed:
        print(f"    - {r.task_id} ({r.duration:.0f}s)")

    if failed:
        print(f"\n  Failed: {len(failed)}")
        for r in failed:
            print(f"    - {r.task_id} (exit: {r.exit_code})")

    if cost_records:
        if not args.no_discord:
            post_cost_summary(cost_records, args.bot_url)
        total_tokens = sum(r.total_tokens for r in cost_records)
        print(f"\n  Total tokens used: {total_tokens:,}")

    if not args.no_discord:
        summary_lines = [f"Workflow finished: {len(completed)} completed, {len(failed)} failed"]
        if completed:
            summary_lines.append("\nCompleted tasks:")
            for r in completed:
                summary_lines.append(f"  - {r.task_id}")
        post_update_to_discord("orchestrator", "\n".join(summary_lines), args.bot_url)


if __name__ == "__main__":
    main()