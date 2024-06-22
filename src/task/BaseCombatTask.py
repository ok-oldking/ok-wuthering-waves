import time

from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.BaseTask import BaseTask
from ok.task.TaskExecutor import CannotFindException
from ok.util.list import safe_get
from src.char import BaseChar
from src.char.BaseChar import Priority, role_values
from src.char.CharFactory import get_char_by_pos
from src.combat.CombatCheck import CombatCheck

logger = get_logger(__name__)


class NotInCombatException(Exception):
    pass


class BaseCombatTask(BaseTask, FindFeature, OCR, CombatCheck):

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

        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']

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
            self.click()
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

    def wait_in_team(self, time_out=10):
        self.wait_until(lambda: self.in_team()[0], time_out=time_out)

    def get_current_char(self):
        for char in self.chars:
            if char.is_current_char:
                return char
        self.log_error('can find current char!!')
        return None

    def sleep_check_combat(self, timeout):
        if not self.in_combat():
            raise NotInCombatException('not in combat')
        super().sleep(timeout)

    def check_combat(self):
        if not self.in_combat():
            raise NotInCombatException('not in combat')

    def walk_until_f(self, time_out=0, raise_if_not_found=True):
        if not self.find_one('pick_up_f', horizontal_variance=0.02, vertical_variance=0.02, use_gray_scale=True):
            self.send_key_down('w')
            f_found = self.wait_feature('pick_up_f', horizontal_variance=0.02, vertical_variance=0.02,
                                        use_gray_scale=True,
                                        wait_until_before_delay=0, time_out=time_out, raise_if_not_found=False)
            self.send_key_up('w')
            if not f_found:
                if raise_if_not_found:
                    raise CannotFindException('cant find the f to enter')
                else:
                    logger.warning(f"can't find the f to enter")
                    return
        self.send_key('f')
        self.sleep(0.5)
        return True

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


white_color = {
    'r': (253, 255),  # Red range
    'g': (253, 255),  # Green range
    'b': (253, 255)  # Blue range
}
