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

    def raise_not_in_combat(self, message):
        logger.error(message)
        self.reset_to_false()
        raise NotInCombatException(message)

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
            self.click()
            logger.warning(f"can't find next char to switch to, maybe switching too fast click and wait")
            return self.switch_next_char(current_char, post_action)
        switch_to.has_intro = has_intro
        current_char.is_current_char = False
        logger.info(f'switch {current_char} -> {switch_to}')
        last_click = 0
        start = time.time()
        while True:
            now = time.time()
            if now - last_click > 0.1:
                self.send_key(switch_to.index + 1)
                last_click = now
            in_team, current_index, size = self.in_team()
            if not in_team:
                if self.debug:
                    self.screenshot(f'not in team while switching chars_{current_char}_to_{switch_to}')
                self.raise_not_in_combat('not in team while switching chars')
            if current_index != switch_to.index:
                if now - start > 3:
                    if self.debug:
                        self.screenshot(f'switch_not_detected_{current_char}_to_{switch_to}')
                    self.raise_not_in_combat('failed switch chars')
                else:
                    self.next_frame()
            else:
                switch_time = time.time()
                switch_to.is_current_char = True
                break

        if post_action:
            post_action()
        logger.info(f'switch_next_char end {(switch_time - start):.3f}s')
        return switch_time

    def wait_in_team(self, time_out=10):
        self.wait_until(lambda: self.in_team()[0], time_out=time_out)

    def get_current_char(self):
        for char in self.chars:
            if char.is_current_char:
                return char
        if not self.in_team()[0]:
            self.raise_not_in_combat('can find current char!!')
        self.load_chars()
        return self.get_current_char()

    def sleep_check_combat(self, timeout):
        start = time.time()
        if not self.in_combat():
            self.raise_not_in_combat('sleep check not in combat')
        super().sleep(timeout - (time.time() - start))

    def check_combat(self):
        if not self.in_combat():
            self.raise_not_in_combat('combat check not in combat')

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
        in_team, current_index, count = self.in_team()
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
        if count == 3:
            char = get_char_by_pos(self, self.get_box_by_name('box_char_3'), 2)
            old_char = safe_get(self.chars, 2)
            if (type(char) is BaseChar and old_char is None) or type(char) is not BaseChar:
                if len(self.chars) == 3:
                    self.chars[2] = char
                else:
                    self.chars.append(char)
                logger.info(f'update char3 to {char.name}')
        else:
            if len(self.chars) == 3:
                self.chars.pop(0)
            logger.info(f'team size changed to 2')

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
        start = time.time()
        c1 = self.find_one('char_1_text', use_gray_scale=True)
        c2 = self.find_one('char_2_text', use_gray_scale=True)
        c3 = self.find_one('char_3_text', use_gray_scale=True)
        arr = [c1, c2, c3]
        logger.debug(f'in_team check {arr} time: {(time.time() - start):.3f}s')
        current = -1
        exist_count = 0
        for i in range(len(arr)):
            if arr[i] is None:
                if current == -1:
                    current = i
            else:
                exist_count += 1
        if exist_count == 2 or exist_count == 1:
            return True, current, exist_count + 1
        else:
            return False, -1, exist_count + 1


white_color = {
    'r': (253, 255),  # Red range
    'g': (253, 255),  # Green range
    'b': (253, 255)  # Blue range
}
