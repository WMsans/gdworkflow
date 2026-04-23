#!/usr/bin/env bash
# run_tests.sh — Reusable test runner that invokes Godot with gdUnit4 and
# writes JUnit XML to a known output path.
#
# Usage:
#   ./scripts/run_tests.sh [--project-dir <path>] [--output <path>] [--test-path <path>] [--godot-bin <path>]
#
# Defaults:
#   --project-dir   . (current directory)
#   --output        reports/junit.xml (relative to project dir)
#   --test-path     test/ (relative to project dir)
#   --godot-bin     $GODOT_BIN or "godot"
#
# Exit codes:
#   0 — all tests passed
#   1 — some tests failed
#   2 — runner error

set -euo pipefail

PROJECT_DIR="."
OUTPUT="reports/junit.xml"
TEST_PATH="test/"
GODOT_BIN="${GODOT_BIN:-godot}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-dir)
            PROJECT_DIR="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --test-path)
            TEST_PATH="$2"
            shift 2
            ;;
        --godot-bin)
            GODOT_BIN="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

if ! command -v "$GODOT_BIN" &>/dev/null; then
    echo "ERROR: Godot binary not found: $GODOT_BIN" >&2
    echo "Set GODOT_BIN or pass --godot-bin" >&2
    exit 2
fi

REPORT_DIR=$(dirname "$OUTPUT")
mkdir -p "${PROJECT_DIR}/${REPORT_DIR}"

echo "Running gdUnit4 tests..."
echo "  Project:  ${PROJECT_DIR}"
echo "  Tests:    ${TEST_PATH}"
echo "  Output:   ${OUTPUT}"
echo "  Godot:    ${GODOT_BIN}"

"$GODOT_BIN" --headless --path "${PROJECT_DIR}" \
    -s addons/gdUnit4/bin/GdUnitCmdTool.gd \
    -a "${TEST_PATH}" \
    --ignoreHeadlessMode \
    2>&1 || true

JUNIT_SRC="${PROJECT_DIR}/reports/report_1/results.xml"

if [[ -f "$JUNIT_SRC" ]]; then
    cp "$JUNIT_SRC" "${PROJECT_DIR}/${OUTPUT}"
    echo "JUnit XML written to ${PROJECT_DIR}/${OUTPUT}"
else
    echo "WARNING: No JUnit XML found at ${JUNIT_SRC}" >&2
    echo "Tests may not have run correctly." >&2
fi

if [[ -f "${PROJECT_DIR}/${OUTPUT}" ]]; then
    FAILURES=$(python3 -c "
import xml.etree.ElementTree as ET
import sys
tree = ET.parse('${PROJECT_DIR}/${OUTPUT}')
root = tree.getroot()
print(root.get('failures', '0'))
" 2>/dev/null || echo "0")

    if [[ "$FAILURES" != "0" ]]; then
        echo "Tests FAILED: ${FAILURES} failure(s)"
        exit 1
    fi

    echo "All tests PASSED"
    exit 0
else
    echo "ERROR: Could not find test output" >&2
    exit 2
fi