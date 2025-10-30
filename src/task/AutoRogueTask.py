import time
import re
import cv2
import numpy as np

from qfluentwidgets import FluentIcon
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from ok import color_range_to_bound
from ok import Logger, TaskDisabledException
from ok import find_boxes_by_name
from src import text_white_color
from src.task.BaseCombatTask import BaseCombatTask
from src.task.BaseWWTask import binarize_for_matching
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class AutoRogueTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.name = "Half-Auto Rougue"
        self.supported_languages = ["zh_CN"]
        self.description = "Enable half-auto combat in weekly rougue, language needs Chinese"
        self.icon = FluentIcon.CALORIES
        self.last_is_click = False
        self._in_realm = False
        self.skip_f = 0
        self.status = -1
        self.stamina = 2
        self.last_purple_icon = None
        self.default_config.update({
            'Stop When Treasure Found': False,
        })
        self.config_description = {
            'Stop When Treasure Found': 'If set to False, treasure will be claimed if stamina is sufficient'
        }
        self.black_list_buff = ["雷暴", "旋风", "矛盾晶体"]
        self.white_list_buff = ["心流", "悲鸣纪", "余音贝", "齿轮之心", "全知之眼", "指南针", "医疗箱", "妄语的残谱",
                                "激越的残谱"]

    def run(self):
        WWOneTimeTask.run(self)
        try:
            return self.do_run()
        except TaskDisabledException as e:
            pass
        except Exception as e:
            logger.error('farm 4c error, try handle monthly card', e)
            raise

    def on_combat_check(self):
        if ult := self.find_one('char_4_text'):
            white_percent = self.calculate_color_percentage(text_white_color, ult)
            self.log_info('on_combat_check found {} {}'.format(ult, white_percent))
            if white_percent > 0.1:
                self.send_key('4')
        return True

    def do_run(self):
        self.log_info('start')
        start = time.time()
        exit_countdown = -1
        while True:
            # 非战斗处理
            in_team = self.in_team()[0]
            if in_team:
                now = time.time()
                if exit_countdown < 0:
                    if not self.in_realm():
                        exit_countdown = now
                else:
                    if now - exit_countdown > 2 and self.in_world():  # 0.8
                        self.log_info('自动肉鸽结束!', notify=True)
                        return
                    if self.in_realm():
                        exit_countdown = -1
            if not in_team:
                exit_countdown = -1
                self.status = -1
                # 交易：直接退出
                if self.check_text(0.02, 0.04, 0.12, 0.09, r'交易', 'trade_text'):
                    self.log_info('skip trade')
                    self.send_key('esc')
                    self.sleep(2)
                    self.skip_f = time.time()
                # 周本主界面/角色选择界面：进入副本
                if self.check_text(0.03, 0.10, 0.24, 0.22, r'千道门扉的异想', 'entrance_title_text'):
                    self.log_info('in entrance title')
                    self.click_relative(0.82, 0.90)
                    self.sleep(2)
                # 是否继续上次探索：点继续
                if self.check_text(0.23, 0.31, 0.30, 0.36, r'退出确认', 'continue_text'):
                    self.log_info('continue the rougue')
                    self.click_relative(0.67, 0.62)
                    self.sleep(2)
                # 领声骸奖励界面：点非中间位置
                if self.check_text(0.46, 0.22, 0.53, 0.28, r'获得', 'gain_echo_text'):
                    self.log_info('gain echos')
                    self.click_relative(0.5, 0.8)
                    self.sleep(2)
                    start = time.time()
                # 选隐喻界面：选中间隐喻
                # todo: 加个隐喻筛选，不然选到开r生命减半可能会翻车
                if self.check_text(0.02, 0.04, 0.12, 0.09, r'隐喻获得', 'buff_text'):
                    self.log_info('choose buff')
                    self.buff_selector()
                    self.click_relative(0.82, 0.95)
                    self.sleep(1)
                    start = time.time()
                # 挑战结束界面：结束循环
                if self.check_text(0.43, 0.26, 0.56, 0.33, r'挑战结束', 'end_text'):
                    self.log_info('Half-Auto Rougue Task Finish', notify=True)
                    break
                self.status = -1
                # 进新的副本时重置time_out计时
            if self.status == -1 and (
                    self.find_next_hint(r'击败怪物') or self.find_next_hint(r'限定时间') or self.find_next_hint(
                r'击破冰茧')):
                self.status = 0
                start = time.time()
            self.middle_click(interval=1, after_sleep=0.2)
            # 战斗处理
            if self.in_combat():
                self.log_info('wait combat')
                self.combat_once(wait_combat_time=0, raise_if_not_found=False)
                start = time.time()
            # 领声骸奖励时体力不够：按Esc
            if self.check_text(0.18, 0.17, 0.28, 0.22, r'补充结晶波片', 'treasure_text'):
                self.stamina -= 1
                self.send_key('esc')
                self.sleep(1)
            # 领声骸：开关开时按序领声骸，否则返回
            if self.check_text(0.23, 0.3, 0.30, 0.35, r'领取奖励', 'treasure_text'):
                self.log_info('collect treasure')
                if self.stamina > 0:
                    self.stamina_enough = False
                    if self.stamina == 2:
                        self.click_relative(0.68, 0.63)
                    else:
                        self.click_relative(0.32, 0.62)
                        self.stamina -= 1
                    self.sleep(1.5)
                else:
                    self.send_key('esc')
                    self.skip_f = time.time()
            # 按F
            if self.find_f_with_text():
                self.log_info('press f')
                self.sleep(0.2)
                self.send_key('f')
                self.sleep(1)
            # 找门，背景白色时会影响左上角提示的文字识别
            if self.find_next_hint(r'前往下一') or self.find_next_hint(r'个记忆区'):
                self.log_info('find the gate')
                self.walk_to_gate()
            if self.config.get('Stop When Treasure Found') and self.find_treasure_icon():
                self.info_set('Treasure Found', True)
                self.log_info('自动肉鸽结束!', notify=True)
                return
            # 走向treasure
            if self.find_treasure_icon() and self.stamina > 0:
                self.log_info('walk to treasure')
                self.walk_to_box(self.find_treasure_icon, time_out=10, end_condition=self.find_f_with_text,
                                 y_offset=0.1, use_hook=True)
                # 走向紫标，多个紫标时优先以离屏幕中心最近的紫标为对象
            elif self.find_purple_icon():
                self.log_info('walk to purple icon')
                self.walk_to_purple_and_restart()
            # 战斗准备time_out为20秒，两个限时战斗10秒，其他场景40秒
            # 等待到按F或者进战斗为止结束接管
            time_out = 40
            if self.find_next_hint(r'击败怪物'):
                time_out = 20
            elif self.find_next_hint(r'限定时间') or self.find_next_hint(r'击破冰茧'):
                time_out = 10
            if time.time() - start > time_out:
                self.log_error('Need mankind help', notify=True)
                start = time.time()
                while True:
                    if time.time() - start > 1:
                        start = time.time()
                        if self.find_f_with_text():
                            break
                        if self.in_combat():
                            break
                    self.next_frame()
            self.next_frame()
        return

    def walk_to_purple_and_restart(self):
        if self.find_next_hint(r'奇异的白猫'):
            if self.walk_to_box(self.find_purple_icon, time_out=10, end_condition=self.find_f_with_text,
                                y_offset=0.1, use_hook=True):
                return True
        elif self.walk_to_box(self.find_purple_icon, time_out=3, end_condition=self.find_f_with_text,
                              y_offset=0.1, x_threshold=0.15, use_hook=True):
            return True

    def walk_to_gate(self):
        self.log_info('find gate')
        i = 0
        while i < 4:
            if self.find_f_with_text():
                return True
            box = self.find_gate()
            if box:
                x = box.center()[0]
                if x < self.width_of_screen(0.35):
                    self.send_key_down('a')
                    self.send_key_down('w')
                    self.sleep(0.2)
                    self.send_key_up('a')
                    self.send_key_up('w')
                    self.sleep(0.3)
                    self.middle_click(interval=1, after_sleep=0.2)
                elif x > self.width_of_screen(0.65):
                    self.send_key_down('d')
                    self.send_key_down('w')
                    self.sleep(0.2)
                    self.send_key_up('d')
                    self.send_key_up('w')
                    self.sleep(0.3)
                    self.middle_click(interval=1, after_sleep=0.2)
                self.sleep(0.5)
                break
            self.send_key('d')
            self.sleep(0.3)
            self.middle_click(interval=1, after_sleep=0.2)
            self.sleep(1)
            i += 1
        timeout = 6
        if i >= 4:
            self.send_key_down('w')
            self.wait_until(self.find_f_with_text, time_out=2)
            self.send_key_up('w')
        else:
            self.find_gate_and_walk()
        return True

    def check_text(self, x1, y1, x2, y2, s, box_name):
        texts = self.ocr(box=self.box_of_screen(x1, y1, x2, y2, hcenter=True),
                         target_height=540, name=box_name)
        fps_text = find_boxes_by_name(texts,
                                      re.compile(s, re.IGNORECASE))
        if fps_text:
            return fps_text

    def find_next_hint(self, hint):
        return self.check_text(0.04, 0.24, 0.17, 0.28, hint, 'hint_text')

    def find_f_with_text(self):
        if time.time() - self.skip_f < 8:
            return False
        return super().find_f_with_text()

    def find_gate_and_walk(self):
        if self.walk_to_box(self.find_gate, time_out=6, end_condition=self.find_f_with_text, y_offset=0.05):
            return True

    def find_gate(self):
        texts = self.ocr(box=self.box_of_screen(0.01, 0.01, 0.99, 0.99, hcenter=True),
                         target_height=540, name='door_text', frame_processor=isolate_gold_text)
        door_text = find_boxes_by_name(texts,
                                       re.compile(r'的记忆', re.IGNORECASE))
        if door_text:
            return door_text[0]
        door_text = find_boxes_by_name(texts,
                                       re.compile(r'梦乡的', re.IGNORECASE))
        if door_text:
            return door_text[0]

    def find_purple_icon(self):
        icons = self.find_feature('purple_target_distance_icon', box=self.box_of_screen(0.18, 0.1, 0.82, 0.81),
                                  threshold=0.65, frame_processor=binarize_for_matching)
        target = None
        if icons:
            target = icons[0]
            if self.last_purple_icon:
                min_distance = target.center_distance(self.last_purple_icon)
                for obj in icons[1:]:
                    current = self.last_purple_icon.center_distance(obj)
                    if current < min_distance:
                        min_distance = current
                        target = obj
            else:
                max_conf = target.confidence
                for obj in icons[1:]:
                    if obj.confidence > max_conf:
                        max_conf = obj.confidence
                        target = obj
        self.last_purple_icon = target
        return target

    def find_buff_select(self):
        texts = self.ocr(box=self.box_of_screen(0.02, 0.04, 0.12, 0.09, hcenter=True), name='boss_lv_text')
        fps_text = find_boxes_by_name(texts,
                                      re.compile(r'隐喻获得', re.IGNORECASE))
        if fps_text:
            return True

    def buff_selector(self):
        texts = self.ocr(box=self.box_of_screen(0.19, 0.55, 0.81, 0.59, hcenter=True), name='buffs_text')
        buffs = find_boxes_by_name(texts, re.compile(r'[\u4e00-\u9fffA-Za-z]+'))
        self.draw_boxes('buff', buffs)
        clicked = False
        for buff in buffs:
            if buff.name in self.white_list_buff:
                self.click_box(buff, after_sleep=1)
                clicked = True
                break
        if not clicked:
            for buff in buffs:
                if buff.name not in self.black_list_buff:
                    self.click_box(buff, after_sleep=1)
                    clicked = True
                    break
        if not clicked:
            self.click_relative(0.5, 0.5, after_sleep=1)

    # def walk_to_box(self, find_function, time_out=30, end_condition=None, y_offset=0.05, x_offset=0.5):
    #     if not find_function:
    #         self.log_info('find_function not found, break')
    #         return False
    #     last_direction = None
    #     start = time.time()
    #     ended = False
    #     last_target = None
    #     centered = False
    #     while time.time() - start < time_out:
    #         self.next_frame()
    #         if end_condition:
    #             ended = end_condition()
    #             if ended:
    #                 break
    #         treasure_icon = find_function()
    #         if isinstance(treasure_icon, list):
    #             if len(treasure_icon) > 0:
    #                 treasure_icon = treasure_icon[0]
    #             else:
    #                 treasure_icon = None
    #         if treasure_icon:
    #             last_target = treasure_icon
    #         if last_target is None:
    #             next_direction = self.opposite_direction(last_direction)
    #             self.log_info('find_function not found, change to opposite direction')
    #         else:
    #             x, y = last_target.center()
    #             y = max(0, y - self.height_of_screen(y_offset))
    #             x_abs = abs(x - self.width_of_screen(x_offset))
    #             threshold = 0.03
    #             centered = centered or x_abs <= self.width_of_screen(threshold)
    #             if not centered:
    #                 if x > self.width_of_screen(x_offset):
    #                     next_direction = 'd'
    #                 else:
    #                     next_direction = 'a'
    #             else:
    #                 if y > self.height_of_screen(0.5):
    #                     next_direction = 's'
    #                 else:
    #                     next_direction = 'w'
    #         if next_direction != last_direction:
    #             if last_direction:
    #                 self.send_key_up(last_direction)
    #                 self.sleep(0.01)
    #             last_direction = next_direction
    #             if next_direction:
    #                 self.send_key_down(next_direction)
    #     if last_direction:
    #         self.send_key_up(last_direction)
    #         self.sleep(0.01)
    #     if not end_condition:
    #         return last_direction is not None
    #     else:
    #         return ended

    def calculate_color_percentage_in_masked(self, target_color, box, mask_r1_ratio=0.0, mask_r2_ratio=0.0):
        cropped = box.crop_frame(self.frame).copy()
        if cropped is None or cropped.size == 0:
            return 0.0
        h, w = cropped.shape[:2]

        center = (w // 2, h // 2)
        r1, r2 = h * mask_r1_ratio, h * mask_r2_ratio
        r1 = Decimal(str(r1)).quantize(Decimal('0'), rounding=ROUND_DOWN)
        r2 = Decimal(str(r2)).quantize(Decimal('0'), rounding=ROUND_UP)

        ring_mask = np.zeros((h, w), dtype=np.uint8)
        if r2 > 0:
            cv2.circle(ring_mask, center, int(r2), 255, -1)
        if r1 > 0:
            cv2.circle(ring_mask, center, int(r1), 0, -1)
        masked_image = cv2.bitwise_and(cropped, cropped, mask=ring_mask)

        if masked_image.ndim == 3:
            non_black_mask = np.all(masked_image != 0, axis=2)
        else:
            return 0.0

        free_space = np.count_nonzero(non_black_mask)
        if free_space == 0:
            return 0.0

        lower_bound, upper_bound = color_range_to_bound(target_color)
        gray = cv2.inRange(masked_image, lower_bound, upper_bound)
        colored_pixels = np.count_nonzero(gray == 255)

        color_percent = colored_pixels / free_space
        return color_percent


def isolate_gold_text(cv_image):
    match_mask = cv2.inRange(cv_image, lower_gold_text, upper_gold_text)
    return cv2.cvtColor(cv2.bitwise_not(match_mask), cv2.COLOR_GRAY2BGR)


lower_gold_text = np.array([100, 170, 185], dtype=np.uint8)  # BGR
upper_gold_text = np.array([125, 195, 210], dtype=np.uint8)  # BGR

ring_purple_color = {
    'r': (135, 165),  # Red range
    'g': (125, 155),  # Green range
    'b': (230, 255)  # Blue range
}  # 151,141,245
