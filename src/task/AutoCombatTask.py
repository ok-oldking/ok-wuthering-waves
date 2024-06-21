import time

from ok.color.Color import find_color_rectangles
from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.TriggerTask import TriggerTask
from ok.util.list import safe_get
from src.char import BaseChar
from src.char.BaseChar import Priority, role_values
from src.char.CharFactory import get_char_by_pos

logger = get_logger(__name__)


class NotInCombatException(Exception):
    pass


class AutoCombatTask(TriggerTask, FindFeature, OCR):

    def __init__(self):
        super().__init__()
        self.chars = [None, None, None]
        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']
        self.default_config.update({
            'Echo Key': 'q',
            'Liberation Key': 'r',
            'Resonance Key': 'e',
            'Character 1 Role': 'Default',
            'Character 2 Role': 'Default',
            'Character 3 Role': 'Default',
        })
        self.config_type["Character 1 Role"] = {'type': "drop_down", 'options': role_values}
        self.config_type["Character 2 Role"] = {'type': "drop_down", 'options': role_values}
        self.config_type["Character 3 Role"] = {'type': "drop_down", 'options': role_values}
        self.last_check_combat = time.time()
        self._in_combat = False
        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']

    def run(self):
        while self.in_combat():
            try:
                logger.debug(f'autocombat loop {self.chars}')
                self.get_current_char().perform()
            except NotInCombatException:
                logger.info('out of combat break')

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
        current_char.is_current_char = False
        self.send_key(switch_to.index + 1)
        while True:
            self.sleep(0.01)
            _, current_index = self.in_team()
            if current_index != switch_to.index:
                self.send_key(switch_to.index + 1)
                logger.info(f'switch not detected, try click again {current_index} {switch_to}')
            else:
                switch_time = time.time()
                switch_to.is_current_char = True
                break

        if post_action:
            post_action()
        return switch_time

    def get_current_char(self):
        for char in self.chars:
            if char.is_current_char:
                return char
        self.log_error('can find current char!!')
        return None

    def in_combat(self):
        current_time = time.time()
        if self._in_combat:
            if current_time - self.last_check_combat > 4:  # delay out of combat check
                self.handler.post(self.check_in_combat, remove_existing=True, skip_if_running=True)
        else:
            if current_time - self.last_check_combat > 2:
                return self.check_in_combat()
        return self._in_combat

    def check_in_combat(self):
        self.last_check_combat = time.time()
        if self._in_combat:
            if self.come_out_of_combat():
                time.sleep(4)
                if self.come_out_of_combat():
                    self._in_combat = False
        else:
            self._in_combat = self.in_team()[0] and self.check_health_bar()

    def come_out_of_combat(self):
        return not self.find_one('gray_combat_count_down') and (
                not self.in_team()[0] or not self.check_health_bar())

    def check_health_bar(self):
        if self._in_combat:
            min_height = self.height_of_screen(10 / 2160)
            max_height = min_height * 3
            min_width = self.width_of_screen(20 / 3840)
        else:
            min_height = self.height_of_screen(12 / 2160)
            max_height = min_height * 3
            min_width = self.width_of_screen(100 / 3840)

        boxes = find_color_rectangles(self.frame, enemy_health_color_red, min_width, min_height, max_height=max_height)

        if len(boxes) > 0:
            self.draw_boxes('enemy_health_bar_red', boxes, color='blue')
            return True
        else:
            boxes = find_color_rectangles(self.frame, boss_health_color, min_width, min_height * 1.4,
                                          box=self.box_of_screen(1269 / 3840, 58 / 2160, 2533 / 3840, 192 / 2160))
            if len(boxes) > 0:
                self.draw_boxes('boss_health', boxes, color='blue')
                return True

    def sleep(self, timeout):
        if not self._in_combat:
            raise NotInCombatException('not in combat')
        super().sleep(timeout)

    def load_chars(self):
        in_team, current_index = self.in_team()
        if not in_team:
            return
        self.log_info('load chars')
        char = get_char_by_pos(self, self.get_box_by_name('box_char_1'), 0)
        old_char = safe_get(self.chars, 0)
        if (type(char) is BaseChar and old_char is None) or type(char) is not BaseChar:
            self.chars[0] = char
            logger.info(f'update char1 to {char.name} {type(char)} {type(char) is not BaseChar}')

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

        for char in self.chars:
            if char.index == current_index:
                char.is_current_char = True
            else:
                char.is_current_char = False

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
        arr = [c1, c2, c3]
        current = -1
        exist_count = 0
        for i in range(len(arr)):
            if arr[i] is None:
                current = i
            else:
                exist_count += 1
        if exist_count == 2:
            return True, current
        else:
            return False, -1


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
