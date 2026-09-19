import math
import os
import sqlite3
from typing import Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPen,
    QPixmap,
    QPolygon,
    QRegion,
)

from src.utils.map_geometry import distance_game_units, edge_arrow_position
from src.utils.PathRoute import PATH_NODE_ICON_KEY

ITEM_COLORS = {
    'qzx_01': QColor(255, 165, 0),
    'qzx_02': QColor(255, 255, 0),
    'qzx_03': QColor(255, 0, 255),
    'qzx_04': QColor(0, 165, 255),
    'cx_0': QColor(0, 255, 0),
}
FALLBACK_COLOR = QColor(255, 255, 255)

ICON_SIZE = 30

# [已弃用] 早先用于在图标黑底直径上额外增加的像素数。现在黑底直径 = 图标本身
# 大小（radius = icon_size // 2），不再额外放大，因此该常量保留为 0 仅为兼容导入
# 它的其它模块，不再参与 :func:`paint_icon_background` 的直径计算。
ICON_BG_EXTRA = 0

ITEM_PIXMAPS = {}

# --------------------------------------------------------------------------
# Pure-logic layer (Qt-free) for draw-item construction.
#
# The functions and constants below contain **no** Qt logic of their own: they
# operate on plain Python data (ids, sets, numbers, strings) and merely pass any
# pixmap/color objects through untouched. They are importable and testable on a
# development machine without a live game, and back the numbered correctness
# properties for task 7 (Properties 4, 6, 7, 8, 17).
#
# Feature: map-overlay-interaction
# Requirements: 2.7, 3.4, 3.5, 4.5, 4.6, 9.10
# --------------------------------------------------------------------------

# Placeholder shown in a Description_Bubble when a location has no description
# (Requirement 2.7).
PLACEHOLDER_DESCRIPTION = "该地点暂无描述"

# Completed / not-completed icon opacity on the big map (Requirement 3.5).
COMPLETED_OPACITY = 0.4
NOT_COMPLETED_OPACITY = 1.0

# Player OCR coordinates are multiplied by this factor to obtain game units
# (matches the existing ``player_x = player_pos[0] * 100`` convention,
# Requirement 9.10).
PLAYER_OCR_TO_GAME_SCALE = 100


class DrawCandidate(NamedTuple):
    """A projected, radius-filtered candidate item ready for draw-item shaping.

    This is the Qt-free input to :func:`build_overlay_draw_items`. ``pixmap`` and
    ``color`` may be real Qt objects in the render path or ``None`` in tests; the
    pure builder only passes them through and never inspects them, so the shaping
    logic stays Qt-free and testable.
    """

    sx: int
    sy: int
    pixmap: object
    name: str
    color: object
    location_id: str
    z: int = 0


# The extended draw item tuple shape produced by the builders and consumed by
# ``make_paint_callback``:
#   (sx, sy, pixmap, name, color, opacity, location_id, z)
DrawItem = Tuple[int, int, object, str, object, float, object, int]


def wrap_text(text, width=25) -> str:
    """按“每 ``width`` 个字符”硬换行，返回用 '\\n' 连接的多行字符串（问题2）。

    纯函数、无 Qt 依赖。中文按 1 个字符计（Python ``len`` 对中文即为字数），因此每
    ``width`` 个字符（含中英文混排）切一行。空串返回空串；``width <= 0`` 时视为不换行
    直接返回原文，避免除零 / 死循环。非字符串输入先转为 ``str`` 再处理。
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if text == "":
        return ""
    if width <= 0:
        return text
    lines = [text[i:i + width] for i in range(0, len(text), width)]
    return "\n".join(lines)


def bubble_text(description) -> str:
    """Return the Description_Bubble text for a location description.

    Returns the placeholder :data:`PLACEHOLDER_DESCRIPTION` ("该地点暂无描述")
    when the description is ``None``, an empty string, or whitespace-only;
    otherwise returns the original description unchanged (Requirement 2.7).
    """
    if description is None:
        return PLACEHOLDER_DESCRIPTION
    if not isinstance(description, str):
        # Defensive: a non-string, non-None value is treated as "has content"
        # only when it is truthy; otherwise fall back to the placeholder.
        return str(description) if description else PLACEHOLDER_DESCRIPTION
    if description.strip() == "":
        return PLACEHOLDER_DESCRIPTION
    return description


def opacity_for(location_id, completed_ids: Optional[Set]) -> float:
    """Return the render opacity for an item given the completed-id set.

    Completed items render at :data:`COMPLETED_OPACITY` (0.4), not-completed
    items at :data:`NOT_COMPLETED_OPACITY` (1.0) (Requirement 3.5).
    """
    completed = completed_ids or ()
    return COMPLETED_OPACITY if location_id in completed else NOT_COMPLETED_OPACITY


def build_overlay_draw_items(
    candidates: Iterable[DrawCandidate],
    *,
    minimap: bool,
    completed_ids: Optional[Set] = None,
) -> List[DrawItem]:
    """Shape projected candidates into extended draw items (pure logic).

    For each candidate produces an 8-tuple
    ``(sx, sy, pixmap, name, color, opacity, location_id, z)``.

    - On the minimap (``minimap=True``) any candidate whose ``location_id`` is in
      ``completed_ids`` is excluded entirely (Requirement 3.4); remaining items
      render fully opaque.
    - On the big map (``minimap=False``) completed candidates are kept but
      rendered at :data:`COMPLETED_OPACITY`, not-completed at
      :data:`NOT_COMPLETED_OPACITY` (Requirement 3.5).
    """
    completed = completed_ids or set()
    result: List[DrawItem] = []
    for c in candidates:
        is_done = c.location_id in completed
        if minimap and is_done:
            continue
        opacity = COMPLETED_OPACITY if is_done else NOT_COMPLETED_OPACITY
        result.append(
            (c.sx, c.sy, c.pixmap, c.name, c.color, opacity, c.location_id, c.z)
        )
    return result


def select_overlay_content(path_mode: bool, db_items, path_layers):
    """Apply Normal_Mode / Path_Mode exclusivity to overlay content (pure logic).

    Returns ``(db_items_to_draw, path_layers_to_draw)``. In Path_Mode only the
    route layers are kept and no Item_DB items are shown; in Normal_Mode only the
    Item_DB items are kept and no route layers are shown (Requirements 4.5, 4.6).
    """
    if path_mode:
        return [], list(path_layers)
    return list(db_items), []


def player_ocr_to_game_units(player_pos: Sequence[float]) -> Tuple[float, float]:
    """Convert player OCR coordinates to game units by multiplying by 100.

    Mirrors the existing ``player_x = player_pos[0] * 100`` convention
    (Requirement 9.10).
    """
    return (
        player_pos[0] * PLAYER_OCR_TO_GAME_SCALE,
        player_pos[1] * PLAYER_OCR_TO_GAME_SCALE,
    )


def player_target_distance(
    player_pos_ocr: Sequence[float],
    target_x: float,
    target_y: float,
) -> float:
    """Euclidean distance (game units) between player and a target node.

    The player's OCR coordinates are converted to game units via
    :func:`player_ocr_to_game_units` (x100) and the target node's
    ``xposition/yposition`` are used directly as game units (Requirement 9.10).
    """
    gx, gy = player_ocr_to_game_units(player_pos_ocr)
    return distance_game_units(gx, gy, target_x, target_y)


# --------------------------------------------------------------------------
# Status_Panel text builders (pure logic, Qt-free) — task 14.1.
#
# These functions build the left-bottom Status_Panel text with no side effects
# and no Qt dependency, so they are importable / testable on a development
# machine (backing Property 20 and the field-existence unit tests). The actual
# painting lives in the render layer (task 14.4); here we only shape strings.
#
# Feature: map-overlay-interaction
# Requirements: 12.4, 12.5, 12.6, 12.7, 12.10, 12.11
# --------------------------------------------------------------------------

# Displayed when a field's value is unavailable (Requirements 12.10, 12.11).
STATUS_UNKNOWN = "未知"

# Tracking-target info when NOT in Path_Mode (Requirement 12.7).
TARGET_INFO_NO_PATH_MODE = "无"

# Tracking-target info in Path_Mode but without a Target (Requirement 12.6).
TARGET_INFO_NO_TARGET = "无目标"

# Field labels for the status lines. The tracking-target line uses no extra
# label because its content already starts with "目标：" / "无目标" / "无"
# (Requirements 12.5, 12.6, 12.7).
STATUS_LABEL_PLAYER = "玩家坐标"
STATUS_LABEL_MAP = "地图"
STATUS_LABEL_SCALE = "比例"
STATUS_LABEL_MODE = "模式"


def _round_half_up(value) -> int:
    """Round a non-negative distance to the nearest integer, halves rounding up.

    Used for the target distance in :func:`format_target_info` so "四舍五入"
    behaves as documented (e.g. 849.5 -> 850) rather than Python's banker's
    rounding (Requirement 12.5). Distances are non-negative game units.
    """
    return int(math.floor(float(value) + 0.5))


def _format_number(value) -> str:
    """Format a number compactly: drop the decimal part for integral values.

    Integer-valued inputs (``5`` or ``5.0``) render as ``"5"``; other floats are
    rounded to 2 decimals with trailing zeros stripped (``12.30`` -> ``"12.3"``).
    Non-numeric values fall back to ``str(value)``.
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f == int(f):
        return str(int(f))
    text = f"{f:.2f}".rstrip("0").rstrip(".")
    return text


def _player_pos_available(player_pos) -> bool:
    """Whether ``player_pos`` carries usable numeric x/y coordinates.

    ``None`` or non-numeric / too-short values are treated as unavailable so the
    coordinate field falls back to "未知" (Requirement 12.10).
    """
    if player_pos is None:
        return False
    try:
        float(player_pos[0])
        float(player_pos[1])
    except (TypeError, ValueError, IndexError):
        return False
    return True


def format_target_info(mode_is_path, target, section_index, node_index,
                       total, name, distance) -> str:
    """Build the tracking-target info string for the Status_Panel (pure logic).

    Three cases (Requirements 12.5, 12.6, 12.7):

    - not in Path_Mode (``mode_is_path`` falsy) -> :data:`TARGET_INFO_NO_PATH_MODE`
      ("无");
    - in Path_Mode but without a Target (``target`` is ``None``) ->
      :data:`TARGET_INFO_NO_TARGET` ("无目标");
    - in Path_Mode with a Target -> ``目标：段{section_index} 第{node_index}/{total}
      {name} 距离{dist}`` where ``section_index`` / ``node_index`` / ``total`` are
      rendered as integers (all ≥1, ``node_index`` ≤ ``total``) and ``dist`` is the
      distance rounded half-up to whole game units (e.g.
      ``目标：段2 第3/12 风鳞蜃甲 距离850``).
    """
    if not mode_is_path:
        return TARGET_INFO_NO_PATH_MODE
    if target is None:
        return TARGET_INFO_NO_TARGET
    dist = _round_half_up(distance)
    return (
        f"目标：段{int(section_index)} 第{int(node_index)}/{int(total)} "
        f"{name} 距离{dist}"
    )


def format_status_lines(player_pos, map_id, scale_per_1000, mode_desc,
                        target_info) -> List[str]:
    """Assemble the Status_Panel text lines (pure logic, Qt-free).

    Produces one line per field in a fixed order: player coordinates, map id,
    map scale, mode and tracking-target info (Requirement 12.4). Each field whose
    value is unavailable renders as "未知": player coordinates when ``player_pos``
    is ``None`` / non-numeric (Requirement 12.10), and map id / scale when
    ``map_id`` / ``scale_per_1000`` is ``None`` (Requirement 12.11).

    Preserving the "last valid value" for the remaining fields when one becomes
    unavailable is the caller's responsibility: it passes the most recent valid
    ``map_id`` / ``scale_per_1000`` / ``mode_desc`` here, so this function stays a
    pure mapping from the supplied values to display strings.

    ``target_info`` is the already-built string from :func:`format_target_info`
    and is used verbatim as its own line (Requirements 12.5, 12.6, 12.7).
    """
    if _player_pos_available(player_pos):
        coord = f"{_format_number(player_pos[0])}, {_format_number(player_pos[1])}"
    else:
        coord = STATUS_UNKNOWN

    map_str = STATUS_UNKNOWN if map_id is None else str(map_id)
    scale_str = (
        STATUS_UNKNOWN if scale_per_1000 is None else _format_number(scale_per_1000)
    )
    mode_str = STATUS_UNKNOWN if mode_desc is None else str(mode_desc)

    return [
        f"{STATUS_LABEL_PLAYER}：{coord}",
        f"{STATUS_LABEL_MAP}：{map_str}",
        f"{STATUS_LABEL_SCALE}：{scale_str}",
        f"{STATUS_LABEL_MODE}：{mode_str}",
        str(target_info),
    ]


def _load_item_pixmaps(assets_dir):
    if ITEM_PIXMAPS:
        return
    for type_id in ('qzx_01', 'qzx_02', 'qzx_03', 'qzx_04'):
        img_path = os.path.join(assets_dir, f'{type_id}.png')
        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                ITEM_PIXMAPS[type_id] = pixmap.scaled(ICON_SIZE, ICON_SIZE)


# --------------------------------------------------------------------------
# Centralized Qt painting helpers (render layer).
#
# These helpers are shared by both render targets so the route / arrow drawing
# logic lives in one place (design.md "Render 层" + task 10.1):
#   - the minimap continues to use ok's ``OverlayWindow`` via
#     :meth:`MapItemOverlay.make_paint_callback`;
#   - the big map uses ``InteractionOverlayWindow`` (which imports these same
#     helpers) so polyline/arrow/node-icon drawing is not duplicated.
#
# Feature: map-overlay-interaction
# Requirements: 3.4, 3.5, 5.1, 5.2, 5.3, 5.4, 8.1, 8.3
# --------------------------------------------------------------------------

# Route polyline / arrow-head styling.
PATH_LINE_WIDTH = 3
ARROW_HEAD_SIZE = 16
ARROW_HEAD_SPREAD_DEG = 25
# Fallback marker radius when the qzx_04 node pixmap is unavailable.
NODE_DOT_RADIUS = 4

# Minimap target-direction edge arrow styling (Requirements 8.1, 8.3).
EDGE_ARROW_SIZE = 14
EDGE_ARROW_COLOR = QColor(255, 80, 80)


def to_qcolor(color) -> QColor:
    """Best-effort conversion of a color value to ``QColor``.

    Accepts an existing ``QColor`` (passed through), an ``(r, g, b)`` /
    ``(r, g, b, a)`` tuple (the Qt-free ``ColorTuple`` produced by
    ``PathRoute.parse_section_color``), ``None`` (-> :data:`FALLBACK_COLOR`), or
    anything ``QColor`` itself understands. Centralizes the section-color tuple
    -> ``QColor`` conversion (Requirement 5.4).
    """
    if isinstance(color, QColor):
        return color
    if color is None:
        return FALLBACK_COLOR
    if isinstance(color, (tuple, list)):
        return QColor(*color)
    return QColor(color)


def paint_icon_background(painter, sx, sy, icon_size, opacity=1.0):
    """Draw a filled black circle behind an icon centered at ``(sx, sy)``.

    黑底圆的直径等于图标本身大小（半径 ``icon_size // 2``），不再额外放大，
    以贴合图片尺寸；仍能填充空心宝箱（qzx）图标中间露出地图的缺口。黑底透明度
    为图标不透明度的一半（``opacity * 0.5``），因此完成态 0.4 的图标其黑底会更淡
    （0.4 * 0.5 = 0.2），两者一起淡出。

    Painter state (opacity / pen / brush) is saved and restored, so callers can
    invoke this immediately before ``drawPixmap`` without side effects. This is
    the only Qt drawing done for the backdrop; it belongs to the render layer.
    """
    radius = int(icon_size) // 2
    painter.save()
    try:
        painter.setOpacity(opacity * 0.5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0)))
        painter.drawEllipse(QPoint(int(sx), int(sy)), radius, radius)
    finally:
        painter.restore()


def draw_arrow_head(painter, start, end, color,
                    size=ARROW_HEAD_SIZE, spread_deg=ARROW_HEAD_SPREAD_DEG,
                    center=None):
    """Draw a filled arrow head pointing from ``start`` to ``end``.

    方向始终为 ``start`` -> ``end``。默认（``center=None``）箭头 tip 画在 ``end``
    处，两条 barb 向 ``start`` 方向扫回，用于指示线段的行进方向（Requirement 5.3）。

    当传入 ``center``（一段线段的中点）时，箭头改为以 ``center`` 为中心绘制：tip
    落在 ``center`` 前方（沿 start->end 方向）约 ``size/2`` 处，barb 落在 ``center``
    后方，整体位于两节点之间、不与节点图标重叠（Adjustment 3）。零长度线段不画箭头。
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return
    angle = math.atan2(dy, dx)
    spread = math.radians(spread_deg)
    if center is not None:
        # 以中点为中心：tip 在中点前方 size/2，barb 在中点后方。
        tip = (
            center[0] + (size / 2.0) * math.cos(angle),
            center[1] + (size / 2.0) * math.sin(angle),
        )
    else:
        tip = (end[0], end[1])
    left = (
        tip[0] - size * math.cos(angle - spread),
        tip[1] - size * math.sin(angle - spread),
    )
    right = (
        tip[0] - size * math.cos(angle + spread),
        tip[1] - size * math.sin(angle + spread),
    )
    head = QPolygon([
        QPoint(int(tip[0]), int(tip[1])),
        QPoint(int(left[0]), int(left[1])),
        QPoint(int(right[0]), int(right[1])),
    ])
    qcolor = to_qcolor(color)
    painter.setBrush(QBrush(qcolor))
    painter.drawPolygon(head)


def paint_path_layers(painter, path_layers, draw_nodes=True) -> None:
    """Paint route ``PathLayer`` polylines, arrows and ``qzx_04`` node icons.

    For each layer:

    - consecutive projected points are connected with line segments colored by
      the layer's (per-section) color, each carrying an arrow head pointing from
      the earlier node to the later one (Requirements 5.3, 5.4);
    - every node is rendered with the uniform ``qzx_04`` icon (Requirement 5.2);
      a single-node section therefore draws only its node icon and no segment
      (Requirement 5.7). When the pixmap is unavailable a small filled dot keeps
      the node visible.

    ``draw_nodes`` 控制是否绘制节点图标 / 占位圆点：

    - ``draw_nodes=True``（默认）：行为不变，连线 + 箭头 + 每个节点的 qzx_04 图标
      （或占位圆点）全部绘制，供小地图 ok 覆盖层同时画线 + 节点使用；
    - ``draw_nodes=False``：**只画连线与箭头，跳过节点图标 / 占位圆点**。用于把连线
      分流到穿透式 ok 覆盖层绘制、而节点图标交由交互窗口绘制的大地图路线场景，避免
      节点被重复绘制两遍。

    The layer's ``color`` may be a Qt-free ``(r, g, b)`` tuple or a ``QColor``;
    :func:`to_qcolor` handles both. This helper is shared by the minimap paint
    callback and ``InteractionOverlayWindow`` so the drawing logic is not
    duplicated.
    """
    if not path_layers:
        return
    half = ICON_SIZE // 2
    for layer in path_layers:
        qcolor = to_qcolor(getattr(layer, "color", None))
        points = list(getattr(layer, "points", ()) or ())
        painter.setOpacity(1.0)
        painter.setPen(QPen(qcolor, PATH_LINE_WIDTH))
        painter.setBrush(QBrush(qcolor))
        for i in range(len(points) - 1):
            start = points[i]
            end = points[i + 1]
            painter.drawLine(int(start[0]), int(start[1]), int(end[0]), int(end[1]))
            # 箭头画在线段中点（而非末端，末端在节点=图标中心会被图标盖住），
            # 方向仍为 start->end（Adjustment 3）。
            mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
            draw_arrow_head(painter, start, end, qcolor, center=mid)

        # draw_nodes=False 时只画连线/箭头，跳过节点图标（大地图连线走 ok 覆盖层、
        # 节点图标由交互窗口画，避免重复绘制）。
        if not draw_nodes:
            continue
        # 每节点图标：优先用该节点下载得到的 pixmap（layer.node_pixmaps 与 points 同
        # 序），未就绪（None）或整层未提供下载图标时回退统一的 qzx_04 图标
        # （node_icon）。二者都不可用时画占位圆点，保证节点始终可见
        # （Requirements 5.2, 11.7, 11.8, 11.9）。
        icon_key = getattr(layer, "node_icon", PATH_NODE_ICON_KEY)
        fallback_pixmap = ITEM_PIXMAPS.get(icon_key)
        node_pixmaps = getattr(layer, "node_pixmaps", ()) or ()
        for idx, pt in enumerate(points):
            node_pixmap = node_pixmaps[idx] if idx < len(node_pixmaps) else None
            if node_pixmap is None:
                node_pixmap = fallback_pixmap
            if node_pixmap is not None:
                paint_icon_background(painter, int(pt[0]), int(pt[1]), ICON_SIZE, 1.0)
                painter.setOpacity(1.0)
                painter.drawPixmap(int(pt[0]) - half, int(pt[1]) - half, node_pixmap)
            else:
                painter.setBrush(QBrush(qcolor))
                painter.drawEllipse(QPoint(int(pt[0]), int(pt[1])),
                                    NODE_DOT_RADIUS, NODE_DOT_RADIUS)


def paint_edge_direction_arrow(painter, bearing_deg, minimap_box,
                               color=EDGE_ARROW_COLOR, size=EDGE_ARROW_SIZE) -> None:
    """Paint the minimap target-direction indicator (问题0).

    方位指示改为“沿小地图圆边、以目标方位角为中心、跨度 30° 的 3px 红色圆弧”
    （不再是多边形箭头）。函数名与调用点保持不变，仅改实现（Requirements 8.1, 8.3）。

    - 圆心 ``cx, cy`` 取 ``minimap_box`` 中心，半径 ``r = min(w, h)//2 + 10``（略大于
      小地图圆边），使 30° 红弧落在小地图圆边外侧、不遮挡小地图内容（问题1）。
    - 使用 ``painter.drawArc``：Qt 角度单位为 1/16 度，0° 在 3 点钟方向、逆时针为正；
      而我们的 ``bearing`` 约定 0=上(北)、90=右(东)、顺时针。换算
      ``qt_center_deg = 90 - bearing_deg``，弧以该角为中心、跨度 30°，
      ``start_deg = qt_center_deg - 15``。
    - 画笔为 ``QPen(QColor(255, 0, 0), 3)``、``Qt.NoBrush``、``setOpacity(1.0)``。

    调用方仅在存在 Target 时才调用本函数，因此省略调用即移除方位指示。
    ``color`` / ``size`` 参数保留以维持签名兼容（当前实现固定用红色 3px 弧）。
    """
    bw = int(getattr(minimap_box, "width"))
    bh = int(getattr(minimap_box, "height"))
    cx = getattr(minimap_box, "x") + bw / 2.0
    cy = getattr(minimap_box, "y") + bh / 2.0
    # 半径贴着小地图圆边内侧（-3px）：make_paint_callback 会把绘制裁剪到半径
    # min(w,h)//2 的圆内，+10 会落在裁剪区外而完全不显示，故改为落在边缘内侧、
    # 位于裁剪区之内，使 30° 红弧显示在小地图边缘（问题1）。
    r = min(bw, bh) // 2 - 3
    if r <= 0:
        return
    # bearing(0=上,顺时针) -> Qt 角度(0=3点钟,逆时针)。
    qt_center_deg = 90.0 - (bearing_deg % 360.0)
    start_deg = qt_center_deg - 15.0
    start16 = int(start_deg * 16)
    span16 = int(30 * 16)
    rect = QRect(int(cx - r), int(cy - r), int(2 * r), int(2 * r))
    painter.setOpacity(1.0)
    painter.setPen(QPen(QColor(255, 0, 0), 3))
    painter.setBrush(Qt.NoBrush)
    painter.drawArc(rect, start16, span16)


# Status_Panel styling (Requirements 12.1, 12.2).
STATUS_PANEL_FONT_FAMILY = "Arial"
STATUS_PANEL_FONT_SIZE = 10
# Inner padding (px) between the panel border and the text on every side.
STATUS_PANEL_PADDING = 6
# Extra vertical spacing (px) added between consecutive text lines.
STATUS_PANEL_LINE_SPACING = 2
# 50%-opacity black background (alpha 128 of 255) and white text (Requirement 12.2).
STATUS_PANEL_BG_COLOR = QColor(0, 0, 0, 128)
STATUS_PANEL_TEXT_COLOR = QColor(255, 255, 255)


def _client_size(view_or_geometry) -> Tuple[int, int]:
    """Return the client area ``(width, height)`` from a view or geometry object.

    Accepts either a Qt widget / view (as passed to the ok ``OverlayWindow`` paint
    callback ``callback(QPainter, OverlayWindow)`` and to ``InteractionOverlayWindow``),
    which exposes callable ``width()`` / ``height()`` methods, or a plain geometry
    object exposing ``width`` / ``height`` attributes (e.g. the Qt-free ``Rect`` /
    minimap box). Returns ``(0, 0)`` when the size cannot be determined so callers
    can skip painting gracefully.
    """
    if view_or_geometry is None:
        return 0, 0
    width_attr = getattr(view_or_geometry, "width", None)
    height_attr = getattr(view_or_geometry, "height", None)
    try:
        w = width_attr() if callable(width_attr) else width_attr
        h = height_attr() if callable(height_attr) else height_attr
        return int(w), int(h)
    except (TypeError, ValueError):
        return 0, 0


def status_panel_rect(lines, view_or_geometry):
    """Compute the left-bottom Status_Panel rectangle ``(left, top, w, h)`` or None.

    Shared by :func:`paint_status_panel` (drawing) and the render targets'
    masking code (``InteractionOverlayWindow._compose_mask_region``) so the drawn
    panel box and the masked region stay identical. Returns ``None`` when there
    is nothing to draw (no lines / unknown client size), so callers can skip both
    the paint and the mask union.

    The panel is measured from the text via ``QFontMetrics`` (widest line width +
    padding for the width; per-line height * line count + padding for the height),
    clamped so it never exceeds the client area (Requirement 12.1), then anchored
    to the client area's left and bottom edges.
    """
    text_lines = [str(line) for line in (lines or [])]
    if not text_lines:
        return None

    client_w, client_h = _client_size(view_or_geometry)
    if client_w <= 0 or client_h <= 0:
        return None

    font = QFont(STATUS_PANEL_FONT_FAMILY, STATUS_PANEL_FONT_SIZE)
    metrics = QFontMetrics(font)
    pad = STATUS_PANEL_PADDING
    line_h = metrics.height() + STATUS_PANEL_LINE_SPACING

    text_w = max((metrics.horizontalAdvance(line) for line in text_lines), default=0)
    panel_w = text_w + pad * 2
    panel_h = line_h * len(text_lines) + pad * 2

    # Clamp so the panel never exceeds the client area (Requirement 12.1).
    panel_w = min(panel_w, client_w)
    panel_h = min(panel_h, client_h)

    # Anchor to the left edge and the bottom edge of the client area.
    left = 0
    top = client_h - panel_h
    return int(left), int(top), int(panel_w), int(panel_h)


def paint_status_panel(painter, lines, view_or_geometry) -> None:
    """Paint the left-bottom Status_Panel shared by both overlay targets.

    Draws the ``lines`` (already-built status strings from
    :func:`format_status_lines`) in a fixed panel anchored to the client area's
    left and bottom edges, without ever spilling outside the client area
    (Requirement 12.1). The panel background is 50%-opacity black and the text is
    white (Requirement 12.2).

    ``view_or_geometry`` supplies the client area size: it is the ok
    ``OverlayWindow`` (minimap) or the ``InteractionOverlayWindow`` (big map)
    passed straight through, or any object exposing ``width`` / ``height``
    (see :func:`_client_size`). Because both render targets call this same helper,
    the panel drawing logic lives in one place and is not duplicated.

    Panel geometry is resolved by :func:`status_panel_rect` (measured from the
    text and clamped to the client area). Painter state (opacity, pen, brush,
    font) is saved and restored, so callers may invoke this at any point in their
    paint pass without side effects.
    """
    text_lines = [str(line) for line in (lines or [])]
    rect = status_panel_rect(text_lines, view_or_geometry)
    if rect is None:
        return
    left, top, panel_w, panel_h = rect

    font = QFont(STATUS_PANEL_FONT_FAMILY, STATUS_PANEL_FONT_SIZE)
    metrics = QFontMetrics(font)
    pad = STATUS_PANEL_PADDING
    line_h = metrics.height() + STATUS_PANEL_LINE_SPACING

    painter.save()
    try:
        painter.setOpacity(1.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(STATUS_PANEL_BG_COLOR))
        painter.drawRect(QRect(int(left), int(top), int(panel_w), int(panel_h)))

        painter.setFont(font)
        painter.setPen(QPen(STATUS_PANEL_TEXT_COLOR))
        # First baseline sits one ascent below the top padding; each subsequent
        # line advances by ``line_h``.
        base_y = top + pad + metrics.ascent()
        for i, line in enumerate(text_lines):
            painter.drawText(int(left + pad), int(base_y + i * line_h), line)
    finally:
        painter.restore()


class MapItemOverlay:

    def __init__(self, db_path):
        # 保存数据库路径，供 get_location_description 在 GUI 线程按需新建短生命周期
        # 连接使用（sqlite 连接默认禁止跨线程复用，见 get_location_description 注释）。
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        assets_dir = os.path.dirname(db_path)
        _load_item_pixmaps(assets_dir)

    def query_nearby(self, px, py, radius, type_filter=None, state_id=None,
                     with_location_id=False):
        """Query items within ``radius`` of ``(px, py)``.

        By default returns ``(name, type_id, x, y, dist)`` 5-tuples (unchanged,
        backward-compatible). When ``with_location_id=True`` each result becomes a
        6-tuple ``(location_id, name, type_id, x, y, dist)`` so callers can build
        click-aware / completion-aware draw items (Requirements 2, 3).
        """
        r2 = radius * radius
        id_col = 'l.id, ' if with_location_id else ''
        if type_filter:
            placeholders = ','.join('?' for _ in type_filter)
            if state_id is not None:
                sql = f"""
                    SELECT {id_col}i.name, l.type_id, l.x, l.y
                    FROM location l
                    JOIN item i ON i.id = l.item_id
                    WHERE l.type_id IN ({placeholders})
                      AND l.state_id = ?
                      AND (l.x - ?)*(l.x - ?) + (l.y - ?)*(l.y - ?) < ?
                """
                params = list(type_filter) + [int(state_id), px, px, py, py, r2]
            else:
                sql = f"""
                    SELECT {id_col}i.name, l.type_id, l.x, l.y
                    FROM location l
                    JOIN item i ON i.id = l.item_id
                    WHERE l.type_id IN ({placeholders})
                      AND (l.x - ?)*(l.x - ?) + (l.y - ?)*(l.y - ?) < ?
                """
                params = list(type_filter) + [px, px, py, py, r2]
        else:
            if state_id is not None:
                sql = f"""
                    SELECT {id_col}i.name, l.type_id, l.x, l.y
                    FROM location l
                    JOIN item i ON i.id = l.item_id
                    WHERE l.state_id = ?
                      AND (l.x - ?)*(l.x - ?) + (l.y - ?)*(l.y - ?) < ?
                """
                params = [int(state_id), px, px, py, py, r2]
            else:
                sql = f"""
                    SELECT {id_col}i.name, l.type_id, l.x, l.y
                    FROM location l
                    JOIN item i ON i.id = l.item_id
                    WHERE (l.x - ?)*(l.x - ?) + (l.y - ?)*(l.y - ?) < ?
                """
                params = [px, px, py, py, r2]

        rows = self._conn.execute(sql, params).fetchall()
        results = []
        if with_location_id:
            for location_id, name, type_id, x, y in rows:
                dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
                results.append((location_id, name, type_id, x, y, dist))
            results.sort(key=lambda r: r[5])
        else:
            for name, type_id, x, y in rows:
                dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
                results.append((name, type_id, x, y, dist))
            results.sort(key=lambda r: r[4])
        return results

    def get_location_description(self, location_id):
        """Return the ``location.description`` for a location id, or ``None``.

        Used by the big-map left-click handler to populate a Description_Bubble
        (Requirement 2.1). Returns ``None`` on any lookup failure or when the row
        / column is missing; the caller passes the result through
        :func:`bubble_text`, which renders the "该地点暂无描述" placeholder for an
        empty/missing description (Requirement 2.7).

        线程安全说明（关键 bug 修复）：本方法通常在 GUI 线程被点击信号槽调用，而
        ``self._conn`` 是在任务线程创建的连接，sqlite 默认禁止跨线程复用连接，复用会
        抛 ``sqlite3.ProgrammingError``（``sqlite3.Error`` 子类）被下方 except 吞掉，
        导致所有描述都回退为占位符。因此这里**每次调用都新建一个短生命周期连接**，
        查询后立即关闭；点击不频繁，新建连接开销可接受。description 在库中为合法
        UTF-8 中文，无需额外解码，直接返回原文（空串 / None 交由 bubble_text 处理）。
        """
        try:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    "SELECT description FROM location WHERE id = ? LIMIT 1",
                    (location_id,),
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            return None
        if not row:
            return None
        return row[0]

    def project_to_minimap(self, item_x, item_y, player_x, player_y, scale, center_x, center_y):
        dx = item_x - player_x
        dy = item_y - player_y

        px = center_x + dx * scale
        py = center_y + dy * scale

        return int(px), int(py)

    def build_draw_items(self, player_x, player_y, minimap_box, radius, scale_per_1000,
                         type_filter=None, state_id=None, completed_ids=None):
        """Build minimap draw items as extended 8-tuples.

        Returns ``(sx, sy, pixmap, name, color, opacity, location_id, z)`` tuples.
        Completed items (id in ``completed_ids``) are excluded from the minimap
        (Requirement 3.4); the completion-aware shaping is delegated to the
        Qt-free :func:`build_overlay_draw_items`. When ``completed_ids`` is
        ``None`` no items are excluded and all render fully opaque, preserving the
        previous behavior (aside from the wider tuple shape).
        """
        scale = scale_per_1000 / 1000.0
        items = self.query_nearby(player_x, player_y, radius, type_filter,
                                  state_id=state_id, with_location_id=True)

        minimap_center_x = minimap_box.x + minimap_box.width/2
        minimap_center_y = minimap_box.y + minimap_box.height/2

        minimap_radius = min(minimap_box.width, minimap_box.height) // 2

        candidates = []
        for location_id, name, type_id, ix, iy, dist in items:
            sx, sy = self.project_to_minimap(
                ix, iy, player_x, player_y, scale,
                minimap_center_x, minimap_center_y
            )

            dx_center = sx - minimap_center_x
            dy_center = sy - minimap_center_y
            if math.sqrt(dx_center ** 2 + dy_center ** 2) > minimap_radius:
                continue

            pixmap = ITEM_PIXMAPS.get(type_id)
            color = ITEM_COLORS.get(type_id, FALLBACK_COLOR)
            candidates.append(
                DrawCandidate(sx, sy, pixmap, name, color, location_id, 0)
            )

        return build_overlay_draw_items(
            candidates, minimap=True, completed_ids=completed_ids
        )

    @staticmethod
    def make_paint_callback(draw_items, path_layers=(), edge_arrow=None,
                            clip_box=None, target_marker=None,
                            draw_path_nodes=True, status_lines=None):
        """Build the ok ``OverlayWindow`` paint callback for the minimap.

        Draws (in back-to-front order):

        - route ``path_layers`` polylines with arrow heads, per-section color and
          ``qzx_04`` node icons (Requirements 5.1, 5.2, 5.3, 5.4) via
          :func:`paint_path_layers`;
        - the ``draw_items`` icons, honoring the completed-state opacity carried
          in the extended 8-tuple (Requirements 3.4, 3.5). Every pixmap-backed
          icon first gets a black circular backdrop via
          :func:`paint_icon_background` (matching the item opacity); placeholder
          dots (no pixmap) are unchanged;
        - an optional minimap target-direction edge arrow when ``edge_arrow`` is
          provided as ``(bearing_deg, minimap_box)`` (Requirements 8.1, 8.3).

        ``path_layers`` and ``edge_arrow`` are optional so existing callers that
        pass only ``draw_items`` keep their previous behavior.

        ``clip_box`` (optional) is a box with ``x`` / ``y`` / ``width`` /
        ``height`` (e.g. the minimap box). When provided, all painting is clipped
        to a circular region inscribed in that box (radius ``min(w, h) // 2``,
        centered on the box) so minimap routes never spill outside the round
        minimap. When ``None`` (the default) behavior is unchanged and no
        clipping is applied (backward compatible).

        ``target_marker`` (optional) is a ``(sx, sy)`` minimap pixel point for the
        current route Target node, or ``None`` when there is no target. When
        provided, a 3px red hollow circle (radius ``ICON_SIZE // 2 + 4``) is drawn
        around that point after the icons and edge arrow, highlighting the target
        node on the minimap (问题1b). The circle is drawn inside the same clip, so
        a target outside the round minimap is naturally hidden. Default ``None``
        keeps the previous behavior.

        ``draw_path_nodes``（默认 True）透传给 :func:`paint_path_layers` 的
        ``draw_nodes``：True 时路线层同时画连线 + 箭头 + 节点图标（小地图既有行为不变）；
        False 时**只画连线与箭头、跳过节点图标**，用于大地图把连线分流到穿透式 ok
        覆盖层、节点图标由交互窗口绘制的场景。

        ``status_lines``（可选）为左下角 Status_Panel 的文本行（``format_status_lines``
        的输出）。非空时在**裁剪区之外**（即整个客户区左下角，不受 ``clip_box`` 小地图
        圆形裁剪影响）经 :func:`paint_status_panel` 绘制，使小地图场景也能在 ok
        ``OverlayWindow`` 上显示状态面板（Requirements 12.3, 12.9）；``None`` / 空时不
        绘制，保持既有行为。
        """
        def paint(painter, view):
            clipped = clip_box is not None
            if clipped:
                painter.save()
                bw = int(getattr(clip_box, "width"))
                bh = int(getattr(clip_box, "height"))
                cx = int(getattr(clip_box, "x") + bw / 2)
                cy = int(getattr(clip_box, "y") + bh / 2)
                r = min(bw, bh) // 2
                painter.setClipRegion(
                    QRegion(cx - r, cy - r, r * 2, r * 2, QRegion.Ellipse)
                )
            try:
                if path_layers:
                    paint_path_layers(painter, path_layers, draw_nodes=draw_path_nodes)
                font = QFont("Arial", 8)
                half = ICON_SIZE // 2
                for item in draw_items:
                    # Tolerate both the legacy 5-tuple (sx, sy, pixmap, name, color)
                    # and the extended 8-tuple
                    # (sx, sy, pixmap, name, color, opacity, location_id, z).
                    sx, sy, pixmap, name, color = item[0], item[1], item[2], item[3], item[4]
                    opacity = item[5] if len(item) > 5 else 1.0
                    painter.setOpacity(opacity)
                    if pixmap is not None:
                        paint_icon_background(painter, sx, sy, ICON_SIZE, opacity)
                        painter.setOpacity(opacity)
                        painter.drawPixmap(sx - half, sy - half, pixmap)
                    else:
                        painter.setPen(QPen(color, 2))
                        painter.setBrush(color)
                        painter.drawEllipse(sx - 3, sy - 3, 6, 6)
                        painter.setFont(font)
                        painter.drawText(sx + 5, sy - 5, name[:4])
                painter.setOpacity(1.0)
                if edge_arrow is not None:
                    bearing_deg, minimap_box = edge_arrow
                    paint_edge_direction_arrow(painter, bearing_deg, minimap_box)
                # 目标红圈（问题1b）：在图标与方位箭头之后画 3px 红色空心圆，圈住
                # 当前路线目标节点；无目标（target_marker is None）时不绘制。
                if target_marker is not None:
                    sx, sy = int(target_marker[0]), int(target_marker[1])
                    r = ICON_SIZE // 2 + 4
                    painter.setOpacity(1.0)
                    painter.setPen(QPen(QColor(255, 0, 0), 3))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPoint(sx, sy), r, r)
            finally:
                if clipped:
                    painter.restore()
            # Status_Panel is drawn after restoring the clip so it lands at the
            # client-area's bottom-left corner rather than inside the round
            # minimap clip (Requirements 12.1, 12.3, 12.9).
            if status_lines:
                paint_status_panel(painter, status_lines, view)

        return paint

    def close(self):
        self._conn.close()
