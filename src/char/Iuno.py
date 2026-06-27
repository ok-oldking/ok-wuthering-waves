import time

from src.char.BaseChar import BaseChar, CharType, get_default_buff_time


class Iuno(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = 0

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

    def perform_stage(self):
        """Stage 2: Iuno's buff burst (see src/combat/StrictRotation.py).

        jump-cancel, lib, skill, ba1234, skill, ba, ha -- the two skill casts apply
        Iuno's buffs, transferred to Augusta when the coordinator gates the outro on
        full concerto and switches.
        """
        if self.has_intro:
            self.wait_down()
        self._iuno_burst()

    def jump_cancel(self):
        """Jump-cancel Iuno's recovery/intro while the jump prompt is shown."""
        while self.task.find_feature("iuno_jump", box="box_extra_action", threshold=0.6):
            self.task.jump(after_sleep=0.1)

    def _iuno_burst(self):
        """Explicit burst: jump-cancel, lib, skill, ba1234, skill, ba, ha.

        The two skill casts are the point: each cast applies one of Iuno's buffs
        to the next character (Augusta), so both must fire before the outro. The
        generic do_everything returns right after Iuno's special heavy and does
        not guarantee the second skill cast, which left Augusta with only one of
        Iuno's two buffs.
        """
        from src.combat.StrictRotation import basic_attacks, heavy
        self.jump_cancel()
        self.click_liberation(wait_if_cd_ready=0)
        self.send_resonance_key(post_sleep=0.1)          # skill -> buff 1
        basic_attacks(self, 4)                           # ba1234
        # let the skill come back up so the second cast actually lands (buff 2).
        # Capped at 2s (not 1s): when the skill CD slightly exceeds 1s the 1s
        # wait timed out and the unconditional send below fired into cooldown,
        # silently dropping Iuno's second buff.
        self.task.wait_until(self.resonance_available, time_out=2)
        self.send_resonance_key(post_sleep=0.1)          # skill -> buff 2
        basic_attacks(self, 1)                           # ba
        if self.task.find_feature("iuno_heavy", box="box_extra_action", threshold=0.6):
            self.heavy_attack()                          # ha (special heavy)
            self.last_heavy = time.time()
        else:
            heavy(self)
        # Concerto is topped off + the outro gated centrally by
        # StrictRotation.run_current, so the burst itself does not wait here.

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
            while self.time_elapsed_accounting_for_freeze(
                    self.last_heavy) > 20 and self.task.find_feature("iuno_heavy",
                                                                     box="box_extra_action",
                                                                     threshold=0.6):
                # 特殊重击可用
                self.sleep(0.05)
                self.heavy_attack()
                self.sleep(0.05)
                heavy_success = True
            if heavy_success:
                self.last_heavy = time.time()
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
