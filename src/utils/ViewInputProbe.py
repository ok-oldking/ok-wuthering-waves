"""大地图视图输入采集探针：把鼠标动作与匹配结果记录到独立日志文件。

目的
----
为"渲染层自行响应拖动/滚轮（航位推算），把匹配降级为低频纠偏"这个方案做前置标定。
渲染变换只有两个自由度（视图中心的游戏坐标 + 像素/游戏单位的 scale，见
``map_geometry.project_game_to_screen``），而拖动改前者、滚轮改后者，因此只要把
"鼠标输入"与"匹配算出的真实视图变化"配对记录下来，就能标定：

- 滚轮 1 tick 对应多少倍缩放，是否离散档位，是否有补间动画
- 缩放是否锚定光标（若锚定，视图中心会随缩放移动）
- 拖动 1 屏幕像素对应多少游戏单位（理论上等于 game_scale），边界是否钳制/回弹
- 匹配延迟与推算误差的量级

设计约束
--------
- **只读、不干预**：用 ``pynput.mouse.Listener``（非侵入监听，不吞事件），不使用
  ``SetWindowsHookEx``；不改渲染、不改匹配逻辑
- 交互覆盖层用 ``setMask`` 把窗口限制在命中框内，掩码外的拖动/滚轮不会进 Qt，
  所以只能走系统级监听
- 监听回调在 pynput 线程，这里只做"写文件"这一件事，不碰 Qt（沿用
  ``on_advance_hotkey`` 的既有范式）
- 默认关闭，异常全部吞掉，任何失败都不影响主流程

产物
----
JSONL（每行一个事件），默认 ``logs/view_probe/view_probe_{时间戳}.jsonl``：

- ``{"t":…, "e":"session", …}``       探针启动/停止、屏幕与窗口信息
- ``{"t":…, "e":"bigmap", "on":1}``   进入/离开大地图界面
- ``{"t":…, "e":"press"/"release", "btn":…, "x":…, "y":…}``
- ``{"t":…, "e":"drag", "x":…, "y":…, "dx":…, "dy":…, "btn":…}``  按住移动（已抽稀）
- ``{"t":…, "e":"move", "x":…, "y":…}``      未按键移动（默认不记，见 ``log_moves``）
- ``{"t":…, "e":"scroll", "x":…, "y":…, "dx":…, "dy":…}``
- ``{"t":…, "e":"match", "map":…, "cx":…, "cy":…, "game_scale":…, "map_scale":…,
   "conf":…, "inliers":…, "matches":…, "crop":…, "full":…, "ms":…}``
   ``cx/cy`` 是匹配算出的**视图中心游戏坐标**，与 ``_last_valid*100`` 同量纲

``t`` 为 ``time.perf_counter()`` 单调时钟（秒，float），同一文件内可直接相减；
``wall`` 仅在 session 行给出一次墙钟时间用于对齐外部录屏。
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Optional

logger = None
try:  # 日志器可选，缺失时静默
    from ok import Logger
    logger = Logger.get_logger(__name__)
except Exception:  # pragma: no cover - 仅在脱离 ok 环境时
    import logging
    logger = logging.getLogger(__name__)

#: 拖动事件抽稀：同一次拖动内两条记录的最小间隔（秒）。0 = 全记。
DRAG_MIN_INTERVAL = 0.008
#: 未按键移动的抽稀间隔（秒），仅在 log_moves=True 时生效。
MOVE_MIN_INTERVAL = 0.05


class ViewInputProbe:
    """鼠标动作 + 匹配结果的配对采集器（线程安全，失败静默）。"""

    def __init__(self, log_dir: str, log_moves: bool = False,
                 drag_min_interval: float = DRAG_MIN_INTERVAL,
                 move_min_interval: float = MOVE_MIN_INTERVAL):
        self._dir = log_dir
        self._log_moves = log_moves
        self._drag_min = drag_min_interval
        self._move_min = move_min_interval
        self._fp = None
        self._path: Optional[str] = None
        self._watcher = None
        self._owns_watcher = False
        self._lock = threading.Lock()
        self._last_drag_t = 0.0
        self._last_move_t = 0.0
        self._started = False
        self._counts = {}

    # ------------------------------------------------------------------ 生命周期
    @property
    def path(self) -> Optional[str]:
        return self._path

    @property
    def started(self) -> bool:
        return self._started

    def start(self, extra: Optional[dict] = None, watcher=None) -> bool:
        """打开日志文件并订阅鼠标事件；返回是否成功。

        ``watcher`` 为 :class:`src.utils.MouseWatcher.MouseWatcher`。缺省时自建一个，
        但推荐由调用方传入共享实例（与视图推算共用同一个监听线程）。
        """
        if self._started:
            return True
        try:
            os.makedirs(self._dir, exist_ok=True)
            stamp = time.strftime('%Y%m%d_%H%M%S')
            self._path = os.path.join(self._dir, f'view_probe_{stamp}.jsonl')
            self._fp = open(self._path, 'a', encoding='utf-8', buffering=1)
        except Exception as exc:
            logger.warning(f'[ViewProbe] 无法打开日志文件: {exc}')
            self._fp = None
            return False

        self._write('session', state='start', wall=time.time(),
                    log_moves=self._log_moves, **(extra or {}))
        try:
            if watcher is None:
                from src.utils.MouseWatcher import MouseWatcher
                watcher = MouseWatcher(emit_moves=self._log_moves)
                self._owns_watcher = True
            self._watcher = watcher
            watcher.subscribe(self)
            if watcher.available is False:
                self._write('session', state='mouse_unavailable')
        except Exception as exc:
            logger.warning(f'[ViewProbe] 订阅鼠标事件失败，只记录匹配事件: {exc}')
            self._watcher = None
            self._write('session', state='mouse_unavailable', error=str(exc))

        self._started = True
        logger.info(f'[ViewProbe] 采集中 -> {self._path}'
                    + ('（无鼠标监听）' if self._watcher is None else ''))
        return True

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        try:
            if self._watcher is not None:
                self._watcher.unsubscribe(self)
                if self._owns_watcher:
                    self._watcher.stop()
        except Exception as exc:  # pragma: no cover
            logger.warning(f'[ViewProbe] 退订鼠标事件失败: {exc}')
        self._watcher = None
        self._write('session', state='stop', counts=dict(self._counts))
        try:
            if self._fp is not None:
                self._fp.close()
        except Exception:
            pass
        self._fp = None
        logger.info(f'[ViewProbe] 已停止，事件统计 {self._counts}，文件 {self._path}')

    # ------------------------------------------------------------------ 写入
    def _write(self, event: str, **fields) -> None:
        fp = self._fp
        if fp is None:
            return
        rec = {'t': round(time.perf_counter(), 6), 'e': event}
        rec.update(fields)
        line = json.dumps(rec, ensure_ascii=False, default=str)
        try:
            with self._lock:
                fp.write(line + '\n')
                self._counts[event] = self._counts.get(event, 0) + 1
        except Exception:
            pass

    # ------------------------------------------------ MouseWatcher 订阅者回调
    def on_mouse_drag(self, x, y, dx, dy, buttons, t):
        if not self._started:
            return
        if self._drag_min and t - self._last_drag_t < self._drag_min:
            return
        self._last_drag_t = t
        self._write('drag', x=x, y=y, dx=dx, dy=dy, btn=list(buttons))

    def on_mouse_move(self, x, y, t):
        if not self._started:
            return
        if t - self._last_move_t >= self._move_min:
            self._last_move_t = t
            self._write('move', x=x, y=y)

    def on_mouse_press(self, x, y, button, t):
        if not self._started:
            return
        self._last_drag_t = 0.0
        self._write('press', x=x, y=y, btn=button)

    def on_mouse_release(self, x, y, button, t):
        if not self._started:
            return
        self._write('release', x=x, y=y, btn=button)

    def on_mouse_scroll(self, x, y, dx, dy, t):
        if not self._started:
            return
        self._write('scroll', x=x, y=y, dx=dx, dy=dy)

    # ------------------------------------------------------------------ 主流程调用
    def log_bigmap(self, on: bool) -> None:
        """进入/离开大地图界面，用于切分会话段。"""
        self._write('bigmap', on=1 if on else 0)

    def log_match(self, *, map_id, result, game_scale, crop_size, full_map,
                  view_center=None) -> None:
        """记录一次大地图匹配（成功或失败都记，失败用于统计中断）。

        ``view_center`` 为最终采用的视图中心游戏坐标 ``(gx, gy)``；缺省时用
        ``result.game_center``。
        """
        try:
            gc = view_center if view_center is not None else getattr(result, 'game_center', None)
            self._write(
                'match',
                map=map_id,
                ok=1 if getattr(result, 'success', False) else 0,
                cx=None if not gc else round(float(gc[0]), 2),
                cy=None if not gc else round(float(gc[1]), 2),
                game_scale=None if game_scale is None else round(float(game_scale), 6),
                map_scale=round(float(getattr(result, 'map_scale', 0.0) or 0.0), 6),
                conf=round(float(getattr(result, 'confidence', 0.0) or 0.0), 4),
                inliers=int(getattr(result, 'inlier_count', 0) or 0),
                matches=int(getattr(result, 'match_count', 0) or 0),
                crop=crop_size,
                full=1 if full_map else 0,
                ms=round(float(getattr(result, 'elapsed_ms', 0.0) or 0.0), 1),
            )
        except Exception:
            pass

    def log_match_failed(self, *, crop_size, full_map, reason='') -> None:
        self._write('match', ok=0, crop=crop_size, full=1 if full_map else 0,
                    reason=reason or None)
