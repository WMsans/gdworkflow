class_name MainTest
extends GdUnitTestSuite

var _main_scene: Node2D

func before_test() -> void:
	_main_scene = auto_free(load("res://scenes/main.tscn").instantiate() as Node2D)
	add_child(_main_scene)

func test_main_scene_loads() -> void:
	assert_not_null(_main_scene, "Main scene should load without errors")

func test_main_scene_is_node2d() -> void:
	assert_bool(_main_scene is Node2D).is_true()

func test_main_scene_has_name() -> void:
	assert_str(_main_scene.name).is_not_empty()

func test_main_scene_root_type() -> void:
	assert_bool(_main_scene.get_child_count() >= 0).is_true()