import time
import re
import cv2
import numpy as np
import win32api, win32gui, win32con

from qfluentwidgets import FluentIcon
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from ok import color_range_to_bound
from ok import Logger, TaskDisabledException, PostMessageInteraction
from ok import find_boxes_by_name
from src.task.BaseCombatTask import BaseCombatTask
from src.task.BaseWWTask import binarize_for_matching
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)

nest_list = {
    '千没沉岛': {'index_cn': "梦魇·振铎", 'index_tw': "夢魘·振鐸", 'index_us': "Nightmare: Tambourinist",
                 'direction': 'w', 'running_time': 1.5, 'set_night': False},
    '受蚀地': {'index_cn': "梦魇·紫羽", 'index_tw': "夢魘·紫羽鷺", 'index_us': "Nightmare: Violet-F", 'direction': 'w',
               'running_time': 2.5, 'set_night': True},
    '潮痕岩摊': {'index_cn': "梦魇·青羽", 'index_tw': "夢魘·青羽鷺", 'index_us': "Nightmare: Cyan-F", 'direction': 'w',
                 'running_time': 2.5, 'set_night': True}
}


class NightmareNestTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.target_enemy_time_out = 10
        self.name = "Nightmare Nest Task"
        self.description = "Auto Farm all Nightmare Nest"
        self.icon = FluentIcon.CALORIES
        self.last_is_click = False

    def run(self):
        WWOneTimeTask.run(self)
        test_picking_echo = False
        if test_picking_echo:
            chance = True
            circle = 0
            while True:
                dropped, has_more = self.yolo_find_echo(turn=True, use_color=False, time_out=12, threshold=0.25)
                self.sleep(0.5)
                circle += 1
                if not dropped and not has_more:
                    if chance:
                        self.log_info('find echo failed, have another chance')
                        chance = False
                    else:
                        self.log_info('find echo failed, tele to the next')
                        break
                else:
                    chance = True
                if circle >= 30:
                    break
        for _, value in nest_list.items():
            if self.game_lang == 'zh_CN':
                echo_name = value.get('index_cn')
            elif self.game_lang == 'zh_TW':
                echo_name = value.get('index_tw')
            else:
                echo_name = value.get('index_us')

            self.ensure_main(time_out=180)
            gray_book_boss = self.openF2Book("gray_book_all_monsters")
            self.click_box(gray_book_boss)
            self.wait_hint(0.05, 0.04, 0.12, 0.08, r'敌迹探寻')
            self.click(0.13, 0.14, after_sleep=0.5)
            self.input_text(echo_name)
            self.click(0.39, 0.13, after_sleep=0.5)
            self.click(0.13, 0.24, after_sleep=0.5)
            self.click(0.89, 0.92, after_sleep=1)
            self.wait_hint(0.79, 0.91, 0.87, 0.95, r'快速旅行')
            if self.find_next_hint(0.90, 0.31, 0.94, 0.41, r'36'):
                self.log_info(f'{echo_name} is complete')
                continue
            self.sleep(1)
            self.log_info('click travel')
            self.click(0.89, 0.92)
            self.wait_in_team_and_world(raise_if_not_found=False, time_out=120)
            self.sleep(1)
            if value.get('set_night'):
                self.change_time_to_night()
                self.sleep(1)
            self.run_until(lambda: False, value.get('direction'), value.get('running_time'), running=True)
            self.wait_until(self.in_combat, post_action=self.middle_click, time_out=10)
            if self.in_combat():
                self.log_info('wait combat')
                self.combat_once(wait_combat_time=0, raise_if_not_found=False)
            else:
                self.log_info(f'combat with {echo_name} error')
                continue
            self.log_info('find echo')
            self.pick_echo()
            circle = 0
            while True:
                self.ensure_main(time_out=180)
                gray_book_boss = self.openF2Book("gray_book_all_monsters")
                self.click_box(gray_book_boss)
                self.wait_hint(0.05, 0.04, 0.12, 0.08, r'敌迹探寻')
                self.click(0.13, 0.14, after_sleep=0.5)
                self.input_text(echo_name)
                self.click(0.39, 0.13, after_sleep=0.5)
                self.click(0.13, 0.24, after_sleep=0.5)
                self.click(0.89, 0.92)
                self.wait_hint(0.79, 0.91, 0.87, 0.95, r'快速旅行')
                self.click(0.89, 0.92)
                self.wait_in_team_and_world(time_out=30, raise_if_not_found=False)
                self.sleep(1)
                self.run_until(lambda: False, value.get('direction'), value.get('running_time'), running=True)
                if not self.try_pick_echo():
                    break
                circle += 1
                if circle > 3:
                    break
        self.ensure_main(time_out=180)
        self.log_info(f'NightmareNestTask complete')

    def on_combat_check(self):
        self.incr_drop(self.pick_f())
        return True

    def find_echo_list(self):
        if self.game_lang == 'zh_CN':
            return self.echo_list_cn
        elif self.game_lang == 'zh_TW':
            return self.echo_list_tw
        return self.echo_list_us

    def find_next_hint(self, x1, y1, x2, y2, s, box_name='hint_text'):
        texts = self.ocr(box=self.box_of_screen(x1, y1, x2, y2, hcenter=True),
                         target_height=540, name=box_name)
        fps_text = find_boxes_by_name(texts,
                                      re.compile(s, re.IGNORECASE))
        if fps_text:
            return True
        return False

    def wait_hint(self, x1, y1, x2, y2, hint, timeout=2):
        if self.wait_until(lambda: self.find_next_hint(x1, y1, x2, y2, hint), time_out=timeout):
            self.sleep(0.2)
            return True
        return False

    def try_pick_echo(self):
        success = False
        circle = 0
        chance = True
        while True:
            dropped, has_more = self.yolo_find_echo(turn=True, use_color=False, time_out=12, threshold=0.25)
            self.incr_drop(dropped)
            self.sleep(0.5)
            circle += 1
            if dropped:
                success = True
            if not dropped and not has_more:
                if chance:
                    chance = False
                else:
                    break
            else:
                chance = True
            if circle > 15:
                break
        return success
