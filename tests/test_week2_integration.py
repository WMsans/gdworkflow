"""Tests for Week 2 features: parallelism, clarifying questions, agent config, skills."""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MEDIUM_TODO = textwrap.dedent("""\
# TODO — Test

---
id: feat-player-movement
feature_name: Player Movement
new_scene_path: scenes/features/player.tscn
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

Player movement with run and jump.

---
id: feat-collectible-coins
feature_name: Collectible Coins
new_scene_path: scenes/features/coin.tscn
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

Collectible coins scattered in the level.

---
id: feat-patrolling-enemies
feature_name: Patrolling Enemies
new_scene_path: scenes/features/enemy.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on:
  - feat-player-movement
estimated_complexity: medium
---

Enemies that patrol platforms.

---
id: feat-hud
feature_name: HUD
new_scene_path: scenes/features/hud.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on:
  - feat-collectible-coins
estimated_complexity: low
---

Heads-up display for score.
""")


class TestDAGAndBatchComputation(unittest.TestCase):
    def test_detect_cycle(self):
        from gdworkflow.orchestrate import Task, detect_cycle

        tasks = [
            Task(id="a", feature_name="A", new_scene_path="scenes/a.tscn",
                 integration_parent="scenes/main.tscn", depends_on=["b"]),
            Task(id="b", feature_name="B", new_scene_path="scenes/b.tscn",
                 integration_parent="scenes/main.tscn", depends_on=["a"]),
        ]
        cycle = detect_cycle(tasks)
        self.assertIsNotNone(cycle)
        self.assertIn("a", cycle)
        self.assertIn("b", cycle)

    def test_no_cycle(self):
        from gdworkflow.orchestrate import Task, detect_cycle

        tasks = [
            Task(id="a", feature_name="A", new_scene_path="scenes/a.tscn",
                 integration_parent="scenes/main.tscn", depends_on=[]),
            Task(id="b", feature_name="B", new_scene_path="scenes/b.tscn",
                 integration_parent="scenes/main.tscn", depends_on=["a"]),
        ]
        cycle = detect_cycle(tasks)
        self.assertIsNone(cycle)

    def test_compute_batches_parallel(self):
        from gdworkflow.orchestrate import Task, compute_batches

        tasks = [
            Task(id="feat-a", feature_name="A", new_scene_path="scenes/a.tscn",
                 integration_parent="scenes/main.tscn", depends_on=[]),
            Task(id="feat-b", feature_name="B", new_scene_path="scenes/b.tscn",
                 integration_parent="scenes/main.tscn", depends_on=[]),
            Task(id="feat-c", feature_name="C", new_scene_path="scenes/c.tscn",
                 integration_parent="scenes/main.tscn", depends_on=[]),
        ]
        batches = compute_batches(tasks, max_batch=5)
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 3)

    def test_compute_batches_sequential(self):
        from gdworkflow.orchestrate import Task, compute_batches

        tasks = [
            Task(id="feat-a", feature_name="A", new_scene_path="scenes/a.tscn",
                 integration_parent="scenes/main.tscn", depends_on=[]),
            Task(id="feat-b", feature_name="B", new_scene_path="scenes/b.tscn",
                 integration_parent="scenes/main.tscn", depends_on=["feat-a"]),
            Task(id="feat-c", feature_name="C", new_scene_path="scenes/c.tscn",
                 integration_parent="scenes/main.tscn", depends_on=["feat-b"]),
        ]
        batches = compute_batches(tasks, max_batch=5)
        self.assertEqual(len(batches), 3)
        self.assertEqual(batches[0], ["feat-a"])
        self.assertEqual(batches[1], ["feat-b"])
        self.assertEqual(batches[2], ["feat-c"])

    def test_compute_batches_mixed_deps(self):
        from gdworkflow.orchestrate import parse_todo, compute_batches

        tmpdir = tempfile.TemporaryDirectory()
        try:
            todo_path = Path(tmpdir.name) / "TODO.md"
            todo_path.write_text(MEDIUM_TODO)
            tasks = parse_todo(todo_path)
            batches = compute_batches(tasks, max_batch=5)

            batch_ids = [set(b) for b in batches]
            self.assertIn({"feat-player-movement", "feat-collectible-coins"}, batch_ids)
            self.assertIn({"feat-patrolling-enemies", "feat-hud"}, batch_ids)
        finally:
            tmpdir.cleanup()

    def test_compute_batches_max_batch_cap(self):
        from gdworkflow.orchestrate import Task, compute_batches

        tasks = [
            Task(id=f"feat-{i}", feature_name=f"Task {i}",
                 new_scene_path=f"scenes/{i}.tscn",
                 integration_parent="scenes/main.tscn", depends_on=[])
            for i in range(7)
        ]
        batches = compute_batches(tasks, max_batch=3)
        self.assertEqual(len(batches[0]), 3)
        self.assertEqual(len(batches[1]), 3)
        self.assertEqual(len(batches[2]), 1)

    def test_cycle_returns_empty_batches(self):
        from gdworkflow.orchestrate import Task, compute_batches

        tasks = [
            Task(id="x", feature_name="X", new_scene_path="scenes/x.tscn",
                 integration_parent="scenes/main.tscn", depends_on=["y"]),
            Task(id="y", feature_name="Y", new_scene_path="scenes/y.tscn",
                 integration_parent="scenes/main.tscn", depends_on=["x"]),
        ]
        batches = compute_batches(tasks)
        self.assertEqual(batches, [])


class TestCostTrackerAndLogging(unittest.TestCase):
    def test_parse_token_usage_dict(self):
        from gdworkflow.orchestrate import _parse_token_usage

        output = '{"usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}'
        result = _parse_token_usage(output)
        self.assertEqual(result["prompt_tokens"], 100)
        self.assertEqual(result["completion_tokens"], 50)
        self.assertEqual(result["total_tokens"], 150)

    def test_parse_token_usage_list(self):
        from gdworkflow.orchestrate import _parse_token_usage

        output = '[{"usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75}}, {"usage": {"prompt_tokens": 60, "completion_tokens": 30, "total_tokens": 90}}]'
        result = _parse_token_usage(output)
        self.assertEqual(result["prompt_tokens"], 110)
        self.assertEqual(result["completion_tokens"], 55)
        self.assertEqual(result["total_tokens"], 165)

    def test_parse_token_usage_invalid(self):
        from gdworkflow.orchestrate import _parse_token_usage

        result = _parse_token_usage("not json")
        self.assertEqual(result, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

    def test_write_agent_log(self):
        from gdworkflow.orchestrate import _write_agent_log

        tmpdir = tempfile.TemporaryDirectory()
        try:
            worktree = Path(tmpdir.name)
            _write_agent_log(worktree, "feat-test", "hello stdout", "hello stderr",
                             0, 42.5, {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
            log_path = worktree / "agent.log"
            self.assertTrue(log_path.exists())
            content = log_path.read_text()
            self.assertIn("feat-test", content)
            self.assertIn("42.5s", content)
            self.assertIn("hello stdout", content)
            self.assertIn("hello stderr", content)
            self.assertIn("prompt=100", content)
        finally:
            tmpdir.cleanup()

    def test_cost_record(self):
        from gdworkflow.orchestrate import CostRecord

        rec = CostRecord(task_id="feat-test", prompt_tokens=100,
                         completion_tokens=50, total_tokens=150, model="opencode-go/glm-5.1")
        self.assertEqual(rec.task_id, "feat-test")
        self.assertEqual(rec.total_tokens, 150)


class TestClarifyingQuestionBot(unittest.TestCase):
    def test_bot_has_post_question_route(self):
        from gdworkflow.bot.main import Config, DiscordBot, create_bot, create_http_app

        cfg = Config(bot_token="test-token", guild_id=12345, http_port=9999)
        bot = create_bot(cfg)
        app = create_http_app(bot, cfg)
        paths = [r.resource.canonical for r in app.router.routes()]
        self.assertIn("/post_question", paths)
        self.assertIn("/post_update", paths)
        self.assertIn("/announce_milestone", paths)
        self.assertIn("/health", paths)

    def test_pending_question_dataclass(self):
        from gdworkflow.bot.main import PendingQuestion
        import asyncio

        pq = PendingQuestion(
            question_id="abc123",
            agent_id="feat-test",
            feature="Test Feature",
            question="Should this be red or blue?",
        )
        self.assertEqual(pq.question_id, "abc123")
        self.assertEqual(pq.status, "pending")
        self.assertIsNone(pq.thread_id)


class TestOrchestratorSequentialFlag(unittest.TestCase):
    def test_sequential_flag_exists(self):
        env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
        result = subprocess.run(
            [sys.executable, "-m", "gdworkflow.orchestrate", "--help"],
            capture_output=True, text=True, env=env,
        )
        self.assertIn("--sequential", result.stdout)

    def test_dry_run_with_medium_todo(self):
        tmpdir = tempfile.TemporaryDirectory()
        try:
            todo_path = Path(tmpdir.name) / "TODO.md"
            todo_path.write_text(MEDIUM_TODO)
            env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
            result = subprocess.run(
                [sys.executable, "-m", "gdworkflow.orchestrate", str(todo_path), "--dry-run"],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            self.assertIn("Batch 1", result.stdout)
            self.assertIn("feat-player-movement", result.stdout)
            self.assertIn("feat-collectible-coins", result.stdout)
        finally:
            tmpdir.cleanup()


class TestSkillFilesExist(unittest.TestCase):
    def test_skills_directory(self):
        skills_dir = PROJECT_ROOT / ".opencode" / "skills"
        self.assertTrue(skills_dir.exists(), "Skills directory should exist")

    def test_clarify_skill(self):
        skill_file = PROJECT_ROOT / ".opencode" / "skills" / "clarify-via-discord.md"
        self.assertTrue(skill_file.exists(), "clarify-via-discord.md should exist")
        content = skill_file.read_text()
        self.assertIn("clarify-via-discord.sh", content)

    def test_clarify_script(self):
        script_file = PROJECT_ROOT / ".opencode" / "skills" / "clarify-via-discord.sh"
        self.assertTrue(script_file.exists(), "clarify-via-discord.sh should exist")
        self.assertTrue(os.access(script_file, os.X_OK), "Script should be executable")

    def test_gdscript_conventions_skill(self):
        skill_file = PROJECT_ROOT / ".opencode" / "skills" / "gdscript-conventions.md"
        self.assertTrue(skill_file.exists(), "gdscript-conventions.md should exist")
        content = skill_file.read_text()
        self.assertIn("snake_case", content)
        self.assertIn("@export", content)

    def test_scene_isolation_skill(self):
        skill_file = PROJECT_ROOT / ".opencode" / "skills" / "scene-isolation.md"
        self.assertTrue(skill_file.exists(), "scene-isolation.md should exist")
        content = skill_file.read_text()
        self.assertIn("scenes/features/", content)

    def test_commit_frequently_skill(self):
        skill_file = PROJECT_ROOT / ".opencode" / "skills" / "commit-frequently.md"
        self.assertTrue(skill_file.exists(), "commit-frequently.md should exist")

    def test_subagent_config(self):
        agent_file = PROJECT_ROOT / ".opencode" / "agents" / "subagent.md"
        self.assertTrue(agent_file.exists(), "subagent.md should exist")
        content = agent_file.read_text()
        self.assertIn("Scene Isolation", content)
        self.assertIn("clarify-via-discord", content)

    def test_drop_in_skills_exist(self):
        for skill_name in ["finishing-a-development-branch", "receiving-code-review",
                           "systematic-debugging", "test-driven-development",
                           "verification-before-completion"]:
            skill_dir = PROJECT_ROOT / ".opencode" / "skills" / skill_name
            self.assertTrue(skill_dir.exists(), f"Skill directory {skill_name} should exist")
            skill_file = skill_dir / "SKILL.md"
            self.assertTrue(skill_file.exists(), f"SKILL.md should exist in {skill_name}")

    def test_ported_skills_exist(self):
        for skill_name in ["brainstorming", "executing-plans", "requesting-code-review",
                           "subagent-driven-development", "using-git-worktrees", "writing-plans"]:
            skill_dir = PROJECT_ROOT / ".opencode" / "skills" / skill_name
            self.assertTrue(skill_dir.exists(), f"Skill directory {skill_name} should exist")
            skill_file = skill_dir / "SKILL.md"
            self.assertTrue(skill_file.exists(), f"SKILL.md should exist in {skill_name}")

    def test_ported_skills_no_superpowers_references(self):
        ported_skills = [
            "brainstorming", "executing-plans", "requesting-code-review",
            "subagent-driven-development", "using-git-worktrees", "writing-plans"
        ]
        for skill_name in ported_skills:
            skill_file = PROJECT_ROOT / ".opencode" / "skills" / skill_name / "SKILL.md"
            content = skill_file.read_text()
            self.assertNotIn("superpowers:", content,
                             f"{skill_name} should not reference superpowers: skill invocation")
            self.assertNotIn("~/.claude/", content,
                             f"{skill_name} should not reference Claude-specific paths")

    def test_companion_files_exist(self):
        companions = {
            "requesting-code-review": ["code-reviewer.md"],
            "subagent-driven-development": ["implementer-prompt.md", "spec-reviewer-prompt.md", "code-quality-reviewer-prompt.md"],
            "writing-plans": ["plan-document-reviewer-prompt.md"],
            "systematic-debugging": ["root-cause-tracing.md", "defense-in-depth.md", "condition-based-waiting.md"],
            "test-driven-development": ["testing-anti-patterns.md"],
        }
        for skill_name, files in companions.items():
            for f in files:
                filepath = PROJECT_ROOT / ".opencode" / "skills" / skill_name / f
                self.assertTrue(filepath.exists(), f"{skill_name}/{f} should exist")


if __name__ == "__main__":
    unittest.main()