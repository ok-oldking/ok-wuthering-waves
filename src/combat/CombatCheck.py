import re
import time

import cv2

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
        self.in_liberation = False  # return True
        self.has_count_down = False
        self.last_out_of_combat_time = 0
        self.last_combat_check = 0
        self.boss_lv_box = None
        self.boss_health_box = None
        self.boss_health = None
        self.out_of_combat_reason = ""
        self.combat_check_interval = 0.8
        self.last_liberation = 0

    def reset_to_false(self, recheck=False, reason=""):
        if self.handle_monthly_card():
            return True
        if is_pure_black(self.frame):
            logger.error('getting a pure black frame for unknown reason, reset_to_false return true')
            return True
        if recheck and time.time() - self.last_out_of_combat_time > 2.1:
            logger.info('out of combat start double check')
            if self.debug:
                self.screenshot('out of combat start double check')
            self.last_out_of_combat_time = time.time()
            return True
        else:
            self.out_of_combat_reason = reason
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
        return time.time() - self.last_liberation < 0.3

    def check_count_down(self):
        count_down_area = self.box_of_screen(1820 / 3840, 266 / 2160, 2100 / 3840,
                                             340 / 2160, name="check_count_down")
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

    def check_boss(self, in_team):
        current = self.boss_lv_box.crop_frame(self.frame)
        max_val = 0
        if current is not None:
            res = cv2.matchTemplate(current, self.boss_lv_template, cv2.TM_CCOEFF_NORMED, mask=self.boss_lv_mask)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val < 0.8:
            if self.debug:
                self.screenshot_boss_lv(current, f'boss lv not detected by edge {max_val}')
            logger.debug(f'boss lv not detected by edge')
            if not self.find_boss_lv_text():  # double check by text
                if not in_team and not self.check_health_bar() and not self.check_count_down() and not self.find_target_enemy():
                    if self.debug:
                        self.screenshot_boss_lv(current, 'out_of combat boss_health disappeared')
                    logger.info(f'out of combat because of boss_health disappeared, res:{max_val}')
                    return False
                else:
                    self.boss_lv_template = None
                    self.boss_lv_box = None
                    logger.info(f'boss_health disappeared, but still in combat')
                    return True
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

    def find_target_enemy(self):
        start = time.time()
        target_enemy = self.find_one('target_enemy_white', box=self.box_of_screen(0.25, 0.25, 0.75, 0.75),
                                     use_gray_scale=True, threshold=0.83,
                                     frame_processor=process_target_enemy_area)
        # if self.debug and target_enemy is not None:
        #     self.screenshot('find_target_enemy')
        logger.debug(f'find_target_enemy {target_enemy} {time.time() - start}')
        return target_enemy is not None

    def in_combat(self, rechecked=False):
        if self.in_liberation or self.recent_liberation():
            self.last_combat_check = time.time()
            logger.debug('in liberation return True')
            return True
        if self._in_combat:
            now = time.time()
            if now - self.last_combat_check > self.combat_check_interval:
                self.last_combat_check = now
                in_team = self.in_team()[0]
                if not in_team:
                    return self.reset_to_false(recheck=False, reason="not in team")
                if self.check_count_down():
                    return True
                if self.boss_lv_template is not None:
                    if self.check_boss(in_team):
                        return True
                    else:
                        return self.reset_to_false(recheck=False, reason="boss disappear")
                if not self.check_health_bar():
                    logger.debug('not in team or no health bar')
                    if not self.target_enemy():
                        logger.error('target_enemy failed, break out of combat')
                        return self.reset_to_false(reason='target enemy failed')
                    return True
                else:
                    logger.debug(
                        'check in combat pass')
                    return True
            else:
                return True
        else:
            in_combat = self.in_team()[0] and self.check_health_bar()
            if in_combat:
                in_combat = self.boss_health_box is not None or self.boss_lv_template is not None or self.has_count_down
                if in_combat:
                    self.target_enemy(wait=False)
                else:
                    in_combat = self.target_enemy()
            if in_combat:
                logger.info(
                    f'enter combat boss_lv_template:{self.boss_lv_template is not None} boss_health_box:{self.boss_health_box} has_count_down:{self.has_count_down}')
                self._in_combat = True
                return True

    def target_enemy(self, wait=True):
        if not wait:
            self.middle_click()
        else:
            if self.find_target_enemy():
                return True
            self.middle_click()
            return self.wait_until(self.find_target_enemy, time_out=2)

    def check_health_bar(self):
        if self._in_combat:
            min_height = self.height_of_screen(10 / 2160)
            max_height = min_height * 3
            min_width = self.width_of_screen(15 / 3840)
        else:
            min_height = self.height_of_screen(12 / 2160)
            max_height = min_height * 3
            min_width = self.width_of_screen(100 / 3840)

        boxes = find_color_rectangles(self.frame, enemy_health_color_red, min_width, min_height, max_height=max_height)

        if len(boxes) > 0:
            self.draw_boxes('enemy_health_bar_red', boxes, color='blue')
            return True
        else:
            boxes = find_color_rectangles(self.frame, boss_health_color, min_width * 3, min_height * 1.3,
                                          box=self.box_of_screen(1269 / 3840, 58 / 2160, 2533 / 3840, 192 / 2160))
            if len(boxes) == 1:
                self.boss_health_box = boxes[0]
                self.boss_health_box.width = 10
                self.boss_health_box.x += 6
                self.boss_health = self.boss_health_box.crop_frame(self.frame)
                self.draw_boxes('boss_health', boxes, color='blue')
                return True

        return self.find_boss_lv_text()

    def find_boss_lv_text(self):
        texts = self.ocr(box=self.box_of_screen(1269 / 3840, 10 / 2160, 2533 / 3840, 140 / 2160),
                         target_height=540)
        boss_lv_texts = find_boxes_by_name(texts,
                                           [re.compile(r'(?i)^L[V].*')])
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


def process_target_enemy_area(frame):
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
