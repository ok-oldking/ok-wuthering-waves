import math
import time

import win32api

from ok.config.ConfigOption import ConfigOption
from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.task.TaskExecutor import CannotFindException
from ok.util.list import safe_get
from src.char import BaseChar
from src.char.BaseChar import Priority
from src.char.CharFactory import get_char_by_pos
from src.combat.CombatCheck import CombatCheck
from src.task.BaseWWTask import BaseWWTask

logger = get_logger(__name__)


class NotInCombatException(Exception):
    pass


class CharDeadException(NotInCombatException):
    pass


key_config_option = ConfigOption('Game Hotkey Config', {
    'Echo Key': 'q',
    'Liberation Key': 'r',
    'Resonance Key': 'e',
}, description='In Game Hotkey for Skills')


class BaseCombatTask(BaseWWTask, FindFeature, OCR, CombatCheck):

    def __init__(self):
        super().__init__()
        CombatCheck.__init__(self)
        self.chars = [None, None, None]
        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']
        self.key_config = self.get_config(key_config_option)

        self.mouse_pos = None

        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']

    def raise_not_in_combat(self, message, exception_type=None):
        logger.error(message)
        self.reset_to_false(reason=message)
        if exception_type is None:
            exception_type = NotInCombatException
        raise exception_type(message)

    def combat_once(self, wait_combat_time=180, wait_before=3):
        self.wait_until(lambda: self.in_combat(), time_out=wait_combat_time, raise_if_not_found=True)
        self.sleep(wait_before)
        self.wait_until(lambda: self.in_combat(), time_out=10, raise_if_not_found=True)
        self.load_chars()
        self.info['Combat Count'] = self.info.get('Combat Count', 0) + 1
        while self.in_combat():
            try:
                logger.debug(f'combat_once loop {self.chars}')
                self.get_current_char().perform()
            except CharDeadException as e:
                raise e
            except NotInCombatException as e:
                logger.info(f'combat_once out of combat break {e}')
                if self.debug:
                    self.screenshot(f'out of combat break {self.out_of_combat_reason}')
                break
        self.wait_in_team_and_world(time_out=10)
        self.sleep(1)
        self.middle_click()
        self.sleep(0.2)

    def run_in_circle_to_find_echo(self, circle_count=3):
        directions = ['w', 'a', 's', 'd']
        step = 1.2
        duration = 0.8
        total_index = 0
        for count in range(circle_count):
            logger.debug(f'running first circle_count{circle_count} circle {total_index} duration:{duration}')
            for direction in directions:
                if total_index > 2 and (total_index + 1) % 2 == 0:
                    duration += step
                picked = self.send_key_and_wait_f(direction, False, time_out=duration, running=True,
                                                  target_text=self.absorb_echo_text)
                if picked:
                    self.mouse_up(key="right")
                    return True
                total_index += 1

    def switch_next_char(self, current_char, post_action=None, free_intro=False, target_low_con=False):
        max_priority = Priority.MIN
        switch_to = None
        has_intro = free_intro
        if not has_intro:
            current_con = current_char.get_current_con()
            if current_con > 0.8 and current_con != 1:
                logger.info(f'switch_next_char current_con {current_con:.2f} almost full, sleep and check again')
                self.sleep(0.05)
                self.next_frame()
                current_con = current_char.get_current_con()
            if current_con == 1:
                has_intro = True

        for i, char in enumerate(self.chars):
            if char == current_char:
                priority = Priority.CURRENT_CHAR
            else:
                priority = char.get_switch_priority(current_char, has_intro)
                if target_low_con:
                    priority += (1 - char.current_con) * 1000 - Priority.SWITCH_CD
                logger.info(
                    f'switch_next_char priority: {char} {priority} {char.current_con} target_low_con {target_low_con}')
            if priority > max_priority:
                max_priority = priority
                switch_to = char
        if switch_to == current_char:
            self.check_combat()
            self.click()
            logger.warning(f"can't find next char to switch to, maybe switching too fast click and wait")
            return self.switch_next_char(current_char, post_action, free_intro, target_low_con)
        switch_to.has_intro = has_intro
        logger.info(f'switch_next_char {current_char} -> {switch_to} has_intro {has_intro}')
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
                    self.screenshot(f'not in team while switching chars_{current_char}_to_{switch_to} {now - start}')
                confirm = self.wait_feature('revive_confirm', threshold=0.8, time_out=3)
                if confirm:
                    self.log_info(f'char dead')
                    self.raise_not_in_combat(f'char dead', exception_type=CharDeadException)
                else:
                    self.raise_not_in_combat(
                        f'not in team while switching chars_{current_char}_to_{switch_to}')
            if now - start > 10:
                self.raise_not_in_combat(
                    f'switch too long failed chars_{current_char}_to_{switch_to}, {now - start}')
            if current_index != switch_to.index:
                has_intro = free_intro if free_intro else current_char.is_con_full()
                switch_to.has_intro = has_intro
                if now - start > 10:
                    if self.debug:
                        self.screenshot(f'switch_not_detected_{current_char}_to_{switch_to}')
                    self.raise_not_in_combat('failed switch chars')
                else:
                    self.next_frame()
            else:
                self.in_liberation = False
                switch_time = time.time()
                current_char.switch_out()
                switch_to.is_current_char = True
                break

        if post_action:
            post_action()
        logger.info(f'switch_next_char end {(switch_time - start):.3f}s')
        return switch_time

    def click(self, x=-1, y=-1, move_back=False, name=None, interval=-1):
        if x == -1 and y == -1:
            x = self.width_of_screen(0.5)
            y = self.height_of_screen(0.5)
        return super().click(x, y, move_back, name, interval)

    def wait_in_team_and_world(self, time_out=10, raise_if_not_found=True):
        return self.wait_until(self.in_team_and_world, time_out=time_out, raise_if_not_found=raise_if_not_found)

    def in_team_and_world(self):
        return self.in_team()[
            0]  # and self.find_one(f'gray_book_button', threshold=0.7, canny_lower=50, canny_higher=150)

    def get_current_char(self):
        for char in self.chars:
            if char.is_current_char:
                return char
        if not self.in_team()[0]:
            self.raise_not_in_combat('can find current char!!')
        self.load_chars()
        return self.get_current_char()

    def sleep_check_combat(self, timeout, check_combat=True):
        start = time.time()
        if not self.in_combat() and check_combat:
            self.raise_not_in_combat('sleep check not in combat')
        self.sleep(timeout - (time.time() - start))

    def check_combat(self):
        if not self.in_combat():
            if self.debug:
                self.screenshot('not_in_combat_calling_check_combat')
            self.raise_not_in_combat('combat check not in combat')

    def send_key_and_wait_f(self, direction, raise_if_not_found, time_out, running=False, target_text=None):
        if time_out <= 0:
            return
        start = time.time()
        if running:
            self.mouse_down(key='right')
        self.send_key_down(direction)
        f_found = self.wait_until(lambda: self.find_f_with_text(target_text=target_text), time_out=time_out,
                                  raise_if_not_found=False)
        if f_found:
            self.send_key('f')
            self.sleep(0.1)
        self.send_key_up(direction)
        if running:
            self.mouse_up(key='right')
        if not f_found:
            if raise_if_not_found:
                raise CannotFindException('cant find the f to enter')
            else:
                logger.warning(f"can't find the f to enter")
                return False
            
        remaining = time.time() - start

        if self.handle_claim_button():
            self.sleep(0.5)
            self.send_key_down(direction)
            if running:
                self.mouse_down(key='right')
            self.sleep(remaining + 0.2)
            if running:
                self.mouse_up(key='right')
            self.send_key_up(direction)
            return False
        return f_found

    def handle_claim_button(self):
        if self.wait_feature('cancel_button', raise_if_not_found=False, horizontal_variance=0.1,
                             vertical_variance=0.1, time_out=1.5, threshold=0.8):
            self.send_key('esc')
            self.sleep(0.05)
            logger.info(f"found a claim reward")
            return True

    def walk_until_f(self, direction='w', time_out=0, raise_if_not_found=True, backward_time=0, target_text=None):
        logger.info(f'walk_until_f direction {direction} target_text: {target_text}')
        if not self.find_f_with_text(target_text=target_text):
            if backward_time > 0:
                if self.send_key_and_wait_f('s', raise_if_not_found, backward_time, target_text=target_text):
                    logger.info('walk backward found f')
                    return True
            return self.send_key_and_wait_f(direction, raise_if_not_found, time_out,
                                            target_text=target_text) and self.sleep(0.5)
        else:
            self.send_key('f')
            if self.handle_claim_button():
                return False
        self.sleep(0.5)
        return True

    def load_chars(self):
        in_team, current_index, count = self.in_team()
        if not in_team:
            return
        self.log_info('load chars')
        char = get_char_by_pos(self, self.get_box_by_name('box_char_1'), 0)
        old_char = safe_get(self.chars, 0)
        if self.should_update(char, old_char):
            self.chars[0] = char
            logger.info(f'update char1 to {char.name} {type(char)} {type(char) is not BaseChar}')

        char = get_char_by_pos(self, self.get_box_by_name('box_char_2'), 1)
        old_char = safe_get(self.chars, 1)
        if self.should_update(char, old_char):
            self.chars[1] = char
            logger.info(f'update char2 to {char.name}')
        if count == 3:
            char = get_char_by_pos(self, self.get_box_by_name('box_char_3'), 2)
            old_char = safe_get(self.chars, 2)
            if self.should_update(char, old_char):
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
            char.reset_state()
            if char.index == current_index:
                char.is_current_char = True
            else:
                char.is_current_char = False

        self.log_info(f'load chars success {self.chars}')

    @staticmethod
    def should_update(char, old_char):
        return (type(char) is BaseChar and old_char is None) or (type(char) is not BaseChar and old_char != char)

    def box_resonance(self):
        return self.get_box_by_name('box_resonance_cd')

    def get_resonance_cd_percentage(self):
        return self.calculate_color_percentage(white_color, self.get_box_by_name('box_resonance_cd'))

    def get_resonance_percentage(self):
        return self.calculate_color_percentage(white_color, self.get_box_by_name('box_resonance'))

    def in_team(self):
        start = time.time()
        c1 = self.find_one('char_1_text',
                           threshold=0.75)
        c2 = self.find_one('char_2_text',
                           threshold=0.75)
        c3 = self.find_one('char_3_text',
                           threshold=0.75)
        arr = [c1, c2, c3]
        # logger.debug(f'in_team check {arr} time: {(time.time() - start):.3f}s')
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

    def mouse_reset(self):
        # logger.debug("mouse_reset")
        try:
            current_position = win32api.GetCursorPos()
            if self.mouse_pos:
                distance = math.sqrt(
                    (current_position[0] - self.mouse_pos[0]) ** 2
                    + (current_position[1] - self.mouse_pos[1]) ** 2
                )
                if distance > 400:
                    logger.debug(f'move mouse back {self.mouse_pos}')
                    win32api.SetCursorPos(self.mouse_pos)
                    self.mouse_pos = None
                    if self.enabled:
                        self.handler.post(self.mouse_reset, 1)
                    return
            self.mouse_pos = current_position
            if self.enabled:
                return self.handler.post(self.mouse_reset, 0.005)
        except Exception as e:
            logger.error('mouse_reset exception', e)


white_color = {
    'r': (253, 255),  # Red range
    'g': (253, 255),  # Green range
    'b': (253, 255)  # Blue range
}
