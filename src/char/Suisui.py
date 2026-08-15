import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, SwitchPriority


class Suisui(BaseChar):
    ATTACK_INTERVAL = 0.1
    FORTE_TIMEOUT = 26.0
    CONCERTO_TIMEOUT = 12.0
    FORTE3_SWITCH_LOCKOUT = 16.0
    MAIN_DPS_FORTE3_SWITCH_LOCKOUT = 32

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_forte3_switch = -1
        self.should_heavy = False

    def reset_state(self):
        super().reset_state()
        self.last_forte3_switch = -1
        self.should_heavy = False

    def do_perform(self):
        if not self.should_heavy:
            self.should_heavy = self.has_intro
        self.perform_forte3_rotation()
        self.switch_next_char()

    def perform_forte3_rotation(self):
        start = time.time()
        if self.should_heavy:
            if self.has_intro:
                self.heavy_attack(1.5)
            self.click_resonance()
            self.should_heavy = False
        while self.time_elapsed_accounting_for_freeze(start) < self.FORTE_TIMEOUT:
            if self.forte3_available():
                self.logger.debug('forte3 available')
                break
            elif self.forte2_available() or self.forte3_available():
                self.logger.debug('forte2 available')
                for i in range(7):
                    if self.forte3_available():
                        break
                    self.click(after_sleep=0.1)
                break
            self.cycle_start()
            if not self.has_intro:
                if self.try_e():
                    return self.switch_next_char()
            self.click()
            self.cycle_sleep(self.ATTACK_INTERVAL)
        else:
            self.logger.warning('Suisui forte3 detection timed out')
            return

        liberation_clicked = False
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < self.CONCERTO_TIMEOUT:
            if not liberation_clicked:
                liberation_clicked = self.click_liberation(wait_if_cd_ready=0)
                if liberation_clicked:
                    self.task.next_frame()
                    continue
            if self.is_con_full() and self.forte3_available():
                return
            self.click(after_sleep=0.1)
        self.logger.warning('Suisui concerto fill timed out')

    def try_e(self):
        if self.task.find_one(Labels.suisui_e1):
            start = time.time()
            while self.task.find_one(Labels.suisui_e1) and self.time_elapsed_accounting_for_freeze(start) < 2:
                self.send_resonance_key()
                self.sleep(0.05)
            return True

    def forte3_available(self):
        return bool(self.task.find_one(Labels.suisui_forte3, threshold=0.75))

    def forte2_available(self):
        return bool(self.task.find_one(Labels.suisui_forte2, threshold=0.75))

    def switch_out(self, con_full=False):
        super().switch_out(con_full=con_full)
        if con_full:
            self.last_forte3_switch = time.time()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        since_last = self.time_elapsed_accounting_for_freeze(self.last_forte3_switch)
        if since_last > 40:
            return SwitchPriority.MUST
        elif since_last < self.FORTE3_SWITCH_LOCKOUT:
            return SwitchPriority.NO
        has_main_dps = any(
            char and char != self and char.is_main_dps
            for char in getattr(self.task, 'chars', [])
        )
        if has_main_dps:
            if current_char and current_char.is_main_dps and has_intro:
                return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)
