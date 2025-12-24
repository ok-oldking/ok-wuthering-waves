import re
from qfluentwidgets import FluentIcon
from ok import Logger
from ok import find_boxes_by_name
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)

nest_list = {
    '千没沉岛': {'index_cn': "梦魇·振铎", 'index_tw': "夢魘·振鐸", 'index_us': "Nightmare: Tambourinist",
                 'direction': 'w', 'running_time': 1.5},
    '受蚀地': {'index_cn': "梦魇·紫羽", 'index_tw': "夢魘·紫羽鷺", 'index_us': "Nightmare: Violet-F", 'direction': 'w',
               'running_time': 2.5},
    '潮痕岩摊': {'index_cn': "梦魇·青羽", 'index_tw': "夢魘·青羽鷺", 'index_us': "Nightmare: Cyan-F", 'direction': 'w',
                 'running_time': 2.5},
    '三王峰': {'index_cn': "梦魇·绿熔", 'index_tw': "夢魘·綠熔", 'index_us': "Nightmare: Viridblaze", 'direction': 'w',
               'running_time': 0},
    '穗波市': {'index_cn': "梦魇·呜咔", 'index_tw': "夢魘·侏侏", 'index_us': "Nightmare: Tick Tack", 'direction': 'w',
               'running_time': 2}
}


class NightmareNestTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.target_enemy_time_out = 10
        self.name = "Nightmare Nest Task"
        self.description = "Auto Farm all Nightmare Nest"
        self.group_name = "Dungeon"
        self.group_icon = FluentIcon.HOME
        self.icon = FluentIcon.CALORIES
        self.last_is_click = False
        self.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")

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
        for _, nest in nest_list.items():
            if self.game_lang == 'zh_CN':
                echo_name = nest.get('index_cn')
            elif self.game_lang == 'zh_TW':
                echo_name = nest.get('index_tw')
            else:
                echo_name = nest.get('index_us')

            if self.travel_to_nest(echo_name):
                continue
            self.log_info('click travel')
            self.click_travel_nest(nest)
            self.wait_until(self.in_combat, post_action=self.middle_click, time_out=10)
            if self.in_combat():
                self.log_info('wait combat')
                self.combat_once(wait_combat_time=0, raise_if_not_found=False)
            else:
                self.log_info(f'combat with {echo_name} error')
                continue
            self.log_info('find echo')
            dropped = self.walk_find_echo(time_out=10)
            if dropped:
                continue
            self.travel_to_nest(echo_name)
            self.click_travel_nest(nest)
            self.walk_find_echo(time_out=10)
        self.ensure_main(time_out=180)
        self.log_info(f'NightmareNestTask complete')

    def click_travel_nest(self, config):
        self.click(0.89, 0.92)
        self.wait_in_team_and_world(time_out=30, raise_if_not_found=False)
        self.sleep(2)
        while self.find_f_with_text():
            self.send_key('f', after_sleep=1)
            self.wait_in_team_and_world(time_out=40, raise_if_not_found=False)
        self.run_until(lambda: False, config.get('direction'), config.get('running_time'), running=True)

    def travel_to_nest(self, echo_name):
        self.ensure_main(time_out=180)
        gray_book_boss = self.openF2Book("gray_book_all_monsters")
        self.click_box(gray_book_boss)
        self.wait_hint(0.05, 0.04, 0.12, 0.08, r'敌迹探寻')
        self.click(0.13, 0.14, after_sleep=0.5)
        self.input_text(echo_name)
        self.sleep(0.2)
        if self.is_browser():
            self.click(0.39, 0.13, after_sleep=0.5)
        self.click(0.39, 0.13, after_sleep=0.5)
        self.click(0.13, 0.24, after_sleep=0.5)
        self.click(0.89, 0.92, after_sleep=3)
        texts = self.ocr()
        count_box = self.find_boxes(texts, match=self.count_re)
        if not count_box:
            self.log_error("can not find nightmare echo")
            self.ensure_main(time_out=180)
            return
        for match in re.finditer(self.count_re, count_box[0].name):
            numerator = match.group(1)
            denominator = match.group(2)
            if numerator == denominator:
                self.log_info(f'{echo_name} {match.group(0)} is complete')
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
