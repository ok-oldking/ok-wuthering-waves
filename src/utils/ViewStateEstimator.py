"""大地图视图状态推算（航位推算）：用鼠标输入在两次匹配之间维持视图状态。

背景
----
大地图叠加层的渲染变换只有两个自由度（见 ``map_geometry.project_game_to_screen``）：

- 视图中心的游戏坐标 ``center``
- ``game_scale``（游戏单位 / 屏幕像素，越小越放大）

而拖动只改前者、滚轮只改后者，所以完全可以由鼠标输入推算，把特征匹配从"每帧的定位
来源"降级为"低频纠偏"。这样能同时解决两个实测问题：匹配间隔造成的渲染滞后（实测
中位 67 px、p90 106 px），以及操作瞬态下的定位丢失（实测 76~90% 的匹配失败都发生在
鼠标操作 0.5 s 内）。

标定值（来自 ``logs/view_probe`` 两份真机日志，见 ``_mapbench/settle_curve.py``）
--------------------------------------------------------------------------------
- 拖动：``Δcenter = -Δmouse_px × game_scale``，严格 1:1（松手瞬间观测/预期 1.03~1.05）
- 滚轮：每 tick ``game_scale × 1.0299``（缩小方向），放大方向取倒数 0.9710；
  n=34、散布 0.0177
- 缩放锚点：**不是**严格锚定光标，而是朝光标方向补偿 ``0.745×``；该系数在稳定时间
  0.5~1.2 s 内恒定（p25 0.737 / p75 0.749，两份日志一致，方向 cos 0.999），
  因此是固定阻尼而非补间动画
- 快甩（松手速度 > 2000 px/s）：松手后继续滑行约 50% 位移，0.3 s 内衰减完
- 滑块无级缩放：不推算（无法从鼠标推断），靠匹配纠偏

设计
----
纯逻辑、无 Qt、无 IO、可单测。鼠标回调在监听线程调用，任务线程读取状态，故内部加锁。
``confidence`` 随推算时长与动作类型衰减，供调用方决定是否信任推算值。
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

try:
    from ok import Logger
    logger = Logger.get_logger(__name__)
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ViewState:
    """某一时刻的视图状态快照。"""

    center: Tuple[float, float]   # 视图中心游戏坐标
    game_scale: float             # 游戏单位 / 屏幕像素
    confidence: float             # 0~1，1 = 刚由匹配确认
    source: str                   # 'match' | 'drag' | 'scroll' | 'coast'
    t: float

    @property
    def ocr_pos(self) -> Tuple[int, int]:
        """换成 OCR 量纲（游戏坐标 / 100），与 ``_last_valid`` 一致。"""
        return int(self.center[0] / 100), int(self.center[1] / 100)


class ViewStateEstimator:
    """鼠标驱动的视图状态推算器（线程安全）。"""

    #: 滚轮每 tick 的 game_scale 倍率（缩小方向，dy<0）
    SCROLL_STEP = 1.0299
    #: 缩放时视图中心朝光标方向补偿的比例（实测固定阻尼）
    ZOOM_ANCHOR_DAMPING = 0.745
    #: 判定"快甩"的松手速度阈值（屏幕像素/秒）
    FLING_SPEED = 2000.0
    #: 快甩滑行的指数衰减时间常数（秒）。滑行总位移 ≈ v_release × FLING_TAU，
    #: 由实测反解：快甩段的额外位移 ≈ 0.5 × 拖动位移，而这些段位移 900~1200 px、
    #: 平均速度 2700~5200 px/s，故 τ ≈ (0.5×1000)/4000 ≈ 0.13 s；
    #: 收敛曲线也显示 0.3 s 内滑行完（≈ 2~3τ），两者一致。
    FLING_TAU = 0.13
    #: 滑行持续时长（超过后强制停住），取 3τ 时已完成 95%
    FLING_DURATION = 3 * FLING_TAU
    #: 估算松手速度所用的时间窗（秒）
    FLING_SAMPLE_WINDOW = 0.06
    #: 推算值与匹配值偏差超过这么多"屏幕像素"时，认为推算已失效并直接吸附
    MAX_MATCH_JUMP_PX = 250.0
    #: 无任何输入时置信度衰减到 0 所需时间（秒）；仅用于让调用方判断新鲜度
    CONFIDENCE_HALFLIFE = 3.0

    def __init__(self):
        self._lock = threading.RLock()
        self._center: Optional[Tuple[float, float]] = None
        self._gs: Optional[float] = None
        self._t = 0.0
        self._conf = 0.0
        self._source = 'none'
        # 快甩滑行
        self._coast_v = (0.0, 0.0)     # 游戏单位/秒
        self._coast_until = 0.0
        # 屏幕中心（游戏窗口客户区中心的屏幕绝对坐标），由任务侧每帧刷新
        self._screen_center: Optional[Tuple[float, float]] = None
        # 最近拖动样本（估算松手速度用）
        self._drag_hist: deque = deque(maxlen=16)
        # 统计（仅用于日志/观察）
        self.stats = {'match': 0, 'drag': 0, 'scroll': 0, 'fling': 0,
                      'reset': 0, 'resid_px': []}

    # ------------------------------------------------------------------ 查询
    @property
    def is_valid(self) -> bool:
        with self._lock:
            return self._center is not None and self._gs is not None and self._gs > 0

    def set_screen_center(self, sx: float, sy: float) -> None:
        """设置游戏窗口客户区中心对应的屏幕绝对坐标（缩放锚点计算要用）。"""
        with self._lock:
            self._screen_center = (float(sx), float(sy))

    def state(self, now: Optional[float] = None) -> Optional[ViewState]:
        """返回当前状态快照（会先推进快甩滑行）。"""
        now = time.perf_counter() if now is None else now
        with self._lock:
            self._advance_coast(now)
            if self._center is None or self._gs is None:
                return None
            age = max(0.0, now - self._t)
            conf = self._conf * math.pow(0.5, age / self.CONFIDENCE_HALFLIFE)
            return ViewState(center=self._center, game_scale=self._gs,
                             confidence=conf, source=self._source, t=self._t)

    def invalidate(self, reason: str = '') -> None:
        with self._lock:
            self._center = None
            self._gs = None
            self._conf = 0.0
            self._source = 'none'
            self._coast_until = 0.0
        if reason:
            logger.info(f'[ViewEst] 状态重置: {reason}')

    # ------------------------------------------------------------------ 匹配纠偏
    def on_match(self, center, game_scale, t: Optional[float] = None) -> Optional[float]:
        """用一次成功匹配吸附状态；返回吸附前推算值的残差（屏幕像素），首次为 None。"""
        if center is None or not game_scale or game_scale <= 0:
            return None
        t = time.perf_counter() if t is None else t
        with self._lock:
            resid = None
            if self._center is not None and self._gs:
                d = math.dist(self._center, center) / self._gs
                resid = d
                self.stats['resid_px'].append(round(d, 1))
                if d > self.MAX_MATCH_JUMP_PX:
                    self.stats['reset'] += 1
                    logger.info(f'[ViewEst] 推算偏差 {d:.0f}px > '
                                f'{self.MAX_MATCH_JUMP_PX:.0f}px，以匹配为准')
            self._center = (float(center[0]), float(center[1]))
            self._gs = float(game_scale)
            self._t = t
            self._conf = 1.0
            self._source = 'match'
            self._coast_until = 0.0
            self.stats['match'] += 1
            return resid

    # ------------------------------------------------------------------ 鼠标事件
    def on_mouse_press(self, x, y, button, t) -> None:
        with self._lock:
            self._coast_until = 0.0   # 重新按下即打断滑行
            self._drag_hist.clear()

    def on_mouse_drag(self, x, y, dx, dy, buttons, t) -> None:
        """拖动：视图中心朝鼠标反方向移动 ``Δpx × game_scale``（实测严格 1:1）。"""
        if not dx and not dy:
            return
        with self._lock:
            self._drag_hist.append((t, x, y))
            if self._center is None or not self._gs:
                return
            self._center = (self._center[0] - dx * self._gs,
                            self._center[1] - dy * self._gs)
            self._t = t
            self._conf = min(self._conf, 0.9)
            self._source = 'drag'
            self._coast_until = 0.0
            self.stats['drag'] += 1

    def on_mouse_release(self, x, y, button, t) -> None:
        """松手：快甩（>FLING_SPEED）时按 ``v_release`` 启动指数衰减滑行。

        松手速度取最近 ``FLING_SAMPLE_WINDOW`` 秒内的平均速度；滑行总位移
        ≈ ``v_release × FLING_TAU``（惯性只由松手速度决定，与拖了多远无关）。
        """
        with self._lock:
            self._coast_until = 0.0
            hist = [h for h in self._drag_hist
                    if t - h[0] <= self.FLING_SAMPLE_WINDOW]
            self._drag_hist.clear()
            if len(hist) < 2 or self._center is None or not self._gs:
                return
            dt = hist[-1][0] - hist[0][0]
            if dt <= 1e-3:
                return
            vx = (hist[-1][1] - hist[0][1]) / dt
            vy = (hist[-1][2] - hist[0][2]) / dt
            if math.hypot(vx, vy) < self.FLING_SPEED:
                return
            gs = self._gs
            # 视图中心朝鼠标反方向滑行，速度单位换成游戏单位/秒
            self._coast_v = (-vx * gs, -vy * gs)
            self._coast_until = t + self.FLING_DURATION
            self._t = t
            self._source = 'coast'
            self._conf = min(self._conf, 0.6)
            self.stats['fling'] += 1

    def on_mouse_scroll(self, x, y, dx, dy, t) -> None:
        """滚轮：按实测倍率改 game_scale，并朝光标方向补偿 0.745× 的中心位移。"""
        if not dy:
            return
        with self._lock:
            if self._center is None or not self._gs:
                return
            gs_old = self._gs
            gs_new = gs_old * math.pow(self.SCROLL_STEP, -float(dy))
            sc = self._screen_center
            if sc is not None:
                k = (gs_old - gs_new) * self.ZOOM_ANCHOR_DAMPING
                self._center = (self._center[0] + (x - sc[0]) * k,
                                self._center[1] + (y - sc[1]) * k)
            self._gs = gs_new
            self._t = t
            # 滑块无级缩放无法从鼠标推断，滚轮推算本身也有 ~2% 档距不确定性
            self._conf = min(self._conf, 0.7)
            self._source = 'scroll'
            self._coast_until = 0.0
            self.stats['scroll'] += 1

    # ------------------------------------------------------------------ 内部
    def _advance_coast(self, now: float) -> None:
        """推进快甩滑行（指数衰减），调用方须持锁。

        积分到 ``min(now, _coast_until)``，这样即使调用间隔跨过了滑行结束时刻也不会
        漏掉这段位移。位移 = ∫v dt = v0 · τ · (1 − e^{−dt/τ})。
        """
        if not self._coast_until or self._center is None:
            return
        end = min(now, self._coast_until)
        dt = end - self._t
        if dt > 0:
            decay = math.exp(-dt / self.FLING_TAU)
            vx, vy = self._coast_v
            step = self.FLING_TAU * (1.0 - decay)
            self._center = (self._center[0] + vx * step,
                            self._center[1] + vy * step)
            self._coast_v = (vx * decay, vy * decay)
            self._t = end
        if now >= self._coast_until:
            self._coast_until = 0.0
            self._coast_v = (0.0, 0.0)

    def summary(self) -> str:
        with self._lock:
            r = self.stats['resid_px'][-50:]
            med = sorted(r)[len(r) // 2] if r else float('nan')
            return (f"match={self.stats['match']} drag={self.stats['drag']} "
                    f"scroll={self.stats['scroll']} reset={self.stats['reset']} "
                    f"近期残差中位={med:.1f}px")
