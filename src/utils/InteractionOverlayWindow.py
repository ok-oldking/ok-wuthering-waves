"""Self-built, clickable, always-on-top transparent overlay window (Scheme C).

This is the Qt adapter layer for the map-overlay-interaction feature. Unlike the
``ok`` library's ``OverlayWindow`` (which sets ``Qt.WindowTransparentForInput``
and therefore can never receive mouse events), this window **must** receive
mouse clicks inside icon Hit_Boxes while letting every other click pass through
to the game. That pass-through is achieved with Qt ``setMask()``: the window's
shape is restricted to the union of the current Hit_Box rectangles, so pixels
outside any Hit_Box do not belong to the window and their mouse events fall
through to the game underneath (Requirements 1.4, 1.6, 10.3).

Key design points (see design.md "InteractionOverlayWindow"):

- Window flags ``Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool``
  plus ``setAttribute(Qt.WA_TranslucentBackground)`` for a 0% opaque background;
  only icons / route polylines / the Description_Bubble paint at their own
  opacity (Requirement 1.1). ``Qt.WindowTransparentForInput`` is deliberately
  **not** set -- that is the fundamental difference from ``OverlayWindow``.
- Clicks inside a Hit_Box are intercepted (``event.accept()``) so they do not
  reach the game (Requirements 1.5, 10.2); clicks outside are handled naturally
  by ``setMask`` (Requirement 1.6).
- The top-most overlapping icon for a click is resolved with
  :func:`~src.utils.map_geometry.topmost_hit` (Requirements 1.10, 2.8).
- Left single click vs. left double click is distinguished with a 500ms
  ``QTimer`` per Requirement 7.1; right click fires immediately.
- At most one Description_Bubble is shown at any time (Requirement 2.2).

Because the detection loop runs on the ``ok`` task thread while Qt widgets must
be touched only on the GUI thread, the public ``render_items`` / ``update_mask``
/ ``show_overlay`` / ``hide_overlay`` methods marshal their work onto the GUI
thread via queued signals -- the same cross-thread pattern ``OverlayWindow``
uses with ``custom_draw_requested``.

This module is a thin Qt adapter and is **manually verified** on the game
machine (see design.md manual test checklist); it is intentionally excluded from
property-based testing.

Feature: map-overlay-interaction
Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8, 2.1, 2.2, 2.8, 10.2
"""

from __future__ import annotations

import ctypes
import logging
from typing import List, NamedTuple, Optional, Sequence, Tuple, Union

from PySide6.QtCore import QRect, Qt, QTimer, Signal, QPoint
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QRegion,
)
from PySide6.QtWidgets import QWidget

from src.utils.map_geometry import topmost_hit
from src.utils.MapItemOverlay import ICON_SIZE, PATH_LINE_WIDTH, paint_icon_background, paint_path_layers
from src.utils.overlay_types import Rect

logger = logging.getLogger(__name__)

# Double-click discrimination window in milliseconds (Requirement 7.1: a left
# double click must complete within 500ms).
DOUBLE_CLICK_MS = 500

# Default icon footprint used when a draw item carries no pixmap, kept in sync
# with ``MapItemOverlay.ICON_SIZE``.
_ICON_SIZE = 30


class BubbleSpec(NamedTuple):
    """A single Description_Bubble to render (Requirements 2.1, 2.2).

    ``x`` / ``y`` are the window-local anchor pixel (typically next to the
    clicked icon) and ``text`` is the already-resolved bubble text (the empty
    description placeholder is applied by the pure-logic ``bubble_text`` helper
    before it reaches this window).
    """

    x: int
    y: int
    text: str


# A Hit_Box entry accepted by ``update_mask``: either a bare ``Rect`` (z order
# defaults to the draw-item z, or 0) or an explicit ``(Rect, z)`` pair.
HitBoxInput = Union[Rect, Tuple[Rect, int]]


def _normalize_bubble(bubble) -> Optional[BubbleSpec]:
    """Coerce a ``render_items`` bubble argument into a ``BubbleSpec`` or None."""
    if bubble is None:
        return None
    if isinstance(bubble, BubbleSpec):
        return bubble
    # Accept a plain (x, y, text) tuple for convenience.
    if isinstance(bubble, (tuple, list)) and len(bubble) >= 3:
        return BubbleSpec(int(bubble[0]), int(bubble[1]), str(bubble[2]))
    return None


def _to_qcolor(color) -> QColor:
    """Best-effort conversion of a color value to ``QColor``.

    Accepts an existing ``QColor`` (passed through), an ``(r, g, b)`` /
    ``(r, g, b, a)`` tuple, or anything ``QColor`` itself understands.
    """
    if isinstance(color, QColor):
        return color
    if isinstance(color, (tuple, list)):
        return QColor(*color)
    if color is None:
        return QColor(255, 255, 255)
    return QColor(color)


class InteractionOverlayWindow(QWidget):
    """Clickable transparent overlay used in Bigmap_Mode (Scheme C)."""

    # Mouse-event signals reported to the OverlayController. The int payload is
    # the index of the hit draw item (aligned with the ``draw_items`` order used
    # in ``render_items`` / ``update_mask``); ``emptyClicked`` carries no index.
    leftClicked = Signal(int)
    leftDoubleClicked = Signal(int)
    rightClicked = Signal(int)
    emptyClicked = Signal()

    # Internal cross-thread marshalling signals: public methods may be called
    # from the ok task thread, but the actual Qt work must run on the GUI
    # thread, so these are connected with Qt.QueuedConnection.
    _render_requested = Signal(object, object, object)
    _mask_requested = Signal(object)
    # 合并渲染帧信号：把内容 + 气泡 + 路线 + 命中区在同一个 GUI 事件里原子更新，
    # 避免 render_items / update_mask 两个独立排队信号产生的半更新中间帧
    # （不确定问题1：拖动路线卡顿/先画中间状态）。
    _frame_requested = Signal(object, object, object, object, object)
    # 几何设置信号：set_window_geometry 可能在 ok 任务线程被调用，但 QWidget.setGeometry
    # 必须在 GUI 线程执行；拖动游戏窗口时几何持续变化，若在任务线程直接 setGeometry 会
    # 跨线程触发窗口系统调用而卡死（无栈挂起）。故经排队信号派发到 GUI 线程。
    _geometry_requested = Signal(int, int, int, int)
    _show_requested = Signal()
    _hide_requested = Signal()

    def __init__(self, x: int = 0, y: int = 0, width: int = 0, height: int = 0,
                 parent=None):
        super().__init__(parent)

        # Fully transparent, frameless, always-on-top tool window that still
        # receives mouse events (no WindowTransparentForInput) (Requirement 1.1).
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 显示时不激活本窗口（问题2）：配合下方 WS_EX_NOACTIVATE，点击/显示交互窗口
        # 都不会从游戏夺取前台焦点，从而无需在每次点击后 bring_to_front 把游戏抬回
        # 前台——正是那次抬前台与置顶覆盖层互抢层级导致了气泡瞬灭与叠加层闪烁。
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # Do NOT set Qt.WA_OpaquePaintEvent here: it would force an opaque
        # background and defeat the translucency this overlay relies on.

        # 是否已应用过 WS_EX_NOACTIVATE 扩展样式（首次 showEvent 后置 True）。
        # SetWindowLong 本身幂等，这里仅用于避免重复调用日志噪声。
        self._no_activate_applied = False

        # Render state (only mutated on the GUI thread).
        self._draw_items: List[tuple] = []
        self._path_layers: tuple = ()
        self._bubble: Optional[BubbleSpec] = None
        # 当前路线目标高亮点（窗口局部像素 ``(sx, sy)``）或 None（无目标）。存在时
        # paintEvent 会在该点周围画一个 3px 红色空心圆，圈住目标节点（问题3）。
        self._target_marker: Optional[Tuple[int, int]] = None
        # Hit_Box rectangles paired with z order, for click hit-testing; aligned
        # by index with ``_draw_items``.
        self._hitboxes_with_z: List[Tuple[Rect, int]] = []

        # Pending left single-click state for the 500ms double-click timer.
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(DOUBLE_CLICK_MS)
        self._click_timer.timeout.connect(self._emit_pending_single_click)
        self._pending_left_index: Optional[int] = None

        # Marshal public calls onto the GUI thread.
        self._render_requested.connect(self._do_render, Qt.QueuedConnection)
        self._mask_requested.connect(self._do_mask, Qt.QueuedConnection)
        self._frame_requested.connect(self._do_frame, Qt.QueuedConnection)
        self._geometry_requested.connect(self._do_set_geometry, Qt.QueuedConnection)
        self._show_requested.connect(self._do_show, Qt.QueuedConnection)
        self._hide_requested.connect(self._do_hide, Qt.QueuedConnection)

        if width > 0 and height > 0:
            self.setGeometry(x, y, width, height)

    # ------------------------------------------------------------------
    # Public API (safe to call from the ok task thread)
    # ------------------------------------------------------------------
    def set_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        """Align the overlay with the game client area (Requirement 1.1).

        可能在 ok 任务线程被调用，因此不直接 ``setGeometry``（QWidget 几何操作必须在
        GUI 线程；拖动窗口时若跨线程 setGeometry 会卡死），改为经排队信号派发到 GUI
        线程执行（见 :meth:`_do_set_geometry`）。
        """
        self._geometry_requested.emit(int(x), int(y), int(width), int(height))

    def render_items(self, draw_items, bubble=None, path_layers=()) -> None:
        """Update overlay content and trigger a repaint (Requirements 2, 5).

        ``draw_items`` are the extended 8-tuples
        ``(sx, sy, pixmap, name, color, opacity, location_id, z)`` produced by
        ``MapItemOverlay``; ``bubble`` is an optional ``BubbleSpec`` /
        ``(x, y, text)`` (at most one is ever shown, Requirement 2.2);
        ``path_layers`` is a sequence of ``PathRoute.PathLayer``.
        """
        self._render_requested.emit(
            list(draw_items) if draw_items else [],
            bubble,
            tuple(path_layers) if path_layers else (),
        )

    def update_mask(self, hitboxes: Sequence[HitBoxInput]) -> None:
        """Restrict the clickable region to the Hit_Boxes (Requirements 1.4, 1.7).

        ``hitboxes`` is a sequence of ``Rect`` (or ``(Rect, z)`` pairs) in
        window-local pixels, aligned by index with the ``draw_items`` last passed
        to :meth:`render_items`. The pixels outside the composed ``QRegion`` do
        not belong to the window, so their clicks pass through to the game
        (Requirement 1.6).
        """
        self._mask_requested.emit(list(hitboxes) if hitboxes else [])

    def render_frame(self, draw_items, bubble=None, path_layers=(),
                     hitboxes=(), target_marker=None) -> None:
        """一次性合并更新内容 + 气泡 + 路线 + 命中区 + 目标高亮（原子帧）。

        把原来 :meth:`render_items` 与 :meth:`update_mask` 两次跨线程排队信号合并为
        单个 ``_frame_requested``，使 GUI 线程在同一个事件里同时设置绘制内容和命中
        掩码，避免出现内容与掩码不一致 / 半更新的中间帧（不确定问题1）。入参做与
        :meth:`render_items` / :meth:`update_mask` 相同的拷贝 / 规范化。

        ``target_marker`` 为路线当前目标节点的窗口局部像素点 ``(sx, sy)`` 或 None
        （无目标）。存在时会在该点周围绘制 3px 红色空心圆以圈住目标节点（问题3）。
        """
        self._frame_requested.emit(
            list(draw_items) if draw_items else [],
            bubble,
            tuple(path_layers) if path_layers else (),
            list(hitboxes) if hitboxes else [],
            tuple(target_marker) if target_marker is not None else None,
        )

    def show_overlay(self) -> None:
        """Show the overlay when entering Bigmap_Mode."""
        self._show_requested.emit()

    def hide_overlay(self) -> None:
        """Hide and clear interactive content when leaving Bigmap_Mode.

        Clears items / bubble / mask so nothing interactive lingers
        (Requirement 1.8).
        """
        self._hide_requested.emit()

    # ------------------------------------------------------------------
    # GUI-thread slots
    # ------------------------------------------------------------------
    def _do_render(self, draw_items, bubble, path_layers) -> None:
        self._draw_items = list(draw_items)
        self._path_layers = tuple(path_layers)
        self._bubble = _normalize_bubble(bubble)
        # Route polylines and the bubble must be part of the window mask, else
        # setMask would clip everything outside the Hit_Box rectangles (long
        # route segments would only show a stub near the nodes, and the bubble
        # would be invisible). Recompose after content changes.
        self._apply_composed_mask()
        self.update()

    def _do_mask(self, hitboxes) -> None:
        self._hitboxes_with_z = self._normalize_hitboxes(hitboxes)
        # Compose the full mask (hit-boxes + route strokes + bubble) rather than
        # masking to hit-box rectangles alone (fixes long lines being clipped).
        self._apply_composed_mask()

    def _normalize_hitboxes(self, hitboxes) -> "List[Tuple[Rect, int]]":
        """把 update_mask/render_frame 传入的命中区规范化为 ``(Rect, z)`` 列表。

        接受裸 ``Rect``（z 回退到同索引 draw item 的 z，否则 0）或显式 ``(Rect, z)``
        对；忽略无法识别的条目。由 :meth:`_do_mask` 与 :meth:`_do_frame` 共用，保证
        两条路径的规范化行为完全一致。
        """
        normalized: List[Tuple[Rect, int]] = []
        for index, entry in enumerate(hitboxes):
            if isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], Rect):
                rect, z = entry
            elif isinstance(entry, Rect):
                rect = entry
                # Fall back to the matching draw item's z, else index order.
                z = self._z_for_index(index)
            else:
                continue
            normalized.append((rect, int(z)))
        return normalized

    def _do_frame(self, draw_items, bubble, path_layers, hitboxes,
                  target_marker=None) -> None:
        """合并帧槽：在同一个 GUI 事件里原子设置内容 + 气泡 + 路线 + 命中掩码。

        等价于把 :meth:`_do_render` 与 :meth:`_do_mask` 的工作合并为一次：先设置
        ``_draw_items`` / ``_path_layers`` / ``_bubble``（这样命中区 z 回退能读到
        最新 draw items），再规范化并存 ``_hitboxes_with_z``，最后统一
        :meth:`_apply_composed_mask` 并只 ``update()`` 一次，避免半更新中间帧。
        ``target_marker`` 为目标高亮点或 None，一并在本帧原子更新。
        """
        self._draw_items = list(draw_items)
        self._path_layers = tuple(path_layers)
        self._bubble = _normalize_bubble(bubble)
        self._hitboxes_with_z = self._normalize_hitboxes(hitboxes)
        self._target_marker = tuple(target_marker) if target_marker is not None else None
        self._apply_composed_mask()
        self.update()

    def _compose_mask_region(self) -> QRegion:
        """Compose the window mask from hit-boxes, route strokes and the bubble.

        The mask determines which pixels belong to the window; anything outside
        it is clipped from painting *and* passes mouse events through to the
        game. Restricting it to the Hit_Box rectangles alone clips the middle of
        long route segments and hides the Description_Bubble, so this unions in:

        - each Hit_Box rectangle (click targets, Requirement 1.4);
        - each route layer's polyline, stroked wide enough to cover the 3px line
          plus its arrow heads, so the whole connector is visible;
        - a small square around every route node dot;
        - the current bubble box (so the bubble is not clipped, fix B).
        """
        region = QRegion()
        # Hit_Box rectangles.
        for rect, _z in self._hitboxes_with_z:
            region = region.united(
                QRect(rect.left, rect.top, rect.width, rect.height)
            )

        # Route polyline strokes + node dots.
        stroke_width = PATH_LINE_WIDTH + 6
        node_radius = ICON_SIZE // 2
        for layer in self._path_layers:
            points = list(getattr(layer, "points", ()) or ())
            if len(points) >= 2:
                path = QPainterPath()
                path.moveTo(float(points[0][0]), float(points[0][1]))
                for pt in points[1:]:
                    path.lineTo(float(pt[0]), float(pt[1]))
                stroker = QPainterPathStroker()
                stroker.setWidth(stroke_width)
                stroke_path = stroker.createStroke(path)
                region = region.united(
                    QRegion(stroke_path.toFillPolygon().toPolygon())
                )
            for pt in points:
                cx = int(pt[0])
                cy = int(pt[1])
                region = region.united(
                    QRegion(cx - node_radius, cy - node_radius,
                            node_radius * 2, node_radius * 2)
                )

        # Description_Bubble box (fix B).
        bubble_rect = self._bubble_box_rect()
        if bubble_rect is not None:
            region = region.united(bubble_rect)

        return region

    def _apply_composed_mask(self) -> None:
        """Recompose and apply the window mask, clearing it when empty."""
        region = self._compose_mask_region()
        if region.isEmpty():
            self.clearMask()
        else:
            self.setMask(region)

    def _do_set_geometry(self, x, y, width, height) -> None:
        """GUI 线程执行几何设置（由 _geometry_requested 排队派发）。"""
        self.setGeometry(int(x), int(y), int(width), int(height))

    def _do_show(self) -> None:
        if not self.isVisible():
            self.show()
    def _do_hide(self) -> None:
        self._cancel_pending_click()
        self._draw_items = []
        self._path_layers = ()
        self._bubble = None
        self._hitboxes_with_z = []
        self._target_marker = None
        self.clearMask()
        if self.isVisible():
            self.hide()
        self.update()

    def _z_for_index(self, index: int) -> int:
        if 0 <= index < len(self._draw_items):
            item = self._draw_items[index]
            if len(item) > 7:
                return int(item[7])
        return 0

    # ------------------------------------------------------------------
    # Mouse handling
    # ------------------------------------------------------------------
    def _event_point(self, event) -> Tuple[int, int]:
        """Return the integer window-local position of a mouse event."""
        pos = getattr(event, "position", None)
        if callable(pos):
            p = event.position().toPoint()
            return p.x(), p.y()
        p = event.pos()
        return p.x(), p.y()

    def _hit_index(self, px: int, py: int) -> Optional[int]:
        if not self._hitboxes_with_z:
            return None
        return topmost_hit(px, py, self._hitboxes_with_z)

    def mousePressEvent(self, event) -> None:
        px, py = self._event_point(event)
        index = self._hit_index(px, py)

        # The mask should keep events outside hit-boxes from reaching us, but be
        # defensive: a click that resolves to no icon is reported as empty.
        if index is None:
            self._cancel_pending_click()
            self.emptyClicked.emit()
            event.accept()
            return

        button = event.button()
        if button == Qt.RightButton:
            self._cancel_pending_click()
            self.rightClicked.emit(index)
            event.accept()
            return

        if button == Qt.LeftButton:
            if self._click_timer.isActive():
                # Second left press within the 500ms window -> double click.
                self._cancel_pending_click()
                self.leftDoubleClicked.emit(index)
            else:
                # First left press: wait to see whether a second one arrives.
                self._pending_left_index = index
                self._click_timer.start()
            event.accept()
            return

        # Any other button inside a hit-box is still intercepted so it does not
        # leak to the game (Requirement 10.2).
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        # 关键修复（问题2）：Qt 对“第二次点击”派发的是本事件，而不是第二个
        # mousePressEvent。若这里只 accept 而不做处理，双击设定目标几乎无法触发。
        # 因此在此直接完成左键双击判定：命中某图标时取消待触发的单击计时器（避免
        # 随后又弹出气泡），再发出 leftDoubleClicked。命中区内的双击一律 accept，
        # 不透传给游戏；mousePressEvent 里“计时器 active 的第二次按下”慢速双击兜底
        # 仍保留，但因本事件会先 _cancel_pending_click，不会重复触发。
        if event.button() == Qt.LeftButton:
            px, py = self._event_point(event)
            index = self._hit_index(px, py)
            if index is not None:
                self._cancel_pending_click()
                self.leftDoubleClicked.emit(index)
        event.accept()

    def _emit_pending_single_click(self) -> None:
        index = self._pending_left_index
        self._pending_left_index = None
        if index is not None:
            self.leftClicked.emit(index)

    def _cancel_pending_click(self) -> None:
        if self._click_timer.isActive():
            self._click_timer.stop()
        self._pending_left_index = None

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def _apply_no_activate(self) -> None:
        """给窗口原生句柄加上 ``WS_EX_NOACTIVATE`` 扩展样式（问题2，Windows 专用）。

        使点击 / 显示本窗口都不会激活它、也不会从游戏夺取前台焦点，同时仍能收到鼠标
        事件（配合现有 ``setMask``）。因此不必在每次点击后调用 ``bring_to_front`` 把
        游戏抬回前台——那次抬前台与置顶覆盖层互抢层级正是气泡瞬灭 / 叠加层闪烁的根因。

        依赖原生 ``hwnd``，故在 :meth:`showEvent`（``winId()`` 此时已创建）中调用。用
        try/except 包裹，任何失败仅告警、不致命（非 Windows 平台或调用异常时降级为
        原有行为）。``SetWindowLong`` 幂等，重复调用无副作用。
        """
        try:
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE)
            self._no_activate_applied = True
        except Exception as exc:  # pragma: no cover - Windows/ctypes runtime specific
            logger.warning(f"[Overlay] apply WS_EX_NOACTIVATE failed: {exc}")

    def showEvent(self, event) -> None:
        """窗口显示时应用一次不夺焦点的扩展样式（问题2）。

        原生句柄在 ``super().showEvent`` 后已存在，此时调用 :meth:`_apply_no_activate`
        设置 ``WS_EX_NOACTIVATE``。只需成功应用一次即可（``SetWindowLong`` 幂等）。
        """
        super().showEvent(event)
        if not self._no_activate_applied:
            self._apply_no_activate()

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            self._paint_path_layers(painter)
            self._paint_draw_items(painter)
            self._paint_target_marker(painter)
            self._paint_bubble(painter)
        finally:
            painter.setOpacity(1.0)
            painter.end()

    def _paint_path_layers(self, painter) -> None:
        # Delegate to the shared render-layer helper so route polyline / arrow /
        # qzx_04 node-icon drawing lives in one place (task 10.1). The big map
        # and the minimap (ok OverlayWindow) thus paint routes identically
        # (Requirements 5.2, 5.3, 5.4).
        paint_path_layers(painter, self._path_layers)

    def _paint_draw_items(self, painter) -> None:
        font = QFont("Arial", 8)
        half = _ICON_SIZE // 2
        for item in self._draw_items:
            sx, sy = item[0], item[1]
            pixmap = item[2] if len(item) > 2 else None
            name = item[3] if len(item) > 3 else ""
            color = item[4] if len(item) > 4 else None
            opacity = item[5] if len(item) > 5 else 1.0
            painter.setOpacity(opacity)
            if pixmap is not None:
                paint_icon_background(painter, sx, sy, _ICON_SIZE, opacity)
                painter.setOpacity(opacity)
                painter.drawPixmap(sx - half, sy - half, pixmap)
            else:
                qcolor = _to_qcolor(color)
                painter.setPen(QPen(qcolor, 2))
                painter.setBrush(QBrush(qcolor))
                painter.drawEllipse(sx - 3, sy - 3, 6, 6)
                if name:
                    painter.setFont(font)
                    painter.drawText(sx + 5, sy - 5, str(name)[:4])
        painter.setOpacity(1.0)

    def _paint_target_marker(self, painter) -> None:
        """在当前路线目标节点周围绘制 3px 红色空心圆（问题3）。

        ``_target_marker`` 为 None 时不绘制。圆以 marker 点为圆心，半径取
        ``ICON_SIZE//2 + 4``，足以圈住节点图标并落在该节点命中区内（命中区半径为
        ``ICON_SIZE//2 + HITBOX_EXPAND``，更大）。画在 draw_items 之后、气泡之前，
        避免被节点图标盖住。目标圈在节点附近、已被该节点命中区覆盖，无需额外并入掩码。
        """
        marker = self._target_marker
        if marker is None:
            return
        sx, sy = int(marker[0]), int(marker[1])
        r = _ICON_SIZE // 2 + 4
        painter.save()
        try:
            painter.setOpacity(1.0)
            painter.setPen(QPen(QColor(255, 0, 0), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPoint(sx, sy), r, r)
        finally:
            painter.restore()

    def _bubble_box_rect(self) -> Optional[QRect]:
        """Compute the current Description_Bubble box rectangle, or ``None``.

        Shared by :meth:`_paint_bubble` (drawing) and
        :meth:`_compose_mask_region` (masking) so the drawn box and the masked
        region stay identical. The box is anchored at ``bubble.x/y``, sized to
        the text via ``QFontMetrics`` of the same ``QFont("Arial", 10)`` used
        when painting, then clamped to stay fully inside the window
        (Requirement 2.1).

        多行支持（问题2）：气泡文本可能包含 '\\n'（由 ``wrap_text`` 每 25 字换行）。
        宽度取各行 ``horizontalAdvance`` 的最大值，高度取 ``行数 * metrics.height()``，
        再各自加两侧 padding。
        """
        bubble = self._bubble
        if bubble is None:
            return None
        metrics = QFontMetrics(QFont("Arial", 10))
        pad = 6
        lines = bubble.text.split("\n")
        text_w = max((metrics.horizontalAdvance(line) for line in lines), default=0)
        text_h = len(lines) * metrics.height()
        box_w = text_w + pad * 2
        box_h = text_h + pad * 2

        bx = bubble.x
        by = bubble.y
        if bx + box_w > self.width():
            bx = max(0, self.width() - box_w)
        if by + box_h > self.height():
            by = max(0, self.height() - box_h)
        return QRect(int(bx), int(by), int(box_w), int(box_h))

    def _paint_bubble(self, painter) -> None:
        rect = self._bubble_box_rect()
        if rect is None:
            return
        bubble = self._bubble
        painter.setOpacity(1.0)
        font = QFont("Arial", 10)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        pad = 6

        painter.setPen(QPen(QColor(0, 0, 0, 200), 1))
        painter.setBrush(QBrush(QColor(30, 30, 30, 220)))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        # 多行逐行绘制（问题2）：首行基线为 rect.y()+pad+ascent，之后每行递增 height()。
        line_h = metrics.height()
        base_y = rect.y() + pad + metrics.ascent()
        for i, line in enumerate(bubble.text.split("\n")):
            painter.drawText(rect.x() + pad, base_y + i * line_h, line)


__all__ = [
    "InteractionOverlayWindow",
    "BubbleSpec",
    "DOUBLE_CLICK_MS",
]
