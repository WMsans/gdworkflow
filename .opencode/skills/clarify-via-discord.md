# Clarify via Discord

Use this skill when you need to ask the human developer a clarifying question during task execution.

## When to use

- You are unsure about a design decision that affects the feature's behavior
- You need clarification on requirements that are ambiguous in the task description
- You need additional context about the game design that isn't provided in the TODO

## When NOT to use

- You can make a reasonable default decision (prefer doing so and noting it in a comment)
- The question is about tool usage or Godot engine mechanics (look it up instead)
- The answer can be inferred from the GDD or existing code

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

## Timeout behavior

Questions time out after 5 minutes by default. If your question times out:
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