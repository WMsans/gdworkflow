@tool
extends SceneTree

var scene_path: String = ""
var output_path: String = "screenshot.png"
var frames_to_wait: int = 10
var viewport_size: Vector2i = Vector2i(800, 600)
var _scene_instance: Node = null
var _frame_count: int = 0

func _initialize() -> void:
	for arg in OS.get_cmdline_args():
		var split_arg = arg.split("=")
		match split_arg[0]:
			"--scene-path":
				scene_path = split_arg[1] if split_arg.size() > 1 else ""
			"--output-path":
				output_path = split_arg[1] if split_arg.size() > 1 else "screenshot.png"
			"--frames":
				frames_to_wait = int(split_arg[1]) if split_arg.size() > 1 else 10
			"--viewport-width":
				viewport_size.x = int(split_arg[1]) if split_arg.size() > 1 else 800
			"--viewport-height":
				viewport_size.y = int(split_arg[1]) if split_arg.size() > 1 else 600

	if scene_path == "":
		push_error("capture_scene: --scene-path is required")
		quit(1)
		return

func _iteration(delta: float) -> bool:
	if _scene_instance == null and scene_path != "":
		if not ResourceLoader.exists(scene_path):
			push_error("capture_scene: Scene not found: " + scene_path)
			quit(1)
			return true

		var scene_res = load(scene_path)
		if scene_res == null:
			push_error("capture_scene: Failed to load scene: " + scene_path)
			quit(1)
			return true

		_scene_instance = scene_res.instantiate()
		get_root().add_child(_scene_instance)

		var camera = _find_or_create_camera(_scene_instance)
		camera.make_current()

	_frame_count += 1

	if _frame_count >= frames_to_wait:
		_capture_screenshot()
		_cleanup()
		quit(0)

	return false

func _find_or_create_camera(node: Node) -> Camera2D:
	var existing = _find_camera_in_tree(node)
	if existing != null:
		return existing

	var new_camera = Camera2D.new()
	new_camera.position = _compute_center(node)
	node.add_child(new_camera)
	return new_camera

func _find_camera_in_tree(node: Node) -> Camera2D:
	if node is Camera2D:
		return node as Camera2D
	for child in node.get_children():
		var found = _find_camera_in_tree(child)
		if found != null:
			return found
	return null

func _compute_center(node: Node) -> Vector2:
	var min_pos = Vector2(INF, INF)
	var max_pos = Vector2(-INF, -INF)
	_collect_bounds(node, min_pos, max_pos)
	if min_pos.x == INF:
		return Vector2(viewport_size.x / 2.0, viewport_size.y / 2.0)
	return (min_pos + max_pos) / 2.0

func _collect_bounds(node: Node, min_pos: Vector2, max_pos: Vector2) -> void:
	if node is Node2D:
		var pos = (node as Node2D).global_position
		min_pos.x = min(min_pos.x, pos.x)
		min_pos.y = min(min_pos.y, pos.y)
		max_pos.x = max(max_pos.x, pos.x)
		max_pos.y = max(max_pos.y, pos.y)
	if node is Control:
		var rect = (node as Control).get_global_rect()
		min_pos.x = min(min_pos.x, rect.position.x)
		min_pos.y = min(min_pos.y, rect.position.y)
		max_pos.x = max(max_pos.x, rect.end.x)
		max_pos.y = max(max_pos.y, rect.end.y)
	for child in node.get_children():
		_collect_bounds(child, min_pos, max_pos)

func _capture_screenshot() -> void:
	var viewport = get_root().get_viewport()
	var img = viewport.get_texture().get_image()
	if img == null:
		push_error("capture_scene: Failed to capture viewport image")
		return

	var dir = output_path.get_base_dir()
	if dir != "" and not DirAccess.dir_exists_absolute(dir):
		DirAccess.make_dir_recursive_absolute(dir)
	img.save_png(output_path)
	print("capture_scene: Screenshot saved to ", output_path)

func _cleanup() -> void:
	if _scene_instance != null and _scene_instance.is_inside_tree():
		_scene_instance.queue_free()