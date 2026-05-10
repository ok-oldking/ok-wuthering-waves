import ast
import unittest
from pathlib import Path


TASK_FILES = {
    "NightmareNestTask": Path("src/task/NightmareNestTask.py"),
    "TacetTask": Path("src/task/TacetTask.py"),
    "ForgeryTask": Path("src/task/ForgeryTask.py"),
    "SimulationTask": Path("src/task/SimulationTask.py"),
}


class TestScheduleSupport(unittest.TestCase):

    def test_selected_tasks_enable_schedule_support(self):
        for class_name, file_path in TASK_FILES.items():
            with self.subTest(class_name=class_name):
                module = ast.parse(file_path.read_text(encoding="utf-8"))
                class_node = next(
                    node for node in module.body
                    if isinstance(node, ast.ClassDef) and node.name == class_name
                )
                init_node = next(
                    node for node in class_node.body
                    if isinstance(node, ast.FunctionDef) and node.name == "__init__"
                )

                has_schedule_assignment = False
                for node in ast.walk(init_node):
                    if not isinstance(node, ast.Assign):
                        continue
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"
                            and target.attr == "support_schedule_task"
                            and isinstance(node.value, ast.Constant)
                            and node.value.value is True
                        ):
                            has_schedule_assignment = True
                            break
                    if has_schedule_assignment:
                        break

                self.assertTrue(has_schedule_assignment, file_path.as_posix())

    def test_tacet_task_run_handles_login_before_entering_world(self):
        module = ast.parse(Path("src/task/TacetTask.py").read_text(encoding="utf-8"))
        class_node = next(
            node for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "TacetTask"
        )
        run_node = next(
            node for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == "run"
        )

        ensure_main_calls = [
            node for node in ast.walk(run_node)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "ensure_main"
        ]

        self.assertTrue(ensure_main_calls)


if __name__ == "__main__":
    unittest.main()
