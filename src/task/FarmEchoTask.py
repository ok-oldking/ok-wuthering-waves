import re
import cv2
import time

from qfluentwidgets import FluentIcon
import numpy as np

from ok import Logger, TaskDisabledException, color_range_to_bound
from src.task.BaseCombatTask import BaseCombatTask, white_color
from src.task.WWOneTimeTask import WWOneTimeTask
from ok import find_boxes_by_name

logger = Logger.get_logger(__name__)


class FarmEchoTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "Click Start after Entering Dungeon or Teleporting to The Boss"
        self.name = "Farm 4C Echo in Dungeon/World"
        self.group_name = "Farm"
        self.group_icon = FluentIcon.SYNC
        self.default_config.update({
            'Boss': 'Other',
            'Repeat Farm Count': 10000,
            'Combat Wait Time': 0,
            'Echo Pickup Method': 'Walk',
            'Use Liberation': True,
        })
        self.config_description.update({
            'Boss': 'Select boss profile (includes Combat Wait Time)',
            'Combat Wait Time': 'Wait time before each combat (seconds), overrides Boss profile if set',
            'Use Liberation': 'Do not use Liberation to Save Time',
        })
        self.find_echo_method = ['Yolo', 'Run in Circle', 'Walk']
        self.config_type['Echo Pickup Method'] = {'type': "drop_down", 'options': self.find_echo_method}
        self.boss_list = ['Other', 'Hyvatia', 'Fallacy of No Return', 'Sentry Construct', 'Lorelei', 'Lioness of Glory',
                          'Nightmare: Hecate', 'Fenrico']
        self.config_type['Boss'] = {'type': "drop_down", 'options': self.boss_list}
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
        self.bypass_end_wait = False
        self.boss_dict = {
            '伪作的神王': {'name': r'伪作的神王'},
            '异构武装': {'name': r'(异构武装|加尔古耶)', 'set_combat_wait': 5},
            '荣耀狮像': {'name': r'(狮像|亚狮诺索)', 'set_combat_wait': 5},
            '罗蕾莱': {'name': r'(罗蕾莱|夜之女皇)', 'set_night': True},
        }
        self.is_revived = False

    def on_combat_check(self):
        if not self._in_realm:
            self.incr_drop(self.pick_f(handle_claim=True))
        self.in_realm_check(20)
        return True

    def revive_action(self):
        if self._in_realm:
            return False
        self.teleport_to_heal()
        self.run_until(lambda: False, 's', 1, running=True)
        self.teleport_to_nearest_boss()
        self.sleep(0.5)
        self.run_until(lambda: self.in_combat() or self.find_treasure_icon(), 'w', time_out=12, running=True,
                       target=True)
        self.execute_treasure_hunt()
        self.is_revived = True
        return True

    def run(self):
        WWOneTimeTask.run(self)
        self.use_liberation = self.config.get('Use Liberation')
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
        self.manage_boss_parameters()
        self.log_info(f'in_realm: {self._in_realm}')
        self._farm_start_time = time.time()
        self._has_treasure = False
        self.is_revived = False
        self.init_parameters()
        while count < self.config.get("Repeat Farm Count", 0):
            self.in_realm_check(60)
            self.log_debug(f'start farming {count} {self._in_realm}')
            if not self.is_revived:
                self.manage_boss_interactions()
            else:
                self.is_revived = False
            if not self.in_combat():
                if self._in_realm and not self.in_world():
                    self.send_key('esc', after_sleep=0.5)
                    self.wait_click_feature('claim_cancel_button_hcenter_vcenter', relative_x=1,
                                            raise_if_not_found=True,
                                            post_action=lambda: self.send_key('esc', after_sleep=1),
                                            settle_time=1)
                    self.wait_in_team_and_world(time_out=120)
                    self.sleep(1)
                else:
                    if self._has_treasure:
                        self.wait_until(
                            lambda: self.find_treasure_icon() or self.in_combat(target=True) or self.find_f_with_text(),
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
                self.execute_treasure_hunt()

            self.sleep(self.combat_wait_time)
            self.log_info(f'combat_wait_time: {self.combat_wait_time}')
            self.check_boss_name()

            self.combat_once(wait_combat_time=0, raise_if_not_found=False)
            if self.is_revived:
                continue
            if self.pick_echo():
                logger.info(f'farm echo on the face')
                dropped = True
            elif self.config.get('Echo Pickup Method', "Yolo") == "Yolo":
                dropped = \
                    self.yolo_find_echo(turn=self._in_realm, use_color=False, time_out=self.yolo_time_out,
                                        threshold=self.yolo_threshold)[0]
                logger.info(f'farm echo yolo find {dropped}')
            elif self.config.get('Echo Pickup Method', "Yolo") == "Run in Circle":
                dropped = self.run_in_circle_to_find_echo(circle_count=2)
                logger.info(f'farm echo walk_circle_find_echo {dropped}')
            else:
                dropped = self.walk_find_echo()
                logger.info(f'farm echo walk_find_echo {dropped}')
            self.incr_drop(dropped)
            if not self.bypass_end_wait:
                if dropped and not self._has_treasure:
                    self.wait_until(self.in_combat, raise_if_not_found=False, time_out=5)
                else:
                    self.wait_until(self.in_combat, raise_if_not_found=False, time_out=1)

    def execute_treasure_hunt(self):
        if not self.in_combat() and self.find_treasure_icon() and self.walk_to_treasure_and_restart():
            self._has_treasure = True
            self.log_info('_has_treasure = True')
            self.scroll_and_click_buttons()

    def in_realm_check(self, time_threshold):
        if not self._in_realm and time.time() - self._farm_start_time < time_threshold:
            self._in_realm = self.in_realm()
            if self._in_realm:
                self.init_parameters()
                self.log_info(f'in_realm: {self._in_realm}')

    def manage_boss_parameters(self):
        boss = self.config.get('Boss')
        if boss in ('Sentry Construct', 'Lioness of Glory', 'Fallacy of No Return'):
            self.combat_wait_time = self.config.get("Combat Wait Time", 0) or 5
        elif boss in ('Hyvatia'):
            self.combat_wait_time = self.config.get("Combat Wait Time", 0) or 7
        else:
            self.combat_wait_time = self.config.get("Combat Wait Time", 0)
        if boss in ('Lady of the Sea'):
            self.log_debug('manage_boss_parameters Lady of the Sea')
            self._in_realm = True
        self.bypass_end_wait = boss in ('Fenrico', 'Fallacy of No Return', 'Lady of the Sea')
        self.treat_as_not_in_realm = boss in ('Nightmare: Hecate')
        self.log_info(
            f"profile: {boss} { {
                'combat_wait_time': self.combat_wait_time,
                'bypass_end_wait': self.bypass_end_wait,
                'treat_as_not_in_realm': self.treat_as_not_in_realm
            } }"
        )

    def manage_boss_interactions(self):
        if self.in_combat():
            return
        boss = self.config.get('Boss')
        if boss != 'Other':
            if boss in ('Lorelei'):
                night_elapsed = time.time() - self.last_night_change
                self.log_info(f"Night elapsed: {night_elapsed:.1f}s")
                if night_elapsed > 660:
                    self.change_time_to_night()
                    self.last_night_change = time.time()
            if boss in ('Fallacy of No Return'):
                if not self.find_f_with_text():
                    self.teleport_to_nearest_boss()
                    self.send_key('d', down_time=0.25, after_sleep=0.5)
                    self.send_key('w', after_sleep=0.5)
                if self.walk_until_f(time_out=20, check_combat=True, running=True):
                    self.scroll_and_click_buttons()
                self.wait_until(self.in_combat, raise_if_not_found=False, time_out=300)
            if boss in ('Fenrico'):
                while self.find_f_with_text():
                    self.sleep(1)
                    self.incr_drop(self.pick_echo())
                try:
                    self.teleport_to_nearest_boss()
                    self.sleep(2)
                except Exception:
                    self.log_info('Fenrico teleport_to_nearest_boss failed')
                    self.ensure_main()
                self.run_until(lambda: self.find_treasure_icon() or self.in_combat() or self.find_f_with_text(), 'w',
                               time_out=5, target=True)
                self.execute_treasure_hunt()
                self.wait_until(self.in_combat, raise_if_not_found=False, time_out=300)
            if boss in ('Lady of the Sea'):
                self.log_debug('manage_boss_interactions Lady of the Sea')
                self._in_realm = True
                if not self.in_world():
                    self.log_debug('manage_boss_interactions Lady of the Sea not self.in_world()')
                    self.send_key('esc', after_sleep=0.5)
                    self.wait_click_feature('confirm_btn_hcenter_vcenter', relative_x=-1, raise_if_not_found=True,
                                            post_action=lambda: self.send_key('esc', after_sleep=1),
                                            settle_time=1)
                    self.sleep(2)
                    self.wait_in_team_and_world(time_out=120)
                    self.sleep(2)
                if self.in_world():
                    self.log_debug('manage_boss_interactions Lady of the Sea self.in_world()')
                    self.pick_f()
                    self.sleep(2)
                    self.wait_in_team_and_world(time_out=120)
                    self.sleep(2)
                    self.wait_until(self.in_combat, raise_if_not_found=False, time_out=10)
            if boss not in self.boss_list:
                logger.warning(f'unknown boss profile {boss}, run as Other')

    def init_parameters(self):
        self.target_enemy_time_out = 3 if self._in_realm else 1.2
        self.switch_char_time_out = 5 if self._in_realm else 3
        self.yolo_threshold = 0.25 if self._in_realm else 0.65
        self.yolo_time_out = 12 if self._in_realm else 4

    def go_to_boss_minimap(self, threshold=0.5, time_out=15):
        start_time = time.time()
        current_direction = None
        current_adjust = None
        self.center_camera()
        while time.time() - start_time < time_out:
            self.sleep(0.01)
            if self.in_combat(target=True):
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
        if not self.in_combat(target=True):
            self.teleport_to_nearest_boss()
            self.sleep(0.5)
            self.run_until(lambda: self.in_combat() or self.find_treasure_icon(), 'w', time_out=12, running=True,
                           target=True)

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
            self.wait_in_team_and_world(time_out=30, raise_if_not_found=False)
            return
        self.send_key('m', after_sleep=2)
        box = self.find_best_match_in_box(self.box_of_screen(0.3, 0.3, 0.7, 0.7),
                                          ['boss_check_mark'], threshold=0.8)
        if box is None:
            boss_template = self.get_feature_by_name('boss_no_check_mark')
            original_mat = boss_template.mat
            (h, w) = boss_template.mat.shape[:2]
            center = (w // 2, h // 2)
            targets = []
            for angle in range(0, 270, 90):
                # Rotate the template image
                rotation_matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
                template = cv2.warpAffine(original_mat, rotation_matrix, (w, h))
                boxes = self.find_feature(box=self.box_of_screen(0.3, 0.3, 0.7, 0.7), template=template, threshold=0.7)
                targets.extend(boxes)
            box = max(targets, key=lambda box: box.confidence, default=None)
            if box is None:
                raise Exception(f"boss not found")

        self.log_info(f'teleport_to_nearest_boss {box}')
        if box:
            self.click_box(box)
            self.wait_click_travel()
            self.wait_in_team_and_world(time_out=30)

    def click_boss_octagon(self):
        # === 1. 读取图像 ===
        img = self.box_of_screen(0.3, 0.3, 0.7, 0.7).crop_frame(self.frame)

        # === 2. 提取白色部分（白边）===
        lower_white, upper_white = color_range_to_bound(white_color)
        mask = cv2.inRange(img, lower_white, upper_white)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

        # 2. 找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 3. 生成理想梯形轮廓（用于形状比对）
        h, w = self.frame.shape[:2]

        # 缩放比例
        scale_x = w / 2560
        scale_y = h / 1440

        # 原梯形轮廓
        trapezoid = np.array([
            [35, 0], [0, 35], [92, 36], [56, 0]
        ], np.int32).reshape((-1, 1, 2))

        # 等比例缩放
        trapezoid_scaled = np.zeros_like(trapezoid, dtype=np.int32)
        trapezoid_scaled[:, 0, 0] = (trapezoid[:, 0, 0] * scale_x).astype(np.int32)
        trapezoid_scaled[:, 0, 1] = (trapezoid[:, 0, 1] * scale_y).astype(np.int32)

        # 定义匹配阈值
        best_mat = None
        best_match = None
        best_ratio = 0

        for cnt in contours:
            cnt = cv2.convexHull(cnt)
            x, y, _, _ = cv2.boundingRect(cnt)
            for dx in range(-10, 11, 2):
                for dy in range(-10, 11, 2):
                    shifted = trapezoid_scaled + [x + dx, y + dy]
                    area_i, mat_i = cv2.intersectConvexConvex(cnt.astype(np.float32), shifted.astype(np.float32))
                    ratio = area_i / cv2.contourArea(trapezoid_scaled)
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = cnt
                        best_mat = mat_i

        # # 画出匹配到的轮廓
        # if best_match is not None:
        #     cv2.polylines(img, [best_match], isClosed=False, color=(0,255,0), thickness=2)

        # if best_mat is not None and len(best_mat) > 0:
        #     best_mat = best_mat.astype(np.int32)
        #     cv2.polylines(img, [best_mat], isClosed=False, color=(255,0,0), thickness=2)

        # # 显示结果
        # print(f'Best match ratio: {best_ratio:.2f}')
        # cv2.imshow("mask", mask)
        # cv2.imshow("Matched", img)
        # cv2.waitKey(1)

        # 点击轮廓中心
        if best_match is None:
            raise RuntimeError('Can not find the boss octagon on map')

        x0, y0 = self.width_of_screen(0.3), self.height_of_screen(0.3)
        x, y, w, h = cv2.boundingRect(best_match)
        cx = x0 + x + w // 2
        cy = y0 + y + h // 2
        self.click(cx, cy, after_sleep=1)

    def teleport_to_octagon_boss(self):
        """传送到八边形Boss图标。"""
        self.log_info('click m to open the map')
        self.send_key('m', after_sleep=2)

        self.click_boss_octagon()
        travel = self.wait_feature('gray_teleport', raise_if_not_found=True, time_out=3)
        if not travel:
            pop_up = self.find_feature('map_way_point', box='map_way_point_pop_up_box')
            if pop_up:
                self.click(pop_up, after_sleep=1)
                travel = self.wait_feature('gray_teleport', raise_if_not_found=True, time_out=3)
        if not travel:
            raise RuntimeError(f'Can not find the travel button')
        self.click_box(travel, relative_x=1.5)
        self.wait_in_team_and_world(time_out=20)
        self.sleep(2)

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
        # self.combat_wait_time = self.config.get("Combat Wait Time", 0)
        # self.set_night = self.config.get('Change Time to Night')
        if self.game_lang != 'zh_CN':
            return
        texts = self.ocr(box=self.box_of_screen(1269 / 3840, 10 / 2160, 2533 / 3840, 140 / 2160, hcenter=True),
                         target_height=540, name='boss_lv_text')
        for key, value in self.boss_dict.items():
            s = value.get('name')
            fps_text = find_boxes_by_name(texts, re.compile(s, re.IGNORECASE))
            if fps_text:
                self.aim_boss = key
                # if value.get('set_combat_wait'):
                #     self.combat_wait_time = value.get('set_combat_wait')
                # if value.get('set_night'):
                #     self.set_night = True
                break
        if self.aim_boss is not None:
            logger.info(f'combat with {self.aim_boss}')
        else:
            logger.info(f'boss_string is {find_boxes_by_name(texts, [re.compile(r'(?i)^L[Vv].*')])}')
