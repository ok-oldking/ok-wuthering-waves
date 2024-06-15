import time

from ok.color.Color import find_color_rectangles
from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.TriggerTask import TriggerTask
from ok.util.list import safe_get
from src.char import BaseChar
from src.char.BaseChar import Priority
from src.char.CharFactory import get_char_by_pos

logger = get_logger(__name__)


class AutoCombatTask(TriggerTask, FindFeature, OCR):

    def __init__(self):
        super().__init__()
        self.chars = [None, None, None]
        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']
        self.default_config.update({
            'Echo Key': 'q',
            'Liberation Key': 'r',
            'Resonance Key': 'e',
        })
        self.last_check_combat = time.time()
        self._in_combat = False
        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']

    def run(self):
        while self.in_combat():
            self.get_current_char().perform()

    def trigger(self):
        if self.in_combat():
            self.load_chars()
            return True

    def switch_next_char(self, current_char, post_action=None):
        max_priority = Priority.MIN
        switch_to = None
        has_intro = current_char.is_con_full()
        for i, char in enumerate(self.chars):
            if char == current_char:
                priority = Priority.CURRENT_CHAR
            else:
                priority = char.get_switch_priority(current_char, has_intro)
                logger.info(f'switch priority: {char} {priority}')
            if priority > max_priority:
                max_priority = priority
                switch_to = char
        if switch_to == current_char:
            logger.warning(f"can't find next char to switch to, maybe switching too fast, sleep and wait")
            return
        switch_to.has_intro = has_intro
        self.send_key(switch_to.index + 1)
        while True:
            self.sleep(0.01)
            if self.find_one(self.char_texts[switch_to.index]):
                self.send_key(switch_to.index + 1)
                logger.info('switch not detected, try click again')
            else:
                switch_time = time.time()
                break

        if post_action:
            post_action()
        return switch_time

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
            if current_time - self.last_check_combat > 4:  # delay out of combat check
                self.handler.post(self.check_in_combat, remove_existing=True, skip_if_running=True)
        else:
            if current_time - self.last_check_combat > 2:
                self.handler.post(self.check_in_combat, remove_existing=True, skip_if_running=True)
        return self._in_combat

    def check_in_combat(self):
        self.last_check_combat = time.time()
        if self._in_combat:
            if not self.in_team() or not self.check_health_bar():
                time.sleep(4)
                if not self.in_team() or not self.check_health_bar():
                    self._in_combat = False
        else:
            self._in_combat = self.in_team() and self.check_health_bar()

    def check_health_bar(self):
        min_height = self.height_of_screen(10 / 2160)
        max_height = min_height * 3
        min_width = self.width_of_screen(40 / 3840)
        boxes = find_color_rectangles(self.frame, enemy_health_color_red, min_width, min_height, max_height=max_height)

        if len(boxes) > 0:
            self.draw_boxes('enemy_health_bar_red', boxes, color='blue')
            return True
        else:
            boxes = find_color_rectangles(self.frame, enemy_health_color_black, min_width, min_height,
                                          max_height=max_height)
            if len(boxes) > 0:
                self.draw_boxes('enemy_health_black', boxes, color='blue')
                return True
            else:
                boxes = find_color_rectangles(self.frame, boss_health_color, min_width, min_height * 1.5,
                                              box=self.box_of_screen(1269 / 3840, 58 / 2160, 2533 / 3840, 192 / 2160))
                if len(boxes) > 0:
                    self.draw_boxes('boss_health', boxes, color='blue')
                    return True

    def load_chars(self):
        if not self.in_team():
            return
        self.log_info('load chars')
        char = get_char_by_pos(self, self.get_box_by_name('box_char_1'), 0)
        old_char = safe_get(self.chars, 0)
        if (type(char) is BaseChar and old_char is None) or type(char) is not BaseChar:
            self.chars[0] = char
            logger.info(f'update char1 to {char.name}')

        char = get_char_by_pos(self, self.get_box_by_name('box_char_2'), 1)
        old_char = safe_get(self.chars, 1)
        if (type(char) is BaseChar and old_char is None) or type(char) is not BaseChar:
            self.chars[1] = char
            logger.info(f'update char2 to {char.name}')

        char = get_char_by_pos(self, self.get_box_by_name('box_char_3'), 2)
        old_char = safe_get(self.chars, 2)
        if (type(char) is BaseChar and old_char is None) or type(char) is not BaseChar:
            self.chars[2] = char
            logger.info(f'update char3 to {char.name}')

        self.log_info(f'load chars success {self.chars}')

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

white_color = {
    'r': (253, 255),  # Red range
    'g': (253, 255),  # Green range
    'b': (253, 255)  # Blue range
}
