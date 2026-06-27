import ast
import unittest
from pathlib import Path


TASK_FILES = {
    "NightmareNestTask": Path("src/task/NightmareNestTask.py"),
    "TacetTask": Path("src/task/TacetTask.py"),
    "ForgeryTask": Path("src/task/ForgeryTask.py"),
    "SimulationTask": Path("src/task/SimulationTask.py"),
}


def _class_function(module_path, class_name, function_name):
    module = ast.parse(Path(module_path).read_text(encoding="utf-8"))
    class_node = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return next(
        node for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )


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
        run_node = _class_function("src/task/TacetTask.py", "TacetTask", "run")

        ensure_main_calls = [
            node for node in ast.walk(run_node)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "ensure_main"
        ]

        self.assertTrue(ensure_main_calls)

    def test_multi_account_returns_to_main_before_switching_to_login(self):
        run_node = _class_function("src/task/MultiAccountDailyTask.py", "MultiAccountDailyTask", "run")

        calls = [
            node for node in ast.walk(run_node)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr in {"run_task_by_class", "ensure_main", "_switch_to_login"}
        ]

        call_names = [node.func.attr for node in sorted(calls, key=lambda call: call.lineno)]
        first_daily_index = call_names.index("run_task_by_class")
        switch_index = call_names.index("_switch_to_login")

        self.assertIn("ensure_main", call_names[first_daily_index + 1:switch_index])

    def test_multi_account_login_dropdown_timeout_is_not_silent(self):
        find_node = _class_function(
            "src/task/MultiAccountDailyTask.py",
            "MultiAccountDailyTask",
            "find_account_drop_down",
        )

        wait_until = next(
            node for node in ast.walk(find_node)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "wait_until"
        )
        raise_kw = next((kw for kw in wait_until.keywords if kw.arg == "raise_if_not_found"), None)

        self.assertIsNotNone(raise_kw)
        self.assertIsInstance(raise_kw.value, ast.Constant)
        self.assertIs(raise_kw.value.value, True)


if __name__ == "__main__":
    unittest.main()
