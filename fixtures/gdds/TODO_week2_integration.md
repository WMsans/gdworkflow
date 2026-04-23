# TODO — Week 2 Integration Test

---
id: feat-blue-square
feature_name: Blue Square
new_scene_path: scenes/features/blue_square.tscn
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

Create a scene with a blue ColorRect square (200x200 px) centered on screen.

- **Scene**: `blue_square.tscn` — `Control` root with a `ColorRect` child
- **ColorRect**: size 200x200, color `#4444FF`, anchored to center
- **Script**: `blue_square.gd` — attach to root, no logic needed, just ensure the scene loads without errors
- **Integration**: Add as child of root node in `scenes/main.tscn`

---
id: feat-green-circle
feature_name: Green Circle
new_scene_path: scenes/features/green_circle.tscn
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

Create a scene with a green circle that bounces slowly up and down.

- **Scene**: `green_circle.tscn` — `Node2D` root with a `Polygon2D` child drawing a circle (32 segments, radius 40px, color `#44FF44`)
- **Script**: `green_circle.gd` — animate vertical position using a sinusoidal bounce (amplitude 30px, period 2 seconds) in `_process`
- **Integration**: Add as child of root node in `scenes/main.tscn`

---
id: feat-score-display
feature_name: Score Display
new_scene_path: scenes/features/score_display.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect:
    - from: score_display
      signal: score_changed
      to: ./hud
      method: on_score_changed
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: low
---

A score display that shows the current score at the top of the screen.

- **Scene**: `score_display.tscn` — `CanvasLayer` root with a `Label` node
- What format should the score label use? Should it display "Score: 0" or just the number?
- Should the score update on a timer or only on events?
- How should this scene connect to the main scene — via the `score_changed` signal or some other mechanism?
- What value type is the score — integer or float?