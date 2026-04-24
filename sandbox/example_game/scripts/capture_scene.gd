extends SceneTree

var scene_path: String = ""
var output_path: String = "res://screenshots/capture.png"
var frames_to_wait: int = 10
var viewport_size: Vector2i = Vector2i(800, 600)
var _scene_instance: Node = null
var _frame_count: int = 0
var _ready: bool = false

func _initialize() -> void:
	var config_path = "res://screenshots/.capture_config.json"
	if not FileAccess.file_exists(config_path):
		push_error("capture_scene: Config file not found at " + config_path)
		quit.call_deferred(1)
		return

	var file = FileAccess.open(config_path, FileAccess.ModeFlags.READ)
	if file == null:
		push_error("capture_scene: Cannot open config file: " + str(FileAccess.get_open_error()))
		quit.call_deferred(1)
		return

	var json_text = file.get_as_text()
	file.close()

	var json = JSON.new()
	var err = json.parse(json_text)
	if err != OK:
		push_error("capture_scene: Config parse error: " + json.get_error_message())
		quit.call_deferred(1)
		return

	var data = json.data
	if data == null:
		push_error("capture_scene: Config is not a valid JSON object")
		quit.call_deferred(1)
		return

	scene_path = data.get("scene_path", "")
	output_path = data.get("output_path", "res://screenshots/capture.png")
	frames_to_wait = int(data.get("frames", 10))
	if data.has("viewport_width"):
		viewport_size.x = int(data["viewport_width"])
	if data.has("viewport_height"):
		viewport_size.y = int(data["viewport_height"])

	if scene_path == "":
		push_error("capture_scene: scene_path is required in config")
		quit.call_deferred(1)
		return

	if not ResourceLoader.exists(scene_path):
		push_error("capture_scene: Scene not found: " + scene_path)
		quit.call_deferred(1)
		return

	var scene_res = load(scene_path)
	if scene_res == null:
		push_error("capture_scene: Failed to load scene: " + scene_path)
		quit.call_deferred(1)
		return

	if not output_path.begins_with("res://") and not output_path.begins_with("/"):
		output_path = "res://" + output_path

	_scene_instance = scene_res.instantiate()
	get_root().add_child(_scene_instance)

	var camera = _find_or_create_camera(_scene_instance)
	camera.call_deferred("make_current")

	_ready = true
	print("capture_scene: Loaded '", scene_path, "', capturing in ", frames_to_wait, " frames...")

func _process(_delta: float) -> bool:
	if not _ready:
		return false

	_frame_count += 1

	if _frame_count >= frames_to_wait:
		_ready = false
		_capture_screenshot()
		_cleanup()
		quit.call_deferred(0)

	return _frame_count >= frames_to_wait

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

	var abs_path = ProjectSettings.globalize_path(output_path)
	var dir = abs_path.get_base_dir()
	if dir != "" and not DirAccess.dir_exists_absolute(dir):
		DirAccess.make_dir_recursive_absolute(dir)

	var err = img.save_png(abs_path)
	if err == OK:
		print("capture_scene: Screenshot saved to ", abs_path)
	else:
		push_error("capture_scene: save_png failed with error " + str(err))

func _cleanup() -> void:
	if _scene_instance != null and _scene_instance.is_inside_tree():
		_scene_instance.queue_free()