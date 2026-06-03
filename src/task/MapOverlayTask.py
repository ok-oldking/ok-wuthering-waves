import json
import math
import os
import time
from collections import deque

import cv2
import numpy as np

from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger, og, get_path_relative_to_exe, Box
from src.task.BaseWWTask import BaseWWTask
from src.utils.MapItemOverlay import MapItemOverlay, ITEM_COLORS

logger = Logger.get_logger(__name__)

TELEPORT_THRESHOLD = 500
TELEPORT_SETTLE_DISTANCE = 10
OUTLIER_RELATIVE_FACTOR = 2.0
OUTLIER_FIXED_THRESHOLD = 200

OVERLAY_DRAW_KEY = "map_items"

MAP_DIR = get_path_relative_to_exe('assets', 'stitched')

MAP_REGION_SIZE = 1000
FRAME_CROP_SIZE = 400
FALLBACK_MAX_FAILURES = 3
BIG_MAP_SEARCH_MULTIPLIER = 5
SMOOTH_WINDOW_SIZE = 3
SMOOTH_WEIGHTS = [1, 2, 3]
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
    coords_dict = {}
    for name in os.listdir(stitched_dir):
        if not name.endswith('_coords.json'):
            continue
        map_id = name.replace('_coords.json', '')
        path = os.path.join(stitched_dir, name)
        try:
            with open(path, 'r') as f:
                d = json.load(f)
            coords_dict[map_id] = d
        except Exception:
            logger.warning(f"Failed to load coords: {path}")
    return coords_dict


CONFIDENCE_THRESHOLD = 0.9

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
            'Map overlay fallback': False,
            'Feature algorithm': 'SURF',
        })
        self.config_type['Item type filter'] = {'type': 'multi_selection', 'options': [
            'qzx_01', 'qzx_02', 'qzx_03', 'qzx_04', 'cx_0',
        ]}
        self.config_type['Feature algorithm'] = {'type': 'drop_down', 'options': [
            'SURF', 'SIFT',
        ]}
        self._window = None
        self._last_valid = None
        self._consecutive_far = 0
        self._overlay = None
        self._overlay_registered = False
        self._fallback_failures = 0
        self._locked_map_id = None
        self._engines = {}
        self._coords_dict = None
        self._smooth_buffer = deque(maxlen=SMOOTH_WINDOW_SIZE)

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

    def _ensure_coords(self):
        if self._coords_dict is not None:
            return
        self._coords_dict = _load_coords_dict(MAP_DIR)
        logger.info(f"[MapFallback] loaded {len(self._coords_dict)} coords from {MAP_DIR}: {list(self._coords_dict.keys())}")

    def _get_engine(self, map_id):
        if map_id in self._engines:
            return self._engines[map_id]

        algo = self.config.get('Feature algorithm', 'SURF').upper()
        assets_dir = get_path_relative_to_exe('src', 'match_engine', 'assets')
        map_path = os.path.join(MAP_DIR, f"{map_id}.png")

        if algo == 'SIFT':
            from src.match_engine import SiftEngine
            engine = SiftEngine(
                map_id=map_id,
                map_path=map_path,
                assets_dir=assets_dir,
            )
        else:
            from src.match_engine import SurfEngine
            engine = SurfEngine(
                map_id=map_id,
                map_path=map_path,
                assets_dir=assets_dir,
            )

        self._engines[map_id] = engine
        return engine

    def _try_map_match(self, player_pos):
        self._ensure_coords()
        if not self._coords_dict:
            logger.warning("[MapFallback] no coords dict loaded")
            return None

        game_x = player_pos[0] * 100
        game_y = player_pos[1] * 100

        if self._locked_map_id is not None:
            candidates = [(self._locked_map_id, self._coords_dict[self._locked_map_id])]
            logger.info(f"[MapFallback] using locked map={self._locked_map_id} OCR=({player_pos[0]},{player_pos[1]})")
        else:
            candidates = _filter_candidate_maps(player_pos, self._coords_dict)
            if not candidates:
                logger.warning(f"[MapFallback] no candidate maps for game=({game_x},{game_y})")
                return None
            logger.info(
                f"[MapFallback] OCR=({player_pos[0]},{player_pos[1]}) game=({game_x},{game_y}) "
                f"candidates={[c[0] for c in candidates]}"
            )
            candidates.sort(key=lambda c: c[0] in SLOW_MAP_IDS)

        h, w = self.frame.shape[:2]
        cx, cy = w // 2, h // 2
        half = FRAME_CROP_SIZE // 2
        cropped = self.frame[cy - half:cy + half, cx - half:cx + half]

        algo = self.config.get('Feature algorithm', 'SURF')

        for map_id, coords_d in candidates:
            coords_min = coords_d.get('min', [0, 0])
            coords_max = coords_d.get('max', [0, 0])

            try:
                engine = self._get_engine(map_id)
            except Exception as e:
                logger.warning(f"[MapFallback] failed to init engine for map {map_id}: {e}")
                continue

            scale = coords_d['scale'][0]
            offset_x = coords_d['offset'][0]
            offset_y = coords_d['offset'][1]
            pixel_x = (game_x - offset_x) / scale
            pixel_y = (game_y - offset_y) / scale

            half_r = MAP_REGION_SIZE // 2
            region = (int(pixel_x - half_r), int(pixel_y - half_r), MAP_REGION_SIZE, MAP_REGION_SIZE)

            logger.info(
                f"[MapFallback] trying map={map_id} "
                f"bounds=({coords_min[0]:.0f},{coords_min[1]:.0f})~({coords_max[0]:.0f},{coords_max[1]:.0f}) "
                f"features={engine.feature_count} "
                f"game_to_pixel=({pixel_x:.0f},{pixel_y:.0f}) "
                f"region=({region[0]},{region[1]},{region[2]}x{region[3]})"
            )

            try:
                result = engine.match_array(cropped, region=region, crop_size=0)
            except Exception as e:
                logger.warning(f"[MapFallback] match_array error for map {map_id}: {e}")
                continue

            logger.info(
                f"[MapFallback] map={map_id} algo={algo} "
                f"success={result.success} matches={result.match_count} "
                f"inliers={result.inlier_count} conf={result.confidence:.3f} "
                f"elapsed={result.elapsed_ms:.0f}ms"
            )

            if result.success and result.center:
                logger.info(
                    f"[MapFallback] center_pixel=({result.center[0]:.0f},{result.center[1]:.0f})"
                )
            if result.success and result.game_center:
                logger.info(
                    f"[MapFallback] game_center=({result.game_center[0]:.0f},{result.game_center[1]:.0f})"
                )

            if result.success and result.confidence >= CONFIDENCE_THRESHOLD and result.match_count >= 10:
                if self._locked_map_id is None:
                    self._locked_map_id = map_id
                    logger.info(f"[MapFallback] locked map_id={map_id} (conf={result.confidence:.3f} >= {CONFIDENCE_THRESHOLD})")
                gc = result.game_center
                gc_str = f"({gc[0]:.0f},{gc[1]:.0f})" if gc else "None"
                logger.info(
                    f"[MapFallback] map={map_id} map_scale={result.map_scale:.4f} "
                    f"game_center={gc_str}"
                )
                return result

            logger.info(
                f"[MapFallback] map={map_id} rejected: "
                f"conf={result.confidence:.3f}(need>={CONFIDENCE_THRESHOLD}) "
                f"matches={result.match_count}(need>=10), trying next"
            )

        logger.warning("[MapFallback] all candidates tried, none with sufficient confidence")
        return None

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
            self._smooth_buffer.clear()
            if self._locked_map_id is not None:
                logger.info(f"[MapFallback] OCR restored, unlocking map_id={self._locked_map_id}")
                self._locked_map_id = None

            start = time.time()
            raw_position = og.my_app.position_detector.detect_position(self.frame)
            elapsed = (time.time() - start) * 1000

            if raw_position:
                result = self._denoise(raw_position)
                if result:
                    if result[0] % 5 == 0:
                        pos_text = f'{result[0]},{result[1]},{result[2]}'
                        self.info_set('OCR check', f'position: {pos_text} took {elapsed:.0f}ms')

                    if self.config.get('Overlay enabled'):
                        self._draw_overlay(result)
                else:
                    logger.info("[ocr check] ocr noresult")
            else:
                logger.info("[ocr check] no raw_position get")

            interval = self.config.get('Detect interval (ms)', 500)
            self.sleep(interval / 1000)
            return

        if self._in_big_map():
            if self.config.get('Map overlay fallback') and self._last_valid is not None:
                if self._fallback_failures < FALLBACK_MAX_FAILURES:
                    logger.info(
                        f"[MapFallback] in big map, attempting fallback match "
                        f"(attempt {self._fallback_failures + 1}/{FALLBACK_MAX_FAILURES})"
                    )
                    result = self._try_map_match(self._last_valid)
                    if result is None or not result.success:
                        self._fallback_failures += 1
                        logger.warning(
                            f"[MapFallback] match failed {self._fallback_failures}/{FALLBACK_MAX_FAILURES}"
                        )
                    else:
                        logger.info("[MapFallback] match succeeded, resetting failure count")
                        self._fallback_failures = 0
                        if result.game_center:
                            self._smooth_buffer.append(result.game_center)
                            smoothed = self._smooth_game_center()
                            new_x = int(smoothed[0] / 100)
                            new_y = int(smoothed[1] / 100)
                            new_z = self._last_valid[2] if len(self._last_valid) > 2 else 0
                            old = self._last_valid
                            self._last_valid = (new_x, new_y, new_z)
                            logger.info(
                                f"[MapFallback] smoothed position from ({old[0]},{old[1]}) "
                                f"to ({new_x},{new_y}) buffer_size={len(self._smooth_buffer)}"
                            )
                        game_scale = self._compute_game_scale(result)
                        self._draw_overlay_screen_center(self._last_valid, game_scale)
                else:
                    logger.warning("[MapFallback] max failures reached, waiting for OCR success")
            else:
                self._clear_overlay()

            interval = self.config.get('Detect interval (ms)', 500)
            self.sleep(interval * 2 / 1000)
            return

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

    def _smooth_game_center(self):
        if not self._smooth_buffer:
            return (0.0, 0.0)
        if len(self._smooth_buffer) == 1:
            return self._smooth_buffer[0]
        n = len(self._smooth_buffer)
        weights = SMOOTH_WEIGHTS[:n]
        w_sum = sum(weights)
        sx = sum(self._smooth_buffer[i][0] * weights[i] for i in range(n)) / w_sum
        sy = sum(self._smooth_buffer[i][1] * weights[i] for i in range(n)) / w_sum
        return (sx, sy)

    def _compute_game_scale(self, result):
        if result.map_scale <= 0 or not result.game_center:
            return None
        map_id = self._locked_map_id
        if map_id is None or map_id not in self._coords_dict:
            return None
        coords_scale = self._coords_dict[map_id].get('scale', [1.0, 1.0])
        game_scale = result.map_scale * coords_scale[0]
        logger.info(
            f"[MapFallback] game_scale={game_scale:.4f} "
            f"(map_scale={result.map_scale:.4f} * coords_scale={coords_scale[0]:.4f})"
        )
        return game_scale

    def _draw_overlay_screen_center(self, player_pos, game_scale=None):
        overlay_view = self.get_overlay_view()
        if overlay_view is None:
            return
        self._init_overlay()
        radius = self.config.get('Search radius (world units)') * BIG_MAP_SEARCH_MULTIPLIER
        if game_scale is not None and game_scale > 0:
            scale = 1.0 / game_scale
            logger.info(
                f"[MapFallback] overlay scale={scale:.6f} (game_scale={game_scale:.2f}, "
                f"1 pixel = {game_scale:.0f} game units)"
            )
        else:
            scale_per_1000 = self.config.get('Map scale (pixels per 1000 units)')
            if self.config.get('Auto map scale'):
                scale_factor = 1 - (1.25 - self.screen_width / 1600)
                scale_per_1000 = scale_factor * 1.205 * 10
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
            color = ITEM_COLORS.get(type_id)
            draw_items.append((sx, sy, name, color))

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
