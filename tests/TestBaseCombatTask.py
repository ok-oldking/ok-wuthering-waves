import ast
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
