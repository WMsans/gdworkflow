"""End-to-end integration tests for the Week 1 milestone."""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TODO_CONTENT = textwrap.dedent("""\
# TODO — Test

---
id: feat-red-square
feature_name: Red Square
new_scene_path: scenes/features/red_square.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: low
---

Create a simple scene with a red square that the player can move with arrow keys.
""")

GDD_CONTENT = textwrap.dedent("""\
# Test Game Design Document

## Features
- Red square that moves with arrow keys
- Blue circle that bounces
""")


class TestWeek1Integration(unittest.TestCase):
    """Integration tests for the full gdworkflow Week 1 pipeline."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir_path = Path(self.tmpdir.name)
        self.todo_path = self.tmpdir_path / "TODO.md"
        self.todo_path.write_text(TODO_CONTENT)
        self.gdd_path = self.tmpdir_path / "GDD.md"
        self.gdd_path.write_text(GDD_CONTENT)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_validate_todo_cli_passes(self):
        env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
        result = subprocess.run(
            [sys.executable, "-m", "gdworkflow.validate_todo", str(self.todo_path)],
            capture_output=True,
            text=True,
            cwd=str(self.tmpdir_path),
            env=env,
        )
        self.assertEqual(
            result.returncode, 0,
            f"Validator failed:\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertIn("Overall: PASS", result.stdout)
        self.assertIn("Tasks found: 1", result.stdout)

    def test_validate_todo_programmatic(self):
        from gdworkflow.validate_todo import (
            check_dependency_cycles,
            check_depends_on_references,
            check_schema_validation,
            load_schema,
            parse_todo,
        )

        schema = load_schema()
        tasks = parse_todo(self.todo_path)

        self.assertEqual(len(tasks), 1, f"Expected 1 task, got {len(tasks)}")

        fm, prose = tasks[0]
        self.assertEqual(fm["id"], "feat-red-square")
        self.assertIn("red square", prose.lower())

        schema_errors = check_schema_validation(tasks, schema)
        self.assertEqual(schema_errors, [], f"Schema validation errors: {schema_errors}")

        ref_errors = check_depends_on_references(tasks)
        self.assertEqual(ref_errors, [], f"Dependency reference errors: {ref_errors}")

        cycle_errors = check_dependency_cycles(tasks)
        self.assertEqual(cycle_errors, [], f"Dependency cycle errors: {cycle_errors}")

    def test_orchestrator_dry_run(self):
        env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
        result = subprocess.run(
            [sys.executable, "-m", "gdworkflow.orchestrate", str(self.todo_path), "--dry-run"],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(
            result.returncode, 0,
            f"Orchestrator dry-run failed:\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertIn("Dispatch plan", result.stdout)
        self.assertIn("feat-red-square", result.stdout)
        self.assertIn("Batch", result.stdout)
        self.assertIn("[DRY RUN]", result.stdout)

    def test_discord_bot_init(self):
        import aiohttp.web
        from gdworkflow.bot.main import Config, DiscordBot, create_bot, create_http_app

        cfg = Config(bot_token="test-token", guild_id=12345, http_port=9999)
        self.assertEqual(cfg.bot_token, "test-token")
        self.assertEqual(cfg.guild_id, 12345)
        self.assertEqual(cfg.http_port, 9999)

        bot = create_bot(cfg)
        self.assertIsInstance(bot, DiscordBot)

        app = create_http_app(bot, cfg)
        self.assertIsNotNone(app)
        paths = [r.resource.canonical for r in app.router.routes()]
        self.assertIn("/health", paths)
        self.assertIn("/post_update", paths)
        self.assertIn("/announce_milestone", paths)

    def test_gen_todo_dry_run(self):
        from gdworkflow.gen_todo import dry_run

        result = dry_run(self.gdd_path)
        self.assertIn("---", result)
        self.assertIn("new_scene_path", result)
        self.assertIn("integration_parent", result)
        self.assertIn("depends_on", result)
        self.assertIn("feature_name", result)

    def test_orchestrator_parse_todo(self):
        from gdworkflow.orchestrate import Task, parse_todo

        tasks = parse_todo(self.todo_path)
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertIsInstance(task, Task)
        self.assertEqual(task.id, "feat-red-square")
        self.assertEqual(task.feature_name, "Red Square")
        self.assertEqual(task.new_scene_path, "scenes/features/red_square.tscn")
        self.assertEqual(task.integration_parent, "scenes/main.tscn")
        self.assertEqual(task.estimated_complexity, "low")
        self.assertEqual(task.depends_on, [])

    def test_orchestrator_compute_batches(self):
        from gdworkflow.orchestrate import parse_todo, compute_batches

        tasks = parse_todo(self.todo_path)
        batches = compute_batches(tasks)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0], ["feat-red-square"])

    def test_orchestrator_build_task_prompt(self):
        from gdworkflow.orchestrate import parse_todo, build_task_prompt

        tasks = parse_todo(self.todo_path)
        task = tasks[0]
        prompt = build_task_prompt(task)
        self.assertIn("Red Square", prompt)
        self.assertIn("feat-red-square", prompt)
        self.assertIn("scenes/features/red_square.tscn", prompt)
        self.assertIn("Integration Hints", prompt)


if __name__ == "__main__":
    unittest.main()