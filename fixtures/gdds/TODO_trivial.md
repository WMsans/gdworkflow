# TODO — Generated from trivial.md

---
id: feat-red-square
feature_name: Red Square Player
new_scene_path: scenes/features/red_square.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: low
---

A red square (`ColorRect` or `Sprite2D`) that the player can move with arrow keys.

- **Input**: Arrow keys mapped to `ui_up`, `ui_down`, `ui_left`, `ui_right`
- **Speed**: 200 pixels/second
- **Boundary**: Clamped to the viewport so the square cannot leave the screen
- **Scene**: Single scene `main.tscn` with the square as a `CharacterBody2D` child node