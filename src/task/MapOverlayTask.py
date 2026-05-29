import math
import time
from collections import deque

from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger, og, get_path_relative_to_exe
from src.task.BaseWWTask import BaseWWTask
from src.utils.MapItemOverlay import MapItemOverlay

logger = Logger.get_logger(__name__)

TELEPORT_THRESHOLD = 500
TELEPORT_SETTLE_DISTANCE = 10
OUTLIER_RELATIVE_FACTOR = 2.0
OUTLIER_FIXED_THRESHOLD = 200

OVERLAY_DRAW_KEY = "map_items"


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


class MapOverlayTask(TriggerTask, BaseWWTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Map Overlay"
        self.description = "Continuously detect and report player position"
        self.icon = FluentIcon.GLOBE
        self.default_config.update({
            '_enabled': False,
            'Detect interval (ms)': 100,
            'Overlay enabled': False,
            'Search radius (world units)': 5000,
            'Auto map scale': True,
            'Map scale (pixels per 1000 units)': 11.45,
            'Item type filter': ['qzx_01', 'qzx_02', 'qzx_03', 'qzx_04', 'cx_0'],
        })
        self.config_type['Item type filter'] = {'type': 'multi_selection', 'options': [
            'qzx_01', 'qzx_02', 'qzx_03', 'qzx_04', 'cx_0',
        ]}
        self._window = None
        self._last_valid = None
        self._consecutive_far = 0
        self._overlay = None
        self._overlay_registered = False

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
            return pos

        if self._consecutive_far > 0:
            return self._last_valid

        filtered = self._filter_outliers()
        self._last_valid = filtered[-1]
        return self._last_valid

    def run(self):
        if not self.scene.in_team(self.in_team_and_world):
            return

        start = time.time()
        raw_position = og.my_app.position_detector.detect_position(self.frame)
        elapsed = (time.time() - start) * 1000

        if raw_position:
            result = self._denoise(raw_position)
            if result:
                if result[0]%5==0:
                    pos_text = f'{result[0]},{result[1]},{result[2]}'
                    self.info_set('OCR check', f'position: {pos_text} took {elapsed:.0f}ms')

                if self.config.get('Overlay enabled'):
                    self._draw_overlay(result)
                else:
                    self._clear_overlay()

        interval = self.config.get('Detect interval (ms)', 500)
        self.sleep(interval / 1000)

    def _init_overlay(self):
        if self._overlay is not None:
            return
        db_path = get_path_relative_to_exe('pick', 'map_items.db')
        self._overlay = MapItemOverlay(db_path)

    def _draw_overlay(self, player_pos):
        overlay_view = self.get_overlay_view()
        if overlay_view is None:
            return

        self._init_overlay()

        minimap_box = self.get_box_by_name('box_minimap')
        if minimap_box is None:
            return

        radius = self.config.get('Search radius (world units)')
        scale_per_1000 = self.config.get('Map scale (pixels per 1000 units)')
        if self.config.get('Auto map scale'):
            scale_factor = 1 - (1.25 - self.screen_width / 1600)
            scale_per_1000 = scale_factor * 1.205 * 10
        type_filter = self.config.get('Item type filter')
        player_x = player_pos[0] * 100
        player_y = player_pos[1] * 100

        draw_items = self._overlay.build_draw_items(
            player_x, player_y, minimap_box, radius, scale_per_1000, type_filter
        )

        callback = MapItemOverlay.make_paint_callback(draw_items)
        overlay_view.draw(OVERLAY_DRAW_KEY, callback, duration=1)
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
        if self._overlay is not None:
            self._overlay.close()
