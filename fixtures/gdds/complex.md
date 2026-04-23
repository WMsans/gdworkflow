# Ember Knight

## Overview

A top-down action RPG where the player fights enemies, collects loot, talks to NPCs, and defeats a boss in a procedurally arranged overworld.

## Core Mechanics

### Player Character — Movement & Dash

The player-controlled character that can move in eight directions and dash short distances.

- **Scene**: `player.tscn` — `CharacterBody2D` root with `AnimatedSprite2D`, `CollisionShape2D`, `DashCooldown` Timer, and `Hitbox` Area2D
- **Movement**: 250 px/s via `input` vector normalized; diagonal normalization so cardinal and diagonal speeds match
- **Dash**: Double-tap or press `shift` to dash 400 px over 0.2 s using a `Tween` on `position`; 1.5 s cooldown enforced by `DashCooldown` Timer
- **Animation**: State machine driving `AnimatedSprite2D` animations — `idle`, `run`, `dash`, `hurt`, `die`
- **Signals**: `player_dashed(Vector2)`, `player_direction_changed(Vector2)`
- **Integration**: Instance under `Entities` YSort node in game world; `player_dashed` consumed by `HealthSystem` to grant iframes

### Health System — Damage & Invincibility Frames

A reusable health component that tracks HP and provides invincibility frames after taking damage.

- **Scene**: `health_component.tscn` — standalone `Node` designed to be added as a child of any damageable entity
- **Max HP**: 5 (player), varies per enemy (set via exported `max_health` int)
- **Invincibility**: 1.0 s of iframe duration after damage; toggles `set_deferred("monitorable", false)` on the entity's `Hitbox`; flashes `Sprite2D` via `AnimationPlayer`
- **Signals**: `health_changed(int, int)`, `died`, `invincibility_started`, `invincibility_ended`
- **Integration**: Attach to `player.tscn` and every `enemy.tscn`; connect `health_changed` to `HUD` for health bar; connect `died` to each entity's death handler; `invincibility_started` disables `Hitbox` monitoring

### Enemy AI — Chase Behavior

Enemies that patrol by default and chase the player when detected within a radius.

- **Scene**: `enemy.tscn` — `CharacterBody2D` root with `AnimatedSprite2D`, `CollisionShape2D`, `DetectionZone` Area2D, and `NavigationAgent2D`
- **Patrol state**: Wander between two random points within 150 px at 80 px/s
- **Chase state**: When `DetectionZone` detects the player (`body_entered`), switch to chase at 160 px/s using `NavigationAgent2D.set_target_position(player.global_position)` updated every 0.3 s
- **Attack state**: When within 40 px of player, deal 1 damage via `Hitbox` Area2D overlap, then retreat 60 px before re-engaging
- **State machine**: `Patrol` → `Chase` → `Attack` → `Chase` cycle; returns to `Patrol` if player leaves detection zone for >3 s
- **Signals**: `enemy_detected_player`, `enemy_lost_player`
- **Integration**: Add `HealthSystem` as child node; connect `enemy_detected_player` to minimap for ping markers; **Boss** depends on this AI controller for its chase logic

### Inventory System — Autoload

A global singleton that manages items the player picks up.

- **Script**: `inventory.gd` registered as autoload `Inventory`
- **Data model**: `Dictionary` of `StringName` item IDs → `{ "name": String, "icon": Texture2D, "count": int, "stackable": bool }`
- **Methods**: `add_item(id, qty)`, `remove_item(id, qty)`, `has_item(id, qty) -> bool`, `get_all() -> Array`
- **Capacity**: 20 slot grid; non-stackable items each occupy one slot; stackable items stack to 99
- **Signals**: `inventory_changed`, `item_added(StringName, int)`, `item_removed(StringName, int)`
- **Persistence**: `save()` / `load()` using `ConfigFile` to `user://inventory.cfg`
- **Integration**: Called by `Pickup` Area2D nodes on `body_entered`; `DialogueSystem` checks `Inventory.has_item()` to gate conversation branches; `Boss` drops high-tier loot that calls `Inventory.add_item()`

### Dialogue System

A text box overlay that displays NPC dialogue with branching choices.

- **Scene**: `dialogue_box.tscn` — `CanvasLayer` root with `RichTextLabel`, `Panel` background, `VBoxContainer` for choice buttons, and `Timer` for character-by-character reveal at 30 chars/s
- **Data format**: JSON resource files under `res://data/dialogues/`; each entry has `speaker`, `text`, `choices[]` where each choice has `text` and `next_id`
- **Conditional branches**: Choice items can include an `"requires_item": "iron_sword"` key; `DialogueSystem` checks `Inventory.has_item()` before showing that choice
- **Input**: Advance with `ui_accept`; mouse click selects a choice button
- **Signals**: `dialogue_started(StringName)`, `dialogue_ended(StringName)`, `choice_made(StringName, int)`
- **Integration**: Instantiate as overlay in `HUD` layer; NPCs call `DialogueSystem.start("npc_name_dialogue_01")` on `body_entered` signal; **depends on** `Inventory` autoload for item-gated choices

### Minimap Overlay

A corner overlay that shows nearby points of interest and enemy pings.

- **Scene**: `minimap.tscn` — `CanvasLayer` with `SubViewport` and `MiniMapCamera2D` at 0.25× zoom; `Sprite2D` icons for POIs
- **Icons**: Green dot for player, red dots for enemies (fed by `enemy_detected_player` signal), yellow for NPCs, blue for pickups
- **Scale**: 0.25× of world coordinates; `MiniMapCamera2D` follows `player.global_position` each frame
- **Legend**: Small `Label` in corner showing icon meanings
- **Toggle**: Press `Tab` to show/hide the overlay; starts hidden
- **Integration**: Added as sibling of `HUD` in `UI` layer; listens to `enemy_detected_player` / `enemy_lost_player` from each `enemy.tscn` to update red pings; **depends on** `EnemyAI` signals and player position

### Boss Encounter — Attack Patterns

A boss fight triggered when the player enters a specific room, featuring multiple attack phases.

- **Scene**: `boss.tscn` — `CharacterBody2D` root extending `enemy.tscn` base; adds `BossAttackController` Node and `HealthBar` ProgressBar
- **Phases**:
  1. **Phase 1 (HP 100%–60%)**: Swing melee attack (arc Area2D, 1 dmg, 0.4 s wind-up) every 2.5 s; charge dash (`Tween` 600 px over 0.35 s) every 6 s
  2. **Phase 2 (HP 60%–30%)**: Adds ground-slam projectile (4 directional projectiles at 200 px/s, 1 dmg each, 3 s cooldown); charge dash cooldown reduced to 4 s
  3. **Phase 3 (HP 30%–0%)**: All previous attacks + spinning orb ring (8 orbs rotating at 120°/s, 2 dmg, 5 s uptime, 8 s cooldown); movement speed increased to 200 px/s
- **Health**: 50 HP; `HealthSystem` attached with exported `max_health = 50`
- **Entry trigger**: `Area2D` at room entrance calls `boss.start_fight()` and locks doors (`StaticBody2D` toggles `collision_layer`)
- **Death**: Emits `boss_defeated`; unlocked doors; spawns LootPickup via `Inventory.add_item()`; triggers `DialogueSystem.start("boss_post_defeat")`
- **Signals**: `boss_phase_changed(int)`, `boss_defeated`
- **Integration**: Inherits chase AI from `EnemyAI`; `HealthSystem` connects `health_changed` to room `HUD`; loot drop calls `Inventory.add_item()`; post-defeat dialogue calls `DialogueSystem.start()` — **depends on** `EnemyAI`, `HealthSystem`, `Inventory`, and `DialogueSystem`