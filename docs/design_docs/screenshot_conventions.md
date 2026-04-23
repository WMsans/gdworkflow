# Screenshot Conventions

## Camera Framing

- **2D scenes**: Use an auto-positioned `Camera2D` centered on the scene's bounding box of visible nodes.
- **UI scenes**: Capture at the project's configured viewport size (default 800x600).
- **3D scenes**: Require an existing `Camera3D` in the scene. If none exists, a top-down orthographic camera is inserted.

## Lighting

- Scenes are captured with whatever lighting they were authored with.
- No additional lighting is injected. The screenshot should reflect the scene as-is.
- For scenes with no lighting, the ambient light from the project's default environment is used.

## Frame Timing

- **Default**: 10 frames of simulation before capture.
- This allows animations, particles, and physics to settle into a representative state.
- For scenes with long startup animations, increase `--frames` (e.g., `--frames 60`).
- The frame counter starts after the scene is fully loaded and instanced.

## Output Format

- **Format**: PNG
- **Resolution**: Matches the project's viewport size (default 800x600)
- **Path convention**: `screenshots/<scene_name>.png` relative to the project root
- **Relationship to features**: Each feature's screenshot is stored in its worktree at `screenshots/<scene_name>.png`

## Headless Mode Notes

- Godot 4.x headless mode can produce screenshots via `Viewport.get_texture().get_image()`.
- The root viewport is used for capture.
- 3D scenes require a GPU for rendering in headless mode. On CI or headless servers, 2D-only scenes are recommended.
- The `capture_scene.gd` script runs as a `SceneTree` script, using the `_iteration` callback to count frames.