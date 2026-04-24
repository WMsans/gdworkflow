# TODO — Week 3 Integration Test

---
id: feat-orange-triangle
feature_name: Orange Triangle
new_scene_path: scenes/features/orange_triangle.tscn
integration_parent: sandbox/scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: low
---

Create a 2D gameplay scene with an orange triangle that slowly rotates clockwise.

- **Scene**: `orange_triangle.tscn` — `Node2D` root with a `Polygon2D` child and a `CollisionPolygon2D` child
- **Polygon2D**: 3 vertices forming an equilateral triangle (side length 60px), color `#FF8800`, centered at origin
- **Script**: `orange_triangle.gd` — attach to root, rotate at 45 degrees/second clockwise using `rotation += delta * deg_to_rad(45)` in `_process`
- **CollisionPolygon2D**: same 3 vertices as the visual triangle
- **Tests**: Write gdUnit4 tests in `test/test_orange_triangle.gd` verifying the scene loads, the Polygon2D has color `#FF8800`, and `rotation` increases over time
- **Integration**: Add as child of root node in `scenes/main.tscn`

---
id: feat-health-bar
feature_name: Health Bar
new_scene_path: scenes/features/health_bar.tscn
integration_parent: sandbox/scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect:
    - from: health_bar
      signal: health_changed
      to: ./hud
      method: on_health_changed
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: low
---

Create a UI health bar scene that displays a green bar representing current health.

- **Scene**: `health_bar.tscn` — `Control` root with a `ColorRect` background (dark gray, 200x20px) and a `ColorRect` foreground (green `#44FF44`, 200x20px)
- **Script**: `health_bar.gd` — attach to root, export `max_health: int = 100` and `current_health: int = 100`, update foreground width based on `float(current_health) / float(max_health) * 200.0`
- **Signal**: Emit `health_changed(current_health: int)` whenever health changes
- **Method**: `take_damage(amount: int)` that decreases `current_health` (min 0), emits `health_changed`, and updates the bar width
- **Tests**: Write gdUnit4 tests verifying the scene loads, health starts at 100, `take_damage(30)` updates health to 70 and the bar width shrinks proportionally
- **Integration**: Add as child of root node in `scenes/main.tscn`

---
id: feat-spark-particles
feature_name: Spark Particles
new_scene_path: scenes/features/spark_particles.tscn
integration_parent: sandbox/scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: low
---

Create a 2D particle effect scene with yellow spark particles that emit upward.

- **Scene**: `spark_particles.tscn` — `Node2D` root with a `GPUParticles2D` child
- **GPUParticles2D**: `amount = 20`, `process_material` with `ParticleProcessMaterial` — initial velocity upward (Y = -100 to -200 spread), gravity Y = 98, color gradient from `#FFFF44` to `#FF880000` (yellow to transparent), lifetime 1.0 second, one-shot disabled (continuous emission)
- **Script**: `spark_particles.gd` — attach to root, export `emitting: bool = true`, add a `start()` and `stop()` method that sets `emitting` on the GPUParticles2D node
- **Tests**: Write gdUnit4 tests verifying the scene loads, `GPUParticles2D` node exists, `emitting` starts as `true`, and calling `stop()` sets `emitting` to `false`
- **Integration**: Add as child of root node in `scenes/main.tscn`