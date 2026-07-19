import re
import cv2
from dataclasses import dataclass

from qfluentwidgets import FluentIcon
from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask, CharRevivedException
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)
TRAVEL_FEATURES = ['fast_travel_custom', 'gray_teleport', 'remove_custom']
CONFIRM_FEATURES = ['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter']


@dataclass
class NestTarget:
    box: object
    cache_key: str


class NightmareNestTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.target_enemy_time_out = 10
        self.name = "Nightmare Nest Task"
        self.description = "Auto Farm all Nightmare Nest"
        self.support_schedule_task = True
        self.group_name = "Daily"
        self.group_icon = FluentIcon.HOME
        self.icon = FluentIcon.CALORIES
        self.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")
        self.queues = []
        self._capture_success = False
        self._capture_mode = False
        self._unreachable_nests = set()
        self.default_config.update({'Which to Farm': ['Nightmare Purification', 'Tacet Discord Nest']})
        self.config_type['Which to Farm'] = {'type': "multi_selection",
                                             'options': ['Nightmare Purification', 'Tacet Discord Nest']}

    def run(self):
        self._capture_mode = False
        self._capture_success = False
        self._unreachable_nests.clear()
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=30)
        self._init_queue()
        self.log_info('opened gray_book_boss')
        while nest := self.get_nest_to_go():
            self.combat_nest(nest)
        self.ensure_main(time_out=30)

    def run_capture_mode(self):
        self._capture_mode = True
        self._capture_success = False
        self._unreachable_nests.clear()
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=30)
        self._init_queue()
        self.log_info('opened gray_book_boss')
        while nest := self.get_nest_to_go():
            self.combat_nest(nest)
            if self._capture_success:
                break
        self.ensure_main(time_out=30)

    def on_combat_check(self):
        if self._capture_mode:
            self.pick_f(handle_claim=False)
            if self.has_echo_notification():
                return self.reset_to_false(reason='echo captured')
        return True

    def has_echo_notification(self):
        if self.find_best_match_in_box(self.box_of_screen(0.078, 0.488, 0.094, 0.514),
                                       ['char_1_text', 'char_3_text'], 0.6,
                                       frame_processor=convert_image_to_negative):
            self._capture_success = True
        return self._capture_success

    def combat_nest(self, nest):
        target_box = nest.box if isinstance(nest, NestTarget) else nest
        self.click(target_box, after_sleep=2)
        feature = self.wait_feature(['fast_travel_custom', 'gray_teleport', 'remove_custom', 'team_close'], time_out=10,
                                    settle_time=0.5, raise_if_not_found=True)
        is_team = feature.name == 'team_close'
        if is_team:
            self.click_team_challenge()
            self.wait_in_team_and_world(time_out=120)
        else:
            if not self._travel_to_nest_or_skip(nest):
                return
            self.sleep(1)
            while self.find_f_with_text():
                self.send_key('f', after_sleep=1)
                self.wait_in_team_and_world(time_out=40, raise_if_not_found=False)
            self.sleep(2)
            self.run_until(self.in_combat, 'w', time_out=10, running=False, target=True)
        need_find = False
        try:
            need_find = self.combat_once(wait_combat_time=10, target=True, raise_if_not_found=False)
        except CharRevivedException:
            self.log_info('nightmare nest: death recovered, re-enter from F2 book')
            return
        captured_early = False
        if self._capture_mode:
            if self._capture_success or self.wait_until(self.has_echo_notification, time_out=3):
                self.log_info("Captured echo during combat, skipping search.")
                captured_early = True
        if not captured_early:
            self.sleep(3)
            if need_find and not self.walk_find_echo(time_out=5, backward_time=2.5):
                dropped = self.yolo_find_echo(turn=True, use_color=False, time_out=30)[0]
                logger.info(f'farm echo yolo find {dropped}')
            else:
                dropped = True
                self.log_info(f'farm echo walk find true')
            self._capture_success = dropped
        # 与刷全部一致：退本后再结束 combat_nest，避免还在巢穴内回 Daily/开书
        if is_team:
            self.send_key('esc', after_sleep=1)
            self.click(0.652, 0.628, after_sleep=2)
            self.wait_in_team_and_world(time_out=120)
        self.sleep(1)

    def _travel_to_nest_or_skip(self, nest):
        travel = self.wait_until(self._find_travel_button, raise_if_not_found=False, time_out=1)
        if travel:
            self.click(travel, after_sleep=1)
            if confirm := self._find_first_feature(CONFIRM_FEATURES, threshold=0.6):
                self.click(confirm, after_sleep=1)

        button_still_visible = travel and self.find_one(travel.name, threshold=0.7)
        if travel and not button_still_visible and self.wait_in_team_and_world(
                time_out=30, raise_if_not_found=False):
            return True

        if isinstance(nest, NestTarget):
            self._unreachable_nests.add(nest.cache_key)
            self.log_info(f'nightmare nest unreachable, skip this run: {nest.cache_key}')
        else:
            self.log_info('nightmare nest unreachable, skip this run')
        self.back(after_sleep=1)
        return False

    def _find_travel_button(self):
        return self._find_first_feature(TRAVEL_FEATURES, threshold=0.7)

    def _find_first_feature(self, feature_names, threshold):
        for feature_name in feature_names:
            if feature := self.find_one(feature_name, threshold=threshold):
                return feature

    def get_nest_to_go(self):
        self.openF2Book("gray_book_boss")

        while self.queues:
            self.queues[0]()
            if nest := self.find_nest():
                return nest
            self.queues.pop(0)

    def _init_queue(self):
        quests = self.config.get('Which to Farm') or ['Nightmare Purification', 'Tacet Discord Nest']
        actions = []
        if 'Tacet Discord Nest' in quests:
            actions.append(self.go_nest)
        if 'Nightmare Purification' in quests:
            actions.append(self.go_nightmare)
            actions.append(self.go_nightmare_scroll)
        self.queues = actions

    def go_nightmare(self):
        self.open_boss_book('mengyan')
        self.log_info('go nightmare')

    def go_nightmare_scroll(self):
        self.open_boss_book('mengyan')
        self.click(3737 / 3840, 0.54, after_sleep=1)
        self.log_info('go nightmare scroll')

    def go_nest(self):
        self.open_boss_book('canxiang')

    def find_nest(self):
        counts = self.ocr(0.36, 0.13, 0.98, 0.91, match=self.count_re)
        for count_box in counts:
            for match in re.finditer(self.count_re, count_box.name):
                numerator = match.group(1)
                denominator = match.group(2)
                if numerator != denominator and denominator in ['24', '36', '48', '41'] and numerator == '0':
                    cache_key = self._make_nest_cache_key(count_box, denominator)
                    if cache_key in self._unreachable_nests:
                        self.log_info(f'skip cached unreachable nightmare nest: {cache_key}')
                        continue
                    self.log_info(f'{count_box} is not complete')
                    count_box.x = self.width_of_screen(0.9)
                    count_box.y -= count_box.height * 0.9
                    count_box.height = 1
                    count_box.width = 1
                    return NestTarget(count_box, cache_key)

    def _make_nest_cache_key(self, count_box, denominator):
        action_name = self.queues[0].__name__ if self.queues else 'unknown'
        screen_height = max(self.height_of_screen(1), 1)
        row_y = (count_box.y + count_box.height / 2) / screen_height
        row_slot = round(row_y / 0.02)
        # 使用粗粒度行槽位，避免 OCR 坐标轻微抖动导致同一目标被重复点击。
        return f'{action_name}:{denominator}:{row_slot}'


def convert_image_to_negative(img):
    to_gray = False
    _mat = img
    if len(_mat.shape) == 3:
        to_gray = True
        _mat = cv2.cvtColor(_mat, cv2.COLOR_BGR2GRAY)
    _, _mat = cv2.threshold(_mat, 80, 255, cv2.THRESH_BINARY)
    _mat = cv2.bitwise_not(_mat)
    if to_gray:
        _mat = cv2.cvtColor(_mat, cv2.COLOR_GRAY2BGR)
    return _mat


from ok import run_task
from config import config

if __name__ == "__main__":
    run_task(config, task=NightmareNestTask, debug=True)
