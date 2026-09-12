"""全局鼠标监听器：把规范化事件分发给多个订阅者。

为什么需要
----------
交互覆盖层用 ``setMask`` 把窗口形状限制在图标命中框内，掩码外的拖动/滚轮**不会**进
Qt（直接落到游戏），所以想观察玩家对大地图的拖动与缩放只能走系统级监听。这里用
``pynput.mouse.Listener``（非侵入监听，不吞事件，不影响游戏收到输入），并把它做成
单一来源 + 多订阅者，避免"采集探针"和"视图推算"各起一个监听线程。

订阅者接口
----------
订阅者是一个对象，可选实现下列方法（缺哪个就不会被调用）：

- ``on_mouse_press(x, y, button, t)``
- ``on_mouse_release(x, y, button, t)``
- ``on_mouse_drag(x, y, dx, dy, buttons, t)``   按住移动
- ``on_mouse_move(x, y, t)``                    未按键移动（默认不分发，见 ``emit_moves``）
- ``on_mouse_scroll(x, y, dx, dy, t)``

``x/y`` 是屏幕绝对坐标（pynput 原样给出），``t`` 是 ``time.perf_counter()``。
回调在监听线程执行，订阅者自己负责线程安全且必须快速返回（不要碰 Qt）。
"""

from __future__ import annotations

import threading
import time
from typing import List

try:
    from ok import Logger
    logger = Logger.get_logger(__name__)
except Exception:  # pragma: no cover - 脱离 ok 环境
    import logging
    logger = logging.getLogger(__name__)


class MouseWatcher:
    """单例式全局鼠标监听（失败静默降级，不影响主流程）。"""

    def __init__(self, emit_moves: bool = False):
        self._subs: List[object] = []
        self._lock = threading.Lock()
        self._listener = None
        self._pressed = set()
        self._last_xy = None
        self._emit_moves = emit_moves
        self._available = None  # None=未尝试, True/False=监听是否可用

    # ------------------------------------------------------------------ 生命周期
    @property
    def available(self):
        return self._available

    @property
    def running(self):
        return self._listener is not None

    def subscribe(self, sub) -> None:
        with self._lock:
            if sub not in self._subs:
                self._subs.append(sub)
        self.start()

    def unsubscribe(self, sub) -> None:
        with self._lock:
            if sub in self._subs:
                self._subs.remove(sub)
            empty = not self._subs
        if empty:
            self.stop()

    def start(self) -> bool:
        if self._listener is not None:
            return True
        try:
            from pynput import mouse
            self._listener = mouse.Listener(
                on_move=self._on_move, on_click=self._on_click,
                on_scroll=self._on_scroll)
            self._listener.daemon = True
            self._listener.start()
            self._available = True
            logger.info('[MouseWatcher] 全局鼠标监听已启动')
            return True
        except Exception as exc:
            self._listener = None
            self._available = False
            logger.warning(f'[MouseWatcher] 监听启动失败，视图推算/探针将退化: {exc}')
            return False

    def stop(self) -> None:
        listener, self._listener = self._listener, None
        if listener is None:
            return
        try:
            listener.stop()
        except Exception as exc:  # pragma: no cover
            logger.warning(f'[MouseWatcher] 停止监听失败: {exc}')
        self._pressed.clear()
        self._last_xy = None
        logger.info('[MouseWatcher] 全局鼠标监听已停止')

    # ------------------------------------------------------------------ 分发
    def _fanout(self, method: str, *args) -> None:
        with self._lock:
            subs = list(self._subs)
        for s in subs:
            fn = getattr(s, method, None)
            if fn is None:
                continue
            try:
                fn(*args)
            except Exception as exc:  # 单个订阅者异常不影响其它
                logger.warning(f'[MouseWatcher] {method} 订阅者异常: {exc}')

    # ------------------------------------------------------------------ pynput 回调
    def _on_move(self, x, y):
        t = time.perf_counter()
        last = self._last_xy
        self._last_xy = (x, y)
        if self._pressed:
            dx = x - last[0] if last else 0
            dy = y - last[1] if last else 0
            self._fanout('on_mouse_drag', x, y, dx, dy,
                         tuple(sorted(self._pressed)), t)
        elif self._emit_moves:
            self._fanout('on_mouse_move', x, y, t)

    def _on_click(self, x, y, button, pressed):
        t = time.perf_counter()
        name = getattr(button, 'name', str(button))
        self._last_xy = (x, y)
        if pressed:
            self._pressed.add(name)
            self._fanout('on_mouse_press', x, y, name, t)
        else:
            self._pressed.discard(name)
            self._fanout('on_mouse_release', x, y, name, t)

    def _on_scroll(self, x, y, dx, dy):
        self._fanout('on_mouse_scroll', x, y, dx, dy, time.perf_counter())
