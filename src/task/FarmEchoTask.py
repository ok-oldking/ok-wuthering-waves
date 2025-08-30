import re
import time

from qfluentwidgets import FluentIcon

from ok import Logger, TaskDisabledException
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask
from ok import find_boxes_by_name

logger = Logger.get_logger(__name__)


class FarmEchoTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "Click Start after Entering Dungeon or Teleporting to The Boss"
        self.name = "Farm 4C Echo in Dungeon/World"
        self.default_config.update({
            'Repeat Farm Count': 10000,
            'Combat Wait Time': 0,
            'Echo Pickup Method': 'Walk',
            'Change Time to Night': False,
            "Don't restart in Realm": False,
        })
        self.config_description.update({
            'Combat Wait Time': 'Wait time before each combat(seconds), set 5 if farming Sentry Construct',
            'Change Time to Night': "Yes if Farming Lorelei",
            "Don't restart in Realm": 'Yes if Farming Nightmare: Hecate',
        })
        self.find_echo_method = ['Yolo', 'Run in Circle', 'Walk']
        self.config_type['Echo Pickup Method'] = {'type': "drop_down", 'options': self.find_echo_method}
        self.icon = FluentIcon.ALBUM
        self.combat_end_condition = self.find_echos
        self.add_exit_after_config()
        self._has_treasure = False
        self._in_realm = False
        self._farm_start_time = time.time()
        self.last_night_change = 0
        self.aim_boss = None
        self.combat_wait_time = 0
        self.set_night = False
        self.boss_dict = {
            '伪作的神王': {'name': r'伪作的神王'},
            '异构武装': {'name': r'(异构武装|加尔古耶)','set_combat_wait': 5},
            '荣耀狮像': {'name': r'(狮像|亚狮诺索)','set_combat_wait': 5},
            '罗蕾莱': {'name': r'(罗蕾莱|夜之女皇)','set_night': True},
        }

    def on_combat_check(self):
        if not self._in_realm:
            self.incr_drop(self.pick_f(handle_claim=True))
        if not self._in_realm and time.time() - self._farm_start_time < 20:
            self._in_realm = self.in_realm()
            self.log_info(f'in_realm: {self._in_realm}')
        return True

    def revive_action(self):
        if self._in_realm:
            return False
        self.teleport_to_heal()
        self.run_until(lambda: False,'s',1,running = True)
        self.teleport_to_nearest_boss()
        return True
        
    def run(self):
        WWOneTimeTask.run(self)
        try:
            return self.do_run()
        except TaskDisabledException as e:
            pass
        except Exception as e:
            logger.error('farm 4c error, try handle monthly card', e)
            if self.handle_claim_button() or self.handle_monthly_card():
                self.run()
            else:
                raise

    def do_run(self):
        count = 0
        self._in_realm = self.in_realm()
        self.log_info(f'in_realm: {self._in_realm}')
        self._farm_start_time = time.time()
        self.target_enemy_time_out = 3 if self._in_realm else 1.2
        self.switch_char_time_out = 5 if self._in_realm else 3
        threshold = 0.25 if self._in_realm else 0.65
        time_out = 12 if self._in_realm else 4
        self._has_treasure = False
        while count < self.config.get("Repeat Farm Count", 0):
            if not self._in_realm and time.time() - self._farm_start_time < 60:
                self._in_realm = self.in_realm()
            if self.set_night and not self.in_combat():
                night_elapsed = time.time() - self.last_night_change
                self.log_info(f"Night elapsed: {night_elapsed:.1f}s")
                if night_elapsed > 660:
                    self.change_time_to_night()
                    self.last_night_change = time.time()
            if self._in_realm:
                self.send_key('esc', after_sleep=0.5)
                self.wait_click_feature('confirm_btn_hcenter_vcenter', relative_x=-1, raise_if_not_found=True,
                                        post_action=lambda: self.send_key('esc', after_sleep=1),
                                        settle_time=1)
                self.wait_in_team_and_world(time_out=120)
                if not self.in_realm():
                    self.sleep(1)
                    self.pick_f()
                    self.sleep(2)
                    self.wait_in_team_and_world(time_out=120)
                self.sleep(2)
            elif not self.in_combat():
                if self._has_treasure:
                    self.wait_until(lambda: self.find_treasure_icon() or self.in_combat() or self.find_f_with_text(),
                                    time_out=5, raise_if_not_found=False)
                if not self.in_combat():
                    self.log_info('not in combat try click restart')
                    if self.walk_to_treasure_and_restart():
                        self._has_treasure = True
                        self.log_info('_has_treasure = True')
                    self.scroll_and_click_buttons()

            count += 1
            self.log_info('start wait in combat')
            if not self._in_realm and not self._has_treasure and not self.in_combat():
                self.go_to_boss_minimap()
                if not self.in_combat() and self.find_treasure_icon() and self.walk_to_treasure_and_restart():
                    self._has_treasure = True
                    self.log_info('_has_treasure = True')
                    self.scroll_and_click_buttons()

            self.sleep(self.combat_wait_time)
            self.check_boss_name()

            self.combat_once(wait_combat_time=0, raise_if_not_found=False)
            if self.pick_echo():
                logger.info(f'farm echo on the face')
                dropped = True
            elif self.config.get('Echo Pickup Method', "Yolo") == "Yolo":
                dropped = \
                    self.yolo_find_echo(turn=self._in_realm, use_color=False, time_out=time_out, threshold=threshold)[0]
                logger.info(f'farm echo yolo find {dropped}')
            elif self.config.get('Echo Pickup Method', "Yolo") == "Run in Circle":
                dropped = self.run_in_circle_to_find_echo(circle_count=2)
                logger.info(f'farm echo walk_circle_find_echo {dropped}')
            else:
                dropped = self.walk_find_echo()
                logger.info(f'farm echo walk_find_echo {dropped}')
            self.incr_drop(dropped)
            if dropped and not self._has_treasure:
                self.wait_until(self.in_combat, raise_if_not_found=False, time_out=5)
            else:
                self.wait_until(self.in_combat, raise_if_not_found=False, time_out=1)

    def go_to_boss_minimap(self, threshold=0.5, time_out=15):
        start_time = time.time()
        current_direction = None
        current_adjust = None
        self.center_camera()
        while time.time() - start_time < time_out:
            self.sleep(0.01)
            if self.in_combat():
                break
            angle = self.get_mini_map_turn_angle('boss_check_mark_minimap', threshold=threshold, x_offset=-1,
                                                 y_offset=1)
            if angle is None:
                angle = 0
            current_direction, current_adjust, should_continue = self._navigate_based_on_angle(
                angle, current_direction, current_adjust
            )
            if should_continue:
                continue

        self._stop_movement(current_direction)
        if not self.in_combat():
            self.teleport_to_nearest_boss()
            self.sleep(0.5)
            self.run_until(lambda: self.in_combat() or self.find_treasure_icon(), 'w', time_out=12, running=True)

    def teleport_to_nearest_boss(self):
        if self.aim_boss is not None:
            self.log_info(f'teleport_to_nearest_boss {self.aim_boss}')
            self.ensure_main(time_out=180)
            gray_book_boss = self.openF2Book("gray_book_all_monsters")
            self.click_box(gray_book_boss, after_sleep=1)
            self.click(0.13, 0.14, after_sleep=0.5)
            self.input_text(self.aim_boss)
            self.click(0.39, 0.13, after_sleep=0.5)
            self.click(0.13, 0.24, after_sleep=0.5)
            self.click(0.89, 0.92, after_sleep=1)
            self.click(0.89, 0.92)
            self.wait_in_team_and_world(time_out=30,raise_if_not_found=False)
            return 
        self.send_key('m', after_sleep=2)
        box = self.find_best_match_in_box(self.box_of_screen(0.3, 0.3, 0.7, 0.7),
                                          ['boss_no_check_mark', 'boss_check_mark'],
                                          threshold=0.6)
        self.log_info(f'teleport_to_nearest_boss {box}')
        if box:
            self.click_box(box)
            self.wait_click_travel()
            self.wait_in_team_and_world(time_out=30)

    def scroll_and_click_buttons(self):
        self.sleep(0.2)
        start = time.time()
        if self._has_treasure and not self.find_f_with_text():
            self.scroll_relative(0.5, 0.5, 1)
            self.sleep(0.2)
        while self.find_f_with_text() and not self.in_combat() and time.time() - start < 5:
            self.log_info('scroll_and_click_buttons')
            self.scroll_relative(0.5, 0.5, 1)
            self.sleep(0.2)
            self.send_key('f')
            if self.handle_claim_button():
                self._has_treasure = True

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
                                   
    def check_boss_name(self):
        self.combat_wait_time = self.config.get("Combat Wait Time", 0)
        self.set_night = self.config.get('Change Time to Night')
        if self.game_lang != 'zh_CN':
            return 
        texts = self.ocr(box=self.box_of_screen(1269 / 3840, 10 / 2160, 2533 / 3840, 140 / 2160, hcenter=True),
                         target_height=540, name='boss_lv_text')
        for key, value in self.boss_dict.items():
            s = value.get('name')
            fps_text = find_boxes_by_name(texts, re.compile(s, re.IGNORECASE))
            if fps_text:
                self.aim_boss = key
                if value.get('set_combat_wait'):
                    self.combat_wait_time = value.get('set_combat_wait')
                if value.get('set_night'):
                    self.set_night = True
                break
        if self.aim_boss is not None:
            logger.info(f'combat with {self.aim_boss}')
        else:
            logger.info(f'boss_string is {find_boxes_by_name(texts, [re.compile(r'(?i)^L[Vv].*')])}')
