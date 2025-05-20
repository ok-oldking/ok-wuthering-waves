import time

from qfluentwidgets import FluentIcon

from ok import Logger, TaskDisabledException
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class FarmEchoTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "Click Start after Entering Dungeon or Teleporting to The Boss"
        self.name = "Farm 4C Echo in Dungeon/World"
        self.default_config.update({
            'Repeat Farm Count': 10000,
            'Combat Wait Time': 0,
        })
        self.config_description.update({
            'Combat Wait Time': 'Wait time before each combat(seconds), set 5 if farming Sentry Construct',
        })
        self.icon = FluentIcon.ALBUM
        self.combat_end_condition = self.find_echos
        self.add_exit_after_config()

    def on_combat_check(self):
        self.incr_drop(self.pick_f(handle_claim=False))
        return True

    def run(self):
        WWOneTimeTask.run(self)
        try:
            return self.do_run()
        except TaskDisabledException as e:
            pass
        except Exception as e:
            logger.error('farm 4c error, try handle monthly card', e)
            if self.handle_monthly_card():
                self.run()
            else:
                raise

    def do_run(self):
        count = 0
        in_realm = self.in_realm()
        threshold = 0.25 if in_realm else 0.65
        time_out = 12 if in_realm else 4
        while count < self.config.get("Repeat Farm Count", 0):
            if in_realm:
                self.send_key('esc', after_sleep=0.5)
                self.wait_click_feature('confirm_btn_hcenter_vcenter', relative_x=-1, raise_if_not_found=True,
                                        post_action=lambda: self.send_key('esc', after_sleep=1),
                                        settle_time=1)
                self.wait_in_team_and_world(time_out=120)
                self.sleep(2)
            elif not self.in_combat():
                self.walk_to_treasure_and_restart()
                self.log_info('scroll_and_click_buttons')
                self.scroll_and_click_buttons()

            count += 1
            self.log_info('start wait in combat')
            if not self.wait_until(self.in_combat, raise_if_not_found=False, time_out=12):
                self.teleport_to_nearest_boss()
                self.run_until(self.in_combat, 'w', time_out=5, running=True)

            self.sleep(self.config.get("Combat Wait Time", 0))

            self.combat_once(wait_combat_time=0, raise_if_not_found=False)
            logger.info(f'farm echo move {self.config.get("Boss")} yolo_find_echo')
            if self.find_f_with_text():
                dropped = self.pick_echo()
            else:
                dropped = self.yolo_find_echo(turn=in_realm, use_color=False, time_out=time_out, threshold=threshold)[0]
            self.incr_drop(dropped)
            if dropped:
                self.wait_until(self.in_combat, raise_if_not_found=False, time_out=5)
            else:
                self.sleep(1)

    def teleport_to_nearest_boss(self):
        self.zoom_map(esc=False)
        boxes = self.find_feature(['boss_no_check_mark', 'boss_check_mark'], box=self.box_of_screen(0.1, 0.1, 0.9, 0.9),
                                  threshold=0.6)
        self.log_info(f'teleport_to_nearest_boss {boxes}')
        if len(boxes) > 0:
            center = self.box_of_screen(0.5, 0.5, 0.5, 0.5)
            nearest_boss = center.find_closest_box('all', boxes)
            self.click_box(nearest_boss)
            self.wait_click_travel()
            self.wait_in_team_and_world(time_out=30)

    def scroll_and_click_buttons(self):
        while self.find_f_with_text() and not self.in_combat():
            self.scroll_relative(0.5, 0.5, 1)
            self.sleep(0.1)
            self.send_key('f')
            self.handle_claim_button()

    def walk_to_treasure_and_restart(self):
        if self.find_treasure_icon():
            self.walk_to_box(self.find_treasure_icon, end_condition=self.find_f_with_text, y_offset=0.1)
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
