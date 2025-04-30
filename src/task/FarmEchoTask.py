import time

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class FarmEchoTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "Click Start after Entering Dungeon or Teleporting to The Boss"
        self.name = "Farm 4C Echo in Dungeon/World"
        self.default_config.update({
            'Repeat Farm Count': 1000
        })
        self.icon = FluentIcon.ALBUM
        self.combat_end_condition = self.find_echos
        self.add_exit_after_config()

    def on_combat_check(self):
        self.incr_drop(self.pick_f())
        return True

    def run(self):
        WWOneTimeTask.run(self)
        self.set_check_monthly_card()

        count = 0
        while count < self.config.get("Repeat Farm Count", 0):
            if self.in_realm():
                self.send_key('esc', after_sleep=0.5)
                self.wait_click_feature('confirm_btn_hcenter_vcenter', relative_x=-1, raise_if_not_found=True,
                                        post_action=lambda: self.send_key('esc', after_sleep=1),
                                        settle_time=1)
                self.wait_in_team_and_world(time_out=120)
                self.sleep(2)
            elif self.walk_to_treasure_and_restart():
                pass
            elif self.find_f_with_text():
                self.scroll_and_click_buttons()
            count += 1
            self.combat_once(wait_combat_time=15, raise_if_not_found=False)
            logger.info(f'farm echo move {self.config.get("Boss")} yolo_find_echo')
            dropped = self.yolo_find_echo(turn=False)[0]
            self.incr_drop(dropped)
            self.sleep(0.5)

    def scroll_and_click_buttons(self):
        while True:
            self.scroll_relative(0.5, 0.5, 1)
            self.sleep(0.1)
            self.send_key('f')
            if not self.handle_claim_button():
                break

    def walk_to_treasure_and_restart(self):
        if self.find_treasure_icon() and self.walk_to_box(self.find_treasure_icon, end_condition=self.find_f_with_text):
            self.scroll_and_click_buttons()
            return True

    def choose_level(self, start):
        y = 0.17
        x = 0.15
        distance = 0.08

        logger.info(f'choose level {start}')
        self.click_relative(x, y + (start - 1) * distance)
        self.sleep(0.5)

        self.wait_click_feature('gray_button_challenge', raise_if_not_found=True,
                                click_after_delay=0.5)
        self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=False,
                                time_out=3, click_after_delay=0.5, threshold=0.8)
        self.wait_click_feature('gray_start_battle', relative_x=-1, raise_if_not_found=True,
                                click_after_delay=0.5, threshold=0.8)


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
