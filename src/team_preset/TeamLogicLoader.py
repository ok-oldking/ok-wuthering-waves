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