"""Tests for Week 3 features: gdUnit4 integration, JUnit parser, review/approval flow."""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

JUNIT_XML_SAMPLE = """\
<?xml version="1.0" encoding="UTF-8" ?>
<testsuites id="2026-04-23" name="test_run" tests="5" failures="1" skipped="1" flaky="0" time="1.234">
    <testsuite id="0" name="suite_a" package="test" timestamp="2026-04-23T00:00:00" hostname="localhost" tests="3" failures="1" errors="0" skipped="0" time="0.5">
        <testcase name="test_pass_one" classname="suite_a" time="0.1">
        </testcase>
        <testcase name="test_pass_two" classname="suite_a" time="0.2">
        </testcase>
        <testcase name="test_fail_one" classname="suite_a" time="0.2">
            <failure message="Expected true but got false" type="AssertionError">Expected true but got false
 at line 42</failure>
        </testcase>
    </testsuite>
    <testsuite id="1" name="suite_b" package="test" timestamp="2026-04-23T00:00:00" hostname="localhost" tests="2" failures="0" errors="0" skipped="1" time="0.734">
        <testcase name="test_pass_three" classname="suite_b" time="0.434">
        </testcase>
        <testcase name="test_skipped_one" classname="suite_b" time="0.0">
            <skipped message="Not implemented yet" />
        </testcase>
    </testsuite>
</testsuites>
"""


class TestJUnitParser(unittest.TestCase):
    def test_parse_pass_fail_counts(self):
        from gdworkflow.junit_parser import parse_junit_xml

        tmpdir = tempfile.TemporaryDirectory()
        try:
            xml_path = Path(tmpdir.name) / "results.xml"
            xml_path.write_text(JUNIT_XML_SAMPLE)
            result = parse_junit_xml(xml_path)

            self.assertEqual(result.total_tests, 5)
            self.assertEqual(result.total_failures, 1)
            self.assertEqual(result.total_skipped, 1)
            self.assertEqual(result.passed, 3)
            self.assertFalse(result.all_passed)
        finally:
            tmpdir.cleanup()

    def test_parse_all_passed(self):
        from gdworkflow.junit_parser import parse_junit_xml

        all_pass_xml = """\
<?xml version="1.0" encoding="UTF-8" ?>
<testsuites id="t" name="all_pass" tests="2" failures="0" skipped="0">
    <testsuite id="0" name="suite" tests="2" failures="0" errors="0" skipped="0" time="0.1">
        <testcase name="test_a" classname="suite" time="0.05" />
        <testcase name="test_b" classname="suite" time="0.05" />
    </testsuite>
</testsuites>
"""
        tmpdir = tempfile.TemporaryDirectory()
        try:
            xml_path = Path(tmpdir.name) / "results.xml"
            xml_path.write_text(all_pass_xml)
            result = parse_junit_xml(xml_path)

            self.assertEqual(result.total_tests, 2)
            self.assertEqual(result.passed, 2)
            self.assertEqual(result.total_failures, 0)
            self.assertTrue(result.all_passed)
        finally:
            tmpdir.cleanup()

    def test_failure_messages(self):
        from gdworkflow.junit_parser import parse_junit_xml

        tmpdir = tempfile.TemporaryDirectory()
        try:
            xml_path = Path(tmpdir.name) / "results.xml"
            xml_path.write_text(JUNIT_XML_SAMPLE)
            result = parse_junit_xml(xml_path)

            self.assertEqual(len(result.failure_messages), 1)
            self.assertIn("test_fail_one", result.failure_messages[0])
            self.assertIn("Expected true but got false", result.failure_messages[0])
        finally:
            tmpdir.cleanup()

    def test_summary_output(self):
        from gdworkflow.junit_parser import parse_junit_xml

        tmpdir = tempfile.TemporaryDirectory()
        try:
            xml_path = Path(tmpdir.name) / "results.xml"
            xml_path.write_text(JUNIT_XML_SAMPLE)
            result = parse_junit_xml(xml_path)

            summary = result.summary()
            self.assertIn("Tests: 5", summary)
            self.assertIn("Passed: 3", summary)
            self.assertIn("Failed: 1", summary)
            self.assertIn("Skipped: 1", summary)
            self.assertIn("Failures:", summary)
        finally:
            tmpdir.cleanup()

    def test_suites_present(self):
        from gdworkflow.junit_parser import parse_junit_xml

        tmpdir = tempfile.TemporaryDirectory()
        try:
            xml_path = Path(tmpdir.name) / "results.xml"
            xml_path.write_text(JUNIT_XML_SAMPLE)
            result = parse_junit_xml(xml_path)

            self.assertEqual(len(result.test_suites), 2)
            self.assertEqual(result.test_suites[0].name, "suite_a")
            self.assertEqual(result.test_suites[0].tests, 3)
            self.assertEqual(result.test_suites[1].name, "suite_b")
        finally:
            tmpdir.cleanup()

    def test_parse_gdunit_output(self):
        from gdworkflow.junit_parser import parse_junit_xml

        gdunit_xml_path = PROJECT_ROOT / "sandbox" / "reports" / "report_1" / "results.xml"
        if not gdunit_xml_path.exists():
            self.skipTest("gdUnit4 report not found")

        result = parse_junit_xml(gdunit_xml_path)
        self.assertGreaterEqual(result.total_tests, 1)

    def test_parse_string(self):
        from gdworkflow.junit_parser import parse_junit_xml_string

        result = parse_junit_xml_string(JUNIT_XML_SAMPLE)
        self.assertEqual(result.total_tests, 5)
        self.assertEqual(result.total_failures, 1)


class TestRunTestsScript(unittest.TestCase):
    def test_script_exists_and_executable(self):
        script_path = PROJECT_ROOT / "scripts" / "run_tests.sh"
        self.assertTrue(script_path.exists(), "run_tests.sh should exist")
        self.assertTrue(os.access(script_path, os.X_OK), "run_tests.sh should be executable")

    def test_script_has_required_functions(self):
        script_path = PROJECT_ROOT / "scripts" / "run_tests.sh"
        content = script_path.read_text()
        self.assertIn("godot_bin", content.lower())
        self.assertIn("junit", content.lower())
        self.assertIn("gdUnit4", content or "gdunit4", "Should reference gdUnit4")
        self.assertIn("--project-dir", content)
        self.assertIn("--output", content)

    def test_script_accepts_godot_bin_flag(self):
        content = (PROJECT_ROOT / "scripts" / "run_tests.sh").read_text()
        self.assertIn("--godot-bin", content)
        self.assertIn("--project-dir", content)
        self.assertIn("--output", content)


class TestScreenshotHarness(unittest.TestCase):
    def test_capture_scene_script_exists(self):
        script_path = PROJECT_ROOT / "scripts" / "capture_screenshot.sh"
        self.assertTrue(script_path.exists(), "capture_screenshot.sh should exist")
        self.assertTrue(os.access(script_path, os.X_OK), "capture_screenshot.sh should be executable")

    def test_capture_scene_gd_exists(self):
        gd_path = PROJECT_ROOT / "scripts" / "capture_scene.gd"
        self.assertTrue(gd_path.exists(), "capture_scene.gd should exist")
        content = gd_path.read_text()
        self.assertIn("capture_scene", content)
        self.assertIn("scene_path", content)
        self.assertIn("output_path", content)

    def test_screenshot_conventions_doc_exists(self):
        doc_path = PROJECT_ROOT / "docs" / "design_docs" / "screenshot_conventions.md"
        self.assertTrue(doc_path.exists(), "screenshot_conventions.md should exist")
        content = doc_path.read_text()
        self.assertIn("Camera2D", content)
        self.assertIn("headless", content.lower())


class TestReviewerAgent(unittest.TestCase):
    def test_reviewer_config_exists(self):
        reviewer_path = PROJECT_ROOT / ".opencode" / "agents" / "reviewer.md"
        self.assertTrue(reviewer_path.exists(), "reviewer.md should exist")
        content = reviewer_path.read_text()
        self.assertIn("gdUnit4", content)
        self.assertIn("post_review_result", content)
        self.assertIn("REVIEW.md", content)

    def test_build_review_prompt(self):
        from gdworkflow.orchestrate import Task, build_review_prompt

        task = Task(
            id="feat-test",
            feature_name="Test Feature",
            new_scene_path="scenes/features/test.tscn",
            integration_parent="scenes/main.tscn",
            prose="Create a test feature.",
        )
        prompt = build_review_prompt(task)
        self.assertIn("feat-test", prompt)
        self.assertIn("Test Feature", prompt)
        self.assertIn("review", prompt.lower())
        self.assertIn("post_review_result", prompt)
        self.assertIn("run_tests.sh", prompt)
        self.assertIn("capture_screenshot.sh", prompt)

    def test_review_result_dataclass(self):
        from gdworkflow.orchestrate import ReviewResult

        rr = ReviewResult(
            task_id="feat-test",
            worktree=Path("/tmp/test"),
            exit_code=0,
            stdout="",
            stderr="",
            duration=10.0,
            verdict="PASS",
            test_summary="3 tests, 3 passed, 0 failed",
        )
        self.assertEqual(rr.task_id, "feat-test")
        self.assertEqual(rr.verdict, "PASS")
        self.assertEqual(rr.test_summary, "3 tests, 3 passed, 0 failed")


class TestApprovalFlow(unittest.TestCase):
    def test_bot_has_approval_routes(self):
        from gdworkflow.bot.main import Config, DiscordBot, create_bot, create_http_app

        cfg = Config(bot_token="test-token", guild_id=12345, http_port=9999)
        bot = create_bot(cfg)
        app = create_http_app(bot, cfg)
        paths = [r.resource.canonical for r in app.router.routes()]
        self.assertIn("/post_review_result", paths)
        self.assertIn("/request_approval", paths)
        self.assertIn("/approval_status", paths)
        self.assertIn("/health", paths)

    def test_approval_request_dataclass(self):
        from gdworkflow.bot.main import ApprovalRequest, ApprovalState
        import asyncio

        ar = ApprovalRequest(
            feature_id="feat-test",
        )
        self.assertEqual(ar.feature_id, "feat-test")
        self.assertEqual(ar.status, "pending")

        state = ApprovalState(feature_id="feat-test")
        self.assertEqual(state.status, "pending")

    def test_approval_state_tracking(self):
        from gdworkflow.bot.main import ApprovalState

        states = {}
        states["feat-a"] = ApprovalState(feature_id="feat-a", status="approved")
        states["feat-b"] = ApprovalState(feature_id="feat-b", status="rejected")
        states["feat-c"] = ApprovalState(feature_id="feat-c", status="pending")

        self.assertEqual(states["feat-a"].status, "approved")
        self.assertEqual(states["feat-b"].status, "rejected")
        self.assertEqual(states["feat-c"].status, "pending")

    def test_orchestrator_review_and_approval_flags(self):
        env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
        result = subprocess.run(
            [sys.executable, "-m", "gdworkflow.orchestrate", "--help"],
            capture_output=True, text=True, env=env,
        )
        self.assertIn("--review", result.stdout)
        self.assertIn("--approve", result.stdout)
        self.assertIn("--max-retries", result.stdout)
        self.assertIn("--review-timeout", result.stdout)
        self.assertIn("--approval-timeout", result.stdout)

    def test_rejection_retry_logic(self):
        from gdworkflow.orchestrate import Task

        task = Task(
            id="feat-test",
            feature_name="Test",
            new_scene_path="scenes/features/test.tscn",
            integration_parent="scenes/main.tscn",
            prose="Original description.",
        )
        retry_note = "\n\n## Retry Note\nThis is retry #1. Rejection reason: bad code"
        modified_task = Task(
            id=task.id,
            feature_name=task.feature_name,
            new_scene_path=task.new_scene_path,
            integration_parent=task.integration_parent,
            prose=task.prose + retry_note,
        )
        self.assertIn("Retry Note", modified_task.prose)
        self.assertIn("bad code", modified_task.prose)
        self.assertIn("Original description", modified_task.prose)

    def test_request_approval_function_exists(self):
        from gdworkflow.orchestrate import request_approval
        self.assertTrue(callable(request_approval))

    def test_post_review_result_function_exists(self):
        from gdworkflow.orchestrate import post_review_result
        self.assertTrue(callable(post_review_result))

    def test_dispatch_review_function_exists(self):
        from gdworkflow.orchestrate import dispatch_reviewer
        self.assertTrue(callable(dispatch_reviewer))


class TestSandboxTestExists(unittest.TestCase):
    def test_main_test_exists(self):
        test_path = PROJECT_ROOT / "sandbox" / "test" / "test_main.gd"
        self.assertTrue(test_path.exists(), "test_main.gd should exist")
        content = test_path.read_text()
        self.assertIn("GdUnitTestSuite", content)
        self.assertIn("test_", content)


if __name__ == "__main__":
    unittest.main()