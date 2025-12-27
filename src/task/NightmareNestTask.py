import re
from qfluentwidgets import FluentIcon
from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


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
        self.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")
        self.step = 0

    def run(self):
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=30)
        self.step = 0
        while nest := self.get_nest_to_go():
            self.combat_nest(nest)

    def combat_nest(self, nest):
        self.click(nest, after_sleep=2)
        self.click(0.89, 0.92, after_sleep=2)
        self.wait_in_team_and_world(time_out=30, raise_if_not_found=False)
        self.sleep(1)
        while self.find_f_with_text():
            self.send_key('f', after_sleep=1)
            self.wait_in_team_and_world(time_out=40, raise_if_not_found=False)
        self.run_until(self.in_combat, 'w', time_out=10, running=False)
        self.combat_once()
        self.sleep(3)
        if not self.walk_find_echo(time_out=5, backward_time=2.5):
            dropped = self.yolo_find_echo(turn=True, use_color=False, time_out=30)[0]
            logger.info(f'farm echo yolo find {dropped}')
        else:
            self.log_info(f'farm echo walk find true')
        self.sleep(1)

    def get_nest_to_go(self):
        self.openF2Book()
        while self.step <= 2:
            self.go_step()
            if nest := self.find_nest():
                return nest
            else:
                self.step += 1

    def go_step(self):
        if self.step <= 1:
            self.click(0.17, 0.68, after_sleep=1)
            if self.step == 1:
                self.click(0.98, 0.54, after_sleep=1)
        else:
            self.click(0.17, 0.77, after_sleep=1)

    def find_nest(self):
        counts = self.ocr(0.36, 0.13, 0.98, 0.91, match=self.count_re)
        for count_box in counts:
            for match in re.finditer(self.count_re, count_box.name):
                numerator = match.group(1)
                denominator = match.group(2)
                if numerator != denominator:
                    self.log_info(f'{count_box} is not complete')
                    count_box.x = self.width_of_screen(0.9)
                    count_box.y -= count_box.height
                    return count_box
