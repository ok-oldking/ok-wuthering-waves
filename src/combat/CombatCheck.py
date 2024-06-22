import re
import time

import cv2

from ok.color.Color import find_color_rectangles
from ok.feature.Box import find_boxes_by_name
from ok.logging.Logger import get_logger

logger = get_logger(__name__)


class CombatCheck:
    last_out_of_combat_time = 0
    last_combat_check = 0
    _in_combat = False
    boss_lv_edge = None
    boss_lv_box = None
    in_liberation = False  # return True
    has_count_down = False  # instant end of combat if count_down goes away

    def reset_to_false(self):
        self._in_combat = False
        self.boss_lv_edge = None
        self.in_liberation = False  # return True
        self.has_count_down = False
        self.last_out_of_combat_time = 0
        self.last_combat_check = 0
        return False

    def check_count_down(self):
        if self.has_count_down:
            count_down = self.find_one('gray_combat_count_down', threshold=0.8)
            if not count_down:
                self.screenshot('out of combat because of count_down disappeared')
                logger.info('out of combat because of count_down disappeared')
                return False
        return True

    def check_boss(self):
        current = cv2.cvtColor(self.boss_lv_box.crop_frame(self.frame), cv2.COLOR_BGR2GRAY)
        current = cv2.Canny(current, 100, 200)
        res = cv2.matchTemplate(current, self.boss_lv_edge, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if max_val < 0.70:
            if not self.find_boss_lv_text():  # double check by text
                self.boss_lv_box.confidence = max_val
                self.draw_boxes('enemy_health_bar_red', self.boss_lv_box, color='red')
                self.screenshot_boss_lv(current, 'out_of combat boss_health disappeared')
                logger.info(f'out of combat because of boss_health disappeared, res:{max_val} {res}')
                return self.reset_to_false()
            else:
                return True
        else:
            logger.debug(f'check boss edge passed {res}')
            return True

    def screenshot_boss_lv(self, current, name):
        if self.debug:
            colored = cv2.cvtColor(self.boss_lv_edge, cv2.COLOR_GRAY2BGR)
            self.frame[self.boss_lv_box.y:self.boss_lv_box.y + self.boss_lv_box.height,
            self.boss_lv_box.x:self.boss_lv_box.x + self.boss_lv_box.width] = cv2.cvtColor(current,
                                                                                           cv2.COLOR_GRAY2BGR)
            x, y, w, h = self.boss_lv_box.x, self.boss_lv_box.height + 50 + self.boss_lv_box.y, self.boss_lv_box.width, self.boss_lv_box.height
            self.frame[y:y + h, x:x + w] = colored
            self.screenshot(name)

    def in_combat(self):
        if self.in_liberation:
            logger.debug('in liberation return True')
            return True
        if self._in_combat:
            now = time.time()
            if now - self.last_combat_check > 0.3:
                self.last_combat_check = now
                if self.boss_lv_edge is not None:
                    return self.check_boss()
                if self.check_count_down():
                    return True
                if not self.in_team()[0] or not self.check_health_bar():
                    logger.debug('not in team and no health bar')
                    if self.last_out_of_combat_time == 0:
                        self.last_out_of_combat_time = now
                        logger.debug(
                            'first time detected, not in team and no health bar, wait for 4 seconds to double check')
                        return True
                    elif now - self.last_out_of_combat_time > 4:
                        logger.debug('out of combat for 4 secs return False')
                        return self.reset_to_false()
                    else:
                        return True
                else:
                    logger.debug(
                        'check in combat pass')
                    self.last_out_of_combat_time = 0
                    return True
            else:
                return True
        else:
            in_combat = self.in_team()[0] and self.check_health_bar()
            if in_combat:
                self.has_count_down = self.find_one('gray_combat_count_down') is not None
                self._in_combat = True
                return True

    def check_health_bar(self, find_boss=True):
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
        elif find_boss:
            return self.find_boss_lv_text()

    def find_boss_lv_text(self):
        texts = self.ocr(box=self.box_of_screen(1269 / 3840, 10 / 2160, 2533 / 3840, 140 / 2160),
                         target_height=720)
        boss_lv_texts = find_boxes_by_name(texts,
                                           [re.compile(r'(?i)^L'), re.compile(r"\d{2}")])
        if len(boss_lv_texts) > 0:
            logger.debug(f'boss_lv_texts: {boss_lv_texts}')
            self.boss_lv_box = boss_lv_texts[0]
            self.boss_lv_edge = cv2.cvtColor(self.boss_lv_box.crop_frame(self.frame), cv2.COLOR_BGR2GRAY)
            self.boss_lv_edge = cv2.Canny(self.boss_lv_edge, 100, 200)
            self.screenshot_boss_lv(self.boss_lv_edge, 'found_boss_lv')
            return True


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

boss_health_color = {
    'r': (250, 255),  # Red range
    'g': (30, 180),  # Green range
    'b': (4, 75)  # Blue range
}
