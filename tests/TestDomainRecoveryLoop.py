import ast
import unittest
from pathlib import Path


class TestDomainRecoveryLoop(unittest.TestCase):
    def setUp(self):
        module = ast.parse(Path("src/task/DomainTask.py").read_text(encoding="utf-8"))
        class_node = next(
            node for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "DomainTask"
        )
        self.method_node = next(
            node for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == "farm_domain_with_recovery_loop"
        )

    def test_method_has_retry_parameter_with_default(self):
        args = self.method_node.args.args
        self.assertEqual(args[-1].arg, "max_recovery_retries")
        self.assertEqual(len(self.method_node.args.defaults), 1)
        default_value = self.method_node.args.defaults[0]
        self.assertIsInstance(default_value, ast.Constant)
        self.assertEqual(default_value.value, 3)

    def test_method_increments_retries(self):
        has_increment = any(
            isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "recovery_retries"
            and isinstance(node.op, ast.Add)
            and isinstance(node.value, ast.Constant)
            and node.value.value == 1
            for node in ast.walk(self.method_node)
        )
        self.assertTrue(has_increment)

    def test_method_stops_when_retry_budget_exceeded(self):
        has_retry_guard = any(
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id == "recovery_retries"
            and any(isinstance(op, ast.GtE) for op in node.ops)
            and any(
                isinstance(comp, ast.Name) and comp.id == "max_recovery_retries"
                for comp in node.comparators
            )
            for node in ast.walk(self.method_node)
        )
        self.assertTrue(has_retry_guard)

        has_make_sure_in_world_call = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "make_sure_in_world"
            for node in ast.walk(self.method_node)
        )
        self.assertTrue(has_make_sure_in_world_call)


if __name__ == "__main__":
    unittest.main()
