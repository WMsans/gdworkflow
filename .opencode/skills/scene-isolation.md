# Scene Isolation

You MUST follow this rule at all times during task execution.

## Core Rule: New Scene, Never Modify Existing Scenes

**Never modify an existing scene file that you did not create.**

This means:
- Create your feature as a NEW `.tscn` file under `scenes/features/`
- Do NOT edit `scenes/main.tscn`, any other feature scene, or any shared scene
- Your scene should be self-contained and standalone
- The integration step (instancing your scene into the parent) will be handled separately by a merger agent

## Why This Matters

Multiple agents work in parallel. If two agents modify the same parent scene, their changes will conflict. By keeping each feature in its own isolated scene, we avoid merge conflicts entirely.

## What You CAN Do

- Create new `.tscn` files in `scenes/features/`
- Create new `.gd` script files
- Create new resources (`.tres`, etc.) that are owned by your feature
- Reference existing scenes by instancing them AS-IS (without modification)
- Read any file in the project for understanding

## What You CANNOT Do

- Edit `scenes/main.tscn`
- Edit any `.tscn` file that is not in your feature's `scenes/features/` directory
- Edit `project.godot` (unless your feature requires an autoload, in which case note it in `integration_hints`)
- Edit any shared scripts that other features might depend on

## If In Doubt

If you think you need to modify an existing file, ask a clarifying question via the `clarify-via-discord` skill instead of making the change.