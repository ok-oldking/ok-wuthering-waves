"""云鸣潮任务出错后的自动恢复：重启浏览器 → 重新进入游戏 → 重跑任务。

云游戏是网页应用，运行期的识别超时、页面卡住、断线等问题常常连页面刷新都
救不回来（页面内存里的会话/WebSocket 已经坏掉）。最可靠的办法是关闭旧浏览器
再用该账号自己的 Cookie profile 打开一个全新实例；浏览器重启不可用时再回退
到页面导航/reload。ok-script 默认会让任何异常终止 onetime task；本模块把这些
异常转成"有限次自动重启"，只有用户主动停止或明确的前置条件错误才直接抛出。

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

from src import cloud_browser

# 默认最多重启 5 次，避免任务在永久性错误上无限循环。
DEFAULT_MAX_RESTARTS = 5
# 刷新后给浏览器一点时间加载 DOM/播放器，再开始识别画面。
PAGE_SETTLE_SECONDS = 5
# 同样的错误连续出现这么多次，说明刷新解决不了(代码/配置错误)，提前停止。
REPEAT_ERROR_LIMIT = 3
# 出错时默认真正重启浏览器(关闭旧实例 + 用账号 profile 重开)，而不是只刷新页面。
# 云游戏断线/卡死后页面内存里的会话已损坏，只有重开浏览器才能可靠恢复。
DEFAULT_RESTART_BROWSER_ON_ERROR = True

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


def refresh_cloud_game(task, *, wait_ready: bool = True, time_out: int = 600,
                       restart_browser: bool | None = None) -> bool:
    """出错后重启云鸣潮浏览器并（可选）等待云端重新进入大世界。

    默认关闭旧浏览器、用当前账号的 Cookie profile 打开一个全新实例——云游戏
    断线或页面卡死后，页面内存里的会话已经损坏，单纯 reload 救不回来。若重启
    浏览器不可用（例如设备管理器缺失），回退到页面导航/reload。

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
            reloaded = bool(cloud_browser.restart_browser(task, save_previous=False))
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

    if wait_ready and not _is_stopped(task):
        try:
            task.wait_cloud_game_ready(time_out=time_out)
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
):
    """运行 ``runner``，出错时刷新云游戏页面并从头重跑任务。

    ``runner`` 可调用多次，必须是幂等的完整任务流程（例如重新等待进入游戏
    后重新执行 DailyTask.run）。用户点停止、任务禁用、应用退出等异常会原样
    抛出；``FatalTaskError``（前置条件错误）也不重试。
    """
    limit = _max_restarts(task, max_restarts)
    label = name or getattr(task, 'name', '云鸣潮任务')
    restarts = 0
    last_signature = None
    repeated = 0

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
                                   restart_browser=restart_browser)
            else:
                # 活动类任务（如拉海洛方块）刷新页面会丢失当前活动关卡 UI，
                # 这里只重置轻量状态，然后原地重跑任务流程。
                task.log_warning(task.tr('不刷新页面，直接重新开始任务…'))
                task.sleep(1)
                task.logged_in = False
