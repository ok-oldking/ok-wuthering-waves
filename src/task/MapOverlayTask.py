import json
import math
import os
import time
from collections import deque
from typing import NamedTuple, Optional

import cv2
import numpy as np

from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger, og, get_path_relative_to_exe, Box
from src.task.BaseWWTask import BaseWWTask
from src.utils.MapItemOverlay import (
    MapItemOverlay, ITEM_COLORS, ITEM_PIXMAPS, ICON_SIZE,
    DrawCandidate, build_overlay_draw_items, select_overlay_content,
    bubble_text, opacity_for, player_ocr_to_game_units, wrap_text,
)
from src.utils.map_geometry import make_hitbox, bearing_degrees
from src.utils.PathRoute import load_path_route, build_path_layers, PathParseError, PathLayer, PATH_NODE_ICON_KEY
from src.utils.TargetTracker import (
    THRESHOLD_MIN, THRESHOLD_MAX, validate_threshold, TargetTracker,
    TargetRef, right_click_dispatch,
)

logger = Logger.get_logger(__name__)

TELEPORT_THRESHOLD = 500
TELEPORT_SETTLE_DISTANCE = 10
OUTLIER_RELATIVE_FACTOR = 2.0
OUTLIER_FIXED_THRESHOLD = 200

OVERLAY_DRAW_KEY = "map_items"

# ok overlay 的 draw(..., duration=...) 到点即过期并清除覆盖层。地图重匹配帧偶发
# >1s，若沿用 duration=1 会导致覆盖层在慢帧时闪烁/消失（问题4）。检测循环约每
# 100ms 会重画一次，用 3s 作为过期时间足以覆盖偶发慢帧而不会残留过久。
OVERLAY_DRAW_DURATION = 3.0

MAP_DIR = get_path_relative_to_exe('assets', 'stitched')

# Fixed route file (Path_Mode source) and completion-marks database
# (Requirements 4.2, 3.1). Resolved relative to the executable like MAP_DIR.
PATH_FILE = get_path_relative_to_exe('assets', 'path.json')
MARKS_DB_PATH = os.path.join(MAP_DIR, 'map_marks.db')

# Hit_Box outward expansion in pixels for big-map clickable icons (the Hit_Box
# definition allows 0..8px; Scheme C uses the upper bound for forgiving clicks).
HITBOX_EXPAND = 8


class ClickTarget(NamedTuple):
    """Resolves an InteractionOverlayWindow click index to a domain action.

    The window reports click indices aligned with the ``draw_items`` /
    ``hitboxes`` order it was last given (see ``InteractionOverlayWindow`` and
    ``topmost_hit``). The controller keeps a parallel ``ClickTarget`` list in the
    same order so a click index can be mapped back to either a DB ``location``
    (Normal_Mode) or a route ``PathNode`` (Path_Mode) and the matching
    bubble / mark / target action taken (Requirements 2, 3, 6, 7).

    - ``kind``: ``'item'`` for a DB location, ``'node'`` for a route node.
    - ``ref_id``: the completion / lookup key — ``location.id`` for items,
      ``Path_Node.position_id`` for nodes.
    - ``sx`` / ``sy``: the icon's window-local pixel anchor (for the bubble).
    - ``section_id`` / ``index``: the owning Section id and in-section index for
      nodes (``-1`` for items), used to set/cancel the Target.
    - ``name``: the node's ``position_name`` (used as its bubble text); empty for
      items (their description is fetched from the DB on click).
    """

    kind: str
    ref_id: str
    sx: int
    sy: int
    section_id: int = -1
    index: int = -1
    name: str = ""

MAP_REGION_SIZE = 1000
FRAME_CROP_SIZE = 400
FALLBACK_MAX_FAILURES = 4
BIG_MAP_SEARCH_MULTIPLIER = 10
SLOW_MAP_IDS = {'8'}


def _parse_position(text):
    parts = text.split(',')
    if len(parts) == 3:
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            pass
    return None


def _dist2d(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _load_coords_dict(stitched_dir):
    coords_path = os.path.join(stitched_dir, 'map_coords.json')
    try:
        with open(coords_path, 'r', encoding='utf-8') as f:
            coords_dict = json.load(f)
    except Exception:
        logger.warning(f"Failed to load coords: {coords_path}")
        coords_dict = {}
    return coords_dict


CONFIDENCE_THRESHOLD = 0.8

BIG_MAP_COLOR_CHECKS = [
    ((0.030, 0.094), (98, 150, 166)),
    ((0.890, 0.059), (249, 249, 238)),
    ((0.939, 0.931), (255, 255, 255)),
    ((0.035, 0.891), (236, 237, 235)),
]
BIG_MAP_COLOR_TOLERANCE = 15


def _filter_candidate_maps(ocr_pos, coords_dict):
    game_x = ocr_pos[0] * 100
    game_y = ocr_pos[1] * 100
    candidates = []
    for map_id, d in coords_dict.items():
        mn = d.get('min', [0, 0])
        mx = d.get('max', [0, 0])
        if mn[0] <= game_x <= mx[0] and mn[1] <= game_y <= mx[1]:
            candidates.append((map_id, d))
    return candidates


class OverlayController:
    """Three-state coordination between the detection loop and the render layer.

    This collaborator translates the ``run()`` detection loop's three states
    (minimap / big map / idle) into render + interaction actions, wiring the
    Qt-free pure-logic modules (``PathRoute`` / ``map_geometry`` /
    ``TargetTracker`` / ``MapMarksDB`` and the ``MapItemOverlay`` draw-item
    builders) to the render layer (the ``ok`` ``OverlayWindow`` for the minimap
    and the self-built ``InteractionOverlayWindow`` for the big map).

    It owns the *coordination* state (display mode, parsed route, target
    tracker, completed-mark set, the interaction window handle); the heavy IO /
    Qt work is delegated to the owning :class:`MapOverlayTask` and the window
    adapter. The existing positioning / denoise / teleport / map-lock logic in
    ``run()`` is left untouched -- this controller is only invoked from inside
    the three already-existing branches.

    Mouse-event wiring (task 11.3), the global advance hotkey + auto-advance
    (task 11.4) and the full create-failure / DB-failure fallbacks (task 11.5)
    are layered on. The hotkey is registered at initialization and only mutates
    target state on its listener thread; auto-advance is evaluated from the
    detection loop's player-coordinate update.

    Feature: map-overlay-interaction
    Requirements: 1.2, 1.3, 1.7, 1.8, 4.1, 4.2, 4.3, 4.5, 4.6, 5.1
    """

    def __init__(self, task):
        self.task = task
        # Display mode mirrors the 'Path mode' config switch (Requirement 4.1).
        self._path_mode = bool(task.config.get('Path mode', False))
        # Parsed route + target tracker, populated lazily on entering Path_Mode.
        self._route = None
        self._tracker = None
        self._route_load_failed = False
        # Completion marks (Requirement 3.5/3.6); loaded lazily, best-effort.
        self._marks_db = None
        self._completed_ids = set()
        self._marks_loaded = False
        # Self-built clickable big-map window (Scheme C); created lazily.
        self._interaction_window = None
        self._interaction_unavailable = False
        # Global Advance_Hotkey listener (pynput GlobalHotKeys) on a background
        # thread; started on entering Path_Mode, stopped on leaving Path_Mode or
        # task destroy (Requirements 9.3, 9.9). Its callback only mutates target
        # state -- never touches Qt (task 11.4).
        self._hotkey_listener = None
        # At most one Description_Bubble at a time (Requirement 2.2). Stored as a
        # plain ``(x, y, text)`` tuple consumed by InteractionOverlayWindow.
        self._bubble = None
        # Player position captured when the bubble was opened, so a subsequent
        # big-map pan/move can close it (Requirement 2.5).
        self._bubble_player_pos = None
        # Most recent big-map player position (refreshed each on_bigmap frame).
        self._current_player_pos = None
        # Click index -> ClickTarget map for the current big-map frame, kept in
        # the same order as the hit-boxes handed to the window (task 11.3).
        self._click_targets: list = []
        # Last content rendered to the big-map window, so a click can re-render
        # (e.g. to show/hide a bubble or refresh completion opacity) without
        # rebuilding from scratch on the task thread.
        self._last_draw_items: list = []
        self._last_path_layers: tuple = ()
        # 大地图路线目标高亮点 (sx, sy) 或 None（无目标 / 找不到投影点）。每帧在
        # _build_bigmap_content 中根据 tracker.target 重算，传给交互窗口画 3px 红圈
        # （问题3）；右键取消目标后 tracker.target 变 None，下一帧此值即变 None，红圈消失。
        self._last_target_marker = None
        # 上一次设置到交互窗口的几何 (x, y, w, h)，未变化则跳过 set_window_geometry，
        # 减少多余 GUI 事件（额外优化）。
        self._last_geometry = None
        # Connect the window's mouse signals to the controller exactly once.
        self._signals_connected = False
        # One-shot warning latches so the per-frame error paths surface their
        # info_set message only once instead of every detection frame (task
        # 11.5). Reset where a recovery makes a fresh warning meaningful again
        # (e.g. a later successful marks write re-arms the save warning).
        self._interaction_warned = False
        self._marks_read_warned = False
        self._marks_save_warned = False
        # Register the global advance hotkey up front so a single keypress
        # advances the target whenever one is set; with no target the callback
        # is a no-op (Requirements 9.3, 9.4). Stopped in close() on task destroy.
        self._start_hotkey()

    # ------------------------------------------------------------------
    # Mode handling (Requirements 4.1, 4.2, 4.3, 4.5, 4.6)
    # ------------------------------------------------------------------
    @property
    def path_mode(self) -> bool:
        return self._path_mode

    def toggle_mode(self) -> bool:
        """Toggle between Normal_Mode and Path_Mode (Requirements 4.1, 4.3)."""
        return self.set_path_mode(not self._path_mode)

    def set_path_mode(self, enabled: bool) -> bool:
        """Activate Path_Mode or Normal_Mode, keeping the config in sync.

        Entering Path_Mode loads ``assets/path.json`` (Requirement 4.2). When
        the route cannot be loaded the controller stays in Normal_Mode and
        surfaces a message (Requirement 4.4; the richer fallback handling is
        task 11.5). The two modes are mutually exclusive (Requirement 4.1) and a
        short status update is emitted so the interface reflects the active mode
        (Requirement 4.3).
        """
        enabled = bool(enabled)
        if enabled:
            if not self._ensure_route_loaded():
                # Load failed -> remain in Normal_Mode and persist that.
                self._path_mode = False
                self._sync_config_mode(False)
                return self._path_mode
            self._path_mode = True
        else:
            self._path_mode = False
        self._sync_config_mode(self._path_mode)
        self.task.info_set('Path mode', '路线模式' if self._path_mode else '普通模式')
        return self._path_mode

    def _sync_config_mode(self, enabled: bool) -> None:
        try:
            if bool(self.task.config.get('Path mode', False)) != enabled:
                self.task.config['Path mode'] = enabled
        except Exception as exc:  # pragma: no cover - config backend specific
            logger.warning(f"[Overlay] failed to sync Path mode config: {exc}")

    def _sync_mode_from_config(self) -> None:
        """Pick up a 'Path mode' change made through the settings UI."""
        cfg = bool(self.task.config.get('Path mode', False))
        if cfg != self._path_mode:
            self.set_path_mode(cfg)

    def _ensure_route_loaded(self) -> bool:
        """Load + parse ``assets/path.json`` once (Requirement 4.2)."""
        if self._route is not None:
            return True
        try:
            self._route = load_path_route(PATH_FILE)
        except PathParseError as exc:
            logger.warning(f"[Overlay] path route load failed: {exc}")
            self._route = None
            self._tracker = None
            self._route_load_failed = True
            self.task.info_set('Path mode', f'路线加载失败，保持普通模式：{exc}')
            return False
        threshold = self.task.config.get('Arrival threshold (game units)', 1000)
        if not validate_threshold(threshold):
            threshold = 1000
        self._tracker = TargetTracker(self._route, arrival_threshold=float(threshold))
        self._route_load_failed = False
        return True

    # ------------------------------------------------------------------
    # Completion marks (Requirements 3.5, 3.6, 3.7).
    # ------------------------------------------------------------------
    def _ensure_marks(self) -> None:
        """Load the completed-mark set once, failure-safe (Requirement 3.7).

        If the marks DB cannot be opened or read (missing/corrupt DB, locked
        file, broken connection) the controller keeps rendering with an empty
        completed set and surfaces a one-time read-failure message via
        ``info_set`` -- the background detection loop and map matching are never
        interrupted (Requirements 3.7, 1.6, 10.3).
        """
        if self._marks_loaded:
            return
        self._marks_loaded = True
        from src.utils.MapMarksDB import MapMarksDB, load_completed_or_empty
        # 1) Opening the DB may itself raise (Requirement 3.7) -> empty + warn.
        try:
            self._marks_db = MapMarksDB(MARKS_DB_PATH)
        except Exception as exc:
            logger.warning(f"[Overlay] marks db open failed: {exc}")
            self._marks_db = None
            self._completed_ids = set()
            self._warn_marks_read()
            return
        # 2) Reading may fail even with an open handle; load_completed_or_empty
        # yields an empty set on failure (best-effort), and we probe to know
        # whether to surface the read-failure message.
        try:
            self._completed_ids = self._marks_db.load_completed()
        except Exception as exc:
            logger.warning(f"[Overlay] marks db read failed: {exc}")
            self._completed_ids = load_completed_or_empty(self._marks_db)
            self._warn_marks_read()

    # ------------------------------------------------------------------
    # Three-state entry points (called from run())
    # ------------------------------------------------------------------
    def on_minimap(self, player_pos, state_id) -> None:
        """Minimap state: render via ok OverlayWindow, hide the big-map window.

        Normal_Mode keeps the existing DB-item minimap rendering unchanged;
        Path_Mode renders only the route layers (Requirements 1.3, 4.5, 4.6,
        5.1). The interaction window is hidden so nothing interactive lingers
        outside the big map (Requirement 1.8).
        """
        self._sync_mode_from_config()
        self._hide_interaction_window()
        if not self.task.config.get('_Overlay enabled'):
            return
        if self._path_mode and self._route is not None:
            # Player coordinate update: evaluate auto-advance before drawing so
            # the edge direction arrow reflects the (possibly) advanced target
            # (Requirements 8.2, 9.1, 9.2). No target -> no-op (Requirement 9.4).
            self.maybe_auto_advance(player_pos)
            self._draw_minimap_path(player_pos, state_id)
        else:
            # 普通模式：先加载完成集合再绘制，使小地图排除已完成物品（问题1a）。
            # build_draw_items(minimap=True) 会剔除 completed_ids 中的项。
            self._ensure_marks()
            self.task._draw_overlay(
                player_pos, state_id=state_id, completed_ids=self._completed_ids
            )

    def on_bigmap(self, player_pos, game_scale) -> None:
        """Big-map state: render via the clickable InteractionOverlayWindow.

        Builds mode-aware content (icons with completion opacity, or route
        layers), shows the window, repaints it and refreshes its ``setMask``
        hit region (Requirements 1.2, 1.7, 4.5, 4.6, 5.1). If the interaction
        window is unavailable, falls back to the existing ok-overlay big-map
        rendering so the feature degrades gracefully (the richer fallback +
        message is task 11.5).
        """
        # 游戏窗口不可见/不在前台时的可见性门控（问题3a / 关键 bug 修复）。
        # ok 的 hwnd.visible == is_foreground()，仅当游戏窗口为前台时才为 True；
        # 点击我们自己的交互窗口会让游戏失去前台焦点，使 visible 变为 False，若此时
        # 直接隐藏窗口会把气泡清掉并导致点击查看描述“死锁”。因此当 visible 为 False
        # 时，进一步判断前台是否是“我们自己 app 的窗口”（用户点了交互窗口）：
        #   - our_active 为 True 表示我们 app 的某个窗口是活动窗口（前台是我们自己），
        #     此时不隐藏，继续正常显示与渲染；
        #   - 仅当 not visible 且 not our_active（前台是别的外部应用）时才隐藏并返回。
        # 截屏按 hwnd 抓取、与前台无关，故点击覆盖层不会导致 OCR/匹配失败，不会误触
        # 发 run() 的 on_idle 清除逻辑。
        hwnd = getattr(self.task, 'hwnd', None)
        visible = getattr(hwnd, 'visible', True) if hwnd is not None else True
        if not visible:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            our_active = app is not None and app.activeWindow() is not None
            if not our_active:
                self._hide_interaction_window()
                return
        self._sync_mode_from_config()
        window = self._ensure_interaction_window()
        if window is None:
            # Create-failure fallback (Requirement 1.9): render the big map with
            # the ok OverlayWindow (not clickable) and surface a one-time message,
            # without blocking map drag/zoom or background matching.
            self._warn_interaction()
            self.task._draw_overlay_screen_center(player_pos, game_scale)
            return
        # A big-map pan/move closes any open Description_Bubble (Requirement 2.5).
        self._close_bubble_if_panned(player_pos)
        if self._path_mode and self._route is not None:
            # Player coordinate update: auto-advance before rebuilding content so
            # the rendered target reflects the advance (Requirements 9.1, 9.2);
            # no target -> no-op (Requirement 9.4).
            self.maybe_auto_advance(player_pos)
        window_draw_items, line_layers, hitboxes = self._build_bigmap_content(
            player_pos, game_scale
        )
        # 连线分流到穿透式 ok OverlayWindow 绘制（路线模式画线、普通模式清线）；交互
        # 窗口不再画线，因此其 setMask 掩码只剩节点命中区(+气泡)，轻量、跟手、不挡拖动。
        self._draw_bigmap_lines(line_layers)
        # Cache the rendered content so a click can re-render without rebuilding.
        # 交互窗口不再画线，故缓存的 path_layers 恒为空，_rerender_bigmap 也不带线。
        self._last_draw_items = list(window_draw_items)
        self._last_path_layers = ()
        # 几何仅在变化时才重设，减少多余 GUI 事件（额外优化）。
        geometry = self._client_geometry()
        if geometry != self._last_geometry:
            self._last_geometry = geometry
            window.set_window_geometry(*geometry)
        window.show_overlay()
        # 合并为单次渲染帧：内容 + 气泡 + 命中区在同一个 GUI 事件里原子更新，避免
        # render_items / update_mask 两次排队信号产生的半更新中间帧。连线已分流到 ok
        # 覆盖层，故 path_layers 传空 () —— 交互窗口 _compose_mask_region 里路线 stroker
        # 部分为空，掩码只剩节点命中区(+气泡)。
        window.render_frame(
            window_draw_items, bubble=self._bubble, path_layers=(),
            hitboxes=hitboxes, target_marker=self._last_target_marker,
        )

    def on_idle(self) -> None:
        """Idle state: hide the interaction window (Requirement 1.8).

        The ok OverlayWindow is cleared by the task's own ``_clear_overlay``;
        here we only ensure the clickable big-map window leaves no interactive
        content behind.
        """
        self._hide_interaction_window()

    # ------------------------------------------------------------------
    # Mouse-event actions (task 11.3): Requirements 2, 3, 6, 7
    # ------------------------------------------------------------------
    def _click_target(self, idx):
        """Return the :class:`ClickTarget` for a window click index, or None."""
        if idx is None or not (0 <= idx < len(self._click_targets)):
            return None
        return self._click_targets[idx]

    def on_left_click(self, idx) -> None:
        """Left single click: show the clicked item/node Description_Bubble.

        Switches the single allowed bubble to the clicked icon (Requirements
        2.1, 2.2, 2.3, 6.6, 7.2). For a DB item the bubble text is the location's
        ``description`` (with the empty-description placeholder applied); for a
        route node it is the node's ``position_name``.
        """
        target = self._click_target(idx)
        if target is None:
            return
        if target.kind == 'item':
            description = None
            overlay = getattr(self.task, '_overlay', None)
            if overlay is not None and target.ref_id is not None:
                description = overlay.get_location_description(target.ref_id)
            text = bubble_text(description)
        else:
            text = bubble_text(target.name)
        self._set_bubble(target.sx, target.sy, text)
        self._rerender_bigmap()

    def on_double_click(self, idx) -> None:
        """Left double click: set/replace the Target on a route node.

        Only meaningful in Path_Mode; sets the double-clicked node as the current
        Target, replacing any previous one (Requirements 7.1, 7.5). A double click
        also dismisses any open bubble. DB items have no target concept and are
        ignored.
        """
        target = self._click_target(idx)
        if target is None or target.kind != 'node':
            return
        if self._tracker is None or target.section_id < 0 or target.index < 0:
            return
        try:
            self._tracker.set_target(target.section_id, target.index)
        except ValueError as exc:
            logger.warning(f"[Overlay] set_target failed: {exc}")
            return
        # 便于确认目标已设定（问题3）；下一帧 on_bigmap 会据此画出红圈高亮。
        logger.info(
            f"[Overlay] target set: section={target.section_id} index={target.index}"
        )
        # A target change supersedes a pending bubble.
        self._bubble = None
        self._bubble_player_pos = None
        self._rerender_bigmap()

    def on_right_click(self, idx) -> None:
        """Right click: cancel the Target if it is the clicked node, else toggle
        the completion mark (Requirements 3.2, 3.3, 6.1, 6.2, 6.3, 7.3, 7.4).

        The unified priority (target-cancel beats mark-toggle) is delegated to
        the pure-logic :func:`right_click_dispatch`. In Normal_Mode there is no
        target, so the dispatch always falls through to toggling the item's mark.
        """
        target = self._click_target(idx)
        if target is None or target.ref_id is None:
            return
        self._ensure_marks()
        current_target = self._tracker.target if self._tracker is not None else None
        if target.kind == 'node':
            clicked_ref = TargetRef(section_id=target.section_id, index=target.index)
        else:
            # Items have no target identity; a ref that never equals the current
            # target keeps the dispatch on the mark-toggle branch.
            clicked_ref = TargetRef(section_id=-1, index=-1)

        new_target, new_completed = right_click_dispatch(
            current_target, clicked_ref, target.ref_id, self._completed_ids
        )

        if new_target is None and current_target is not None:
            # Priority 1: the clicked node was the Target -> cancel it, marks
            # left untouched (Requirements 6.3, 7.3).
            if self._tracker is not None:
                self._tracker.clear_target()
            self._rerender_bigmap()
            return

        # Priority 2: persist the toggled completion mark and refresh opacity.
        # On a write/delete failure the in-memory set is rolled back to match the
        # DB's existing records (Requirements 3.8, 6.5); the authoritative set is
        # returned so the cached opacity + re-render reflect the rollback.
        self._completed_ids = self._persist_mark_change(
            self._completed_ids, new_completed
        )
        self._refresh_completion_opacity()
        self._rerender_bigmap()

    def close_bubble(self) -> None:
        """Close the current Description_Bubble (Requirements 2.4, 2.5).

        Invoked when the player clicks empty space inside the mask, when the map
        pans, or when leaving Bigmap_Mode.
        """
        if self._bubble is None and self._bubble_player_pos is None:
            return
        self._bubble = None
        self._bubble_player_pos = None
        self._rerender_bigmap()

    # ------------------------------------------------------------------
    # Advance: global hotkey (manual) + arrival-based (auto). Task 11.4.
    # Requirements 8.2, 9.1, 9.2, 9.3, 9.4.
    # ------------------------------------------------------------------
    def on_advance_hotkey(self) -> None:
        """Manual target advance via the global Advance_Hotkey.

        Runs on the pynput listener thread, so it performs only a lightweight
        state change -- advancing the target one node within its Section -- and
        never touches Qt or triggers a repaint directly (design.md "线程与事件
        模型"). The next detection-loop frame (``on_minimap`` / ``on_bigmap``)
        rebuilds the render to reflect the new target (edge arrow / highlight).
        With no target set, :meth:`TargetTracker.advance` is a no-op so the
        keypress changes nothing (Requirements 9.3, 9.4).
        """
        tracker = self._tracker
        if tracker is None:
            return
        try:
            tracker.advance()
        except Exception as exc:  # pragma: no cover - defensive on listener thread
            logger.warning(f"[Overlay] advance hotkey failed: {exc}")

    def maybe_auto_advance(self, player_pos) -> bool:
        """Auto-advance the target when the player reaches it.

        Called from the detection loop's player-coordinate update (the minimap
        ``result`` and big-map ``self._last_valid`` branches). The player's OCR
        coordinates are converted to game units (x100) via
        :func:`player_ocr_to_game_units` before the distance check
        (Requirement 9.10); arrival within the configured Arrival_Threshold
        advances a single node, debounced so a stationary player only advances
        once (Requirements 9.1, 9.2). With no target this is a no-op
        (:meth:`TargetTracker.maybe_auto_advance` returns ``False``).
        """
        tracker = self._tracker
        if tracker is None or player_pos is None:
            return False
        gx, gy = player_ocr_to_game_units(player_pos)
        advanced = tracker.maybe_auto_advance(gx, gy)
        if advanced:
            # 诊断日志（问题3）：确认每帧都在评估、且到达阈值时确实推进了目标。
            # 不改变阈值默认值与推进逻辑，仅在发生推进时记录新目标。
            logger.info(f"[Overlay] auto-advance -> {tracker.target}")
        return advanced

    def _start_hotkey(self) -> None:
        """Register the global Advance_Hotkey listener on a background thread.

        Called once at controller initialization (and idempotent if called
        again). Uses pynput's ``GlobalHotKeys`` (a daemon listener thread). The
        hotkey string is read from the ``Advance hotkey`` config in pynput format
        (default ``<ctrl>+<f9>``). The callback (:meth:`on_advance_hotkey`) only
        mutates tracker state; rendering is refreshed by the next detection
        frame (Requirements 9.3, 9.9). A registration failure is logged and left
        non-fatal so the rest of the feature keeps working.
        """
        if self._hotkey_listener is not None:
            return
        hotkey = self.task.config.get('Advance hotkey', '<ctrl>+<f9>')
        try:
            from pynput import keyboard
            listener = keyboard.GlobalHotKeys({hotkey: self.on_advance_hotkey})
            listener.daemon = True
            listener.start()
        except Exception as exc:  # pragma: no cover - pynput/runtime specific
            logger.warning(
                f"[Overlay] advance hotkey register failed ({hotkey!r}): {exc}"
            )
            self._hotkey_listener = None
            return
        self._hotkey_listener = listener

    def _stop_hotkey(self) -> None:
        """Stop the global Advance_Hotkey listener (on task destroy)."""
        listener = self._hotkey_listener
        self._hotkey_listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception as exc:  # pragma: no cover - pynput/runtime specific
                logger.warning(f"[Overlay] advance hotkey stop failed: {exc}")

    # -- bubble / render helpers -------------------------------------------
    def _restore_game_focus(self) -> None:
        """[已弃用，不再调用] 点击后把前台焦点还给游戏窗口（问题2）。

        原用于在每次点击后 ``hwnd.bring_to_front()`` 把游戏抬回前台，但该抬前台与置顶
        交互窗口互抢层级，导致点击后气泡瞬灭、叠加层闪烁。现改为让交互窗口根本不夺取
        焦点（``WA_ShowWithoutActivating`` + ``WS_EX_NOACTIVATE``，见
        :class:`InteractionOverlayWindow`），游戏始终保持前台，因此**不再需要**本方法，
        所有点击处理路径均已移除对它的调用。保留方法体仅为兼容性与历史参考，不应再被调用。
        """
        hwnd = getattr(self.task, 'hwnd', None)
        if hwnd is None:
            return
        bring = getattr(hwnd, 'bring_to_front', None)
        if not callable(bring):
            return
        try:
            bring()
        except Exception as e:  # pragma: no cover - Qt/win32 runtime specific
            logger.warning(f"[Overlay] restore game focus failed: {e}")

    def _set_bubble(self, sx, sy, text) -> None:
        """Store the single allowed bubble anchored next to the clicked icon."""
        # 问题2：描述每 25 字硬换行为多行气泡后再存储，交由交互窗口按行绘制。
        text = wrap_text(text, 25)
        half = ICON_SIZE // 2
        self._bubble = (int(sx) + half, int(sy) - half, text)
        self._bubble_player_pos = self._current_player_pos

    def _close_bubble_if_panned(self, player_pos) -> None:
        """Close the bubble when the big map has panned (Requirement 2.5)."""
        self._current_player_pos = player_pos
        if self._bubble is None:
            return
        prev = self._bubble_player_pos
        if prev is None:
            return
        if int(prev[0]) != int(player_pos[0]) or int(prev[1]) != int(player_pos[1]):
            self._bubble = None
            self._bubble_player_pos = None

    def _rerender_bigmap(self) -> None:
        """Repaint the big-map window with the cached content + current bubble.

        Used by click handlers (running on the GUI thread) to reflect a bubble
        or completion-opacity change immediately, without rebuilding content on
        the task thread.
        """
        window = self._interaction_window
        if window is None:
            return
        window.render_items(
            self._last_draw_items, bubble=self._bubble,
            path_layers=self._last_path_layers,
        )

    def _refresh_completion_opacity(self) -> None:
        """Recompute cached draw-item opacity from the completed set (3.5)."""
        refreshed = []
        for item in self._last_draw_items:
            if len(item) > 6:
                location_id = item[6]
                opacity = opacity_for(location_id, self._completed_ids)
                item = item[:5] + (opacity,) + item[6:]
            refreshed.append(item)
        self._last_draw_items = refreshed

    def _persist_mark_change(self, old_completed, new_completed) -> set:
        """Write the add/remove implied by a completion-set change to Marks_DB.

        Returns the authoritative completed set the caller should adopt: the
        optimistic ``new_completed`` on success, or -- when the write/delete
        fails -- the set reconciled against the DB's existing records so the
        in-memory state never diverges from what is persisted (Requirements 3.8,
        6.5). A save failure surfaces a one-time message via ``info_set`` and
        never crashes the GUI thread or interrupts the detection loop.

        When no marks DB is available (its open/read failed earlier, see
        :meth:`_ensure_marks`) there is nothing to persist to; the optimistic
        in-memory toggle is kept so the UI still responds, and the read-failure
        message has already been surfaced.
        """
        if self._marks_db is None:
            return set(new_completed)
        added = new_completed - old_completed
        removed = old_completed - new_completed
        try:
            for location_id in added:
                self._marks_db.add(location_id)
            for location_id in removed:
                self._marks_db.remove(location_id)
        except Exception as exc:
            logger.warning(f"[Overlay] mark persist failed: {exc}")
            from src.utils.MapMarksDB import reconcile_completed
            reconciled = reconcile_completed(new_completed, self._marks_db)
            self._warn_marks_save()
            return reconciled
        # A successful write re-arms the save warning for any future failure.
        self._marks_save_warned = False
        return set(new_completed)

    # ------------------------------------------------------------------
    # One-shot user-visible warnings (task 11.5). Each latch keeps the
    # per-frame / per-click error paths from spamming info_set every time;
    # messages are routed through the task's info_set, consistent with the
    # rest of the task, and never interrupt the detection loop.
    # ------------------------------------------------------------------
    def _warn_interaction(self) -> None:
        if self._interaction_warned:
            return
        self._interaction_warned = True
        self.task.info_set('Overlay', '交互窗口创建失败，已回退到不可点击的覆盖层')

    def _warn_marks_read(self) -> None:
        if self._marks_read_warned:
            return
        self._marks_read_warned = True
        self.task.info_set('Overlay', '标记读取失败，已以空完成集合继续')

    def _warn_marks_save(self) -> None:
        if self._marks_save_warned:
            return
        self._marks_save_warned = True
        self.task.info_set('Overlay', '标记保存失败，已回滚至库内现有记录')

    # ------------------------------------------------------------------
    # Content builders
    # ------------------------------------------------------------------
    def _draw_bigmap_lines(self, line_layers) -> None:
        """把大地图路线连线分流到穿透式 ok OverlayWindow 绘制。

        ok 的 ``OverlayWindow``（``task.get_overlay_view()``）是穿透式
        （``WindowTransparentForInput``）、可自由绘制、无需 mask，因此细连线不会挡拖动，
        与宝箱/小地图共用同一覆盖层机制。

        - ``line_layers`` 非空（路线模式）：用 :meth:`MapItemOverlay.make_paint_callback`
          以 ``draw_path_nodes=False`` 只画连线 + 箭头、跳过节点图标（节点图标由交互
          窗口绘制），注册到 ok 覆盖层。``overlay_view`` 为 None 时跳过。
        - ``line_layers`` 为空（普通模式）：清掉 ok 覆盖层的线（``_clear_overlay``）。
        """
        if line_layers:
            overlay_view = self.task.get_overlay_view()
            if overlay_view is None:
                return
            callback = MapItemOverlay.make_paint_callback(
                [], path_layers=line_layers, draw_path_nodes=False, clip_box=None,
            )
            overlay_view.draw(
                OVERLAY_DRAW_KEY, callback, duration=OVERLAY_DRAW_DURATION
            )
            self.task._overlay_registered = True
        else:
            self.task._clear_overlay()

    def _build_bigmap_content(self, player_pos, game_scale):
        """Build ``(window_draw_items, line_layers, hitboxes)`` for the big map.

        - ``window_draw_items``：交互窗口要绘制的图标（普通模式=db 宝箱项含完成态
          不透明度；路线模式=可见路线节点图标）。
        - ``line_layers``：要在穿透式 ok 覆盖层绘制的连线（仅路线模式非空；普通模式为
          空 ``()``）。
        - ``hitboxes``：交互窗口命中区（与 ``window_draw_items`` / ``click_targets``
          同序）。

        用显式 if/else 实现 Normal_Mode / Path_Mode 互斥（Requirements 4.5, 4.6）：路线
        模式只出节点图标 + 连线，普通模式只出 db 项、无连线。完成态不透明度由
        :func:`build_overlay_draw_items` / :func:`opacity_for` 施加（Requirement 3.5）。
        db 项可见性矩形判定（view_bounds）保持不变。
        """
        task = self.task
        task._init_overlay()
        overlay = task._overlay

        radius = task.config.get('_Search radius (world units)') * BIG_MAP_SEARCH_MULTIPLIER
        if game_scale is not None and 0.01 < game_scale:
            scale = 1.0 / game_scale
        else:
            scale = task._get_default_scale_per_1000() / 1000.0

        type_filter = task.config.get('Item type filter')
        player_x = player_pos[0] * 100
        player_y = player_pos[1] * 100

        _, _, w, h = self._client_geometry()
        center_x = w // 2
        center_y = h // 2
        # 可见区改用“矩形”判定：游戏画面是矩形，用圆判定会漏掉左右两侧（问题3）。
        # 外扩 margin 让进出视野的连线/图标自然过渡；宝箱与路线共用同一矩形边界。
        margin = ICON_SIZE * 2
        view_bounds = (-margin, -margin, w + margin, h + margin)

        self._ensure_marks()
        completed = self._completed_ids

        rows = overlay.query_nearby(
            player_x, player_y, radius, type_filter,
            state_id=task._locked_map_id, with_location_id=True,
        )
        candidates = []
        for location_id, name, type_id, ix, iy, dist in rows:
            sx, sy = overlay.project_to_minimap(
                ix, iy, player_x, player_y, scale, center_x, center_y
            )
            vx_min, vy_min, vx_max, vy_max = view_bounds
            if not (vx_min <= sx <= vx_max and vy_min <= sy <= vy_max):
                continue
            pixmap = ITEM_PIXMAPS.get(type_id)
            color = ITEM_COLORS.get(type_id)
            candidates.append(
                DrawCandidate(sx, sy, pixmap, name, color, location_id, 0)
            )
        db_items = build_overlay_draw_items(
            candidates, minimap=False, completed_ids=completed
        )

        # 两模式互斥（显式 if/else，不再经 select_overlay_content）：
        # - 路线模式：交互窗口画可见节点图标 + 命中区，连线走 ok 覆盖层；
        # - 普通模式：交互窗口画 db 宝箱项 + 命中区，无连线。
        if self._path_mode and self._route is not None:
            clipped_layers, node_draw_items, node_hitboxes, node_click_targets = \
                self._build_visible_path(
                    player_x, player_y, scale, center_x, center_y, view_bounds
                )
            window_draw_items = node_draw_items
            hitboxes = node_hitboxes
            click_targets = node_click_targets
            line_layers = clipped_layers
        else:
            hitboxes, click_targets = self._build_clickables(db_items)
            window_draw_items = db_items
            line_layers = ()

        self._click_targets = click_targets
        self._last_target_marker = self._compute_target_marker(click_targets)
        return window_draw_items, line_layers, hitboxes

    def _build_visible_path(self, player_x, player_y, scale,
                            center_x, center_y, view_bounds):
        """按大地图宝箱套路把路线裁剪到可见区（问题3）。

        返回 ``(clipped_layers, node_draw_items, node_hitboxes, node_click_targets)``：

        - ``clipped_layers``：只含可见附近短折线的 :class:`PathLayer` 序列，供在穿透式
          ok 覆盖层绘制连线（掩码开销小、无远处乱线、随缩放抖动的远段被丢弃）；
        - ``node_draw_items``：每个可见节点的扩展 8-tuple
          ``(sx, sy, pixmap, name, color, opacity, location_id, z)``，供**交互窗口**绘制
          节点图标（qzx_04）；顺序与 ``node_hitboxes`` / ``node_click_targets`` 完全对应
          （同一遍循环产出）；完成路线节点随之变暗（opacity 0.4）；

        - 可见判定用**矩形**边界 ``view_bounds=(x_min,y_min,x_max,y_max)``（游戏画面为
          矩形，圆判定会漏掉左右两侧）；与 db 项共用同一矩形，投影用
          ``overlay.project_to_minimap`` 以相同的 player/scale/center 上下文，与 db 项
          投影完全一致，因此稳定、不随远处抖动。
        - 对每个 section 按**原始节点顺序**投影，按“节点是否可见”切分为若干极大连续
          可见 run（相邻可见节点组成一段折线）。每个 run 生成一个 :class:`PathLayer`
          （``color`` 为该 section 颜色，``points`` 为 run 内节点屏幕点，``node_ids``
          对应）。这样 path_layers 只含可见附近的短折线，掩码 stroker 开销小、无远处
          乱线、随缩放抖动的远段被丢弃；不固定缩放（继续用传入 ``scale``）、不丢弃近处
          可见节点。
        - 命中区与 ClickTarget 只为**可见节点**生成，且使用节点在 section 内的**原始
          index**（下面的 ``node_index``），保证双击 ``set_target(section_id, index)``
          正确、并让 :meth:`_compute_target_marker` 能按 section_id/index 找回目标。

        路线 state 门控与 build_path_layers 一致：仅当路线 ``state_id`` 与当前上下文
        ``_context_state_id`` 匹配时才产出，否则返回空（Requirements 5.5, 5.6）。
        """
        clipped_layers = []
        node_draw_items = []
        node_hitboxes = []
        node_click_targets = []
        if self._route is None:
            return (), node_draw_items, node_hitboxes, node_click_targets
        context_state_id = self._context_state_id()
        if context_state_id is None or self._route.state_id != context_state_id:
            return (), node_draw_items, node_hitboxes, node_click_targets

        overlay = self.task._overlay
        # 节点图标统一使用 qzx_04（Requirement 5.2）；颜色/图标从 MapItemOverlay 常量取，
        # opacity 依完成集合决定（完成路线节点变暗 0.4）。
        node_pixmap = ITEM_PIXMAPS.get(PATH_NODE_ICON_KEY)
        node_color = ITEM_COLORS.get(PATH_NODE_ICON_KEY)
        for section in self._route.sections:
            nodes = section.nodes
            # 与 db 项相同的投影；可见判定用同一屏幕圆，仅多一点外扩 margin。
            projected = [
                overlay.project_to_minimap(
                    node.x, node.y, player_x, player_y, scale, center_x, center_y
                )
                for node in nodes
            ]
            visible = [
                view_bounds[0] <= px <= view_bounds[2]
                and view_bounds[1] <= py <= view_bounds[3]
                for (px, py) in projected
            ]
            n = len(nodes)
            i = 0
            while i < n:
                if not visible[i]:
                    i += 1
                    continue
                # [i..j] 为极大连续可见 run。
                j = i
                while j + 1 < n and visible[j + 1]:
                    j += 1
                run_points = tuple(projected[k] for k in range(i, j + 1))
                run_node_ids = tuple(nodes[k].position_id for k in range(i, j + 1))
                clipped_layers.append(
                    PathLayer(
                        color=section.color,
                        points=run_points,
                        node_ids=run_node_ids,
                    )
                )
                for k in range(i, j + 1):
                    px, py = projected[k]
                    node = nodes[k]
                    node_hitboxes.append(
                        (make_hitbox(px, py, ICON_SIZE, HITBOX_EXPAND), 0)
                    )
                    node_click_targets.append(
                        ClickTarget(
                            kind='node', ref_id=node.position_id,
                            sx=int(px), sy=int(py),
                            section_id=section.section_id, index=k,
                            name=node.position_name,
                        )
                    )
                    # 可见节点的绘制项（交互窗口画节点图标）：8-tuple 顺序与命中区/
                    # ClickTarget 完全一致；opacity 依完成集合（完成路线节点变暗 0.4）。
                    node_draw_items.append(
                        (int(px), int(py), node_pixmap, node.position_name,
                         node_color,
                         opacity_for(node.position_id, self._completed_ids),
                         node.position_id, 0)
                    )
                i = j + 1
        return tuple(clipped_layers), node_draw_items, node_hitboxes, node_click_targets

    def _compute_target_marker(self, click_targets):
        """计算当前路线目标节点在大地图上的投影屏幕点 ``(sx, sy)`` 或 None（问题3）。

        仅路线模式且 tracker 存在目标时才可能非 None：在与目标同序构建的
        ``click_targets`` 中找到 ``kind=='node'`` 且 ``section_id`` / ``index`` 与
        ``tracker.target`` 一致的节点，取其 ``(sx, sy)`` 作为红圈圆心。无目标、非路线
        模式、或该目标节点不在当前帧可见节点中（找不到）时返回 None，使红圈消失。
        """
        tracker = self._tracker
        if not self._path_mode or tracker is None:
            return None
        target = tracker.target
        if target is None:
            return None
        for ct in click_targets:
            if (ct.kind == 'node'
                    and ct.section_id == target.section_id
                    and ct.index == target.index):
                return (ct.sx, ct.sy)
        return None

    def _build_clickables(self, db_items):
        """Compose Hit_Boxes and a parallel :class:`ClickTarget` list for DB items.

        仅处理 db 项（宝箱）：路线节点的命中区/ClickTarget 现由
        :meth:`_build_visible_path` 按可见区裁剪产出（问题3），不再在此处理 path_layers。
        本方法产出的 db 命中区在合并时排在最前（db 在前、path 在后），与掩码/索引顺序
        一致；调用方保证 Normal_Mode / Path_Mode 两组互斥、只有一组非空。
        """
        boxes = []
        targets = []
        for item in db_items:
            sx, sy = item[0], item[1]
            location_id = item[6] if len(item) > 6 else None
            z = item[7] if len(item) > 7 else 0
            boxes.append((make_hitbox(sx, sy, ICON_SIZE, HITBOX_EXPAND), z))
            targets.append(
                ClickTarget(kind='item', ref_id=location_id, sx=sx, sy=sy)
            )
        return boxes, targets

    def _draw_minimap_path(self, player_pos, state_id) -> None:
        """Draw route layers on the minimap via the ok OverlayWindow."""
        task = self.task
        overlay_view = task.get_overlay_view()
        if overlay_view is None:
            return
        task._init_overlay()
        minimap_box = task.get_box_by_name('box_minimap')
        if minimap_box is None:
            return
        scale_per_1000 = task._minimap_scale_per_1000()
        scale = scale_per_1000 / 1000.0
        center_x = minimap_box.x + minimap_box.width / 2
        center_y = minimap_box.y + minimap_box.height / 2
        player_x = player_pos[0] * 100
        player_y = player_pos[1] * 100

        layers = ()
        # 路线层不再要求已锁定地图/上下文 state 匹配：只要 self._route 存在，就用路线
        # 自身的 state_id 构建层（问题1b/1c）。这样只要 OCR 坐标匹配即可绘制路线，
        # 远处的点投影后会被下方 clip_box 的小地图圆形裁剪自然隐藏。
        if self._route is not None:
            layers = build_path_layers(
                self._route, self._route.state_id,
                player_x, player_y, scale, center_x, center_y,
            )
        edge_arrow = self._edge_arrow(player_pos, minimap_box)
        # 目标红圈（问题1b）：tracker 有目标时取目标节点，投影到小地图坐标作为
        # target_marker=(sx,sy) 传入；无目标传 None。圈若落在小地图外会被 clip 裁掉。
        target_marker = None
        node = self._target_node()
        if node is not None:
            target_marker = task._overlay.project_to_minimap(
                node.x, node.y, player_x, player_y, scale, center_x, center_y
            )
        # 将路线连线/箭头裁剪到小地图圆形区域内，避免覆盖整个屏幕（问题4）。
        # minimap_box 即上面通过 get_box_by_name('box_minimap') 获取的小地图框。
        callback = MapItemOverlay.make_paint_callback(
            [], path_layers=layers, edge_arrow=edge_arrow, clip_box=minimap_box,
            target_marker=target_marker,
        )
        overlay_view.draw(OVERLAY_DRAW_KEY, callback, duration=OVERLAY_DRAW_DURATION)
        task._overlay_registered = True

    def _edge_arrow(self, player_pos, minimap_box):
        """Return ``(bearing_deg, minimap_box)`` for the target arrow, or None.

        When either the player's current position or the Target position cannot
        be obtained, the arrow is hidden (returns ``None``) while the Target
        itself is preserved -- it is never cleared here (Requirement 8.4).
        """
        node = self._target_node()
        if node is None:
            # No valid Target position -> hide the arrow, keep the Target.
            return None
        if not self._valid_player_pos(player_pos):
            # No valid player position -> hide the arrow, keep the Target.
            return None
        player_x = player_pos[0] * 100
        player_y = player_pos[1] * 100
        bearing = bearing_degrees(player_x, player_y, node.x, node.y)
        return (bearing, minimap_box)

    @staticmethod
    def _valid_player_pos(player_pos) -> bool:
        """Whether ``player_pos`` carries usable numeric x/y coordinates."""
        if player_pos is None:
            return False
        try:
            float(player_pos[0])
            float(player_pos[1])
        except (TypeError, ValueError, IndexError):
            return False
        return True

    def _target_node(self):
        if self._route is None or self._tracker is None or self._tracker.target is None:
            return None
        ref = self._tracker.target
        for section in self._route.sections:
            if section.section_id == ref.section_id:
                if 0 <= ref.index < len(section.nodes):
                    return section.nodes[ref.index]
        return None

    def _context_state_id(self):
        """Map the locked map id to the route ``state_id`` namespace.

        ``_locked_map_id`` is the items DB / coords map key (a string such as
        ``'906'``) while ``PathRoute.state_id`` (and ``path.json`` ``stateId``)
        is an integer. They share the same numeric identity, so the route is
        drawn only when ``int(_locked_map_id) == route.state_id``
        (Requirements 5.5, 5.6).
        """
        lid = self.task._locked_map_id
        if lid is None:
            return None
        try:
            return int(lid)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Interaction window lifecycle (cross-thread safe)
    # ------------------------------------------------------------------
    def _client_geometry(self):
        """Return the game client area as logical ``(x, y, w, h)`` pixels.

        Mirrors ``ok`` ``OverlayWindow.update_overlay`` which divides by the
        window scaling. Falls back to the captured frame size when the hwnd
        geometry is unavailable.
        """
        hwnd = getattr(self.task, 'hwnd', None)
        if hwnd is not None:
            try:
                scaling = getattr(hwnd, 'scaling', 1) or 1
                x = getattr(hwnd, 'x', 0)
                y = getattr(hwnd, 'y', 0)
                w = getattr(hwnd, 'width', 0)
                h = getattr(hwnd, 'height', 0)
                if w and h:
                    return (int(x / scaling), int(y / scaling),
                            int(w / scaling), int(h / scaling))
            except Exception as exc:  # pragma: no cover - runtime specific
                logger.warning(f"[Overlay] hwnd geometry unavailable: {exc}")
        return 0, 0, self.task.screen_width, self.task.screen_height

    def _ensure_interaction_window(self):
        """Lazily create the InteractionOverlayWindow on the GUI thread.

        The window is a ``QWidget`` and must be constructed on the GUI thread,
        while ``run()`` executes on the ok task thread. Construction is therefore
        marshalled to the GUI thread (the same thread the ok OverlayWindow lives
        on) with a blocking queued invocation. Any failure marks the window
        permanently unavailable so the caller falls back gracefully (the full
        create-failure message is task 11.5).
        """
        if self._interaction_unavailable:
            return None
        if self._interaction_window is not None:
            return self._interaction_window
        try:
            window = self._create_interaction_window()
        except Exception as exc:
            logger.warning(f"[Overlay] interaction window create failed: {exc}")
            window = None
        if window is None:
            # Mark permanently unavailable and surface the one-time create
            # failure message; the big-map caller falls back to the ok
            # OverlayWindow rendering (Requirement 1.9).
            self._interaction_unavailable = True
            self._warn_interaction()
            return None
        self._interaction_window = window
        self._connect_window_signals(window)
        return window

    def _connect_window_signals(self, window) -> None:
        """Wire the window's mouse signals to controller actions, once.

        ``leftClicked`` / ``leftDoubleClicked`` / ``rightClicked`` /
        ``emptyClicked`` carry the hit draw-item index (aligned with
        ``_click_targets``) and are routed to the bubble / target / mark logic
        (task 11.3). Connections are made with the default (auto) connection
        type; the signals are emitted on the GUI thread where the slots then run.
        """
        if self._signals_connected:
            return
        try:
            window.leftClicked.connect(self.on_left_click)
            window.leftDoubleClicked.connect(self.on_double_click)
            window.rightClicked.connect(self.on_right_click)
            window.emptyClicked.connect(self.close_bubble)
        except Exception as exc:  # pragma: no cover - Qt runtime specific
            logger.warning(f"[Overlay] failed to connect window signals: {exc}")
            return
        self._signals_connected = True

    def _create_interaction_window(self):
        from PySide6.QtCore import QMetaObject, QObject, Qt, Slot
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return None

        geometry = self._client_geometry()

        class _Creator(QObject):
            def __init__(self):
                super().__init__()
                self.window = None
                self.error = None

            @Slot()
            def build(self):
                try:
                    from src.utils.InteractionOverlayWindow import (
                        InteractionOverlayWindow,
                    )
                    x, y, w, h = geometry
                    self.window = InteractionOverlayWindow(x, y, w, h)
                except Exception as exc:  # pragma: no cover - Qt runtime
                    self.error = exc

        creator = _Creator()
        gui_thread = app.thread()
        from PySide6.QtCore import QThread
        if QThread.currentThread() is gui_thread:
            creator.build()
        else:
            creator.moveToThread(gui_thread)
            QMetaObject.invokeMethod(creator, "build", Qt.BlockingQueuedConnection)
        if creator.error is not None:
            raise creator.error
        return creator.window

    def _hide_interaction_window(self) -> None:
        # Leaving the big map clears any interactive content + bubble state
        # (Requirements 1.8, 2.6: no bubbles outside Bigmap_Mode).
        self._bubble = None
        self._bubble_player_pos = None
        self._click_targets = []
        if self._interaction_window is not None:
            self._interaction_window.hide_overlay()

    def close(self) -> None:
        """Release the interaction window and marks DB (task on_destroy)."""
        self._stop_hotkey()
        if self._interaction_window is not None:
            try:
                self._interaction_window.hide_overlay()
            except Exception:  # pragma: no cover - Qt runtime
                pass
            self._interaction_window = None
        if self._marks_db is not None:
            try:
                self._marks_db.close()
            except Exception:  # pragma: no cover
                pass
            self._marks_db = None


class MapOverlayTask(TriggerTask, BaseWWTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "High-value items display"
        self.description = "Get player position and display nearby high value items"
        self.icon = FluentIcon.GLOBE
        self.default_config.update({
            '_enabled': True,
            'Detect interval (ms)': 100,
            '_Overlay enabled': True,
            '_Search radius (world units)': 10000,
            '_Auto map scale': True,
            '_Map scale (pixels per 1000 units)': 11.45,
            'World map overlay': True,
            'Item type filter': ['qzx_01', 'qzx_02', 'qzx_03', 'qzx_04'],
            '_Feature algorithm': 'SIFTGZ',
            # Path Mode 开关：Normal_Mode(False) <-> Path_Mode(True)（需求 4.1）
            'Path mode': False,
            # 到达阈值（游戏单位），默认 1000，有效范围 1..100000（需求 9.7、9.8）
            'Arrival threshold (game units)': 1000,
            # 推进热键，pynput GlobalHotKeys 格式，默认 Ctrl+F9（需求 9.9）
            'Advance hotkey': '<ctrl>+<f9>',
        })
        self.config_type['Item type filter'] = {'type': 'multi_selection', 'options': [
            'qzx_01', 'qzx_02', 'qzx_03', 'qzx_04',
        ]}
        self.config_type['_Feature algorithm'] = {'type': 'drop_down', 'options': [
            'SURF', 'SIFT', 'SIFTGZ',
        ]}
        # SpinBox 控件按此范围限制输入；越界值在 validate_config 中由
        # validate_threshold 再次校验并拒绝（需求 9.7、9.8）。
        self.config_type['Arrival threshold (game units)'] = {
            'min': THRESHOLD_MIN, 'max': THRESHOLD_MAX,
        }
        self.config_description = {
            'Path mode': '路线模式：仅显示 assets/path.json 路线，不显示高价值物品',
            'Arrival threshold (game units)': f'自动推进到达阈值（游戏单位），范围 {THRESHOLD_MIN}..{THRESHOLD_MAX}',
            'Advance hotkey': '手动推进目标的热键（pynput 格式，如 <ctrl>+<f9>）',
        }
        self._window = None
        self._last_valid = None
        self._consecutive_far = 0
        self._overlay = None
        self._overlay_registered = False
        self._overlay_controller = None
        self._fallback_failures = 0
        self._locked_map_id = None
        self._last_match_scale = None
        self._engines = {}
        self._coords_dict = None
        self._engine_settings = None
        self._in_team_failures = 0
        self._minimap_match_counter = 0
        self._recheck_counter = 0
        self._minimap_match_scale = None
        # 问题4：小地图缩放缓存（pixels per 1000 game units）。地图锁定态在
        # “匹配缩放 <-> 默认缩放”间瞬断会导致远处路线节点随缩放剧烈抖动。缓存最近一次
        # 基于匹配算得的缩放；当前无匹配缩放但已有缓存时返回缓存值，避免瞬断跳变。
        # 仅在从未获得过匹配缩放时才回退默认值。
        self._last_minimap_scale_per_1000 = None
        self._lock_ocr_pos = None
        self._second_check_done = False
        self._fallback_log_counter = 0
        self._ocr_noresult_counter = 0
        self._position_detector = None

    def validate_config(self, key, value):
        """校验配置项；返回非空消息表示拒绝该值。

        框架的 ``Config.__setitem__`` 仅在校验通过时写入新值，因此返回错误消息会
        让到达阈值保留上一个有效值（需求 9.8）。这里复用纯函数
        ``validate_threshold`` 做范围判定（1..100000 游戏单位），并经 ``info_set``
        额外提示一条配置无效信息。
        """
        if key == 'Arrival threshold (game units)':
            if not validate_threshold(value):
                message = (f"到达阈值无效：{value!r}，须为 "
                           f"{THRESHOLD_MIN}..{THRESHOLD_MAX} 游戏单位，已保留上一有效值")
                self.info_set('Config error', message)
                return message
        return None

    def _get_position_detector(self):
        if self._position_detector is None:
            from src.utils.positionDetector import PositionDetector
            self._position_detector = PositionDetector()
        return self._position_detector

    def _detections_per_second(self):
        interval = self.config.get('Detect interval (ms)')
        return math.ceil(1000 / interval)

    def _window_size(self):
        return max(5, self._detections_per_second())

    def _teleport_confirm_count(self):
        return math.ceil(self._detections_per_second() / 4) + 1

    def _ensure_window(self):
        size = self._window_size()
        if self._window is None or self._window.maxlen != size:
            old = list(self._window) if self._window else []
            self._window = deque(old[-size:], maxlen=size)

    def _check_teleport(self, pos):
        if self._last_valid is None:
            return False
        if _dist2d(pos, self._last_valid) > TELEPORT_THRESHOLD:
            self._consecutive_far += 1
        else:
            self._consecutive_far = 0
            return False

        if self._consecutive_far <= self._teleport_confirm_count():
            return False

        positions = list(self._window)
        if len(positions) >= 2 and _dist2d(positions[-1], positions[-2]) < TELEPORT_SETTLE_DISTANCE:
            return True
        return False

    def _filter_outliers(self):
        if len(self._window) < 3:
            return list(self._window)

        positions = list(self._window)
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        cx = sorted(xs)[len(xs) // 2]
        cy = sorted(ys)[len(ys) // 2]
        center = (cx, cy)

        distances = [_dist2d(p, center) for p in positions]
        sorted_dists = sorted(distances)
        median_dist = sorted_dists[len(sorted_dists) // 2]
        threshold = max(median_dist * OUTLIER_RELATIVE_FACTOR, OUTLIER_FIXED_THRESHOLD)

        filtered = [p for p, d in zip(positions, distances) if d <= threshold]
        return filtered if filtered else [positions[-1]]

    def _denoise(self, position_text):
        pos = _parse_position(position_text)
        if pos is None:
            return self._last_valid

        self._ensure_window()
        self._window.append(pos)

        if self._last_valid is None:
            self._last_valid = pos
            return pos

        if self._check_teleport(pos):
            self._window.clear()
            self._window.append(pos)
            self._last_valid = pos
            self._consecutive_far = 0
            if self._locked_map_id is not None:
                logger.info(f"[MapFallback] teleport detected, unlocking map_id={self._locked_map_id}")
                self._locked_map_id = None
                self._minimap_match_scale = None
                self._lock_ocr_pos = None
                self._second_check_done = False
            return pos

        if self._consecutive_far > 0:
            return self._last_valid

        filtered = self._filter_outliers()
        self._last_valid = filtered[-1]
        return self._last_valid

    def _ensure_coords(self):
        if self._coords_dict is not None:
            return
        self._coords_dict = _load_coords_dict(MAP_DIR)
        logger.info(f"[MapFallback] loaded {len(self._coords_dict)} coords from {MAP_DIR}: {list(self._coords_dict.keys())}")

    def _load_engine_settings(self):
        if self._engine_settings is not None:
            return self._engine_settings
        settings_path = os.path.join(MAP_DIR, 'setting.json')
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                self._engine_settings = json.load(f)
        except Exception as e:
            logger.warning(f"[MapFallback] failed to load setting.json: {e}")
            self._engine_settings = {}
        return self._engine_settings

    def _resolve_engine_kwargs(self, algo, map_id):
        from src.match_engine.params import ParamSet, params_to_engine_kwargs

        settings = self._load_engine_settings()
        algo_key = algo.lower()
        algo_cfg = settings.get(algo_key, {})

        param_name = None
        maps_cfg = algo_cfg.get('maps', {})
        if map_id in maps_cfg:
            param_name = maps_cfg[map_id]
        elif 'default' in algo_cfg:
            param_name = algo_cfg['default']

        if param_name:
            try:
                ps = ParamSet.from_name(param_name)
                kwargs = params_to_engine_kwargs(ps)
                logger.info(f"[MapFallback] setting.json resolved {algo_key}/{map_id} → {param_name}")
                return kwargs
            except Exception as e:
                logger.warning(f"[MapFallback] failed to parse param name {param_name!r}: {e}")

        return None

    def _get_engine(self, map_id):
        if map_id in self._engines:
            return self._engines[map_id]

        algo = self.config.get('_Feature algorithm', 'SIFTGZ').upper()
        algo_lower = algo.lower()
        npz_path = os.path.join(MAP_DIR, f"{map_id}_{algo_lower}.npz")
        map_path = os.path.join(MAP_DIR, f"{map_id}.png")

        if not os.path.exists(npz_path) and not os.path.exists(map_path):
            logger.warning(f"[MapFallback] no npz cache or png for map {map_id}")
            return None

        kwargs = self._resolve_engine_kwargs(algo, map_id) or {}
        dummy_coords = os.path.join(MAP_DIR, f"__no_coords_{map_id}")

        if algo == 'SIFT':
            from src.match_engine import SiftEngine
            engine = SiftEngine(map_id=map_id, map_path=map_path,
                                assets_dir=MAP_DIR,
                                coords_path=dummy_coords, **kwargs)
        elif algo == 'SIFTGZ':
            from src.match_engine import SiftGzEngine
            engine = SiftGzEngine(map_id=map_id, map_path=map_path,
                                  assets_dir=MAP_DIR,
                                  coords_path=dummy_coords, **kwargs)
        else:
            from src.match_engine import SurfEngine
            engine = SurfEngine(map_id=map_id, map_path=map_path,
                                assets_dir=MAP_DIR,
                                coords_path=dummy_coords, **kwargs)

        self._attach_coords(engine, map_id)
        self._engines[map_id] = engine
        return engine

    def _attach_coords(self, engine, map_id):
        from src.match_engine.common import CoordsRef
        self._ensure_coords()
        d = self._coords_dict.get(map_id)
        if d is None:
            return
        try:
            engine.coords = CoordsRef(
                offset=(float(d['offset'][0]), float(d['offset'][1])),
                scale=(float(d['scale'][0]), float(d['scale'][1])),
                min_xy=(float(d.get('min', [0, 0])[0]), float(d.get('min', [0, 0])[1])),
                max_xy=(float(d.get('max', [0, 0])[0]), float(d.get('max', [0, 0])[1])),
            )
        except Exception as e:
            logger.warning(f"[MapFallback] failed to load coords for map {map_id}: {e}")

    def _try_map_match(self, player_pos, full_map=False, crop_size=FRAME_CROP_SIZE):
        self._ensure_coords()
        if not self._coords_dict:
            logger.warning("[MapFallback] no coords dict loaded")
            return None

        game_x = player_pos[0] * 100
        game_y = player_pos[1] * 100

        if full_map and self._locked_map_id is None:
            candidates = list(self._coords_dict.items())
        elif self._locked_map_id is not None:
            candidates = [(self._locked_map_id, self._coords_dict[self._locked_map_id])]
        else:
            candidates = _filter_candidate_maps(player_pos, self._coords_dict)
            if not candidates:
                logger.warning(f"[MapFallback] no candidate maps for game=({game_x},{game_y})")
                return None
            candidates.sort(key=lambda c: c[0] in SLOW_MAP_IDS)

        self._fallback_log_counter += 1
        verbose = self._fallback_log_counter <= 3 or self._fallback_log_counter % 20 == 0
        if verbose:
            logger.info(
                f"[MapFallback] OCR=({player_pos[0]},{player_pos[1]}) "
                f"{'full-map' if full_map else 'region'} "
                f"candidates={[c[0] for c in candidates]}"
            )

        h, w = self.frame.shape[:2]
        cx, cy = w // 2, h // 2
        half = crop_size // 2
        cropped = self.frame[cy - half:cy + half, cx - half:cx + half]

        algo = self.config.get('_Feature algorithm', 'SIFTGZ')

        for map_id, coords_d in candidates:
            try:
                engine = self._get_engine(map_id)
            except Exception as e:
                logger.warning(f"[MapFallback] failed to init engine for map {map_id}: {e}")
                continue

            if full_map:
                region = None
                region_str = "full-map"
            else:
                scale = coords_d['scale'][0]
                offset_x = coords_d['offset'][0]
                offset_y = coords_d['offset'][1]
                pixel_x = (game_x - offset_x) / scale
                pixel_y = (game_y - offset_y) / scale

                region_size = MAP_REGION_SIZE
                if self._last_match_scale is not None and self._last_match_scale > 1:
                    region_size = max(MAP_REGION_SIZE, int(MAP_REGION_SIZE * self._last_match_scale))
                half_r = region_size // 2
                region = (int(pixel_x - half_r), int(pixel_y - half_r), region_size, region_size)
                region_str = f"region=({region[0]},{region[1]},{region[2]}x{region[3]})"

            try:
                result = engine.match_array(cropped, region=region, crop_size=0)
            except Exception as e:
                logger.warning(f"[MapFallback] match error map={map_id}: {e}")
                continue

            if result.success and result.confidence >= CONFIDENCE_THRESHOLD and result.match_count >= 10:
                gc = result.game_center
                gc_str = f"({gc[0]:.0f},{gc[1]:.0f})" if gc else "None"
                center_str = f"({result.center[0]:.0f},{result.center[1]:.0f})" if result.center else "None"
                if self._locked_map_id is None:
                    self._locked_map_id = map_id
                logger.info(
                    f"[MapFallback] map={map_id} {region_str} algo={algo} "
                    f"matches={result.match_count} inliers={result.inlier_count} "
                    f"conf={result.confidence:.3f} scale={result.map_scale:.4f} "
                    f"center={center_str} game={gc_str} "
                    f"elapsed={result.elapsed_ms:.0f}ms"
                )
                return result

            if verbose:
                logger.info(
                    f"[MapFallback] map={map_id} {region_str} algo={algo} "
                    f"matches={result.match_count} inliers={result.inlier_count} "
                    f"conf={result.confidence:.3f} "
                    f"{'rejected (conf<%.1f or matches<10)' % CONFIDENCE_THRESHOLD if not result.success else 'rejected'} "
                    f"elapsed={result.elapsed_ms:.0f}ms"
                )

        logger.warning("[MapFallback] all candidates tried, none with sufficient confidence")
        return None

    def _is_minimap_dark(self):
        minimap_box = self.get_box_by_name('box_minimap')
        if minimap_box is None:
            return True
        x, y, w, h = minimap_box.x, minimap_box.y, minimap_box.width, minimap_box.height
        if x < 0 or y < 0 or x + w > self.frame.shape[1] or y + h > self.frame.shape[0]:
            return True
        minimap_img = self.frame[y:y + h, x:x + w]
        gray = cv2.cvtColor(minimap_img, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray)) < 60

    def _match_minimap_map_id(self, player_pos):
        minimap_box = self.get_box_by_name('box_minimap')
        if minimap_box is None:
            return None

        x, y, w, h = minimap_box.x, minimap_box.y, minimap_box.width, minimap_box.height
        if x < 0 or y < 0 or x + w > self.frame.shape[1] or y + h > self.frame.shape[0]:
            return None

        minimap_img = self.frame[y:y + h, x:x + w]
        center = (w // 2, h // 2)
        radius = min(w, h) // 2
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, center, radius, 255, -1)
        masked = cv2.bitwise_and(minimap_img, minimap_img, mask=mask)
        gray = cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)

        self._ensure_coords()
        if not self._coords_dict:
            return None

        candidates = _filter_candidate_maps(player_pos, self._coords_dict)
        if not candidates:
            return None

        matched = []
        for map_id, coords_d in candidates:
            engine = self._get_engine(map_id)
            if engine is None:
                continue

            game_x = player_pos[0] * 100
            game_y = player_pos[1] * 100
            scale = coords_d['scale'][0]
            offset_x = coords_d['offset'][0]
            offset_y = coords_d['offset'][1]
            pixel_x = (game_x - offset_x) / scale
            pixel_y = (game_y - offset_y) / scale

            region_size = MAP_REGION_SIZE
            half_r = region_size // 2
            region = (int(pixel_x - half_r), int(pixel_y - half_r), region_size, region_size)

            try:
                result = engine.match_array(gray, region=region, crop_size=0, constrained=True)
            except Exception as e:
                logger.warning(f"[MinimapMatch] match error for map {map_id}: {e}")
                continue

            logger.info(
                f"[MinimapMatch] map={map_id} conf={result.confidence:.3f} "
                f"matches={result.match_count} inliers={result.inlier_count}"
            )

            if result.success and result.confidence >= CONFIDENCE_THRESHOLD and result.match_count >= 10:
                matched.append((map_id, result.map_scale))

        if len(matched) == 1:
            return matched[0]
        if len(matched) > 1:
            logger.info(f"[MinimapMatch] ambiguous: {len(matched)} maps matched {[m[0] for m in matched]}")
        return None

    def _verify_locked_map(self, player_pos):
        if self._locked_map_id is None:
            return False

        minimap_box = self.get_box_by_name('box_minimap')
        if minimap_box is None:
            return False

        x, y, w, h = minimap_box.x, minimap_box.y, minimap_box.width, minimap_box.height
        if x < 0 or y < 0 or x + w > self.frame.shape[1] or y + h > self.frame.shape[0]:
            return False

        minimap_img = self.frame[y:y + h, x:x + w]
        center = (w // 2, h // 2)
        radius = min(w, h) // 2
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, center, radius, 255, -1)
        masked = cv2.bitwise_and(minimap_img, minimap_img, mask=mask)
        gray = cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)

        self._ensure_coords()
        if not self._coords_dict:
            return False

        coords_d = self._coords_dict.get(self._locked_map_id)
        if coords_d is None:
            return False

        engine = self._get_engine(self._locked_map_id)
        if engine is None:
            return False

        game_x = player_pos[0] * 100
        game_y = player_pos[1] * 100
        scale = coords_d['scale'][0]
        offset_x = coords_d['offset'][0]
        offset_y = coords_d['offset'][1]
        pixel_x = (game_x - offset_x) / scale
        pixel_y = (game_y - offset_y) / scale

        region_size = MAP_REGION_SIZE
        half_r = region_size // 2
        region = (int(pixel_x - half_r), int(pixel_y - half_r), region_size, region_size)

        try:
            result = engine.match_array(gray, region=region, crop_size=0, constrained=True)
        except Exception as e:
            logger.warning(f"[MinimapVerify] match error for map {self._locked_map_id}: {e}")
            return False

        logger.info(
            f"[MinimapVerify] map={self._locked_map_id} conf={result.confidence:.3f} "
            f"matches={result.match_count} inliers={result.inlier_count}"
        )

        if result.success and result.confidence >= CONFIDENCE_THRESHOLD and result.match_count >= 10:
            self._minimap_match_scale = result.map_scale
            return True
        return False

    def _in_big_map(self):
        if self.frame is None:
            return False
        h, w = self.frame.shape[:2]
        matches = 0
        for (rx, ry), (b, g, r) in BIG_MAP_COLOR_CHECKS:
            px = int(rx * w)
            py = int(ry * h)
            pixel = self.frame[py, px]
            pb, pg, pr = int(pixel[0]), int(pixel[1]), int(pixel[2])
            if (abs(pb - b) <= BIG_MAP_COLOR_TOLERANCE and
                    abs(pg - g) <= BIG_MAP_COLOR_TOLERANCE and
                    abs(pr - r) <= BIG_MAP_COLOR_TOLERANCE):
                matches += 1
        return matches >= 3

    def run(self):

        if self.scene.in_team(self.in_team_and_world):
            self._fallback_failures = 0
            self._in_team_failures = 0
            self._last_match_scale = None

            start = time.time()
            raw_position = self._get_position_detector().detect_position(self.frame)
            elapsed = (time.time() - start) * 1000

            if raw_position:
                result = self._denoise(raw_position)
                if result:
                    self._ocr_noresult_counter = 0
                    if result[0] % 25 == 0:
                        pos_text = f'{result[0]},{result[1]},{result[2]}'
                        self.info_set('OCR check', f'position: {pos_text} took {elapsed:.0f}ms')

                    if self._is_minimap_dark():
                        if self._locked_map_id is not None:
                            logger.info("[MinimapMatch] minimap too dark, unlocking")
                            self._locked_map_id = None
                            self._minimap_match_scale = None
                            self._lock_ocr_pos = None
                            self._second_check_done = False
                        self.sleep(2)
                        return

                    self._recheck_counter += 1
                    interval = self.config.get('Detect interval (ms)', 500)
                    recheck_interval = math.ceil(30 * 1000 / interval)

                    if self._locked_map_id is not None and self._recheck_counter >= recheck_interval:
                        self._recheck_counter = 0
                        if self._verify_locked_map(result):
                            logger.info(f"[MinimapVerify] recheck passed, map_id={self._locked_map_id}")
                        else:
                            logger.info(f"[MinimapVerify] recheck failed, unlocking map_id={self._locked_map_id}")
                            self._locked_map_id = None
                            self._minimap_match_scale = None
                            self._lock_ocr_pos = None
                            self._second_check_done = False
                    elif self._locked_map_id is None:
                        self._recheck_counter = 0

                    match_interval = max(1, math.ceil(1000 / interval))
                    self._minimap_match_counter += 1

                    if self._locked_map_id is None and self._minimap_match_counter >= match_interval:
                        self._minimap_match_counter = 0
                        match_result = self._match_minimap_map_id(result)
                        if match_result:
                            self._locked_map_id, self._minimap_match_scale = match_result
                            self._lock_ocr_pos = (result[0], result[1])
                            self._second_check_done = False
                            logger.info(f"[MinimapMatch] locked map_id={self._locked_map_id} map_scale={self._minimap_match_scale:.4f}")

                    if self._locked_map_id is not None and not self._second_check_done and self._lock_ocr_pos is not None:
                        dx = abs(result[0] - self._lock_ocr_pos[0])
                        dy = abs(result[1] - self._lock_ocr_pos[1])
                        if dx + dy >= 20:
                            if self._verify_locked_map(result):
                                self._second_check_done = True
                                self._lock_ocr_pos = (result[0], result[1])
                                logger.info(f"[MinimapVerify] second check passed, map_id={self._locked_map_id}")
                            else:
                                logger.info(f"[MinimapVerify] second check failed, unlocking map_id={self._locked_map_id}")
                                self._locked_map_id = None
                                self._minimap_match_scale = None
                                self._lock_ocr_pos = None
                                self._second_check_done = False

                    if self.config.get('_Overlay enabled'):
                        self._overlay_ctl().on_minimap(result, self._locked_map_id)
                else:
                    self._ocr_noresult_counter += 1
                    if self._ocr_noresult_counter <= 3 or self._ocr_noresult_counter % 20 == 0:
                        logger.info(f"[ocr check] ocr noresult ({self._ocr_noresult_counter})")
                    # 当前帧去噪后无有效定位（丢失定位）：清理交互窗口绘制（问题3b）。
                    self._overlay_ctl().on_idle()
            else:
                self._ocr_noresult_counter += 1
                if self._ocr_noresult_counter <= 3 or self._ocr_noresult_counter % 20 == 0:
                    logger.info(f"[ocr check] no raw_position ({self._ocr_noresult_counter})")
                # 当前帧无原始定位（丢失 OCR）：清理交互窗口绘制（问题3b）。
                self._overlay_ctl().on_idle()

            interval = self.config.get('Detect interval (ms)', 500)
            self.sleep(interval / 1000)
            return

        if self._in_big_map():
            if self.config.get('World map overlay') and self._last_valid is not None:
                attempt = self._fallback_failures + 1
                is_third = (self._fallback_failures == 2)
                is_fourth = (self._fallback_failures == 3)

                use_full_map = is_third or is_fourth
                if is_fourth and self._locked_map_id is not None:
                    logger.info(f"[MapFallback] attempt {attempt}/{FALLBACK_MAX_FAILURES}, unlocking map_id={self._locked_map_id} for full-map all")
                    self._locked_map_id = None
                    self._minimap_match_scale = None
                    self._lock_ocr_pos = None
                    self._second_check_done = False

                crop_size = FRAME_CROP_SIZE + 100 * self._fallback_failures

                verbose = self._fallback_log_counter <= 3 or self._fallback_log_counter % 20 == 0
                if verbose:
                    logger.info(
                        f"[MapFallback] big map attempt {attempt}/{FALLBACK_MAX_FAILURES}"
                        f"{', full-map' if use_full_map else ''}, crop={crop_size}"
                    )
                result = self._try_map_match(self._last_valid, full_map=use_full_map, crop_size=crop_size)
                if result is None or not result.success:
                    self._fallback_failures += 1
                    logger.warning(
                        f"[MapFallback] failed {self._fallback_failures}/{FALLBACK_MAX_FAILURES}"
                    )
                    # 大地图匹配失败（丢失定位）：清理交互窗口绘制（问题3b）。
                    # 不改变回退计数与重试逻辑。
                    self._overlay_ctl().on_idle()
                else:
                    self._last_match_scale = result.map_scale
                    self._fallback_failures = 0
                    if result.game_center:
                        new_x = int(result.game_center[0] / 100)
                        new_y = int(result.game_center[1] / 100)
                        new_z = self._last_valid[2] if len(self._last_valid) > 2 else 0
                        self._last_valid = (new_x, new_y, new_z)
                    game_scale = self._compute_game_scale(result)
                    self._overlay_ctl().on_bigmap(self._last_valid, game_scale)

                if self._fallback_failures >= FALLBACK_MAX_FAILURES:
                    logger.warning("[MapFallback] max failures reached, sleeping 2s then resetting")
                    self._locked_map_id = None
                    self._minimap_match_scale = None
                    self._lock_ocr_pos = None
                    self._second_check_done = False
                    self._fallback_failures = 0
                    self.sleep(2)
            else:
                self._clear_overlay()
                self._overlay_ctl().on_idle()

            interval = self.config.get('Detect interval (ms)', 500)
            self.sleep(interval * 2 / 1000)
            return

        self._clear_overlay()
        self._overlay_ctl().on_idle()
        self._in_team_failures += 1
        if self._in_team_failures >= 5 and self._locked_map_id is not None:
            logger.info(f"[MinimapMatch] in_team failed {self._in_team_failures} times, unlocking map_id={self._locked_map_id}")
            self._locked_map_id = None
            self._minimap_match_scale = None
            self._lock_ocr_pos = None
            self._second_check_done = False
        interval = self.config.get('Detect interval (ms)', 500)
        self.sleep(interval / 1000)

    def _init_overlay(self):
        if self._overlay is not None:
            return
        db_path = os.path.join(MAP_DIR, 'map_items.db')
        self._overlay = MapItemOverlay(db_path)

    def _overlay_ctl(self):
        """Lazily build the three-state OverlayController collaborator."""
        if self._overlay_controller is None:
            self._overlay_controller = OverlayController(self)
        return self._overlay_controller

    def _minimap_scale_per_1000(self):
        """Resolve the minimap scale (pixels per 1000 game units).

        Prefers the live minimap match scale combined with the locked map's
        coords scale; otherwise falls back to the configured/auto default.
        Shared by both the Normal_Mode minimap draw and the Path_Mode minimap
        route draw so the two stay aligned.
        """
        if self._minimap_match_scale is not None and self._locked_map_id is not None:
            self._ensure_coords()
            coords_d = self._coords_dict.get(self._locked_map_id) if self._coords_dict else None
            if coords_d:
                coords_scale = coords_d.get('scale', [1.0, 1.0])[0]
                game_scale = self._minimap_match_scale * coords_scale
                if game_scale > 0:
                    # 问题4：能算出基于匹配的缩放 -> 更新缓存并返回，稳定后续帧。
                    scale = 1000.0 / game_scale
                    self._last_minimap_scale_per_1000 = scale
                    return scale
                return 0
        # 无匹配缩放（会回退默认）但存在缓存值 -> 返回缓存值，避免锁定态瞬断造成的
        # 缩放跳变导致路线/宝箱节点抖动（问题4）。仅在从未获得过匹配缩放时用默认值。
        if self._last_minimap_scale_per_1000 is not None:
            return self._last_minimap_scale_per_1000
        return self._get_default_scale_per_1000()

    def _get_default_scale_per_1000(self):
        if self.config.get('_Auto map scale'):
            scale_factor = 1 - (1.25 - self.screen_width / 1600)
            return scale_factor * 1.205 * 10
        return self.config.get('_Map scale (pixels per 1000 units)')

    _scale_log_counter = 0

    def _draw_overlay(self, player_pos, state_id=None, completed_ids=None):
        overlay_view = self.get_overlay_view()
        if overlay_view is None:
            return

        self._init_overlay()

        minimap_box = self.get_box_by_name('box_minimap')
        if minimap_box is None:
            return

        minimap_r = min(minimap_box.width, minimap_box.height) // 2
        scale_per_1000 = self._minimap_scale_per_1000()

        scale = scale_per_1000 / 1000.0
        radius = minimap_r / scale if scale > 0 else self.config.get('_Search radius (world units)')

        self._scale_log_counter += 1
        if self._scale_log_counter <= 3 or self._scale_log_counter % 50 == 0:
            logger.info(
                f"[OverlayScale] map_id={self._locked_map_id} "
                f"scale_per_1000={scale_per_1000:.4f} "
                f"minimap_r={minimap_r} "
                f"search_radius={radius:.0f}"
            )

        type_filter = self.config.get('Item type filter')
        player_x = player_pos[0] * 100
        player_y = player_pos[1] * 100

        draw_items = self._overlay.build_draw_items(
            player_x, player_y, minimap_box, radius, scale_per_1000, type_filter,
            state_id=state_id, completed_ids=completed_ids
        )

        callback = MapItemOverlay.make_paint_callback(draw_items)
        overlay_view.draw(OVERLAY_DRAW_KEY, callback, duration=OVERLAY_DRAW_DURATION)
        self._overlay_registered = True

    def _compute_game_scale(self, result):
        if result.map_scale <= 0 or not result.game_center:
            return None
        map_id = self._locked_map_id
        if map_id is None or map_id not in self._coords_dict:
            return None
        coords_scale = self._coords_dict[map_id].get('scale', [1.0, 1.0])
        game_scale = result.map_scale * coords_scale[0]
        return game_scale

    def _draw_overlay_screen_center(self, player_pos, game_scale=None):
        overlay_view = self.get_overlay_view()
        if overlay_view is None:
            return
        self._init_overlay()
        radius = self.config.get('_Search radius (world units)') * BIG_MAP_SEARCH_MULTIPLIER
        if game_scale is not None and 0.01 < game_scale:
            scale = 1.0 / game_scale
        else:
            scale_per_1000 = self._get_default_scale_per_1000()
            scale = scale_per_1000 / 1000.0
        type_filter = self.config.get('Item type filter')
        player_x = player_pos[0] * 100
        player_y = player_pos[1] * 100

        items = self._overlay.query_nearby(player_x, player_y, radius, type_filter,
                                            state_id=self._locked_map_id)

        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        screen_radius = min(self.screen_width, self.screen_height) // 2

        draw_items = []
        for name, type_id, ix, iy, dist in items:
            sx, sy = self._overlay.project_to_minimap(
                ix, iy, player_x, player_y, scale, center_x, center_y
            )
            dx_center = sx - center_x
            dy_center = sy - center_y
            if math.sqrt(dx_center ** 2 + dy_center ** 2) > screen_radius:
                continue
            pixmap = ITEM_PIXMAPS.get(type_id)
            color = ITEM_COLORS.get(type_id)
            draw_items.append((sx, sy, pixmap, name, color))

        callback = MapItemOverlay.make_paint_callback(draw_items)
        overlay_view.draw(OVERLAY_DRAW_KEY, callback, duration=OVERLAY_DRAW_DURATION)
        self._overlay_registered = True

    def _clear_overlay(self):
        if not self._overlay_registered:
            return
        overlay_view = self.get_overlay_view()
        if overlay_view is not None:
            overlay_view.clear_draw(OVERLAY_DRAW_KEY)
        self._overlay_registered = False

    def on_destroy(self):
        overlay_view = self.get_overlay_view()
        if overlay_view is not None:
            overlay_view.clear_draw(OVERLAY_DRAW_KEY)
        if self._overlay_controller is not None:
            self._overlay_controller.close()
        if self._overlay is not None:
            self._overlay.close()
