# GDScript Conventions

Use this skill when writing GDScript code for a Godot 4.x project.

## Naming

- Use `snake_case` for variables, functions, and file names
- Use `PascalCase` for class names and node names
- Constants are `UPPER_SNAKE_CASE`
- Signal names are `snake_case`
- Boolean variables and properties use `is_`, `has_`, `can_` prefixes

## Signals over Polling

- Prefer emitting signals to communicate between nodes rather than polling `_process` each frame
- Define signals in the node that owns the state change
- Connect signals in the scene tree (editor) or in `_ready()` via code — avoid connecting in `_process()`

## Composition via Scene Instancing

- Prefer instancing separate scenes over adding child nodes procedurally
- Each feature lives in its own `.tscn` file under `scenes/features/`
- Compose scenes by instancing them as children in the parent scene

## Exports and Typed References

- Use `@export` variables for properties that the parent scene or designer should configure
- Prefer `@export var speed: float = 300.0` over magic numbers
- Avoid `get_node("HardcodedPath")` — use `@export` references or `%UniqueNode` syntax when a node reference is needed
- When a node reference must be set, use `@onready @export var target: Node2D` instead of string paths

## Type Hints

- Add type hints to all function parameters and return types
- Use `var health: int = 100` instead of `var health = 100`
- Use typed arrays: `var items: Array[Item] = []`

## Error Handling

- Use `push_error()` for runtime errors that should be logged
- Use `push_warning()` for non-critical issues
- Validate `@export` values in `_ready()` and push warnings for invalid configurations

## File Organization

- One scene per feature: `scenes/features/<feature_name>.tscn`
- Corresponding script: Same directory or `scripts/` with matching name
- Shared utilities: `scripts/utils/`
- Do not modify files outside your assigned feature scene