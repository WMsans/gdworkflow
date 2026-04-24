"""Tests for Week 4 features: merger, tscn parser, graceful shutdown, slash commands."""

import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestTscnParser(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_parse_simple_scene(self):
        from gdworkflow.tscn_parser import parse_tscn_string

        content = textwrap.dedent("""\
            [gd_scene format=3 uid="uid://abc123"]

            [ext_resource type="Script" uid="uid://script1" path="res://main.gd" id="1"]

            [node name="Main" type="Node2D"]
            script = ExtResource("1")

            [node name="Sprite" type="Sprite2D" parent="."]
            texture = ExtResource("2")
        """)

        tscn = parse_tscn_string(content)
        self.assertEqual(len(tscn.ext_resources), 1)
        self.assertEqual(tscn.ext_resources[0].type, "Script")
        self.assertEqual(tscn.ext_resources[0].id, "1")
        self.assertEqual(tscn.ext_resources[0].path, "res://main.gd")
        self.assertEqual(len(tscn.nodes), 2)
        self.assertEqual(tscn.nodes[0].name, "Main")
        self.assertEqual(tscn.nodes[0].node_type, "Node2D")
        self.assertIsNone(tscn.nodes[0].parent)
        self.assertEqual(tscn.nodes[1].name, "Sprite")
        self.assertEqual(tscn.nodes[1].parent, ".")
        self.assertEqual(tscn.nodes[1].node_type, "Sprite2D")

    def test_parse_connections(self):
        from gdworkflow.tscn_parser import parse_tscn_string

        content = textwrap.dedent("""\
            [gd_scene format=3 uid="uid://abc123"]

            [node name="Main" type="Node2D"]

            [node name="Button" type="Button" parent="."]

            [connection signal="pressed" from="Button" to="." method="_on_button_pressed"]
        """)

        tscn = parse_tscn_string(content)
        self.assertEqual(len(tscn.connections), 1)
        self.assertEqual(tscn.connections[0].signal, "pressed")
        self.assertEqual(tscn.connections[0].from_path, "Button")
        self.assertEqual(tscn.connections[0].to_path, ".")
        self.assertEqual(tscn.connections[0].method, "_on_button_pressed")

    def test_parse_sub_resources(self):
        from gdworkflow.tscn_parser import parse_tscn_string

        content = textwrap.dedent("""\
            [gd_scene format=3 uid="uid://abc123"]

            [sub_resource type="RectangleShape2D" id="RectShape"]
            size = Vector2(100, 50)

            [node name="Main" type="Node2D"]
        """)

        tscn = parse_tscn_string(content)
        self.assertEqual(len(tscn.sub_resources), 1)
        self.assertEqual(tscn.sub_resources[0].type, "RectangleShape2D")
        self.assertEqual(tscn.sub_resources[0].id, "RectShape")
        self.assertEqual(len(tscn.sub_resources[0].properties), 1)

    def test_round_trip(self):
        from gdworkflow.tscn_parser import parse_tscn_string

        content = textwrap.dedent("""\
            [gd_scene format=3 uid="uid://ctjpslkt3n5ge"]

            [ext_resource type="Script" uid="uid://bhbv2mi8gfa0k" path="res://scenes/main.gd" id="1"]

            [node name="Main" type="Node2D" unique_id=412537413]
            script = ExtResource("1")

            [node name="Sprite2D" type="Sprite2D" parent="." unique_id=1985002850]

            [node name="Camera2D" type="Camera2D" parent="Sprite2D" unique_id=72118897]
        """)

        tscn = parse_tscn_string(content)
        self.assertEqual(len(tscn.ext_resources), 1)
        self.assertEqual(len(tscn.nodes), 3)
        self.assertEqual(tscn.nodes[0].unique_id, 412537413)

        output = tscn.to_string()
        tscn2 = parse_tscn_string(output)
        self.assertEqual(len(tscn2.ext_resources), 1)
        self.assertEqual(len(tscn2.nodes), 3)
        self.assertEqual(tscn2.nodes[0].name, "Main")

    def test_generate_ext_resource_id(self):
        from gdworkflow.tscn_parser import parse_tscn_string

        content = textwrap.dedent("""\
            [gd_scene format=3 uid="uid://abc"]

            [ext_resource type="Script" uid="uid://s1" path="res://a.gd" id="1"]
            [ext_resource type="Texture2D" uid="uid://t1" path="res://b.png" id="2"]

            [node name="Main" type="Node2D"]
        """)

        tscn = parse_tscn_string(content)
        new_id = tscn.generate_ext_resource_id()
        self.assertEqual(int(new_id), 3)

    def test_add_connection(self):
        from gdworkflow.tscn_parser import parse_tscn_string

        content = textwrap.dedent("""\
            [gd_scene format=3 uid="uid://abc"]

            [node name="Main" type="Node2D"]
        """)

        tscn = parse_tscn_string(content)
        conn = tscn.add_connection("pressed", "Button", ".", "_on_pressed")
        self.assertEqual(conn.signal, "pressed")
        self.assertEqual(len(tscn.connections), 1)

        output = tscn.to_string()
        self.assertIn("[connection signal=\"pressed\" from=\"Button\" to=\".\" method=\"_on_pressed\"]", output)

    def test_add_node_instance(self):
        from gdworkflow.tscn_parser import parse_tscn_string

        content = textwrap.dedent("""\
            [gd_scene format=3 uid="uid://abc"]

            [node name="Main" type="Node2D"]
        """)

        tscn = parse_tscn_string(content)
        tscn.add_ext_resource("PackedScene", "", "res://scenes/features/feature.tscn", "3")
        node = tscn.add_node_instance("Feature", ".", "3")

        self.assertEqual(node.name, "Feature")
        self.assertEqual(node.parent, ".")
        self.assertIn("Feature", tscn.to_string())

    def test_write_and_read(self):
        from gdworkflow.tscn_parser import parse_tscn, TscnFile, ExtResource, NodeEntry

        tscn = TscnFile(
            header="[gd_scene format=3 uid=\"uid://abc\"]",
            ext_resources=[ExtResource(id="1", type="Script", uid="uid://s1", path="res://main.gd")],
            nodes=[NodeEntry(name="Main", node_type="Node2D")],
        )

        path = self.tmpdir_path / "test.tscn"
        tscn.write(path)

        tscn2 = parse_tscn(path)
        self.assertEqual(len(tscn2.ext_resources), 1)
        self.assertEqual(tscn2.ext_resources[0].path, "res://main.gd")
        self.assertEqual(len(tscn2.nodes), 1)
        self.assertEqual(tscn2.nodes[0].name, "Main")

    def test_update_load_steps(self):
        from gdworkflow.tscn_parser import update_load_steps

        header = "[gd_scene load_steps=3 format=3 uid=\"uid://abc\"]"
        updated = update_load_steps(header, delta=1)
        self.assertIn("load_steps=4", updated)
        self.assertNotIn("load_steps=3", updated)

    def test_parse_sandbox_main(self):
        from gdworkflow.tscn_parser import parse_tscn

        main_path = PROJECT_ROOT / "sandbox" / "scenes" / "main.tscn"
        if not main_path.exists():
            self.skipTest("sandbox/scenes/main.tscn not found")

        tscn = parse_tscn(main_path)
        self.assertIn("Main", [n.name for n in tscn.nodes])
        self.assertGreaterEqual(len(tscn.ext_resources), 1)


class TestMergerIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_integrate_scene_adds_instance(self):
        from gdworkflow.merger import integrate_scene

        parent_content = textwrap.dedent("""\
            [gd_scene format=3 uid="uid://parent"]

            [ext_resource type="Script" uid="uid://script1" path="res://main.gd" id="1"]

            [node name="Main" type="Node2D"]
            script = ExtResource("1")
        """)

        parent_path = self.tmpdir_path / "scenes" / "main.tscn"
        parent_path.parent.mkdir(parents=True, exist_ok=True)
        parent_path.write_text(parent_content)

        feature_path = Path("scenes/features/player_dash.tscn")

        result = integrate_scene(
            parent_path=parent_path,
            feature_path=feature_path,
            integration_hints={
                "node_type": "instance",
                "position": "as_child_of_root",
                "signals_to_connect": [],
                "autoload": False,
            },
        )

        self.assertTrue(result.success, f"Integration failed: {result.message}")

        updated = parent_path.read_text()
        self.assertIn("player_dash", updated)
        self.assertIn("PackedScene", updated)
        self.assertIn("res://scenes/features/player_dash.tscn", updated)

    def test_integrate_scene_with_signals(self):
        from gdworkflow.merger import integrate_scene

        parent_content = textwrap.dedent("""\
            [gd_scene format=3 uid="uid://parent"]

            [node name="Main" type="Node2D"]
        """)

        parent_path = self.tmpdir_path / "scenes" / "main.tscn"
        parent_path.parent.mkdir(parents=True, exist_ok=True)
        parent_path.write_text(parent_content)

        feature_path = Path("scenes/features/health_bar.tscn")

        result = integrate_scene(
            parent_path=parent_path,
            feature_path=feature_path,
            integration_hints={
                "node_type": "instance",
                "position": "as_child_of_root",
                "signals_to_connect": [
                    {"from": "health_bar", "signal": "health_changed", "to": ".", "method": "_on_health_changed"},
                ],
                "autoload": False,
            },
        )

        self.assertTrue(result.success)
        updated = parent_path.read_text()
        self.assertIn("health_changed", updated)
        self.assertIn("_on_health_changed", updated)
        self.assertIn("[connection", updated)

    def test_connect_signals(self):
        from gdworkflow.merger import connect_signals

        parent_content = textwrap.dedent("""\
            [gd_scene format=3 uid="uid://parent"]

            [node name="Main" type="Node2D"]
        """)

        parent_path = self.tmpdir_path / "scenes" / "main.tscn"
        parent_path.parent.mkdir(parents=True, exist_ok=True)
        parent_path.write_text(parent_content)

        signals = [
            {"from": "Player", "signal": "died", "to": "HUD", "method": "_on_player_died"},
        ]

        result = connect_signals(parent_path, signals)
        self.assertTrue(result.success)

        updated = parent_path.read_text()
        self.assertIn("[connection", updated)
        self.assertIn("signal=\"died\"", updated)
        self.assertIn("method=\"_on_player_died\"", updated)

    def test_register_autoload(self):
        from gdworkflow.merger import register_autoload

        project_content = textwrap.dedent("""\
            ; Engine configuration file.

            [application]
            config/name="TestProject"

            [display]
            window/size/viewport_width=800
        """)

        project_path = self.tmpdir_path / "project.godot"
        project_path.write_text(project_content)

        result = register_autoload(
            project_path, "GameManager", "res://scripts/game_manager.gd", singleton=True
        )

        self.assertTrue(result.success)
        updated = project_path.read_text()
        self.assertIn("[autoload]", updated)
        self.assertIn('GameManager="*res://scripts/game_manager.gd"', updated)
        self.assertIn("[application]", updated)

    def test_register_autoload_existing_section(self):
        from gdworkflow.merger import register_autoload

        project_content = textwrap.dedent("""\
            [application]
            config/name="TestProject"

            [autoload]
            Existing="*res://existing.gd"
        """)

        project_path = self.tmpdir_path / "project.godot"
        project_path.write_text(project_content)

        result = register_autoload(
            project_path, "GameManager", "res://scripts/game_manager.gd", singleton=True
        )

        self.assertTrue(result.success)
        updated = project_path.read_text()
        self.assertIn('GameManager="*res://scripts/game_manager.gd"', updated)
        self.assertIn('Existing="*res://existing.gd"', updated)

    def test_register_autoload_update_existing(self):
        from gdworkflow.merger import register_autoload

        project_content = textwrap.dedent("""\
            [autoload]
            GameManager="*res://old_path.gd"
        """)

        project_path = self.tmpdir_path / "project.godot"
        project_path.write_text(project_content)

        result = register_autoload(
            project_path, "GameManager", "res://scripts/game_manager.gd", singleton=True
        )

        self.assertTrue(result.success)
        updated = project_path.read_text()
        self.assertIn('GameManager="*res://scripts/game_manager.gd"', updated)
        self.assertNotIn('old_path.gd', updated)

    def test_register_autoload_non_singleton(self):
        from gdworkflow.merger import register_autoload

        project_content = "[application]\nconfig/name=\"Test\"\n"

        project_path = self.tmpdir_path / "project.godot"
        project_path.write_text(project_content)

        result = register_autoload(
            project_path, "Helper", "res://scripts/helper.gd", singleton=False
        )

        self.assertTrue(result.success)
        updated = project_path.read_text()
        self.assertIn('[autoload]', updated)
        self.assertIn('Helper="res://scripts/helper.gd"', updated)
        self.assertNotIn('*res://scripts/helper.gd', updated)


class TestOrchestratorState(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_write_and_read_state(self):
        from gdworkflow.merger import write_orchestrator_state, read_orchestrator_state

        state = {
            "status": "running",
            "current_batch": 1,
            "total_batches": 3,
            "tasks": {"feat-x": {"status": "running"}},
        }
        write_orchestrator_state(state, self.tmpdir_path)
        loaded = read_orchestrator_state(self.tmpdir_path)
        self.assertEqual(loaded["status"], "running")
        self.assertEqual(loaded["current_batch"], 1)
        self.assertEqual(loaded["tasks"]["feat-x"]["status"], "running")

    def test_read_missing_state(self):
        from gdworkflow.merger import read_orchestrator_state

        state = read_orchestrator_state(self.tmpdir_path)
        self.assertEqual(state["status"], "unknown")

    def test_cancel_signals(self):
        from gdworkflow.merger import (
            write_cancel_signal, check_cancel_signal, clear_cancel_signal,
            write_cancel_run_signal, check_cancel_run_signal, clear_cancel_run_signal,
        )

        self.assertFalse(check_cancel_signal("feat-test", self.tmpdir_path))
        write_cancel_signal("feat-test", self.tmpdir_path)
        self.assertTrue(check_cancel_signal("feat-test", self.tmpdir_path))
        clear_cancel_signal("feat-test", self.tmpdir_path)
        self.assertFalse(check_cancel_signal("feat-test", self.tmpdir_path))

        self.assertFalse(check_cancel_run_signal(self.tmpdir_path))
        write_cancel_run_signal(self.tmpdir_path)
        self.assertTrue(check_cancel_run_signal(self.tmpdir_path))
        clear_cancel_run_signal(self.tmpdir_path)
        self.assertFalse(check_cancel_run_signal(self.tmpdir_path))


class TestOrchestratorCLIFlags(unittest.TestCase):
    def test_merge_flag_exists(self):
        import subprocess
        import sys

        env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
        result = subprocess.run(
            [sys.executable, "-m", "gdworkflow.orchestrate", "--help"],
            capture_output=True, text=True, env=env,
        )
        self.assertIn("--merge", result.stdout)
        self.assertIn("--skip-tests", result.stdout)
        self.assertIn("--export-release", result.stdout)
        self.assertIn("--milestone-tag", result.stdout)

    def test_dry_run_still_works(self):
        import subprocess
        import sys

        env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
        result = subprocess.run(
            [sys.executable, "-m", "gdworkflow.orchestrate", "nonexistent.md", "--dry-run"],
            capture_output=True, text=True, env=env,
        )
        self.assertNotEqual(result.returncode, 0)


class TestBotSlashCommands(unittest.TestCase):
    def test_bot_has_status_cancel_commands(self):
        from gdworkflow.bot.main import Config, DiscordBot, create_bot, create_http_app

        cfg = Config(bot_token="test-token", guild_id=12345, http_port=9999)
        bot = create_bot(cfg)
        app = create_http_app(bot, cfg)
        paths = [r.resource.canonical for r in app.router.routes()]
        self.assertIn("/orchestrator_status", paths)
        self.assertIn("/cancel_feature", paths)
        self.assertIn("/cancel_run", paths)

    def test_cancel_signal_file_creation(self):
        from gdworkflow.merger import write_cancel_signal, check_cancel_signal, clear_cancel_signal

        tmpdir = tempfile.TemporaryDirectory()
        try:
            tmpdir_path = Path(tmpdir.name)
            self.assertFalse(check_cancel_signal("feat-abc", tmpdir_path))
            write_cancel_signal("feat-abc", tmpdir_path)
            self.assertTrue(check_cancel_signal("feat-abc", tmpdir_path))
            clear_cancel_signal("feat-abc", tmpdir_path)
            self.assertFalse(check_cancel_signal("feat-abc", tmpdir_path))
        finally:
            tmpdir.cleanup()


class TestMilestoneFunctions(unittest.TestCase):
    def test_announce_milestone_no_discord(self):
        from gdworkflow.merger import announce_milestone

        result = announce_milestone(
            bot_url="http://localhost:8080",
            tag="milestone-test",
            merged_features=[],
            no_discord=True,
        )
        self.assertTrue(result, "announce_milestone with no_discord should return True")

    def test_create_milestone_tag_in_repo(self):
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            self.skipTest("Not in a git repo")

        from gdworkflow.merger import create_milestone_tag
        from gdworkflow.orchestrate import get_git_root

        git_root = get_git_root()
        tag = create_milestone_tag(git_root)

        if tag:
            self.assertTrue(tag.startswith("milestone-"))
            subprocess.run(["git", "tag", "-d", tag], capture_output=True, cwd=str(git_root))


if __name__ == "__main__":
    unittest.main()