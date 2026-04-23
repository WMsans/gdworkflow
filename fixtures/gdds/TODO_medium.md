# TODO — Generated from medium.md

---
id: feat-player-movement
feature_name: Player Movement
new_scene_path: scenes/features/player.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect:
    - from: player/input
      signal: player_died
      to: ./hud
      method: on_player_died
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: medium
---

The player character can run and jump across platforms.

- **Scene**: `player.tscn` — `CharacterBody2D` root with `AnimatedSprite2D` and `CollisionShape2D`
- **Run speed**: 300 px/s, applied via `velocity.x` on `input` direction
- **Jump velocity**: -500 px/s, with standard gravity (980 px/s²)
- **Input**: `move_left`, `move_right`, `jump` actions
- **Integration**: Add `player.tscn` instance to `level_01.tscn` as a child of the `Entities` node; emits `player_died` signal on Y-sort bounds

---
id: feat-collectible-coins
feature_name: Collectible Coins
new_scene_path: scenes/features/coin.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect:
    - from: coin
      signal: coin_collected
      to: ./hud
      method: on_coin_collected
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: low
---

Coins placed throughout the level that the player can pick up.

- **Scene**: `coin.tscn` — `Area2D` root with `AnimatedSprite2D`, `CollisionShape2D`, and a `Timer` for auto-spin animation
- **On `body_entered`**: Increment global score, play pickup SFX, queue_free
- **Integration**: Emits `coin_collected` signal; `HUD` scene connects to this to update the score display

---
id: feat-patrolling-enemies
feature_name: Patrolling Enemies
new_scene_path: scenes/features/enemy.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect:
    - from: enemy/hitbox
      signal: player_hit
      to: ./player
      method: take_damage
  autoload: false
touches_existing_files: []
depends_on:
  - feat-player-movement
estimated_complexity: medium
---

Enemies walk back and forth on platforms, hurting the player on contact.

- **Scene**: `enemy.tscn` — `CharacterBody2D` root with `Sprite2D`, `CollisionShape2D`, and `RayCast2D` for edge detection
- **Patrol behavior**: Move at 100 px/s; flip horizontal direction when `RayCast2D` loses floor contact or hits a wall
- **Damage**: On `body_entered` with the player, emit `player_hit` signal with damage amount of 1
- **Integration**: Place as sibling of `player` under `Entities`; connect `player_hit` to the player's `take_damage` method

---
id: feat-hud
feature_name: HUD
new_scene_path: scenes/features/hud.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on:
  - feat-collectible-coins
estimated_complexity: low
---

A heads-up display showing the current score.

- **Scene**: `hud.tscn` — `CanvasLayer` root with a `Label` node for score text
- **Update logic**: Connects to the `coin_collected` signal from each `coin` instance to increment and display `Score: X`
- **Integration**: Add as child of the main `Level` scene's `UI` layer