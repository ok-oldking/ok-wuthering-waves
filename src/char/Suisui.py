import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, SwitchPriority


class Suisui(BaseChar):
    ATTACK_DURATION = 1.2
    ATTACK_INTERVAL = 0.1
    FORTE_TIMEOUT = 26.0
    CONCERTO_TIMEOUT = 12.0
    FORTE3_SWITCH_LOCKOUT = 26.0
    MAIN_DPS_FORTE3_SWITCH_LOCKOUT = 24.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock_after_switch = False
        self.last_forte3_switch = -1

    def reset_state(self):
        super().reset_state()
        self._lock_after_switch = False
        self.last_forte3_switch = -1

    def do_perform(self):
        self.perform_forte3_rotation()
        self.switch_next_char()

    def perform_forte3_rotation(self):
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < self.FORTE_TIMEOUT:
            if self.forte3_available():
                self.logger.debug('forte3 available')
                break
            self.continues_normal_attack(
                self.ATTACK_DURATION,
                interval=self.ATTACK_INTERVAL,
                click_resonance_if_ready_and_return=True,
            )
            self.task.next_frame()
        else:
            self.logger.warning('Suisui forte3 detection timed out')
            return

        self._lock_after_switch = True
        self.click_liberation(wait_if_cd_ready=0)

        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < self.CONCERTO_TIMEOUT:
            if self.is_con_full():
                return
            self.continues_normal_attack(
                self.ATTACK_DURATION,
                interval=self.ATTACK_INTERVAL,
                click_resonance_if_ready_and_return=True,
            )
            self.task.next_frame()
        self.logger.warning('Suisui concerto fill timed out')

    def forte3_available(self):
        return bool(self.task.find_one(Labels.suisui_forte3, threshold=0.6))

    def switch_out(self, con_full=False):
        lock_after_switch = self._lock_after_switch
        self._lock_after_switch = False
        super().switch_out(con_full=con_full)
        if lock_after_switch:
            self.last_forte3_switch = time.time()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        has_main_dps = any(
            char and char != self and char.is_main_dps
            for char in getattr(self.task, 'chars', [])
        )
        switch_lockout = (
            self.MAIN_DPS_FORTE3_SWITCH_LOCKOUT
            if has_main_dps
            else self.FORTE3_SWITCH_LOCKOUT
        )
        if self.time_elapsed_accounting_for_freeze(self.last_forte3_switch) < switch_lockout:
            return SwitchPriority.NO
        if has_main_dps:
            if current_char and current_char.is_main_dps and has_intro:
                return SwitchPriority.MUST
            return SwitchPriority.NO
        return SwitchPriority.MUST
