import time

import cv2

import re
from ok.color.Color import find_color_rectangles, get_mask_in_color_range, is_pure_black
from ok.feature.Box import find_boxes_by_name
from ok.logging.Logger import get_logger
from src import text_white_color

logger = get_logger(__name__)


class CombatCheck:

    def __init__(self):
        self._in_combat = False
        self.boss_lv_template = None
        self.boss_lv_mask = None
        self._in_liberation = False  # return True
        self.has_count_down = False
        self.last_out_of_combat_time = 0
        self.last_combat_check = 0
        self.boss_lv_box = None
        self.boss_health_box = None
        self.boss_health = None
        self.out_of_combat_reason = ""
        self.combat_check_interval = 1
        self._last_liberation = 0

    @property
    def in_liberation(self):
        return self._in_liberation

    @in_liberation.setter
    def in_liberation(self, value):
        self._in_liberation = value
        if value:
            self._last_liberation = time.time()

    def reset_to_false(self, recheck=False, reason=""):
        if self.should_check_monthly_card() and self.handle_monthly_card():
            return True
        if is_pure_black(self.frame):
            logger.error('getting a pure black frame for unknown reason, reset_to_false return true')
            return True
        if recheck:
            logger.info('out of combat start double check')
            if self.debug:
                self.screenshot('out of combat start double check')
            if self.wait_until(self.check_health_bar, time_out=1.2, wait_until_before_delay=0,
                               wait_until_check_delay=0):
                return True
        self.out_of_combat_reason = reason
        self.do_reset_to_false()
        return False

    def do_reset_to_false(self):
        self._in_combat = False
        self.boss_lv_mask = None
        self.boss_lv_template = None
        self.in_liberation = False  # return True
        self.has_count_down = False
        self.last_out_of_combat_time = 0
        self.last_combat_check = 0
        self.boss_lv_box = None
        self.boss_health = None
        self.boss_health_box = None
        return False

    def recent_liberation(self):
        return time.time() - self._last_liberation < 0.15

    def check_count_down(self):
        count_down_area = self.box_of_screen_scaled(3840, 2160, 1820, 266, 2100,
                                                    340, name="check_count_down", hcenter=True)
        count_down = self.calculate_color_percentage(text_white_color,
                                                     count_down_area)

        if self.has_count_down:
            if count_down < 0.03:
                numbers = self.ocr(box=count_down_area, match=count_down_re)
                if self.debug:
                    self.screenshot(f'count_down disappeared {count_down:.2f}%')
                logger.info(f'count_down disappeared {numbers} {count_down:.2f}%')
                if not numbers:
                    self.has_count_down = False
                    return False
                else:
                    return True
            else:
                return True
        else:
            if count_down > 0.03:
                numbers = self.ocr(box=count_down_area, match=count_down_re)
                if numbers:
                    self.has_count_down = True
                logger.info(f'set count_down to {self.has_count_down}  {numbers} {count_down:.2f}%')
            return self.has_count_down

    def check_boss(self):
        if self.boss_lv_box is not None:
            current = self.boss_lv_box.crop_frame(self.frame)
        else:
            self.boss_lv_template = None
            self.boss_lv_box = None
            current = None
        max_val = 0
        if current is not None:
            res = cv2.matchTemplate(current, self.boss_lv_template, cv2.TM_CCOEFF_NORMED, mask=self.boss_lv_mask)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val < 0.8:
            if self.debug:
                self.screenshot_boss_lv(current, f'boss lv not detected by edge {max_val}')
            logger.debug(f'boss lv not detected by edge')
            if not self.find_boss_lv_text():  # double check by text
                if self.debug:
                    self.screenshot_boss_lv(current, 'out_of combat boss_health disappeared')
                self.boss_lv_template = None
                self.boss_lv_box = None
                logger.info(f'out of combat because of boss_health disappeared, res:{max_val}')
                return False
            else:
                return True
        else:
            logger.debug(f'check boss edge passed {max_val}')
            return True

    def screenshot_boss_lv(self, current, name):
        if self.debug:
            if self.boss_lv_box is not None and self.boss_lv_template is not None and current is not None:
                frame = self.frame.copy()
                frame[self.boss_lv_box.y:self.boss_lv_box.y + self.boss_lv_box.height,
                self.boss_lv_box.x:self.boss_lv_box.x + self.boss_lv_box.width] = current
                x, y, w, h = self.boss_lv_box.x, self.boss_lv_box.height + 50 + self.boss_lv_box.y, self.boss_lv_box.width, self.boss_lv_box.height
                frame[y:y + h, x:x + w] = self.boss_lv_template
                self.screenshot(name, frame)

    @property
    def target_area_box(self):
        return self.box_of_screen(0.1, 0.10, 0.9, 0.9, hcenter=True, name="target_area_box")

    def find_target_enemy(self):
        start = time.time()
        target_enemy = self.find_one('target_enemy_white', box=self.target_area_box,
                                     use_gray_scale=True, threshold=0.85,
                                     frame_processor=keep_only_white)
        if self.debug and target_enemy is None:
            self.screenshot('find_target_enemy')
        logger.debug(f'find_target_enemy {target_enemy} {time.time() - start}')
        return target_enemy is not None

    def in_combat(self, check_team=True):
        if self.in_liberation or self.recent_liberation():
            return True
        if self._in_combat:
            now = time.time()
            if now - self.last_combat_check > self.combat_check_interval:
                self.last_combat_check = now
                if check_team and not self.in_team()[0]:
                    logger.info('not in team break out of combat')
                    return self.reset_to_false(recheck=False, reason="not in team")
                if not self.check_target_enemy():
                    return self.reset_to_false(recheck=False, reason="no target enemy")
                if self.check_count_down():
                    return self.log_time(now, 'check_count_down')
                if self.boss_lv_template is not None:
                    if self.check_boss():
                        return self.log_time(now, 'check_boss')
                if self.check_health_bar():
                    return self.log_time(now, 'check_health_bar')
                if self.find_target_enemy():
                    return self.log_time(now, 'find_target_enemy')
                if self.ocr_lv_text():
                    return self.log_time(now, 'ocr_lv_text')
                self.next_frame()
                if self.target_enemy():
                    return self.log_time(now, 'target_enemy')
                logger.error('target_enemy failed, try recheck break out of combat')
                return self.reset_to_false(recheck=True, reason='target enemy failed')
            else:
                return True
        else:
            start = time.time()
            in_combat = ((not check_team) or self.in_team()[0]) and self.check_health_bar()
            if in_combat:
                self.target_enemy(wait=False)
                if self.boss_lv_template is None:
                    self.find_boss_lv_text()
                logger.info(
                    f'enter combat cost {(time.time() - start):2f} boss_lv_template:{self.boss_lv_template is not None} boss_health_box:{self.boss_health_box} has_count_down:{self.has_count_down}')
                self._in_combat = True
                return True

    def log_time(self, start, name):
        logger.debug(f'check cost {name} {time.time() - start}')
        return True

    def ocr_lv_text(self):
        lvs = self.ocr(box=self.target_area_box,
                       match=re.compile(r'lv\.\d{1,3}', re.IGNORECASE),
                       target_height=540, name='lv_text', log=True)
        return lvs

    def check_target_enemy(self):
        if self.calculate_color_percentage(text_white_color,
                                           self.get_box_by_name('box_target_enemy')) == 0:
            logger.info(f'check target_enemy failed, wait 3 seconds')
            if self.wait_until(lambda: self.calculate_color_percentage(text_white_color,
                                                                       self.get_box_by_name('box_target_enemy')) != 0,
                               wait_until_before_delay=0, wait_until_check_delay=0,
                               time_out=5):
                return True
            self.log_error(
                "Auto combat error: Make sure you're equipping echos and turn off effect that changes the game color, (Game Gammar/Nvidia AMD Game Filter), turn off Motion Blur in game video options",
                notify=True, tray=True)
            self.screenshot('check_target_enemy')
            self.pause()
        return True

    def target_enemy(self, wait=True):
        if not wait:
            self.middle_click()
        else:
            if self.find_target_enemy():
                return True
            return self.wait_until(self.find_target_enemy, time_out=2.5, wait_until_before_delay=0,
                                   wait_until_check_delay=0.1,
                                   pre_action=self.middle_click)

    def check_health_bar(self):
        if self._in_combat:
            min_height = self.height_of_screen(12 / 2160)
            max_height = min_height * 3
            min_width = self.width_of_screen(12 / 3840)
        else:
            min_height = self.height_of_screen(12 / 2160)
            max_height = min_height * 3
            min_width = self.width_of_screen(100 / 3840)

        boxes = find_color_rectangles(self.frame, enemy_health_color_red, min_width, min_height, max_height=max_height)

        if len(boxes) > 0:
            self.draw_boxes('enemy_health_bar_red', boxes, color='blue')
            return True
        else:
            boxes = find_color_rectangles(self.frame, boss_health_color, min_width, min_height * 1.3,
                                          box=self.box_of_screen(1269 / 3840, 58 / 2160, 2533 / 3840, 200 / 2160))
            if len(boxes) == 1:
                self.boss_health_box = boxes[0]
                self.boss_health_box.width = 10
                self.boss_health_box.x += 6
                self.boss_health = self.boss_health_box.crop_frame(self.frame)
                self.draw_boxes('boss_health', boxes, color='blue')
                return True

        return self.find_boss_lv_text()

    def find_boss_lv_text(self):
        texts = self.ocr(box=self.box_of_screen(1269 / 3840, 10 / 2160, 2533 / 3840, 140 / 2160, hcenter=True),
                         target_height=540, name='boss_lv_text')
        fps_text = find_boxes_by_name(texts,
                                      re.compile(r'FPS', re.IGNORECASE))
        if fps_text:
            raise Exception('FPS text detected on screen, please close any FPS overlay!')
        boss_lv_texts = find_boxes_by_name(texts,
                                           [re.compile(r'(?i)^L[Vv].*')])
        if len(boss_lv_texts) > 0:
            logger.debug(f'boss_lv_texts: {boss_lv_texts}')
            self.boss_lv_box = boss_lv_texts[0]
            self.boss_lv_template, self.boss_lv_mask = self.keep_boss_text_white()
            if self.boss_lv_template is None:
                self.boss_lv_box = None
                return False
            return True

    def keep_boss_text_white(self):
        cropped = self.boss_lv_box.crop_frame(self.frame)
        mask, area = get_mask_in_color_range(cropped, boss_white_text_color)
        if area / mask.shape[0] * mask.shape[1] < 0.05:
            mask, area = get_mask_in_color_range(cropped, boss_orange_text_color)
            if area / mask.shape[0] * mask.shape[1] < 0.05:
                mask, area = get_mask_in_color_range(cropped,
                                                     boss_red_text_color)
                if area / mask.shape[0] * mask.shape[1] < 0.05:
                    logger.error(f'keep_boss_text_white cant find text with the correct color')
                    return None, 0
        return cropped, mask


count_down_re = re.compile(r'\d\d')


def keep_only_white(frame):
    frame[frame != 255] = 0
    return frame


enemy_health_color_red = {
    'r': (202, 212),  # Red range
    'g': (70, 80),  # Green range
    'b': (55, 65)  # Blue range
}  # 207,75,60

enemy_health_color_black = {
    'r': (10, 55),  # Red range
    'g': (28, 50),  # Green range
    'b': (18, 70)  # Blue range
}

boss_white_text_color = {
    'r': (200, 255),  # Red range
    'g': (200, 255),  # Green range
    'b': (200, 255)  # Blue range
}

boss_orange_text_color = {
    'r': (218, 218),  # Red range
    'g': (178, 178),  # Green range
    'b': (68, 68)  # Blue range
}

boss_red_text_color = {
    'r': (200, 230),  # Red range
    'g': (70, 90),  # Green range
    'b': (60, 80)  # Blue range
}

boss_health_color = {
    'r': (245, 255),  # Red range
    'g': (30, 185),  # Green range
    'b': (4, 75)  # Blue range
}
