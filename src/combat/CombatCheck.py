import re
import time

import win32api

from ok import find_boxes_by_name, Logger, calculate_color_percentage
from ok import find_color_rectangles, get_mask_in_color_range, is_pure_black
from src import text_white_color
from src.char.Roccia import Roccia
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)


class CombatCheck(BaseWWTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._in_combat = False
        self.skip_combat_check = False
        self.boss_lv_template = None
        self.boss_lv_mask = None
        self._in_liberation = False  # return True
        self.has_count_down = False
        self.sleep_check_interval = 0.1
        self.last_out_of_combat_time = 0
        self.boss_lv_box = None
        self.boss_health_box = None
        self.boss_health = None
        self.out_of_combat_reason = ""
        self.last_in_realm_not_combat = 0
        self._last_liberation = 0
        self.target_enemy_time_out = 3
        self.switch_char_time_out = 5
        self.combat_end_condition = None
        self.has_lavitator = False
        self.target_enemy_error_notified = False
        self.cds = {
        }
        self.cd_refreshed = False
        self.esc_count = 0
        self.can_break = False

    @property
    def in_liberation(self):
        return self._in_liberation

    @in_liberation.setter
    def in_liberation(self, value):
        self._in_liberation = value
        if value:
            self._last_liberation = time.time()

    def on_combat_check(self):
        return True

    def reset_to_false(self, recheck=False, reason=""):
        if self.should_check_monthly_card() and self.handle_monthly_card():
            return True
        if is_pure_black(self.frame):
            logger.error('getting a pure black frame for unknown reason, reset_to_false return true')
            return True
        if recheck:
            logger.info('out of combat start double check')
            self._in_combat = False
            if self.wait_until(self.check_health_bar, time_out=1.2):
                self._in_combat = True
                return True
        self.out_of_combat_reason = reason
        self.do_reset_to_false()
        return False

    def do_reset_to_false(self):
        self.cds = {}
        self.cd_refreshed = False
        self._in_combat = False
        self.boss_lv_mask = None
        self.esc_count = 0
        self.boss_lv_template = None
        self.in_liberation = False  # return True
        self.has_count_down = False
        self.last_out_of_combat_time = 0
        self.boss_lv_box = None
        self.boss_health = None
        self.boss_health_box = None
        self.last_in_realm_not_combat = 0
        self.has_lavitator = False
        self.can_break = False
        return False

    def check_f_break(self):
        if not self.can_break and self.find_one('f_break', box=self.box_of_screen(0.2, 0.2, 0.75, 0.8)):
            if not self.is_pick_f():
                self.can_break = True
                return True

    def f_break(self):
        if self.can_break or self.check_f_break():
            self.send_key('f', after_sleep=0.1)
            self.can_break = False

    def recent_liberation(self):
        return time.time() - self._last_liberation < 0.15

    def check_count_down(self):
        count_down_area = self.box_of_screen_scaled(3840, 2160, 1820, 266, 2100,
                                                    340, name="check_count_down", hcenter=True)
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

    @property
    def target_area_box(self):
        return self.box_of_screen(0.1, 0.10, 0.9, 0.9, hcenter=True, name="target_area_box")

    def is_boss(self):
        return self.find_one('boss_break_shield') or self.find_one('boss_break_lock')

    def do_check_in_combat(self, target):
        if self.in_liberation or self.recent_liberation():
            return True
        if self._in_combat:
            self.check_f_break()
            if current_char := self.get_current_char():
                if current_char.skip_combat_check():
                    return True
            if not self.on_combat_check():
                self.log_info('on_combat_check failed')
                return self.reset_to_false(recheck=False, reason='on_combat_check failed')
            if self.has_target():
                self.last_in_realm_not_combat = 0
                return True
            if self.combat_end_condition is not None and self.combat_end_condition():
                return self.reset_to_false(recheck=True, reason='end condition reached')
            if self.target_enemy(wait=True):
                logger.debug(f'retarget enemy succeeded')
                return True
            logger.error('target_enemy failed, try recheck break out of combat')
            return self.reset_to_false(recheck=True, reason='target enemy failed')
        else:
            from src.task.AutoCombatTask import AutoCombatTask
            has_target = self.has_target()
            if not has_target and target:
                self.log_debug('try target')
                self.middle_click(after_sleep=0.1)
            in_combat = has_target or ((self.config.get('Auto Target') or not isinstance(self,
                                                                                         AutoCombatTask)) and self.check_health_bar())
            if in_combat:
                if not has_target and not self.target_enemy(wait=True):
                    if not self.target_enemy_error_notified:
                        self.target_enemy_error_notified = True
                        self.log_error('Target enemy failed, please disable Nvidia/AMD Filter or Sharpening!',
                                       notify=True)
                    return False
                self.has_lavitator = False
                self._in_combat = self.load_chars()
                return self._in_combat

    def in_combat(self, target=False):
        self.in_sleep_check = True
        try:
            return self.do_check_in_combat(target)
        except Exception as e:
            logger.error(f'do_check_in_combat: {e}')
        finally:
            self.in_sleep_check = False

    def ensure_levitator(self):  # 目前未使用
        if not self.config.get('Check Levitator', True):
            return True
        if levi := self.find_one('edge_levitator', threshold=0.6):
            self.log_debug('edge levitator found {}'.format(levi))
            return True
        if self.has_char(Roccia):
            if self.find_one('levitator_roccia', threshold=0.6):
                return True
        if self.is_open_world_auto_combat():
            return False
        start = time.time()
        self.sleep(0.2)
        if levi := self.find_one('edge_levitator', threshold=0.6):
            self.log_debug('recheck edge levitator found {}'.format(levi))
            return True
        while time.time() - start < 1 and self.in_team()[0]:
            self.send_key_down(self.key_config.get('Wheel Key'))
            self.sleep(0.4)
        if self.in_team()[0]:
            self.log_info('can not open wheel')
            self.send_key_up(self.key_config.get('Wheel Key'))
            self.sleep(0.1)
            return False
        levitator = self.wait_feature('wheel_levitator', threshold=0.65, box=self.box_of_screen(0.27, 0.16, 0.68, 0.76))
        self.sleep(0.1)
        if not levitator:
            self.send_key_up(self.key_config.get('Wheel Key'))
            raise Exception('no levitator tool in the tab wheel!')
        old = win32api.GetCursorPos()
        self.move(levitator.x, levitator.y)
        abs_pos = self.executor.interaction.capture.get_abs_cords(levitator.x, levitator.y)
        win32api.SetCursorPos(abs_pos)
        self.sleep(0.1)
        self.send_key_up(self.key_config.get('Wheel Key'))
        self.sleep(0.2)
        win32api.SetCursorPos(old)
        if not self.wait_feature('edge_levitator', threshold=0.6, time_out=1):
            if self.has_char(Roccia):
                if self.find_one('levitator_roccia', threshold=0.6):
                    return True
        self.log_debug(f'ensuring leviator succees {levitator}')
        return self.target_enemy()

    def log_time(self, start, name):
        logger.debug(f'check cost {name} {time.time() - start}')
        return True

    def ocr_lv_text(self):
        lvs = self.ocr(box=self.target_area_box,
                       match=re.compile(r'lv\.\d{1,3}', re.IGNORECASE),
                       target_height=540, name='lv_text')
        return lvs

    def get_target_names(self):
        has_name = 'has_target'
        no_name = 'no_target'
        if self.is_browser():
            has_name += '_cloud'
            no_name += '_cloud'
        elif self.width == 1600:
            has_name += '_169'
            no_name += '_169'
        return has_name, no_name

    def has_target(self, double_check=False):
        threshold = 0.6
        has_name, no_name = self.get_target_names()
        scale = 1.2 if self.is_browser() else 1.1
        best = self.find_best_match_in_box(self.get_box_by_name(has_name).scale(scale), [has_name, no_name],
                                           threshold=threshold)
        if not best:
            best = self.find_best_match_in_box(self.get_box_by_name('box_target_enemy_long'),
                                               [has_name, no_name],
                                               threshold=threshold)
        if not best:
            best = self.find_best_match_in_box(self.get_box_by_name('target_box_long2'), [has_name, no_name],
                                               threshold=threshold)

        if not best:
            best = self.find_best_match_in_box(self.get_box_by_name(has_name).scale(1.1, 2.0),
                                               [has_name, no_name],
                                               threshold=threshold)
            if best and self.esc_count == 0:
                if double_check:
                    logger.error(f'try fix bear echo')
                    self.send_key('esc', after_sleep=2)
                    self.send_key('esc', after_sleep=1.5)
                    self.esc_count = 1
                    return False
                else:
                    self.sleep(1)
                    return self.has_target(double_check=True)
        return best and best.name == has_name

    def target_enemy(self, wait=True):
        if not wait:
            self.middle_click()
        else:
            if self.has_target():
                return True
            else:
                logger.info(f'target lost try retarget')
                start = time.time()
                time_out = 1 if self.is_pick_f() else self.target_enemy_time_out
                while time.time() - start < time_out:
                    if self.has_target():
                        return True
                    self.middle_click(interval=0.1)
                    self.sleep(0.01)

    def has_health_bar(self):
        if self._in_combat:
            min_height = self.height_of_screen(9 / 2160)
            max_height = min_height * 3
            min_width = self.width_of_screen(12 / 3840)
        else:
            min_height = self.height_of_screen(9 / 2160)
            max_height = min_height * 3
            min_width = self.width_of_screen(100 / 3840)

        boxes = find_color_rectangles(self.frame, enemy_health_color_red, min_width, min_height, max_height=max_height)

        if len(boxes) > 0:
            self.draw_boxes('enemy_health_bar_red', boxes, color='blue')
            return True
        else:
            boxes = find_color_rectangles(self.frame, boss_health_color, min_width, min_height * 1.3,
                                          box=self.box_of_screen(1269 / 3840, 58 / 2160, 2533 / 3840, 200 / 2160))
            if len(boxes) == 1:
                self.boss_health_box = boxes[0]
                self.boss_health_box.width = 10
                self.boss_health_box.x += 6
                self.boss_health = self.boss_health_box.crop_frame(self.frame)
                self.draw_boxes('boss_health', boxes, color='blue')
                return True
        return False

    def check_health_bar(self):
        return self.has_health_bar() or self.is_boss()

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


def keep_only_white(frame):
    frame[frame != 255] = 0
    return frame


target_enemy_color_yellow = {
    'r': (0x84, 0xAD),  # Red range
    'g': (0x84, 0xAF),  # Green range
    'b': (0x20, 0x6F)  # Blue range
}  # 207,75,60

enemy_health_color_red = {
    'r': (174, 225),  # Red range
    'g': (55, 85),  # Green range
    'b': (55, 76)  # Blue range
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

aim_color = {
    'r': (150, 213),  # Red range
    'g': (148, 185),  # Green range
    'b': (22, 62)  # Blue range
}
