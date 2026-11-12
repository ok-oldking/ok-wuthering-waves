import ast
import unittest
from pathlib import Path
from unittest.mock import Mock


class FakeBox:
    def __init__(self, name, x=0, y=0, width=10, height=10):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.confidence = 1.0


class TestBaseCombatTask(unittest.TestCase):
    def setUp(self):
        module = ast.parse(Path("src/task/BaseCombatTask.py").read_text(encoding="utf-8"))
        class_node = next(
            node for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "BaseCombatTask"
        )
        self.method_node = next(
            (node for node in class_node.body
             if isinstance(node, ast.FunctionDef) and node.name == "get_revive_search_boss_name"),
            None,
        )
        self.revive_method_node = next(
            node for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == "revive_at_tower_and_heal"
        )
        self.travel_method_node = next(
            (node for node in class_node.body
             if isinstance(node, ast.FunctionDef) and node.name == "_travel_to_nearest_waypoint"),
            None,
        )

    def _build_method_owner(self):
        self.assertIsNotNone(self.method_node, "BaseCombatTask should define get_revive_search_boss_name")
        compiled = ast.fix_missing_locations(ast.Module(body=[
            ast.ClassDef(
                name="MethodOwner",
                bases=[],
                keywords=[],
                decorator_list=[],
                body=[self.method_node],
            )
        ], type_ignores=[]))
        namespace = {}
        exec(compile(compiled, "<test>", "exec"), namespace)
        return namespace["MethodOwner"]

    def _build_travel_owner(self):
        self.assertIsNotNone(self.travel_method_node, "BaseCombatTask should define _travel_to_nearest_waypoint")
        compiled = ast.fix_missing_locations(ast.Module(body=[
            ast.ClassDef(
                name="MethodOwner",
                bases=[],
                keywords=[],
                decorator_list=[],
                body=[self.travel_method_node],
            )
        ], type_ignores=[]))
        namespace = {}
        exec(compile(compiled, "<test>", "exec"), namespace)
        return namespace["MethodOwner"]

    def _make_travel_task(self):
        task = self._build_travel_owner()()
        task.sleep = Mock()
        task.width = 1920
        task.height = 1080
        task.box_of_screen = Mock(return_value=FakeBox("map"))
        task.tr = Mock(side_effect=lambda text: text)
        task.click = Mock()
        task.click_box = Mock()
        task.find_feature = Mock(return_value=[])
        task.wait_feature = Mock(return_value=None)
        task.wait_in_team_and_world = Mock()
        return task

    def test_revive_search_boss_name_matches_game_language(self):
        method_owner = self._build_method_owner()
        cases = {
            "zh_CN": "无冠者",
            "zh_TW": "無冠者",
            "en_US": "Crownless",
            "unknown_lang": "无冠者",
        }

        for lang, expected in cases.items():
            with self.subTest(lang=lang):
                task = method_owner()
                task.game_lang = lang
                self.assertEqual(task.get_revive_search_boss_name(), expected)

    def test_revive_flow_uses_language_aware_search_name(self):
        has_call = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "input_text"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Call)
            and isinstance(node.args[0].func, ast.Attribute)
            and isinstance(node.args[0].func.value, ast.Name)
            and node.args[0].func.value.id == "self"
            and node.args[0].func.attr == "get_revive_search_boss_name"
            for node in ast.walk(self.revive_method_node)
        )
        self.assertTrue(has_call)

    def test_travel_to_nearest_waypoint_waits_without_raising(self):
        self.assertIsNotNone(self.travel_method_node, "BaseCombatTask should define _travel_to_nearest_waypoint")
        waits = [
            node for node in ast.walk(self.travel_method_node)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "wait_feature"
        ]
        self.assertEqual(1, len(waits))
        keywords = {keyword.arg: keyword.value for keyword in waits[0].keywords}
        self.assertIn("raise_if_not_found", keywords)
        self.assertIsInstance(keywords["raise_if_not_found"], ast.Constant)
        self.assertFalse(keywords["raise_if_not_found"].value)

    def test_travel_tries_nearest_candidate_first(self):
        task = self._make_travel_task()
        far = FakeBox("map_way_point", 1700, 900)
        near = FakeBox("map_way_point", 940, 520)
        task.find_feature = Mock(side_effect=[[far, near], []])
        travel = FakeBox("gray_teleport", 1300, 900)
        task.wait_feature = Mock(return_value=travel)

        task._travel_to_nearest_waypoint()

        self.assertEqual(near, task.click.call_args_list[0].args[0])
        task.click_box.assert_called_once_with(travel, relative_x=1.5)

    def test_travel_skips_candidate_when_choice_list_is_shown(self):
        task = self._make_travel_task()
        overlap = FakeBox("map_way_point", 930, 500)
        other = FakeBox("map_way_point", 1000, 600)
        task.find_feature = Mock(side_effect=[[overlap, other], []])
        travel = FakeBox("gray_teleport", 1300, 900)
        task.wait_feature = Mock(side_effect=[None, travel])

        task._travel_to_nearest_waypoint()

        clicked = [call.args for call in task.click.call_args_list]
        self.assertEqual([(overlap,), (0.06, 0.5), (other,)], clicked)
        task.click_box.assert_called_once_with(travel, relative_x=1.5)

    def test_travel_raises_when_all_candidates_fail(self):
        task = self._make_travel_task()
        overlap = FakeBox("map_way_point", 930, 500)
        task.find_feature = Mock(side_effect=[[overlap], []])

        with self.assertRaises(RuntimeError):
            task._travel_to_nearest_waypoint()

        task.click_box.assert_not_called()


if __name__ == "__main__":
    unittest.main()
