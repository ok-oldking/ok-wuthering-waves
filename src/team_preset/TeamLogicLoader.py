"""队伍级出招逻辑加载器。

把预设的 team_code.py 编译为一个 BaseTeamCombat 子类。
加载失败或代码无效时返回 None(战斗回退到逐角色逻辑),绝不抛给战斗。
"""

import importlib.util

from ok import Logger
from src.team_preset.BaseTeamCombat import BaseTeamCombat

logger = Logger.get_logger(__name__)

_team_logic_cache = {}


def load_team_logic(preset_id):
    """加载预设的队伍逻辑类;无代码或加载失败返回 None。"""
    if not preset_id:
        return None
    from src.team_preset.TeamPresetStore import TeamPresetStore
    path = TeamPresetStore.get_team_code_path(preset_id)
    if not path.exists():
        return None
    try:
        return _load_team_logic_from_file(preset_id, path)
    except Exception as e:
        logger.error(f"load team logic failed for {preset_id}: {e}")
        clear_team_logic_cache(preset_id)
        return None


def clear_team_logic_cache(preset_id=None):
    if preset_id is None:
        _team_logic_cache.clear()
    else:
        _team_logic_cache.pop(preset_id, None)


def _load_team_logic_from_file(preset_id, path):
    stat = path.stat()
    cached = _team_logic_cache.get(preset_id)
    if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]

    module_name = f"ok_ww_team_logic_{preset_id}_{stat.st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load team logic module: {path}")

    module = importlib.util.module_from_spec(spec)
    module.BaseTeamCombat = BaseTeamCombat
    spec.loader.exec_module(module)
    candidates = [obj for obj in vars(module).values()
                  if isinstance(obj, type) and issubclass(obj, BaseTeamCombat)
                  and obj is not BaseTeamCombat]
    if not candidates:
        raise RuntimeError("Team logic must define a class inheriting BaseTeamCombat")

    _team_logic_cache[preset_id] = (stat.st_mtime_ns, stat.st_size, candidates[0])
    return candidates[0]


# ---------- 试运行 ----------

class _FakeChar:
    """试运行用的假角色:所有动作 no-op,只有状态字段可读。"""

    def __init__(self, index, char_name):
        self.index = index
        self.char_name = char_name
        self.is_current_char = index == 0
        self.last_switch_in_time = 0.0
        self.has_intro = False
        self.has_sub_dps_intro = False

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return False
        return _noop


class _FakeTask:
    """试运行用的假任务:不截图、不发按键,只计数帧数。"""

    skip_combat_check = False
    in_liberation = False

    def __init__(self):
        self.frames = 0

    def next_frame(self):
        self.frames += 1

    def sleep(self, sec, check_combat=True):
        pass

    def check_combat(self):
        pass

    def send_key(self, key):
        pass

    def click(self):
        pass

    def in_team(self):
        return True, 0, 3

    def raise_not_in_combat(self, msg):
        raise RuntimeError(msg)

    def get_cd(self, box_name, index):
        return 0.0

    def update_lib_portrait_icon(self):
        pass

    def log_info(self, msg):
        pass

    def log_debug(self, msg):
        pass

    def log_error(self, msg):
        logger.debug(f"team logic test run log: {msg}")

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return None
        return _noop


def test_run_team_logic(preset_id, frames=120):
    """在无战斗的模拟环境里试运行队伍逻辑。

    编译失败或第 n 帧抛异常返回 (False, 消息);跑满 frames 帧返回 (True, 消息)。
    不产生任何真实按键/截图,可安全在 GUI 中同步调用。
    """
    cls = load_team_logic(preset_id)
    if cls is None:
        return False, "failed to load team logic (see logs)"
    task = _FakeTask()
    chars = [_FakeChar(i, f"Char{i + 1}") for i in range(3)]
    logic = cls(task, chars)
    try:
        for _ in range(frames):
            logic.perform()
            task.next_frame()
    except Exception as e:
        return False, f"frame {task.frames}: {type(e).__name__}: {e}"
    return True, f"ran {frames} frames without error"