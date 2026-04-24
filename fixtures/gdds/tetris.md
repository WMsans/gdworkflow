# Tetris

## Overview

A classic falling-block puzzle game where the player rotates and positions tetromino pieces to clear horizontal lines, following modern Tetris guidelines with SRS rotation, hold piece, next queue, and 7-bag randomizer.

## Core Mechanics

### Playfield Grid

A 10-column by 20-row visible playfield with hidden buffer rows above for piece spawning.

- **Scene**: `board.tscn` — `Node2D` root with a `TileMapLayer` for cell rendering and a `ColorRect` border outline
- **Grid dimensions**: 10 columns × 20 visible rows, plus 2 hidden buffer rows above the visible area
- **Cell size**: 32×32 pixels per block
- **Data model**: 2D `Array` of `int` (0 = empty, 1–7 = filled with piece color index) stored in `board.gd`
- **Boundary**: Pieces cannot move past left/right walls (columns 0 and 9) or below row 19
- **Integration**: Board is the central scene; `TetrominoPiece` writes cells on lock, `LineClear` reads rows to detect completions

### Tetromino Movement & SRS Rotation

Seven tetromino shapes the player controls with keyboard input, using the Super Rotation System for wall kicks.

- **Scene**: `tetromino.tscn` — `Node2D` root with `Sprite2D` blocks positioned per piece shape, and a `Timer` for gravity ticks
- **Piece types**: I, O, T, S, Z, J, L — each defined as shape data (4×4 matrix per rotation state) in `piece_data.gd`
- **Movement**: Left/right at `input` rate (0.17 s initial delay, 0.05 s repeat); soft drop at 20× current gravity; hard drop teleports piece to lowest valid position instantly
- **SRS Rotation**: 4 rotation states per piece; wall kick tables (5 tests per clockwise/counterclockwise rotation) per SRS standard
- **Gravity**: Starts at 0.8 rows/second per tick; increases per level (see Scoring & Level Progression)
- **Lock delay**: 0.5 s after piece touches stack; resets on successful move/rotation up to 15 resets
- **Input**: `move_left`, `move_right`, `soft_drop`, `hard_drop`, `rotate_cw`, `rotate_ccw`, `hold` actions
- **Signals**: `piece_locked(Vector2i[], int)` emitted with occupied cells and color index; `game_over`
- **Integration**: Tetromino instance added as child of `Board`; on lock, calls `Board.lock_piece()` which writes cells and frees the piece; spawns next piece from `NextQueue`

### Next Queue & Hold Piece

A preview of the next 3 upcoming pieces and a hold slot for saving the current piece.

- **Scene**: `next_queue.tscn` — `VBoxContainer`-based `CanvasLayer` overlay showing 3 piece previews as `Sprite2D` arrangements; `hold_display.tscn` — single-slot display for held piece
- **7-bag randomizer**: Shuffles a bag of all 7 piece types; generates a new bag when empty. Ensures even distribution of pieces
- **Hold**: Press `hold` action to swap current piece with hold slot; blocked for the rest of the current piece's lifetime after one use
- **Hold cooldown**: Resets when a new piece spawns; first hold stores current piece and pulls from hold slot (or next queue if hold is empty)
- **Signals**: `next_queue_updated(Array)` emitted on bag refresh; `hold_swapped(int, int)` emitted with old and new piece types
- **Integration**: Both instantiated as children of `HUD`; `NextQueue` feeds piece data to `Board.spawn_piece()`, `HoldDisplay` swaps with `Board` on `hold` input; both read `piece_data.gd` for shape rendering

### Line Clearing

Detection and removal of fully completed horizontal rows with visual feedback.

- **Scene**: `line_clear_effect.tscn` — `AnimationPlayer` with flash and dissolve animation for cleared rows
- **Detection**: After each `Board.lock_piece()` call, scan rows 0–19 for any row where all 10 cells are non-zero
- **Clear behavior**: Remove filled rows, shift all rows above downward by the count of cleared rows
- **Scoring**: 100 × level for single, 300 × level for double, 500 × level for triple, 800 × level for tetris (4 lines)
- **Animation**: 0.4 s flash on cleared rows before removal; gameplay pauses during animation
- **Signals**: `lines_cleared(int)` emitted with count; `tetris_cleared` emitted specifically for 4-line clears
- **Integration**: `Board` calls line-clear check after `lock_piece`; connects `lines_cleared` to `ScoreManager` for points and `LevelManager` for line count tracking

### Scoring & Level Progression

A global score tracker and level system that increases gravity speed as the player clears more lines.

- **Script**: `score_manager.gd` and `level_manager.gd` registered as autoloads `ScoreManager` and `LevelManager`
- **Scoring**: Lines award `base_points × level` (100/300/500/800 for 1/2/3/4 lines); soft drop awards 1 point per cell; hard drop awards 2 points per cell
- **Level**: Starts at 1; advances when 10 × current level lines have been cleared total
- **Gravity curve**: Gravity in seconds-per-row = `(0.8 - ((level - 1) × 0.007)) ^ (level - 1)`, minimum 1/60 s per row at level 29
- **Signals**: `ScoreManager`: `score_changed(int)`; `LevelManager`: `level_changed(int)`
- **Persistence**: `save()` / `load()` high score to `user://tetris_highscore.cfg`
- **Integration**: `ScoreManager` connects to `lines_cleared` from `Board`; `LevelManager` updates level on line count milestones; both feed `HUD` for display

### HUD

A heads-up display showing score, level, lines cleared, next queue, hold piece, and game-over overlay.

- **Scene**: `hud.tscn` — `CanvasLayer` root with `Label` nodes for score/level/lines, plus `NextQueue` and `HoldDisplay` instances; `ColorRect` overlay for game-over state
- **Score display**: `Label` showing `Score: 0` updated on `score_changed`
- **Level display**: `Label` showing `Level: 1` updated on `level_changed`
- **Lines display**: `Label` showing `Lines: 0` updated on `lines_cleared`
- **Game over**: On `game_over` signal, show `ColorRect` overlay with `Restart` and `Quit` `Button` nodes
- **Pause**: Press `Escape` to toggle pause; `PauseMenu` overlay with `Resume` and `Quit` buttons
- **Integration**: Added as child of main scene root; connects to `ScoreManager` and `LevelManager` autoloads; connects `game_over` from `Board` to show overlay