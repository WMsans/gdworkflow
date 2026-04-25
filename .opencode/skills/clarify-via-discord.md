# Clarify via Discord

Use this skill to ask the human developer a clarifying question during task execution. Ask early and often — a wrong assumption wastes far more time than a question.

## When to use

**Ask a question whenever:**

- You are unsure about a design decision that affects the feature's behavior
- You need clarification on requirements that are ambiguous in the task description
- You need additional context about the game design that isn't provided in the TODO
- The task description contains question marks or unresolved choices
- You need to decide between two or more reasonable approaches
- A signal, method, or node name is ambiguous
- The task references something that does not exist yet (e.g., a node, a script, a signal)
- You are unsure what format, type, or value to use
- Anything is unclear — err on the side of asking rather than guessing

## How to use

1. Formulate your question clearly and concisely
2. Run the clarifying question script:

```bash
bash .opencode/skills/clarify-via-discord.sh "<agent_id>" "<feature_name>" "<your question>"
```

Where:
- `<agent_id>` is your task ID (e.g., `feat-player-dash`)
- `<feature_name>` is the human-readable feature name
- `<your question>` is the question you need answered

3. The script will POST to the Discord bot and block until an answer arrives.
4. Check the output:
   - If `"status": "answered"`, the `answer` field contains the developer's response.
   - If `"status": "paused"`, the question timed out. You must checkpoint your work, commit changes so far, create a `DONE` marker file, and exit cleanly. The orchestrator will handle re-dispatch.

## How to ask well

- **One question at a time** — ask, wait for the answer, then ask the next if needed
- **Prefer multiple choice** when possible — e.g., "Should the label show 'Score: 0' or just '0'?"
- **Be specific** — e.g., "Should coins respawn after being collected, or are they one-time pickups?" not "How should coins work?"
- **Include context** — briefly mention what you're deciding between and why

## Timeout behavior

Questions time out after 15 minutes by default. If your question times out:
1. Commit all current work with a descriptive message
2. Create a `DONE` marker file in the worktree root
3. Exit cleanly — do not continue with assumptions

The orchestrator may re-dispatch you with the answer appended to your task description.

## Example

```bash
ANSWER=$(bash .opencode/skills/clarify-via-discord.sh "feat-coins" "Collectible Coins" "Should coins respawn after being collected, or are they one-time pickups?")
echo "$ANSWER"
# {"status": "answered", "question_id": "a1b2c3d4", "answer": "One-time pickups, no respawn."}
```
