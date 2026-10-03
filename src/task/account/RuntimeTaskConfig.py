from contextlib import contextmanager
from copy import deepcopy


class RuntimeTaskConfig(dict):
    """ConfigCard-compatible configuration that never writes to disk."""

    def __init__(self, values, defaults):
        self.default = deepcopy(defaults)
        super().__init__(deepcopy(defaults))
        self.update(deepcopy(values))

    def get_default(self, key):
        return deepcopy(self.default.get(key))

    def has_user_config(self):
        return any(not key.startswith('_') for key in self)

    def reset_to_default(self):
        self.clear()
        self.update(deepcopy(self.default))

    def save_file(self):
        # Some tasks explicitly save their Config; runtime changes stay in memory.
        pass


def effective_config(task, saved):
    values = deepcopy(task.default_config)
    values.update(deepcopy(dict(task.config)))
    values.update(deepcopy(saved))
    return RuntimeTaskConfig(values, task.default_config)


@contextmanager
def isolated_task_configs(tasks):
    """Protect nested task calls as well as the selected task's configuration.

    Enter only on the executor thread. Ordinary task widgets retain their own
    persistent Config references; all runtime replacements are restored on exit.
    """
    originals = []
    try:
        for task in tasks:
            runtime = effective_config(task, {})
            originals.append((task, task.config))
            task.config = runtime
        yield
    finally:
        for task, original in reversed(originals):
            task.config = original


@contextmanager
def account_task_config(task, saved):
    original = task.config
    try:
        task.config = effective_config(task, saved)
        yield task.config
    finally:
        task.config = original
