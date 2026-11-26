"""云鸣潮任务出错后的自动恢复：重启浏览器 → 重新进入游戏 → 重跑任务。

云游戏是网页应用，运行期的识别超时、页面卡住、断线等问题常常连页面刷新都
救不回来（页面内存里的会话/WebSocket 已经坏掉）。最可靠的办法是关闭旧浏览器
再用该账号自己的 Cookie profile 打开一个全新实例；浏览器重启不可用时再回退
到页面导航/reload。ok-script 默认会让任何异常终止 onetime task；本模块把这些
异常转成"有限次自动重启"，只有用户主动停止或明确的前置条件错误才直接抛出。

出错时若正处在无音区等战斗奖励副本里，浏览器重启后云端会话往往还在副本中：
先由 ``src.reward_dungeon_recovery`` 续打/检测战斗结束/按 F 领奖，而不是被
``ensure_main`` 的自动 Esc 踢出副本、再从 F2 图鉴重进（白丢这一场）。

用法::

    from src.cloud_recovery import FatalTaskError, run_with_cloud_recovery

    def run(self):
        def runner():
            ...
        run_with_cloud_recovery(self, runner, name=self.name)
"""

from __future__ import annotations

from typing import Callable

from ok.task.exceptions import FinishedException, TaskDisabledException

from src import cloud_browser, reward_dungeon_recovery

# 默认最多重启 5 次，避免任务在永久性错误上无限循环。
DEFAULT_MAX_RESTARTS = 5
# 刷新后给浏览器一点时间加载 DOM/播放器，再开始识别画面。
PAGE_SETTLE_SECONDS = 5
# 同样的错误连续出现这么多次，说明刷新解决不了(代码/配置错误)，提前停止。
REPEAT_ERROR_LIMIT = 3
# 出错时默认真正重启浏览器(关闭旧实例 + 用账号 profile 重开)，而不是只刷新页面。
# 云游戏断线/卡死后页面内存里的会话已损坏，只有重开浏览器才能可靠恢复。
DEFAULT_RESTART_BROWSER_ON_ERROR = True
# 出错时在战斗奖励副本里，重启后先续打/领奖，不再从头重进副本。
DEFAULT_RESUME_REWARD_DUNGEON = True

# 这些异常永远不应该被"刷新重启"吞掉。
_NEVER_RETRY = (TaskDisabledException, FinishedException, SystemExit, KeyboardInterrupt)


class FatalTaskError(RuntimeError):
    """用户侧前置条件不满足；刷新页面无法修复，直接停止任务。"""


def _is_stopped(task) -> bool:
    executor = getattr(task, 'executor', None)
    event = getattr(executor, 'exit_event', None)
    return bool(event is not None and event.is_set())


def _error_signature(error: BaseException) -> tuple[str, str]:
    """用于判断是不是同一个错误反复出现。"""
    return (type(error).__name__, str(error)[:200])


def _max_restarts(task, override) -> int:
    if override is not None:
        try:
            return max(0, int(override))
        except (TypeError, ValueError):
            return DEFAULT_MAX_RESTARTS
    saved = getattr(task, 'config', None) or {}
    for key in ('Cloud Error Restarts', 'CloudAutoRestartCount'):
        if isinstance(saved, dict) and key in saved:
            try:
                return max(0, int(saved[key]))
            except (TypeError, ValueError):
                break
    return DEFAULT_MAX_RESTARTS


def _restart_browser_on_error(task, override) -> bool:
    if override is not None:
        return bool(override)
    saved = getattr(task, 'config', None) or {}
    for key in ('Cloud Restart Browser On Error',):
        if isinstance(saved, dict) and key in saved:
            return bool(saved[key])
    return DEFAULT_RESTART_BROWSER_ON_ERROR


def _resume_reward_dungeon(task, override=None) -> bool:
    """任务配置里可以把副本续打关掉（默认开）。"""
    if override is not None:
        return bool(override)
    saved = getattr(task, 'config', None) or {}
    if isinstance(saved, dict) and 'Cloud Resume Reward Dungeon' in saved:
        return bool(saved['Cloud Resume Reward Dungeon'])
    return DEFAULT_RESUME_REWARD_DUNGEON


def snapshot_reward_dungeon(task) -> bool:
    """出错瞬间记录"是否正在战斗奖励副本里"，供重启后决定是否现场续打。"""
    try:
        value = bool(reward_dungeon_recovery.in_reward_dungeon(task))
    except Exception:  # pragma: no cover - 探测失败就走原流程
        value = False
    task._cloud_in_reward_dungeon_before_error = value
    return value


def wait_cloud_ready(task, time_out: int = 600) -> bool:
    """等到云鸣潮真正进入大世界。

    云游戏要经过「云游戏首页 → 进入游戏 → 排队/加载 → 登录/月卡 → 大世界」几段
    画面, 期间点击会落在加载页上。``ensure_main`` 已经包含登录框、"进入游戏"按钮、
    月卡弹窗和断线重连的处理, 这里只需要把 ``logged_in`` 复位(让它自动加长超时)
    并且关掉 esc(避免在加载页按返回退回云游戏首页)。
    """
    task.logged_in = False
    if hasattr(task, '_cloud_start_click_time'):
        task._cloud_start_click_time = 0
    if hasattr(task, '_cloud_start_clicks'):
        task._cloud_start_clicks = 0
    task.ensure_main(esc=False, time_out=time_out)
    return True


def refresh_cloud_game(task, *, wait_ready: bool = True, time_out: int = 600,
                       restart_browser: bool | None = None,
                       resume_dungeon: bool | None = None) -> bool:
    """出错后重启云鸣潮浏览器并（可选）等待云端重新进入大世界。

    默认关闭旧浏览器、用当前账号的 Cookie profile 打开一个全新实例——云游戏
    断线或页面卡死后，页面内存里的会话已经损坏，单纯 reload 救不回来。若重启
    浏览器不可用（例如设备管理器缺失），回退到页面导航/reload。

    出错前若正在战斗奖励副本里，重启后先尝试现场续打并按 F 领奖，成功则跳过
    ``wait_cloud_ready``（它的 ``ensure_main`` 会把我们踢出副本）。

    返回是否成功重启/刷新。失败不抛异常，调用方仍会尝试重跑任务，因为有些错误
    与页面本身无关（例如一次识别抖动）。
    """
    use_browser_restart = _restart_browser_on_error(task, restart_browser)
    if use_browser_restart:
        task.log_warning(task.tr('云鸣潮出错，正在重启浏览器并重新开始任务…'), notify=True)
    else:
        task.log_warning(task.tr('云鸣潮出错，正在刷新页面并重新开始任务…'), notify=True)

    reloaded = False
    if use_browser_restart:
        try:
            # 必须显式带上当前账号：restart_browser 若猜 default，会把正在用的
            # profile 换成 default（甚至空目录），表现就是"重启任务后掉登录"。
            account = cloud_browser.resolve_account()
            reloaded = bool(cloud_browser.restart_browser(
                task, account_key=account, save_previous=False))
        except Exception as error:  # pragma: no cover - depends on live browser
            task.log_warning(task.tr('重启浏览器失败：{error}').format(error=error))
            reloaded = False
        if not reloaded:
            task.log_warning(task.tr('浏览器重启不可用，回退到刷新页面。'))

    if not reloaded:
        try:
            reloaded = cloud_browser.restart_page(task)
        except Exception as error:  # pragma: no cover - depends on live browser
            task.log_warning(task.tr('刷新云鸣潮页面失败：{error}').format(error=error))
            try:
                reloaded = cloud_browser.reload_page(task)
            except Exception as fallback_error:  # pragma: no cover
                task.log_warning(
                    task.tr('重试刷新页面仍失败：{error}').format(error=fallback_error))
    if not reloaded:
        task.log_warning(task.tr('未能重启或刷新浏览器页面，将直接重试任务。'))

    task.sleep(PAGE_SETTLE_SECONDS)

    # 重置"已进入游戏/刚点过进入游戏"的标记，让下一轮能重新点击一次进入游戏。
    task.logged_in = False
    if hasattr(task, '_cloud_start_click_time'):
        task._cloud_start_click_time = 0
    if hasattr(task, '_cloud_start_clicks'):
        task._cloud_start_clicks = 0
    try:
        task.next_frame()
    except _NEVER_RETRY:
        raise
    except Exception as error:  # pragma: no cover - capture may be briefly busy
        task.log_warning(task.tr('刷新后重新截取画面失败：{error}').format(error=error))

    # 战斗奖励副本现场优先：云端会话还在副本里时先续打/领奖，绝不让
    # ensure_main 的自动 Esc 把这一场丢掉再从 F2 重进。
    task._cloud_reward_resumed = False
    if (_resume_reward_dungeon(task, resume_dungeon)
            and getattr(task, '_cloud_in_reward_dungeon_before_error', False)
            and not _is_stopped(task)):
        try:
            resumed = reward_dungeon_recovery.resume_reward_dungeon(task)
        except Exception as error:  # pragma: no cover - 恢复本身失败走原路径
            task.log_warning(task.tr('副本现场恢复失败，按原流程重新开始：{error}')
                             .format(error=error))
            resumed = False
        if resumed:
            task._cloud_reward_resumed = True
            return reloaded

    if wait_ready and not _is_stopped(task):
        try:
            wait_cloud_ready(task, time_out=time_out)
        except _NEVER_RETRY:
            raise
        except Exception as error:
            task.log_warning(
                task.tr('刷新后等待进入游戏失败，将继续重试任务：{error}').format(error=error))
            return False
    return reloaded


def run_with_cloud_recovery(
    task,
    runner: Callable[[], object],
    *,
    name: str | None = None,
    max_restarts: int | None = None,
    refresh_page: bool = True,
    wait_ready: bool = True,
    time_out: int = 600,
    restart_browser: bool | None = None,
    resume_dungeon: bool | None = None,
):
    """运行 ``runner``，出错时刷新云游戏页面并从头重跑任务。

    ``runner`` 可调用多次，必须是幂等的完整任务流程（例如重新等待进入游戏
    后重新执行 DailyTask.run）。用户点停止、任务禁用、应用退出等异常会原样
    抛出；``FatalTaskError``（前置条件错误）也不重试。

    若出错时正在战斗奖励副本，先把现场续打完再重跑任务（见
    ``refresh_cloud_game`` 的 ``resume_dungeon``）。
    """
    limit = _max_restarts(task, max_restarts)
    label = name or getattr(task, 'name', '云鸣潮任务')
    restarts = 0
    last_signature = None
    repeated = 0
    task._cloud_in_reward_dungeon_before_error = False
    task._cloud_reward_resumed = False

    while True:
        if _is_stopped(task):
            raise TaskDisabledException()
        try:
            return runner()
        except _NEVER_RETRY:
            raise
        except FatalTaskError:
            raise
        except Exception as error:
            try:
                is_cloud = bool(task.is_browser())
            except Exception:
                is_cloud = False
            # 本地客户端沿用原有的错误处理逻辑，不刷新网页。
            if not is_cloud:
                raise

            restarts += 1
            task.log_error(task.tr('{name} 运行出错').format(name=label), error)

            # 在画面还没被重启/刷新破坏前记录是否在奖励副本，供恢复链决定
            # 「现场续打」还是「正常重进」。探测失败就当不在副本。
            task._cloud_reward_resumed = False
            if _resume_reward_dungeon(task, resume_dungeon) and refresh_page:
                snapshot_reward_dungeon(task)
            else:
                task._cloud_in_reward_dungeon_before_error = False

            signature = _error_signature(error)
            if signature == last_signature:
                repeated += 1
            else:
                last_signature = signature
                repeated = 1

            if repeated >= REPEAT_ERROR_LIMIT:
                # 例如代码里的 super() 用法错误: 每次重启都会在同一处失败,
                # 再刷新页面没有意义, 提前停止并给出明确提示。
                task.log_error(
                    task.tr('{name} 连续 {count} 次出现相同错误，判定为无法自动恢复：{error}')
                    .format(name=label, count=repeated, error=error))
                task.info_set('状态', '执行失败')
                raise
            if restarts > limit:
                task.log_error(
                    task.tr('{name} 已自动重启 {count} 次仍然失败，停止任务。')
                    .format(name=label, count=limit), error)
                task.info_set('状态', '执行失败')
                raise

            task.info_set('状态', task.tr('出错，正在自动重启 {current}/{limit}')
                          .format(current=restarts, limit=limit))
            if refresh_page:
                refresh_cloud_game(task, wait_ready=wait_ready, time_out=time_out,
                                   restart_browser=restart_browser,
                                   resume_dungeon=resume_dungeon)
            else:
                # 活动类任务（如拉海洛方块）刷新页面会丢失当前活动关卡 UI，
                # 这里只重置轻量状态，然后原地重跑任务流程。
                task.log_warning(task.tr('不刷新页面，直接重新开始任务…'))
                task.sleep(1)
                task.logged_in = False
