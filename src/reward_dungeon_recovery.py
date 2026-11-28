"""云鸣潮「战斗奖励副本」出错后的现场续打（无音区/伪造挑战/模拟等）。

云游戏浏览器重启后，云端会话通常仍停在副本里。ok-ww 的 ``ensure_main()``
看到 ``in_realm()`` 会按 Esc + 确认框退出副本；随后 DailyTask 又从 F2 图鉴
重新进本。表现就是「一次识别错误 → 丢掉正在打的这一场 → 重进副本」，
云游戏延迟大时还会连续多扣体力。

本模块只在**确认画面仍在战斗奖励副本**时接管恢复：

1. 等云端画面回到副本（不发送 Esc）；
2. 仍在战斗 → ``combat_once`` 续打；
3. 等战斗结束（血量/锁定图标消失）；
4. 有「领取」F 提示或宝箱图标 → 按 F 领奖；
5. 从副本菜单正常退出，把控制权交回原任务流程。

任何一步判定失败都只返回 False，让上层走原来的恢复路径，绝不吞掉异常。
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# 浏览器重开后等云端会话回到副本的时间；回大世界则立刻放弃等待。
DEFAULT_SETTLE_TIMEOUT = 60
# 续打一场战斗的超时（云游戏延迟比本地大，别用本地的 200 秒上限）。
DEFAULT_COMBAT_TIMEOUT = 120
# 战斗打完后等奖励出现的时间。
DEFAULT_REWARD_TIMEOUT = 20


def _call(task, name, *args, **kwargs):
    """调用任务上的可选方法；不存在或抛异常都返回 None，不打断恢复。"""
    method = getattr(task, name, None)
    if not callable(method):
        return None
    try:
        return method(*args, **kwargs)
    except Exception as error:  # noqa: BLE001 - 恢复路径宁可保守失败
        logger.debug('%s failed during reward dungeon recovery: %s', name, error)
        return None


def _log(task, level: str, message: str, *, notify: bool = False) -> None:
    method = getattr(task, level, None)
    if callable(method):
        try:
            method(message, notify=notify) if notify else method(message)
        except Exception:  # noqa: BLE001 - 日志不能影响恢复
            pass
    else:
        getattr(logger, 'info' if level == 'log_info' else 'warning')(message)


def is_browser(task) -> bool:
    """只给云鸣潮浏览器设备做副本续打；PC / 安卓保持原行为。"""
    method = getattr(task, 'is_browser', None)
    if not callable(method):
        return True
    return bool(_call(task, 'is_browser'))


def in_reward_dungeon(task) -> bool:
    """当前画面是否仍在战斗奖励副本中（只读画面，不发送任何按键）。

    ``in_realm()`` 只说明在副本类场景；再要求能看到战斗 HUD、F 提示、宝箱
    或体力领取标记，避免把纯过场/加载画面误判成"正在打副本"。
    """
    if not is_browser(task) or not _call(task, 'in_realm'):
        return False
    return bool(
        _call(task, 'in_combat')
        or _call(task, 'check_health_bar')
        or _call(task, 'find_f_with_claim_text')
        or _call(task, 'find_f_with_text')
        or _call(task, 'find_treasure_icon')
        or _call(task, 'has_claim_stamina')
    )


def wait_for_dungeon(task, timeout: float = DEFAULT_SETTLE_TIMEOUT) -> bool:
    """等云端会话回到副本；明确回到大世界就立刻放弃。"""
    deadline = time.monotonic() + timeout
    while True:
        if in_reward_dungeon(task):
            return True
        if _call(task, 'in_world'):
            return False
        if time.monotonic() >= deadline:
            return False
        _call(task, 'sleep', 1)
        _call(task, 'next_frame')


def resume_combat(task, timeout: float = DEFAULT_COMBAT_TIMEOUT) -> bool:
    """如果还在战斗中，续打至脱战；返回是否实际打过。"""
    if not (_call(task, 'in_combat') or _call(task, 'check_health_bar')):
        return False
    _log(task, 'log_info', '云鸣潮副本中断：检测到未结束的战斗，先续打当前战斗。')
    _call(task, 'combat_once', target=True, wait_combat_time=timeout,
          raise_if_not_found=False)
    return True


def wait_combat_end(task, timeout: float = DEFAULT_REWARD_TIMEOUT) -> bool:
    """探测战斗是否已经结束；超时返回 False（仍然继续尝试领奖）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not (_call(task, 'in_combat') or _call(task, 'check_health_bar')):
            _log(task, 'log_info', '云鸣潮副本中断：战斗已结束，检查奖励。')
            return True
        _call(task, 'sleep', 0.5)
        _call(task, 'next_frame')
    _log(task, 'log_warning', '云鸣潮副本中断：等待战斗结束超时，仍尝试领取奖励。')
    return False


def claim_reward(task) -> bool:
    """按 F 领取当前副本奖励（含走到宝箱）；返回是否执行过领奖动作。"""
    if _call(task, 'find_f_with_claim_text'):
        _log(task, 'log_info', '云鸣潮副本中断：发现「领取」提示，按 F 领取奖励。')
        _call(task, 'send_key', 'f', after_sleep=1)
        return True
    if _call(task, 'find_treasure_icon'):
        _log(task, 'log_info', '云鸣潮副本中断：发现宝箱，走过去按 F 领取奖励。')
        _call(task, 'walk_to_treasure', send_f=True, raise_if_not_found=False)
        return True
    if _call(task, 'find_f_with_text'):
        # 普通 F 提示（声骸/残留拾取），按了不影响副本流程。
        _call(task, 'pick_f', handle_claim=False)
        return True
    return False


def leave_dungeon(task, timeout: float = 120) -> bool:
    """从副本菜单正常退出，交回大世界；不走 ensure_main 的自动 Esc 分支。"""
    if not _call(task, 'in_realm'):
        return True
    _call(task, 'send_key', 'esc', after_sleep=1)
    _call(task, 'wait_click_feature', 'gray_confirm_exit_button', relative_x=-1,
          raise_if_not_found=False, time_out=3, click_after_delay=0.5,
          threshold=0.7, after_sleep=1)
    _call(task, 'wait_in_team_and_world', time_out=timeout, raise_if_not_found=False)
    left = not _call(task, 'in_realm')
    if not left:
        _log(task, 'log_warning', '云鸣潮副本中断：未能确认退出副本，请检查画面。')
    return left


def resume_reward_dungeon(
    task,
    *,
    settle_timeout: float = DEFAULT_SETTLE_TIMEOUT,
    combat_timeout: float = DEFAULT_COMBAT_TIMEOUT,
    reward_timeout: float = DEFAULT_REWARD_TIMEOUT,
    leave: bool = True,
) -> bool:
    """出错重启后优先续打当前副本并领奖。

    Returns:
        True  = 确实在副本里接管过现场（调用方不应再"重进副本"）；
        False = 不在副本/未等到副本画面，走原来的恢复流程。
    """
    if not wait_for_dungeon(task, timeout=settle_timeout):
        return False

    _log(task, 'log_info', '云鸣潮仍在战斗奖励副本中：先续打并领取奖励，不重进副本。',
         notify=True)
    fought = resume_combat(task, timeout=combat_timeout)
    ended = wait_combat_end(task, timeout=reward_timeout) if fought else True
    claimed = claim_reward(task)
    if leave:
        leave_dungeon(task)

    _log(task, 'log_info',
         '云鸣潮副本现场恢复完成：{fought} / 战斗结束 {ended} / 已按 F 领奖 {claimed}'
         .format(fought='续打' if fought else '无需续打',
                 ended='是' if ended else '未确认',
                 claimed='是' if claimed else '否'), notify=True)
    return True
