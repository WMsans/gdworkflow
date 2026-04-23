#!/usr/bin/env bash
# clarify-via-discord.sh — Post a clarifying question to Discord and wait for an answer.
#
# Usage: bash .opencode/skills/clarify-via-discord.sh <agent_id> <feature_name> <question>
#
# Environment variables:
#   DISCORD_BOT_URL — URL of the Discord bot HTTP server (default: http://localhost:8080)
#   QUESTION_TIMEOUT — Seconds to wait for an answer (default: 300)

set -euo pipefail

AGENT_ID="${1:?Usage: clarify-via-discord.sh <agent_id> <feature_name> <question>}"
FEATURE="${2:?Missing feature_name}"
QUESTION="${3:?Missing question}"

BOT_URL="${DISCORD_BOT_URL:-http://localhost:8080}"
TIMEOUT="${QUESTION_TIMEOUT:-300}"

RESPONSE=$(curl -s -X POST \
  "${BOT_URL}/post_question" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"${AGENT_ID}\", \"feature\": \"${FEATURE}\", \"question\": \"${QUESTION}\", \"timeout\": ${TIMEOUT}}")

echo "$RESPONSE"

# Check status
STATUS=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")

if [ "$STATUS" = "paused" ]; then
  echo "WARNING: Question timed out. Checkpoint and exit." >&2
  exit 1
fi

if [ "$STATUS" = "answered" ]; then
  ANSWER=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('answer', ''))" 2>/dev/null)
  echo "Answer: $ANSWER"
  exit 0
fi

echo "ERROR: Unexpected response status: $STATUS" >&2
exit 1