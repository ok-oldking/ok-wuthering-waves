import time

from src.char.BaseChar import BaseChar, CharType, get_default_buff_time


class Iuno(BaseChar):

    def is_c6(self):
        return self.task and self.task.char_config.get("Iuno C6")

    def get_char_type(self):
        if self.is_c6():
            return CharType.MAIN_DPS
        return super().get_char_type()

    def get_buff_time(self):
        if self.is_c6():
            return get_default_buff_time(CharType.MAIN_DPS)
        return super().get_buff_time()

    def do_perform(self):
        from src.combat.StrictRotation import get_strict_rotation
        if get_strict_rotation(self.task).run_current(self):
            return
        self._do_perform_default()

    def _do_perform_default(self):
        self.wait_down()
        self.do_everything()
        self.switch_next_char()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        from src.combat.StrictRotation import get_strict_rotation, MUST, NO
        from src.char.BaseChar import SwitchPriority
        rot = get_strict_rotation(self.task)
        if rot.is_active():
            priority = rot.priority_for(self.name)
            if priority == MUST:
                return SwitchPriority.MUST
            if priority == NO:
                return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def perform_beat(self, beat):
        """Execute one strict-rotation beat (see src/combat/StrictRotation.py)."""
        from src.combat.StrictRotation import dash
        if beat.name in ('iuno_open1', 'iuno_open2'):
            # 2 / 4. skill
            self.click_resonance()
        elif beat.name == 'iuno_open3':
            # 6. echo
            self.click_echo()
        elif beat.name == 'iuno_loop1':
            # 12. skill, echo, dash, skill
            self.click_resonance()
            self.click_echo()
            dash(self)
            self.click_resonance()
        elif beat.name in ('iuno_burst', 'iuno_burst2'):
            # 8 / 14. (intro) jump-cancel, lib, skill, ba1234, skill, ba, ha, outro
            if beat.intro:
                self.wait_down()
            # force_complete so the no-intro burst (step 14) still fires lib/
            # skill/heavy after the jump instead of switch-cancelling early.
            self.do_everything(force_complete=True)
        else:  # defensive: unknown beat
            self.do_everything()

    def do_everything(self, time_out=1.5, force_complete=False):
        if self.has_intro:
            time_out += 4
        start = time.time()
        last_action = "click"
        self.click_echo()
        c6_performed = False
        jumped = False
        while self.time_elapsed_accounting_for_freeze(start) < time_out:
            cycle_start = time.time()
            heavy_success = False
            while self.task.find_feature("iuno_heavy", box="box_extra_action",
                                         threshold=0.6):
                # 特殊重击可用. The game only shows this prompt while the special
                # heavy can actually be cast, so the indicator is the authority on
                # availability. (The old ``last_heavy > 20s`` throttle also gated
                # this: it made the C6 second heavy impossible -- last_heavy is set
                # to "now" right after the first heavy -- and blocked the heavy on
                # back-to-back rotation bursts that land under 20s apart, so Iuno
                # would switch out without ever triggering it.)
                self.sleep(0.05)
                self.heavy_attack()
                self.sleep(0.05)
                heavy_success = True
            if heavy_success:
                if not c6_performed and self.is_c6():
                    c6_performed = True
                    start = time.time()
                    time_out = 5
                    # 6命多打一轮
                    self.logger.debug('iuno c6 continue')
                else:
                    return True
            if not jumped and self.task.find_feature("iuno_jump", box="box_extra_action", threshold=0.6):
                # 可以跳 起跳
                while self.task.find_feature("iuno_jump", box="box_extra_action", threshold=0.6):
                    self.task.jump(after_sleep=0.1)
                time_out += 3
                jumped = True
                if self.has_intro or force_complete:
                    continue
                else:  # 没有intro, 切人取消后摇
                    return
            if self.time_elapsed_accounting_for_freeze(
                    self.last_liberation) > 20 and self.click_liberation(
                wait_if_cd_ready=0):
                # 开大招
                start = time.time()
                time_out = 3
            if last_action == "click":  # 左键和e轮流点击
                last_action = "resonance"
                self.send_resonance_key()
            else:
                last_action = "click"
                self.click()
            self.sleep(0.1 - (time.time() - cycle_start))

    def on_combat_end(self, chars):
        self.switch_other_char()
