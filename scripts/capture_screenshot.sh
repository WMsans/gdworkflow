#!/usr/bin/env bash
# capture_screenshot.sh — Run Godot to capture a screenshot of a scene.
#
# IMPORTANT: Screenshots require an active renderer, so this script does NOT use
# --headless. On headless CI, use xvfb-run or similar to provide a virtual display.
# Config is passed via a JSON file (res://screenshots/.capture_config.json) because
# Godot's command-line arg forwarding for SceneTree scripts is unreliable.
#
# Usage:
#   ./scripts/capture_screenshot.sh --scene <scene_path> [--output <path>] [--frames <N>] [--project-dir <path>] [--godot-bin <path>]
#
# Required:
#   --scene         Path to the .tscn scene file (res:// path), e.g. res://scenes/main.tscn
#
# Optional:
#   --output        Output PNG path (default: screenshots/<scene_name>.png, relative to project dir)
#   --frames        Number of frames to simulate before capture (default: 10)
#   --project-dir   Godot project directory (default: .)
#   --godot-bin     Path to Godot binary (default: $GODOT_BIN or "godot")

set -euo pipefail

SCENE_PATH=""
OUTPUT_PATH=""
FRAMES=10
PROJECT_DIR="."
GODOT_BIN="${GODOT_BIN:-godot}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scene)
            SCENE_PATH="$2"
            shift 2
            ;;
        --output)
            OUTPUT_PATH="$2"
            shift 2
            ;;
        --frames)
            FRAMES="$2"
            shift 2
            ;;
        --project-dir)
            PROJECT_DIR="$2"
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

if [[ -z "$SCENE_PATH" ]]; then
    echo "ERROR: --scene is required" >&2
    echo "Usage: $0 --scene res://scenes/main.tscn [--output screenshot.png] [--frames 10] [--project-dir .]" >&2
    exit 2
fi

if ! command -v "$GODOT_BIN" &>/dev/null; then
    echo "ERROR: Godot binary not found: $GODOT_BIN" >&2
    exit 2
fi

SCENE_BASENAME=$(basename "$SCENE_PATH" .tscn)
if [[ -z "$OUTPUT_PATH" ]]; then
    OUTPUT_PATH="screenshots/${SCENE_BASENAME}.png"
fi

SCRIPT_PATH="res://scripts/capture_scene.gd"
CONFIG_PATH="${PROJECT_DIR}/screenshots/.capture_config.json"

# Ensure the capture script is in the project (always copy to pick up updates)
mkdir -p "${PROJECT_DIR}/scripts"
SCRIPT_SRC="$(cd "$(dirname "$0")" && pwd)/capture_scene.gd"
if [[ -f "$SCRIPT_SRC" ]]; then
	cp "$SCRIPT_SRC" "${PROJECT_DIR}/scripts/capture_scene.gd"
else
	echo "ERROR: capture_scene.gd not found" >&2
	exit 2
fi

mkdir -p "${PROJECT_DIR}/screenshots"

# Write config as a res:// path so GDScript can resolve it via ProjectSettings
RES_OUTPUT="res://screenshots/${SCENE_BASENAME}.png"

cat > "$CONFIG_PATH" <<EOF
{
    "scene_path": "${SCENE_PATH}",
    "output_path": "${RES_OUTPUT}",
    "frames": ${FRAMES}
}
EOF

echo "Capturing screenshot..."
echo "  Scene:      ${SCENE_PATH}"
echo "  Output:     ${OUTPUT_PATH}"
echo "  Frames:     ${FRAMES}"
echo "  Project:    ${PROJECT_DIR}"

"$GODOT_BIN" --path "${PROJECT_DIR}" \
    -s "${SCRIPT_PATH}" \
    2>&1 || true

# Clean up config file
rm -f "$CONFIG_PATH"

ABS_OUTPUT="${PROJECT_DIR}/screenshots/${SCENE_BASENAME}.png"

if [[ -f "$ABS_OUTPUT" ]]; then
    # Move to the requested output path if different from default
    if [[ "$OUTPUT_PATH" != "screenshots/${SCENE_BASENAME}.png" ]]; then
        mkdir -p "$(dirname "${PROJECT_DIR}/${OUTPUT_PATH}")" 2>/dev/null || true
        mv "$ABS_OUTPUT" "${PROJECT_DIR}/${OUTPUT_PATH}"
        echo "Screenshot saved to ${PROJECT_DIR}/${OUTPUT_PATH}"
    else
        echo "Screenshot saved to ${ABS_OUTPUT}"
    fi
    exit 0
else
    echo "WARNING: Screenshot file not found at ${ABS_OUTPUT}" >&2
    echo "The scene may not have rendered correctly." >&2
    echo "On headless CI, run with xvfb-run or similar virtual display." >&2
    exit 1
fi