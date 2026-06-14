import math
import os
import sqlite3

from PySide6.QtGui import QColor, QFont, QPen, QPixmap

ITEM_COLORS = {
    'qzx_01': QColor(255, 165, 0),
    'qzx_02': QColor(255, 255, 0),
    'qzx_03': QColor(255, 0, 255),
    'qzx_04': QColor(0, 165, 255),
    'cx_0': QColor(0, 255, 0),
}
FALLBACK_COLOR = QColor(255, 255, 255)

ICON_SIZE = 30

ITEM_PIXMAPS = {}


def _load_item_pixmaps(assets_dir):
    if ITEM_PIXMAPS:
        return
    for type_id in ('qzx_01', 'qzx_02', 'qzx_03', 'qzx_04'):
        img_path = os.path.join(assets_dir, f'{type_id}.png')
        if os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                ITEM_PIXMAPS[type_id] = pixmap.scaled(ICON_SIZE, ICON_SIZE)


class MapItemOverlay:

    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        assets_dir = os.path.dirname(db_path)
        _load_item_pixmaps(assets_dir)

    def query_nearby(self, px, py, radius, type_filter=None, state_id=None):
        r2 = radius * radius
        if type_filter:
            placeholders = ','.join('?' for _ in type_filter)
            if state_id is not None:
                sql = f"""
                    SELECT i.name, l.type_id, l.x, l.y
                    FROM location l
                    JOIN item i ON i.id = l.item_id
                    WHERE l.type_id IN ({placeholders})
                      AND l.state_id = ?
                      AND (l.x - ?)*(l.x - ?) + (l.y - ?)*(l.y - ?) < ?
                """
                params = list(type_filter) + [int(state_id), px, px, py, py, r2]
            else:
                sql = f"""
                    SELECT i.name, l.type_id, l.x, l.y
                    FROM location l
                    JOIN item i ON i.id = l.item_id
                    WHERE l.type_id IN ({placeholders})
                      AND (l.x - ?)*(l.x - ?) + (l.y - ?)*(l.y - ?) < ?
                """
                params = list(type_filter) + [px, px, py, py, r2]
        else:
            if state_id is not None:
                sql = """
                    SELECT i.name, l.type_id, l.x, l.y
                    FROM location l
                    JOIN item i ON i.id = l.item_id
                    WHERE l.state_id = ?
                      AND (l.x - ?)*(l.x - ?) + (l.y - ?)*(l.y - ?) < ?
                """
                params = [int(state_id), px, px, py, py, r2]
            else:
                sql = """
                    SELECT i.name, l.type_id, l.x, l.y
                    FROM location l
                    JOIN item i ON i.id = l.item_id
                    WHERE (l.x - ?)*(l.x - ?) + (l.y - ?)*(l.y - ?) < ?
                """
                params = [px, px, py, py, r2]

        rows = self._conn.execute(sql, params).fetchall()
        results = []
        for name, type_id, x, y in rows:
            dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
            results.append((name, type_id, x, y, dist))
        results.sort(key=lambda r: r[4])
        return results

    def project_to_minimap(self, item_x, item_y, player_x, player_y, scale, center_x, center_y):
        dx = item_x - player_x
        dy = item_y - player_y

        px = center_x + dx * scale
        py = center_y + dy * scale

        return int(px), int(py)

    def build_draw_items(self, player_x, player_y, minimap_box, radius, scale_per_1000, type_filter=None, state_id=None):
        scale = scale_per_1000 / 1000.0
        items = self.query_nearby(player_x, player_y, radius, type_filter, state_id=state_id)

        minimap_center_x = minimap_box.x + minimap_box.width/2
        minimap_center_y = minimap_box.y + minimap_box.height/2

        minimap_radius = min(minimap_box.width, minimap_box.height) // 2

        draw_items = []
        for name, type_id, ix, iy, dist in items:
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
            draw_items.append((sx, sy, pixmap, name, color))

        return draw_items

    @staticmethod
    def make_paint_callback(draw_items):
        def paint(painter, view):
            font = QFont("Arial", 8)
            half = ICON_SIZE // 2
            for sx, sy, pixmap, name, color in draw_items:
                if pixmap is not None:
                    painter.drawPixmap(sx - half, sy - half, pixmap)
                else:
                    painter.setPen(QPen(color, 2))
                    painter.setBrush(color)
                    painter.drawEllipse(sx - 3, sy - 3, 6, 6)
                    painter.setFont(font)
                    painter.drawText(sx + 5, sy - 5, name[:4])

        return paint

    def close(self):
        self._conn.close()
