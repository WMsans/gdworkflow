# Red Square

## Overview

A single-screen arcade game where the player controls a red square.

## Core Mechanics

### Player Movement

A red square (`ColorRect` or `Sprite2D`) that the player can move with arrow keys.

- **Input**: Arrow keys mapped to `ui_up`, `ui_down`, `ui_left`, `ui_right`
- **Speed**: 200 pixels/second
- **Boundary**: Clamped to the viewport so the square cannot leave the screen
- **Scene**: Single scene `main.tscn` with the square as a `CharacterBody2D` child node