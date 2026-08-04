import time

from src.char.BaseChar import BaseChar, CharType, get_default_buff_time


class Chisa(BaseChar):
    NO_INTRO_NORMAL_ATTACK_TIME = 2.8
    INTRO_NORMAL_ATTACK_TIME = 2.8
    INTRO_RESONANCE_WAIT_TIMEOUT = 1.5
    INTRO_RESONANCE_ATTEMPTS = 2
    E2_ICON_CHANGE_TIMEOUT = 0.2
    E2_READY_TIMEOUT = 8.0
    E2_ATTACK_INTERVAL = 0.2
    CONCERTO_ATTACK_TIMEOUT = 10.0

    def is_dps_config(self):
        return self.task and self.task.char_config.get("Chisa DPS")

    def get_char_type(self):
        if self.is_dps_config():
            return CharType.MAIN_DPS
        return super().get_char_type()

    def get_buff_time(self):
        if self.is_dps_config():
            return get_default_buff_time(CharType.MAIN_DPS)
        return super().get_buff_time()

    def _find_e2_match(self):
        return self.task.find_one(
            'chisa_e2',
            box=self.task.get_box_by_name('box_resonance'),
            threshold=0.7,
        )

    def e2_available(self):
        match = self._find_e2_match()
        if match:
            self.logger.info(f'Chisa [e2_available] chisa_e2 template detected: {match}')
        else:
            self.logger.info('Chisa [e2_available] chisa_e2 template not detected')
        return bool(match)

    def _wait_for_e2_icon_change(self):
        changed = self.task.wait_until(
            lambda: not self._find_e2_match(),
            time_out=self.E2_ICON_CHANGE_TIMEOUT,
        )
        if changed:
            self.logger.info('Chisa [e2] icon changed after use')
        else:
            self.logger.warning('Chisa [e2] icon change not detected after use')
        return changed

    def _wait_for_e2_with_normal_attack(self):
        self.logger.warning(
            'Chisa [e2] template not detected, normal attack until it becomes available')
        start = time.time()
        while time.time() - start < self.E2_READY_TIMEOUT:
            self.continues_normal_attack(self.E2_ATTACK_INTERVAL)
            if self.e2_available():
                self.logger.info('Chisa [e2] template detected after normal-attack fallback')
                return True
        self.logger.warning(
            f'Chisa [e2] template still not detected after {self.E2_READY_TIMEOUT:.1f}s')
        return False

    def _is_live_con_full(self):
        self.current_con = 0
        current_con = self.task.get_current_con()
        self.logger.debug(f'Chisa support live concerto={current_con}')
        return current_con == 1

    def _switch_to_sub_dps(self):
        sub_dps = next(
            (char for char in self.task.chars
             if char is not None and char is not self and char.is_sub_dps),
            None,
        )
        if sub_dps is None:
            self.logger.warning('Chisa support rotation found no SubDps, use default switch selector')
            return self.switch_next_char()
        self.logger.info(f'Chisa support rotation switch to SubDps {sub_dps}')
        return self._switch_to_exact_target(sub_dps)

    def _find_main_dps(self):
        return next(
            (char for char in self.task.chars
             if char is not None and char is not self and char.is_main_dps),
            None,
        )

    def _switch_from_char_to_exact_target(self, current_char, target):
        """把任意当前角色临时切到指定目标，并恢复原选人器。"""
        if current_char is None or target is None or current_char is target:
            return False

        original_selector = self.task._choose_switch_target

        def choose_target(selected_char, has_intro, target_low_con=False):
            if selected_char is current_char:
                return target
            return original_selector(selected_char, has_intro, target_low_con)

        self.task._choose_switch_target = choose_target
        try:
            BaseChar.switch_next_char(current_char)
        finally:
            self.task._choose_switch_target = original_selector

        in_team, current_index, _ = self.task.in_team()
        return in_team and current_index == target.index

    def _perform_main_dps_interlude(self):
        """重击后切主C短暂普攻，再切回千咲。"""
        main_dps = self._find_main_dps()
        if main_dps is None:
            self.logger.warning('Chisa support interlude found no MainDps')
            return False
        if not self._switch_to_exact_target(main_dps):
            self.logger.warning('Chisa support interlude failed to switch to MainDps')
            return False

        interlude_char = self.task.get_current_char(raise_exception=False)
        if interlude_char is None or interlude_char is self:
            self.logger.warning('Chisa support interlude could not identify current MainDps')
            return False

        self.logger.info(f'Chisa support interlude normal attack with {interlude_char}')
        interlude_char.continues_normal_attack(0.4)
        if not self._switch_from_char_to_exact_target(interlude_char, self):
            self.logger.warning('Chisa support interlude failed to switch back to Chisa')
            return False

        self.sleep(0.2)
        return True

    def _use_resonance_after_intro(self):
        """变奏动画结束后释放共鸣技能，动画吞键时最多尝试两次。"""
        resonance_used = False
        for attempt in range(1, self.INTRO_RESONANCE_ATTEMPTS + 1):
            ready = self.task.wait_until(
                self.resonance_available,
                time_out=self.INTRO_RESONANCE_WAIT_TIMEOUT,
            )
            if not ready:
                self.logger.warning(
                    f'Chisa intro resonance not available on attempt {attempt}')
                break

            used = self.click_resonance(time_out=0.5)[0]
            resonance_used = resonance_used or used
            if used:
                self.logger.info(f'Chisa intro resonance key sent, attempt {attempt}')
            else:
                self.logger.warning(f'Chisa intro resonance use failed, attempt {attempt}')

            # click_resonance 只能确认按键已发送；图标仍可用时，说明可能被入场动画吞掉。
            if not self.resonance_available():
                self.logger.info('Chisa intro resonance release confirmed')
                return resonance_used
            if attempt < self.INTRO_RESONANCE_ATTEMPTS:
                self.logger.warning(
                    f'Chisa intro resonance still available, retrying ({attempt + 1}/'
                    f'{self.INTRO_RESONANCE_ATTEMPTS})')
                self.sleep(0.1)

        if resonance_used:
            self.logger.warning('Chisa intro resonance sent but release was not confirmed')
        else:
            self.logger.warning('Chisa intro resonance failed after all attempts')
        return resonance_used

    def _support_skills_available(self):
        resonance_ready = self.resonance_available()
        liberation_ready = self.liberation_available()
        self.logger.info(
            f'Chisa support skill readiness resonance={resonance_ready} '
            f'liberation={liberation_ready}')
        return resonance_ready and liberation_ready

    def _ensure_support_skills_ready(self):
        if self._support_skills_available():
            return True

        self.logger.warning(
            'Chisa support skills not ready, normal attack for 2.0s before retry')
        self.continues_normal_attack(2.0)
        if self._support_skills_available():
            self.logger.info('Chisa support skills became ready after fallback wait')
            return True

        self.logger.warning('Chisa support skills still not ready, switch to next character')
        self.switch_next_char()
        return False

    def _use_e2_if_available(self):
        if not self.e2_available():
            if not self._wait_for_e2_with_normal_attack():
                return False

        e2_used = self.click_resonance(time_out=0.5)[0]
        if e2_used:
            self.logger.info('Chisa [e2] used successfully')
        else:
            self.logger.warning('Chisa [e2] detected but use failed')
        return e2_used

    def _hold_heavy_and_dodge(self, wait_for_e2_icon):
        dodge_key = self.task.key_config.get('Dodge Key')
        if wait_for_e2_icon:
            self._wait_for_e2_icon_change()
        self.task.mouse_down()
        try:
            self.sleep(0.2)
            self.task.send_key(dodge_key)
            self.sleep(0.9)
            self.task.send_key(dodge_key)
            hold_start = time.time()
            while time.time() - hold_start < 2.8:
                if self._is_live_con_full():
                    self.logger.info(
                        'Chisa support concerto became full during heavy hold')
                    break
                self.sleep(0.1, check_combat=False)
        finally:
            self.task.mouse_up()
        self.sleep(0.01)

    def _perform_support_tail(self):
        self.click_echo(time_out=0)

        if self.click_liberation():
            self.record_support_buff()

        e2_used = self._use_e2_if_available()
        self._hold_heavy_and_dodge(e2_used)
        if not self._is_live_con_full():
            dodge_key = self.task.key_config.get('Dodge Key')
            self.logger.info(
                'Chisa support concerto not full, dodge then attack until full')
            self.task.send_key(dodge_key)
            self.current_con = 0
            self.continues_normal_attack(
                self.CONCERTO_ATTACK_TIMEOUT,
                until_con_full=True,
            )
        return self._switch_to_sub_dps()

    def _perform_intro_support(self):
        """变奏入场辅助连段；仅在辅助模式调用。"""
        self.wait_intro(1.2)
        self.check_f_on_switch = True
        self.logger.info('Chisa intro support rotation start')

        if not self._ensure_support_skills_ready():
            return False
        self._use_resonance_after_intro()
        self.continues_normal_attack(self.INTRO_NORMAL_ATTACK_TIME)
        return self._perform_support_tail()

    def _perform_no_intro_support(self):
        """无变奏入场辅助连段；仅在辅助模式调用。"""
        self.check_f_on_switch = True
        self.logger.info('Chisa no-intro support rotation start')

        if not self._ensure_support_skills_ready():
            return False
        self.task.jump()
        self.continues_normal_attack(1.0)
        self.click_resonance(time_out=0.5)
        self.continues_normal_attack(self.NO_INTRO_NORMAL_ATTACK_TIME)
        return self._perform_support_tail()

    def do_perform(self):
        # 输出模式保持原逻辑；辅助模式区分变奏与无变奏入场。
        if not self.is_dps_config():
            if self.has_intro:
                return self._perform_intro_support()
            return self._perform_no_intro_support()

        return self.do_dps_perform()

    def record_support_buff(self):
        """Track the buff granted by Chisa's Intro Skill or Resonance Liberation."""
        self.last_buff_time = time.time()

    def switch_out(self, con_full=False):
        support_buff_time = self.last_buff_time
        super().switch_out(con_full=con_full)
        if not self.is_dps_config():
            self.last_buff_time = support_buff_time

    def do_dps_perform(self):
        timeout = 2.5
        self.check_f_on_switch = True
        if self.has_intro:
            self.continues_normal_attack(0.8)
            timeout = 2.3
        if self.flying() and not self.liberation_available() and not self.resonance_available():
            self.wait_down()
        self.click_echo()
        start = time.time()
        under_liber = False
        while time.time() - start < timeout:
            if time.time() - start < 0.5 and self.click_liberation():
                start = time.time()
                under_liber = True
                timeout = 10
                self.sleep(0.2)
            if time.time() - start < 0.5 and not self.is_forte_full() and self.click_resonance()[0]:
                start = time.time()
                if timeout != 10:
                    timeout = 1.7
            if (under_liber or self.is_dps_config()) and self.is_forte_full() and self.perform_forte():
                self.check_f_on_switch = False
                return self.switch_next_char()
            self.click()
            self.check_combat()
            self.task.next_frame()
        self.switch_next_char()

    def perform_forte(self):
        if self.flying():
            self.wait_down()
        self.task.send_key(self.get_resonance_key(), down_time=1.2)
        if self.is_forte_full():
            return False
        self.heavy_attack(3.5)
        return True

    def _switch_to_exact_target(self, target, post_action=None, free_intro=False, target_low_con=False):

        if target is None or target is self:
            return False

        original_selector = self.task._choose_switch_target

        def choose_target(current_char, has_intro, target_low_con=False):
            # 只限制“千咲作为当前角色”的这次选择；其他调用仍走原选择器。
            if current_char is self:
                return target
            return original_selector(current_char, has_intro, target_low_con)

        self.task._choose_switch_target = choose_target
        try:
            super().switch_next_char(
                post_action=post_action,
                free_intro=free_intro,
                target_low_con=target_low_con,
            )
        finally:
            self.task._choose_switch_target = original_selector

        # 切人可能被战斗状态或按键时序阻塞，不能仅凭调用完成就认为已切到目标。
        in_team, current_index, _ = self.task.in_team()
        return in_team and current_index == target.index
