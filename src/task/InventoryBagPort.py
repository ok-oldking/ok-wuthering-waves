from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Read-only native ok-ww bag port; navigation requires native calibration.

Reuses Task.next_frame/ocr, the configured Bag Key and native click/scroll.
Unlike MergeEchoTask, no ensure_main, login, dialog confirmation, item use,
merging/discarding or game startup is reachable from this port.
"""
import hashlib
import json
import logging
import importlib.util
from pathlib import Path
from math import ceil, floor, isfinite
import unicodedata
import time
import re

def exact_token(boxes):
    if not isinstance(boxes, list) or len(boxes) != 1:
        return None
    box = boxes[0]
    name, confidence = (getattr(box, 'name', None), getattr(box, 'confidence', None))
    if not isinstance(name, str) or not name.strip() or isinstance(confidence, bool) or (not isinstance(confidence, (int, float))) or (not isfinite(confidence)) or (not 0.9 <= confidence <= 1):
        return None
    return {'text': name, 'confidence': confidence}

def compact(value):
    return ''.join(unicodedata.normalize('NFKC', value).split())

def normalized_weapon_footers(boxes, width, height):
    """Validated level-label geometry, never an inventory count."""
    if not isinstance(boxes, list) or len(boxes) > 512:
        return []
    if any((type(n) is not int or n <= 0 for n in (width, height))):
        raise ValueError('Invalid native frame size')
    result = []
    for box in boxes:
        name = getattr(box, 'name', None)
        confidence = getattr(box, 'confidence', None)
        if not isinstance(name, str) or re.fullmatch('Lv\\.(?:[1-9]|[1-8][0-9]|90)', compact(name), re.IGNORECASE) is None or isinstance(confidence, bool) or (not isinstance(confidence, (int, float))) or (not isfinite(confidence)) or (not 0.98 <= confidence <= 1):
            continue
        coords = [getattr(box, key, None) for key in ('x', 'y', 'width', 'height')]
        if any((isinstance(n, bool) or not isinstance(n, (int, float)) or (not isfinite(n)) for n in coords)):
            continue
        x, y, w, h = coords
        if x < 0 or y < 0 or w <= 0 or (h <= 0) or (x + w > width) or (y + h > height):
            continue
        x, y, w, h = (x * 1920 / width, y * 1080 / height, w * 1920 / width, h * 1080 / height)
        result.append((x, y, w, h, 'Lv.' + compact(name)[3:]))
    return result

def weapon_level_cells(cells, boxes, width, height):
    """Positive footer identities only; uncertain OCR keeps the cell readable."""
    matches = {}
    for x, y, w, h, name in normalized_weapon_footers(boxes, width, height):
        bound = [tuple(cell) for cell in cells if cell[0] - 70 <= x and x + w <= cell[0] + 70 and (cell[1] + 40 <= y) and (y + h <= cell[1] + 110)]
        if len(bound) == 1:
            matches.setdefault(bound[0], []).append(name)
    return {cell: names[0] for cell, names in matches.items() if len(names) == 1}

def weapon_viewport_grid(cells, boxes, width, height):
    """Infer the shifted row lattice only from two multi-column Lv rows.

    Native card pitch is 210 canonical pixels. A click 65 pixels above a
    verified footer lies inside its card, not in the row gap. Unknown material
    rows share this lattice but are still clicked and exactly identified.
    No individual Lv label can move the grid. Conflicts keep the old grid.
    """
    columns = sorted({cell[0] for cell in cells})
    if len(columns) != 6 or len(cells) != 18 or sorted({cell[1] for cell in cells}) != [225, 435, 645]:
        return cells
    rows = []
    for x, y, w, h, _ in sorted(normalized_weapon_footers(boxes, width, height), key=lambda b: b[1]):
        bound = [column for column in columns if column - 70 <= x and x + w <= column + 70]
        if len(bound) != 1 or not 8 <= h <= 32 or (not 20 <= w <= 100):
            continue
        if not rows or y - rows[-1][0][1] > 8:
            rows.append([])
        rows[-1].append((bound[0], y))
    if any((len(row) >= 2 and len({x for x, _ in row}) != len(row) for row in rows)):
        return cells
    evidence = [sum((y for _, y in row)) / len(row) for row in rows if len(row) >= 2 and len({x for x, _ in row}) == len(row)]
    if len(evidence) < 2 or any((abs(b - a - 210) > 8 for a, b in zip(evidence, evidence[1:]))):
        return cells
    origin = round(sum((y - 65 - 210 * i for i, y in enumerate(evidence))) / len(evidence))
    while origin > 225:
        origin -= 210
    while origin < 225:
        origin += 210
    centers = list(range(origin, 822, 210))
    if not 2 <= len(centers) <= 3:
        return cells
    return [[x, y] for y in centers for x in columns]

class NativeBagPort:

    def __init__(self, task, guard):
        self.task = task
        self.scrollbar = None
        self.scroll_mode = 'native_track_click'
        self.selection_policy = None
        self._navigation_log_count = 0
        self._anchor_cache = None
        self._metrics = {'frames': 0, 'ocr_calls': 0, 'ocr_seconds': 0.0, 'anchor_cache_hits': 0, 'anchor_cache_misses': 0, 'guard_calls': 0, 'guard_seconds': 0.0, 'frame_seconds': 0.0, 'click_calls': 0, 'click_seconds': 0.0}

        def measured_guard():
            started = time.monotonic()
            self._metrics['guard_calls'] += 1
            try:
                return guard()
            finally:
                self._metrics['guard_seconds'] += max(0.0, time.monotonic() - started)
        self.guard = measured_guard

    def diagnostics(self):
        """Numeric snapshot only; safe to save even after cancellation."""
        return dict(self._metrics)

    def _navigation_trace(self, event, **values):
        """Bounded numeric navigation evidence, no OCR/account/window text."""
        if self._navigation_log_count > 256:
            return
        if self._navigation_log_count == 256:
            row = {'event': 'navigation_trace_limit', 'limit': 256}
        else:
            row = {'event': event, **values}
        self._navigation_log_count += 1
        try:
            logging.getLogger('ok.inventory.navigation').info('inventory_navigation %s', json.dumps(row, sort_keys=True))
        except Exception:
            pass

    def configure_scroll_mode(self, mode):
        self.guard()
        if self.scrollbar is None or mode not in ('native_track_click', 'native_grid_wheel'):
            raise ValueError('Explicit calibrated scrollbar mode required')
        self.scroll_mode = mode

    def configure_selection_policy(self, policy):
        self.guard()
        if policy != 'exclude_confirmed_weapon_level_footers' or self.scrollbar is None or self.scroll_mode != 'native_grid_wheel':
            raise ValueError('Explicit candidate weapon-footer policy required')
        self.selection_policy = policy

    def viewport_cells(self, cells):
        if self.selection_policy != 'exclude_confirmed_weapon_level_footers':
            raise ValueError('Weapon-footer policy not configured')
        before = self._thumb()
        observations = []
        for index in range(2):
            frame = self._frame()
            height, width = frame.shape[:2]
            self.guard()
            self._metrics['ocr_calls'] += 1
            started = time.monotonic()
            try:
                boxes = self.task.ocr(x=175 / 1920, y=138 / 1080, to_x=1205 / 1920, to_y=908 / 1080, threshold=0.98, frame=frame, log=False, screenshot=False)
            finally:
                self._metrics['ocr_seconds'] += max(0.0, time.monotonic() - started)
            self.guard()
            observations.append((boxes, width, height, weapon_viewport_grid(cells, boxes, width, height)))
            if index == 0:
                self.task.sleep(0.15)
        if self._thumb() != before:
            raise RuntimeError('Native viewport changed during footer verification')
        first, second = (observations[0][3], observations[1][3])
        agreed = len(first) == len(second) and all((a[0] == b[0] and abs(a[1] - b[1]) <= 2 for a, b in zip(first, second)))
        grid = [[a[0], (a[1] + b[1]) // 2] for a, b in zip(first, second)] if before[0] != 0 and agreed else cells
        levels = [weapon_level_cells(grid, boxes, width, height) for boxes, width, height, _ in observations]
        excluded = {cell for cell, name in levels[0].items() if levels[1].get(cell) == name}
        self._navigation_trace('weapon_footer_exclusion', excluded=len(excluded), retained=len(grid) - len(excluded), rows_relocated=grid != cells, row_geometry_agreed=agreed, inferred_rows=[sorted({cell[1] for cell in observation[3]}) for observation in observations], valid_footer_counts=[len(normalized_weapon_footers(boxes, width, height)) for boxes, width, height, _ in observations])
        return [cell for cell in grid if tuple(cell) not in excluded]

    def configure_scrollbar(self, value):
        from src.inventory_support import inventory_scrollbar as module
        self.guard()
        module.validate(value)
        self.scrollbar = (module, value)

    def _thumb(self):
        import cv2
        module, value = self.scrollbar
        frame = cv2.resize(self._frame(), (1920, 1080))
        x, y, w, h = value['roi']
        return module.thumb(frame[y:y + h, x:x + w], value)

    def _frame(self):
        self.guard()
        self._metrics['frames'] += 1
        started = time.monotonic()
        try:
            frame = self.task.next_frame()
        finally:
            self._metrics['frame_seconds'] += max(0.0, time.monotonic() - started)
        if frame is None or len(frame.shape) != 3 or frame.shape[2] != 3 or (frame.shape[0] <= 0) or (abs(frame.shape[1] / frame.shape[0] - 16 / 9) > 0.01):
            raise RuntimeError('Native bag frame missing or aspect ratio changed')
        self.guard()
        return frame

    def _read(self, roi, frame):
        x, y, w, h = roi
        if any((type(n) is not int for n in roi)) or x < 0 or y < 0 or (w <= 0) or (h <= 0) or (x + w > 1920) or (y + h > 1080):
            raise ValueError('Uncalibrated native OCR ROI')
        self.guard()
        started = time.monotonic()
        self._metrics['ocr_calls'] += 1
        try:
            boxes = self.task.ocr(x=x / 1920, y=y / 1080, to_x=(x + w) / 1920, to_y=(y + h) / 1080, threshold=0.9, frame=frame, log=False, screenshot=False)
        finally:
            self._metrics['ocr_seconds'] += max(0.0, time.monotonic() - started)
        self.guard()
        return exact_token(boxes)

    def bag_open(self):
        value = self._read([105, 45, 64, 45], self._frame())
        return value is not None and compact(value['text']) in ('资源', '素材', '武器', '声骸', '补给', '任务')

    def open_bag(self):
        self._frame()
        self.guard()
        if not self.task.in_team_and_world():
            return False
        self.guard()
        self.task.send_key(self.task.key_config.get('Bag Key', 'b'))
        for _ in range(12):
            self.task.sleep(0.25)
            if self.bag_open():
                return True
        return False

    def select_tab(self, page, tab_roi):
        if self.page_verified(page):
            return True
        if not self.bag_open():
            return False
        x, y, w, h = tab_roi
        self.guard()
        self.task.click_relative((x + w / 2) / 1920, (y + h / 2) / 1080, after_sleep=0.2)
        for _ in range(12):
            if self.page_verified(page):
                return True
            self.task.sleep(0.25)
        return False

    def open_currency_popup(self, page, route):
        """One calibrated read-only tooltip click, no purchase/use/confirmation.

        Shared navigation validates this route before native APIs. Never toggle
        an already verified popup or call ensure_main on a foreign screen.
        """
        if self.page_verified(page):
            return True
        if not self.bag_open() and (not self.open_bag()):
            return False
        base = {'page_anchor': route['base_page_anchor']}
        if not self.select_tab(base, route['base_tab_roi']):
            return False
        if not self.page_verified(base):
            return False
        x, y, w, h = route['open_roi']
        self.guard()
        self.task.click_relative((x + w / 2) / 1920, (y + h / 2) / 1080, after_sleep=0.2)
        for _ in range(12):
            if self.page_verified(page):
                return True
            self.task.sleep(0.25)
        return False

    def close_currency_popup(self, page, route):
        """Dismiss only the verified read-only Shell Credit tooltip once.

        Do not send Escape to an unknown modal, shop or item-use dialog.
        Verify the calibrated underlying bag page before reporting cleanup.
        """
        self.guard()
        if compact(page['page_anchor']['text']) != '贝币' or route.get('strategy') != 'readonly_currency_popup':
            raise ValueError('Unreviewed currency popup cleanup')
        if not self.page_verified(page):
            return False
        self.guard()
        self.task.send_key('esc')
        base = {'page_anchor': route['base_page_anchor']}
        for _ in range(12):
            self.task.sleep(0.25)
            if self.page_verified(base):
                self._navigation_trace('currency_popup_closed')
                return True
        return False

    def _read_anchor(self, anchor, frame):
        """Reuse OCR only for identical fresh anchor pixels, never item data.

        Keep a single bounded cache entry. A one-pixel halo covers OCR crop
        rounding; resolution, ROI and expected label are part of its identity.
        Both page-verification frames are still acquired and guarded normally.
        """
        self.guard()
        roi = anchor['roi']
        if len(roi) != 4 or any((type(n) is not int for n in roi)):
            raise ValueError('Uncalibrated native anchor ROI')
        x, y, w, h = roi
        if x < 0 or y < 0 or w <= 0 or (h <= 0) or (x + w > 1920) or (y + h > 1080):
            raise ValueError('Uncalibrated native anchor ROI')
        height, width = frame.shape[:2]
        crop = frame[max(0, floor(y * height / 1080) - 1):min(height, ceil((y + h) * height / 1080) + 1), max(0, floor(x * width / 1920) - 1):min(width, ceil((x + w) * width / 1920) + 1)]
        key = (tuple(roi), anchor['text'], frame.shape, crop.tobytes())
        if self._anchor_cache is not None and self._anchor_cache[0] == key:
            self.guard()
            self._metrics['anchor_cache_hits'] += 1
            return dict(self._anchor_cache[1])
        self._metrics['anchor_cache_misses'] += 1
        self._anchor_cache = None
        token = self._read(roi, frame)
        if token is not None and compact(token['text']) == compact(anchor['text']):
            self._anchor_cache = (key, dict(token))
        self.guard()
        return token

    def page_verified(self, page):
        anchor = page['page_anchor']
        for index in range(2):
            token = self._read_anchor(anchor, self._frame())
            if token is None or compact(token['text']) != compact(anchor['text']):
                return False
            if index == 0:
                self.task.sleep(0.15)
        return True

    def click_cell(self, point):
        self.guard()
        started = time.monotonic()
        self._metrics['click_calls'] += 1
        try:
            self.task.click_relative(point[0] / 1920, point[1] / 1080, after_sleep=0.15)
        finally:
            self._metrics['click_seconds'] += max(0.0, time.monotonic() - started)
        self._frame()

    def read_detail(self, roi):
        return self._read(roi, self._frame())

    def grid_signature(self, roi):
        if self.scrollbar is not None:
            first = self._thumb()
            self.task.sleep(0.15)
            if self._thumb() != first:
                raise RuntimeError('Native scroll thumb is still moving')
            return self.scrollbar[0].signature(first)
        frame = self._frame()
        x, y, w, h = roi
        height, width = frame.shape[:2]
        crop = frame[round(y * height / 1080):round((y + h) * height / 1080), round(x * width / 1920):round((x + w) * width / 1920)]
        if crop.size == 0:
            raise RuntimeError('Native inventory grid crop empty')
        return hashlib.sha256(crop.tobytes()).hexdigest()

    def at_top(self):
        if self.scrollbar is None:
            raise RuntimeError('Native top geometry not configured')
        position = self._thumb()
        self.task.sleep(0.15)
        if self._thumb() != position:
            return False
        return self.scrollbar[0].at_top(position, self.scrollbar[1])

    def at_bottom(self, max_gap):
        if self.scrollbar is None or type(max_gap) is not int or (not 0 <= max_gap <= 30):
            raise ValueError('Explicit native bottom geometry required')
        position = self._thumb()
        self.task.sleep(0.15)
        if self._thumb() != position:
            return False
        height = self.scrollbar[1]['roi'][3]
        if position[1] > height:
            raise ValueError('Thumb outside calibrated track')
        return 0 <= height - position[1] <= max_gap

    def _foreground_grid_input(self):
        """Reuse OK's foreground driver only for the explicitly calibrated grid.

        PostMessage selection updates the detail panel but does not establish
        WuWa's physical pointer/focus for the wheel: the category pane can keep
        receiving it. Do not change the configured interaction or bring a
        background game forward. An occupied desktop must fail before input.
        """
        from ok.device.interaction_methods.pynput import PynputInteraction
        self.guard()
        native = self.task.executor.interaction
        window = getattr(native, 'hwnd_window', None)
        capture = getattr(native, 'capture', None)
        if window is None or capture is None or (not window.is_foreground()):
            raise RuntimeError('Native inventory grid requires foreground game; no input')
        driver = PynputInteraction(capture, window)
        if not driver.clickable():
            raise RuntimeError('Native inventory grid lost foreground; no input')
        return driver

    def _grid_input_guard(self, driver):
        self.guard()
        if not driver.clickable():
            raise RuntimeError('Native inventory grid lost foreground; no input')

    def _settled_wheel_thumb(self, driver):
        """Wait finitely for wheel inertia; never send input while it moves."""
        previous = self._thumb()
        observations = [previous]
        for index in range(8):
            self.task.sleep(0.15)
            self._grid_input_guard(driver)
            current = self._thumb()
            observations.append(current)
            if current == previous:
                self._navigation_trace('wheel_settled', observations=observations, polls=index + 1)
                return current
            previous = current
        self._navigation_trace('wheel_settle_exhausted', observations=observations, polls=8)
        raise RuntimeError('Native thumb is still moving after wheel: bounded settle exhausted')

    def scroll_grid(self, roi, notches, endpoint_seek=False):
        if type(notches) is not int or not 1 <= abs(notches) <= 6:
            raise ValueError('Bounded nonzero native scroll count required')
        if type(endpoint_seek) is not bool or (endpoint_seek and (self.scrollbar is None or self.scroll_mode != 'native_grid_wheel')):
            raise ValueError('Endpoint seek requires explicit calibrated native wheel')
        if self.scrollbar is not None:
            module, value = self.scrollbar
            position = self._thumb()
            self.task.sleep(0.15)
            stable = self._thumb()
            if stable != position:
                self._navigation_trace('preinput_thumb_moving', before=position, observed=stable)
                raise RuntimeError('Native scroll thumb is still moving; no input')
            if self.scroll_mode == 'native_grid_wheel':
                x, y, w, h = roi
                if any((type(n) is not int for n in roi)) or x < 0 or y < 0 or (w <= 0) or (h <= 0) or (x + w > 1920) or (y + h > 1080):
                    raise ValueError('Uncalibrated native grid focus ROI')
                driver = self._foreground_grid_input()
                px = int(self.task.width * (x + w / 2) / 1920)
                py = int(self.task.height * (y + h / 2) / 1080)
                self._grid_input_guard(driver)
                driver.click(px, py)
                self.task.executor.reset_scene()
                self.task.sleep(0.15)
                self._frame()
                focused = self._thumb()
                self._navigation_trace('grid_focus', before=position, after=focused, point=[px, py], endpoint_seek=endpoint_seek)
                if focused != position:
                    if focused[0] != position[0] or abs(focused[1] - position[1]) != 1:
                        raise RuntimeError('Native thumb changed while focusing grid')
                    for _ in range(2):
                        self.task.sleep(0.15)
                        self._grid_input_guard(driver)
                        observed = self._thumb()
                        if observed != focused:
                            self._navigation_trace('grid_focus_jitter_rejected', before=position, after=observed)
                            raise RuntimeError('Native thumb changed while focusing grid')
                    self._navigation_trace('grid_focus_edge_jitter_confirmed', before=position, after=focused, polls=2)
                    position = focused
                target = value['roi'][3] if endpoint_seek else max(1, (position[1] - position[0]) // 2)
                previous = position
                wheel_notches = (24 if notches > 0 else -24) if endpoint_seek else notches
                for transaction in range(64 if endpoint_seek else 8):
                    self._grid_input_guard(driver)
                    driver.scroll(px, py, -wheel_notches)
                    self.task.executor.reset_scene()
                    self.task.sleep(0.3)
                    self._frame()
                    self._grid_input_guard(driver)
                    current = self._settled_wheel_thumb(driver)
                    travel = current[0] - previous[0]
                    self._navigation_trace('wheel_transaction', index=transaction + 1, before=previous, after=current, notches=wheel_notches, target=target, endpoint_seek=endpoint_seek)
                    if travel and (travel > 0) != (notches > 0):
                        raise RuntimeError('Native grid moved in the wrong direction')
                    if abs(current[1] - current[0] - (position[1] - position[0])) > 2:
                        raise RuntimeError('Native grid thumb span changed during wheel')
                    if current == previous or abs(current[0] - position[0]) >= target:
                        break
                    previous = current
                return
            point = module.track_point(position, value, -1 if notches < 0 else 1)
            self.guard()
            self.task.click_relative(point[0] / 1920, point[1] / 1080, after_sleep=0.3)
            self._frame()
            return
        x, y, w, h = roi
        self.guard()
        self.task.scroll_relative((x + w / 2) / 1920, (y + h / 2) / 1080, -notches)
        self.task.sleep(0.2)
        self._frame()
