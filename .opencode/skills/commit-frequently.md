# Commit Frequently

You MUST commit your changes frequently throughout your work session. This is a hard rule, not a suggestion.

## When to Commit

Commit after each of these milestones:
- After writing your plan summary (within 5 minutes of starting)
- After creating a new scene file
- After implementing a core behavior (e.g., movement, collision, UI update)
- After adding signals or exports
- After writing tests
- After fixing a bug
- After any change that compiles and runs without errors

## Commit Message Format

Use descriptive messages that explain what and why:
- `feat: add player movement with keyboard input`
- `fix: correct jump velocity calculation`
- `test: add gdUnit4 tests for coin pickup`
- `refactor: extract health bar into reusable component`

## How to Commit

```bash
git add -A
git commit -m "<type>: <description>"
```

Do NOT use generic messages like "wip" or "changes". Each commit should be a logical unit of work.

## What NOT to Do

- Do NOT wait until the end to commit everything at once
- Do NOT commit broken code (verify it loads in Godot first)
- Do NOT commit the `DONE` marker until you are truly finished