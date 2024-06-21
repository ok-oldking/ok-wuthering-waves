import time

import cv2

from ok.color.Color import find_color_rectangles
from ok.logging.Logger import get_logger

logger = get_logger(__name__)


class CombatCheck:
    last_out_of_combat_time = 0
    last_combat_check = 0
    _in_combat = False
    boss_health = None
    boss_health_box = None
    in_liberation = False  # return True
    has_count_down = False  # instant end of combat if count_down goes away

    def reset_to_false(self):
        self._in_combat = False
        self.boss_health = None
        self.in_liberation = False  # return True
        self.has_count_down = False
        self.last_out_of_combat_time = 0
        self.last_combat_check = 0
        return False

    def check_if_instant_end(self):
        if self.boss_health is not None:
            res = cv2.matchTemplate(self.boss_health, self.boss_health_box.crop_frame(self.frame), cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            if max_val < 0.98:
                self.boss_health_box.confidence = max_val
                self.draw_boxes('enemy_health_bar_red', self.boss_health_box, color='red')
                logger.info(f'out of combat because of boss_health disappeared, res:{max_val} {res}')
                return True
        if self.has_count_down:
            count_down = self.find_one('gray_combat_count_down')
            if not count_down:
                logger.info('out of combat because of count_down disappeared')
                return True

    def in_combat(self):
        if self._in_combat:
            now = time.time()
            if now - self.last_combat_check > 0.5:
                self.last_combat_check = now
                if self.check_if_instant_end():
                    return self.reset_to_false()
                if not self.in_team()[0] or not self.check_health_bar():
                    logger.debug('not in team and no health bar')
                    if self.last_out_of_combat_time == 0:
                        self.last_out_of_combat_time = now
                        logger.debug(
                            'first time detected, not in team and no health bar, wait for 4 seconds to double check')
                        return True
                    elif now - self.last_combat_check > 4:
                        logger.debug('out of combat for 4 secs return False')
                        return self.reset_to_false()
                    else:
                        return True
                else:
                    logger.debug(
                        'back to combat')
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
