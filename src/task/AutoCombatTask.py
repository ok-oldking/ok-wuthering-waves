import re
import time

from ok.color.Color import white_color
from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.TriggerTask import TriggerTask
from src.char.CharFactory import get_char_by_pos

logger = get_logger(__name__)


class AutoCombatTask(TriggerTask, FindFeature, OCR):

    def __init__(self):
        super().__init__()
        self.chars = list()
        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']
        self.default_config = {
            'Echo Key': 'q',
            'Liberation Key': 'r',
            'Resonance Key': 'e',
        }
        self.last_check_combat = time.time()
        self._in_combat = False
        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']

    def run(self):
        self.load_chars()
        if self.chars and self.in_combat():
            self.get_current_char().perform()

    def switch_next_char(self, current_char, post_action=None):
        max_priority = -1
        switch_to = None
        has_intro = current_char.is_con_full()
        for i, char in enumerate(self.chars):
            if char == current_char:
                priority = 0
            else:
                priority = char.get_switch_priority(current_char, has_intro)
            if priority > max_priority:
                max_priority = priority
                switch_to = char
        if switch_to == current_char:
            self.sleep(0.2)
            current_char.normal_attack()
            logger.warning(f"can't find next char to switch to, maybe switching too fast, sleep and wait")
            return self.switch_next_char(current_char, post_action)
        switch_to.has_intro = has_intro
        self.send_key(switch_to.index + 1)
        while True:
            self.sleep(0.01)
            if self.find_one(self.char_texts[switch_to.index]):
                self.send_key(switch_to.index + 1)
                logger.info('switch not detected, try click again')
            else:
                break

        if post_action:
            post_action()

    def get_current_char(self):
        for i, char in enumerate(self.char_texts):
            feature = self.find_one(char)
            if not feature:
                return self.chars[i]
        self.log_error('can find current char!!')
        return None

    def in_combat(self):
        current_time = time.time()
        if self._in_combat:
            if current_time - self.last_check_combat > 3:  # delay out of combat check
                self._in_combat = self.check_in_combat()
        else:
            if current_time - self.last_check_combat > 0.2:
                self._in_combat = self.check_in_combat()
        return self._in_combat

    def check_in_combat(self):
        self.last_check_combat = time.time()
        return self.in_team() and self.ocr(0.1, 0, 0.9, 0.9, match=re.compile(r'^Lv'), target_height=720)

        # min_height = self.height_of_screen(10 / 2160)
        # max_height = min_height * 3
        # min_width = self.width_of_screen(90 / 3840)
        # boxes = find_color_rectangles(self.frame, enemy_health_color_red, min_width, min_height, max_height=max_height)
        #
        # if len(boxes) > 0:
        #     self.draw_boxes('enemy_health_bar_red', boxes, color='blue')
        #     return True
        # else:
        #     boxes = find_color_rectangles(self.frame, enemy_health_color_black, min_width, min_height,
        #                                   max_height=max_height)
        #     if len(boxes) > 0:
        #         self.draw_boxes('enemy_health_black', boxes, color='blue')
        #         return True
        #     else:
        #         boxes = find_color_rectangles(self.frame, boss_health_color, min_width, min_height * 1.5,
        #                                       box=self.box_of_screen(1269 / 3840, 58 / 2160, 2533 / 3840, 192 / 2160))
        #         if len(boxes) > 0:
        #             self.draw_boxes('boss_health', boxes, color='blue')
        #             return True

    def load_chars(self):
        if self.chars:
            return
        if not self.in_team():
            return
        self.log_info('load chars')
        self.chars.clear()
        self.chars.append(get_char_by_pos(self, self.get_box_by_name('box_char_1'), 0))
        self.chars.append(get_char_by_pos(self, self.get_box_by_name('box_char_2'), 1))
        self.chars.append(get_char_by_pos(self, self.get_box_by_name('box_char_3'), 2))
        self.log_info(f'load chars success {self.chars}', notify=True)

    def box_resonance(self):
        return self.get_box_by_name('box_resonance_cd')

    def get_resonance_cd_percentage(self):
        return self.calculate_color_percentage(white_color, self.get_box_by_name('box_resonance_cd'))

    def get_resonance_percentage(self):
        return self.calculate_color_percentage(white_color, self.get_box_by_name('box_resonance'))

    def in_team(self):
        c1 = self.find_one('char_1_text')
        c2 = self.find_one('char_2_text')
        c3 = self.find_one('char_3_text')
        logger.debug(f'in team {c1} {c2} {c3}')
        return sum(x is not None for x in [c1, c2, c3]) == 2


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
