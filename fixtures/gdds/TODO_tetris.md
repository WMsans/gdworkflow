# TODO — Generated from tetris.md

---
id: feat-playfield-board
feature_name: Playfield Board
new_scene_path: scenes/features/playfield_board.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on: []
estimated_complexity: medium
---

The 10x20 visible playfield with 2 hidden buffer rows above, rendered via TileMapLayer at 32x32 px cell size with a ColorRect border. Stores block data as a 2D int array (0=empty, 1-7=filled) in board.gd. Enforces left/right wall and bottom boundary constraints.

# ---

---
id: feat-tetromino-piece
feature_name: Tetromino Piece & SRS Movement
new_scene_path: scenes/features/tetromino_piece.tscn
integration_parent: scenes/features/playfield_board.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on:
- feat-playfield-board
estimated_complexity: high
---

Seven tetromino shapes (I, O, T, S, Z, J, L) with shape data in piece_data.gd as 4x4 matrices per rotation state. Implements SRS rotation with wall kick tables, gravity (0.8 rows/s base, increasing per level), lock delay (0.5 s, up to 15 resets), and keyboard input for move, soft/hard drop, and rotation. Emits piece_locked(Vector2i[], int) and game_over signals. Spawned as a dynamic child of Board; on lock calls Board.lock_piece().

# ---

---
id: feat-line-clearing
feature_name: Line Clearing Effect
new_scene_path: scenes/features/line_clear_effect.tscn
integration_parent: scenes/features/playfield_board.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on:
- feat-playfield-board
estimated_complexity: medium
---

After each piece lock, scans rows 0-19 for full rows (all 10 cells non-zero), removes them, and shifts all rows above downward. Plays a 0.4 s flash/dissolve animation via AnimationPlayer before removal. Awards 100/300/500/800 x level for 1/2/3/4 lines. Emits lines_cleared(int) and tetris_cleared signals.

# ---

---
id: feat-next-queue-hold
feature_name: Next Queue & Hold Piece
new_scene_path: scenes/features/next_queue_hold_display.tscn
integration_parent: scenes/features/hud.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect: []
  autoload: false
touches_existing_files: []
depends_on:
- feat-tetromino-piece
estimated_complexity: high
---

Displays 3 upcoming piece previews as Sprite2D arrangements and a single hold slot. Implements 7-bag randomizer (shuffles all 7 pieces, generates new bag when empty). Hold swaps current piece with hold slot with one-use-per-drop cooldown (resets on new piece spawn). Reads piece_data.gd for shape rendering. Feeds piece data to Board.spawn_piece().

# ---

---
id: feat-score-manager
feature_name: Score Manager
new_scene_path: scenes/features/score_manager.tscn
integration_parent: res://project.godot
integration_hints:
  node_type: script_attach
  position: autoload
  signals_to_connect: []
  autoload: true
touches_existing_files: []
depends_on: []
estimated_complexity: low
---

Autoload tracking score from line clears (base points x level), soft drop (1 pt/cell), and hard drop (2 pts/cell). Persists high score to user://tetris_highscore.cfg via save()/load(). Emits score_changed(int) signal.

# ---

---
id: feat-level-manager
feature_name: Level Manager
new_scene_path: scenes/features/level_manager.tscn
integration_parent: res://project.godot
integration_hints:
  node_type: script_attach
  position: autoload
  signals_to_connect: []
  autoload: true
touches_existing_files: []
depends_on: []
estimated_complexity: low
---

Autoload tracking level progression. Level starts at 1, advances when 10 x current_level lines are cleared. Gravity curve: (0.8 - ((level-1) x 0.007)) ^ (level-1), minimum 1/60 s per row at level 29. Emits level_changed(int) signal.

# ---

---
id: feat-hud
feature_name: HUD & Pause Menu
new_scene_path: scenes/features/hud.tscn
integration_parent: scenes/main.tscn
integration_hints:
  node_type: instance
  position: as_child_of_root
  signals_to_connect:
  - from: '%Board'
    signal: game_over
    to: .
    method: show_game_over
  autoload: false
touches_existing_files: []
depends_on:
- feat-next-queue-hold
- feat-score-manager
- feat-level-manager
estimated_complexity: medium
---

CanvasLayer overlay with Labels for score, level, and lines, updated via signal connections to ScoreManager and LevelManager autoloads. On game_over, shows ColorRect overlay with Restart and Quit buttons. Escape toggles PauseMenu overlay with Resume and Quit buttons. Instances NextQueue and HoldDisplay as child scenes.
