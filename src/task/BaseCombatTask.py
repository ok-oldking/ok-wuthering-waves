import math
import re
import time

import win32api

from ok.config.ConfigOption import ConfigOption
from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
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
    'HotKey Verify': True,
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
        self.combat_start = 0

        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']

    def raise_not_in_combat(self, message, exception_type=None):
        logger.error(message)
        if self.reset_to_false(reason=message):
            logger.error(f'reset to false failed: {message}')
        if exception_type is None:
            exception_type = NotInCombatException
        raise exception_type(message)

    def combat_once(self, wait_combat_time=180, wait_before=1.5):
        self.wait_until(self.in_combat, time_out=wait_combat_time, raise_if_not_found=True)
        self.sleep(wait_before)
        self.do_reset_to_false()
        self.wait_until(self.in_combat, time_out=5, raise_if_not_found=True)

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
                # self.screenshot(f'combat_once_ooc {self.out_of_combat_reason}')
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
                                                  target_text=self.absorb_echo_text())
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
            logger.warning(f"can't find next char to switch to, maybe switching too fast click and wait")
            if time.time() - current_char.last_perform < 0.1:
                current_char.continues_normal_attack(0.1)
                logger.warning(f"can't find next char to switch to, performing too fast add a normal attack")
            return current_char.perform()
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
                confirm = self.wait_feature('revive_confirm_hcenter_vcenter', threshold=0.8, time_out=3)
                if confirm:
                    self.log_info(f'char dead')
                    self.raise_not_in_combat(f'char dead', exception_type=CharDeadException)
                # else:
                #     self.raise_not_in_combat(
                #         f'not in team while switching chars_{current_char}_to_{switch_to}')
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
                current_char.switch_out()
                switch_to.is_current_char = True
                break

        if post_action:
            post_action()
        logger.info(f'switch_next_char end {(current_char.last_switch_time - start):.3f}s')

    def get_current_char(self) -> BaseChar:
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

    def load_hotkey(self, force=False):
        if not self.key_config['HotKey Verify'] and not force:
            return
        resonance_key = self.ocr(0.82, 0.92, 0.85, 0.96, match=re.compile(r'^[a-zA-Z]$'), threshold=0.8,
                                 name='resonance_key', use_grayscale=True)
        echo_key = self.ocr(0.88, 0.92, 0.90, 0.96, match=re.compile(r'^[a-zA-Z]$'), threshold=0.8,
                            name='echo_key')
        liberation_key = self.ocr(0.93, 0.92, 0.96, 0.96, match=re.compile(r'^[a-zA-Z]$'), threshold=0.8,
                                  name='liberation_key')
        keys_str = str(resonance_key) + str(echo_key) + str(liberation_key)

        # if not resonance_key or not echo_key or not liberation_key:
        #     raise Exception(ok.gui.app.tr(
        #         "Can't load game hotkey, please equip echos for all characters and use A-Z as hotkeys for skills, detected key:{}").format(
        #         keys_str))
        if echo_key:
            self.key_config['Echo Key'] = echo_key[0].name.lower()
        if liberation_key:
            self.key_config['Liberation Key'] = liberation_key[0].name.lower()
        if resonance_key:
            self.key_config['Resonance Key'] = resonance_key[0].name.lower()
        self.key_config['HotKey Verify'] = False
        logger.info(f'set hotkey {self.key_config}')
        self.info['Skill HotKeys'] = keys_str

    def load_chars(self):
        self.load_hotkey()
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
                self.chars = self.chars[:2]
            logger.info(f'team size changed to 2')

        for char in self.chars:
            if char is not None:
                char.reset_state()
                if char.index == current_index:
                    char.is_current_char = True
                else:
                    char.is_current_char = False
        self.combat_start = time.time()

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
