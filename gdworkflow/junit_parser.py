"""JUnit XML parser for gdUnit4 test results.

Extracts pass/fail counts, failure messages, and suite-level summaries
from the JUnit XML files produced by gdUnit4's command-line runner.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestCaseResult:
    name: str
    classname: str
    time: float = 0.0
    status: str = "passed"
    failure_message: str = ""
    failure_type: str = ""
    failure_text: str = ""


@dataclass
class TestSuiteResult:
    name: str
    package: str = ""
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    time: float = 0.0
    cases: list[TestCaseResult] = field(default_factory=list)


@dataclass
class TestRunResult:
    test_suites: list[TestSuiteResult] = field(default_factory=list)

    @property
    def total_tests(self) -> int:
        return sum(s.tests for s in self.test_suites)

    @property
    def total_failures(self) -> int:
        return sum(s.failures for s in self.test_suites)

    @property
    def total_errors(self) -> int:
        return sum(s.errors for s in self.test_suites)

    @property
    def total_skipped(self) -> int:
        return sum(s.skipped for s in self.test_suites)

    @property
    def passed(self) -> int:
        return self.total_tests - self.total_failures - self.total_errors - self.total_skipped

    @property
    def all_passed(self) -> bool:
        return self.total_failures == 0 and self.total_errors == 0

    @property
    def failure_messages(self) -> list[str]:
        messages = []
        for suite in self.test_suites:
            for case in suite.cases:
                if case.status == "failed" and case.failure_message:
                    messages.append(f"[{suite.name}.{case.name}] {case.failure_message}")
        return messages

    def summary(self) -> str:
        lines = [
            f"Tests: {self.total_tests}",
            f"Passed: {self.passed}",
            f"Failed: {self.total_failures}",
            f"Errors: {self.total_errors}",
            f"Skipped: {self.total_skipped}",
        ]
        if self.failure_messages:
            lines.append("")
            lines.append("Failures:")
            for msg in self.failure_messages:
                lines.append(f"  - {msg}")
        return "\n".join(lines)


def parse_junit_xml(path: Path) -> TestRunResult:
    tree = ET.parse(str(path))
    root = tree.getroot()
    result = TestRunResult()

    for suite_elem in root.iter("testsuite"):
        suite = TestSuiteResult(
            name=suite_elem.get("name", ""),
            package=suite_elem.get("package", ""),
            tests=int(suite_elem.get("tests", "0")),
            failures=int(suite_elem.get("failures", "0")),
            errors=int(suite_elem.get("errors", "0")),
            skipped=int(suite_elem.get("skipped", "0")),
            time=float(suite_elem.get("time", "0")),
        )

        for case_elem in suite_elem.iter("testcase"):
            case = TestCaseResult(
                name=case_elem.get("name", ""),
                classname=case_elem.get("classname", ""),
                time=float(case_elem.get("time", "0")),
            )

            failure_elem = case_elem.find("failure")
            error_elem = case_elem.find("error")
            skipped_elem = case_elem.find("skipped")

            if failure_elem is not None:
                case.status = "failed"
                case.failure_message = failure_elem.get("message", "")
                case.failure_type = failure_elem.get("type", "")
                case.failure_text = failure_elem.text or ""
            elif error_elem is not None:
                case.status = "error"
                case.failure_message = error_elem.get("message", "")
                case.failure_type = error_elem.get("type", "")
                case.failure_text = error_elem.text or ""
            elif skipped_elem is not None:
                case.status = "skipped"
            else:
                case.status = "passed"

            suite.cases.append(case)

        result.test_suites.append(suite)

    return result


def parse_junit_xml_string(content: str) -> TestRunResult:
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(content)
        f.flush()
        result = parse_junit_xml(Path(f.name))
    Path(f.name).unlink(missing_ok=True)
    return result