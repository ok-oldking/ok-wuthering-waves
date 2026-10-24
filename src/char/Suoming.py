import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, CharType, get_default_buff_time


class Suoming(BaseChar):
    FORTE_TIMEOUT = 15
    RESONANCE_HOLD_TIMEOUT = 6
    RESONANCE_READY_TIMEOUT = 8

    def is_dps_config(self):
        return bool(self.task and self.task.char_config.get('Suoming DPS', False))

    def get_char_type(self):
        return CharType.MAIN_DPS if self.is_dps_config() else CharType.SUB_DPS

    def get_buff_time(self):
        if self.is_dps_config():
            return get_default_buff_time(CharType.MAIN_DPS)
        return super().get_buff_time()

    def do_perform(self):
        # Kit reference: https://ww.nanoka.cc/character/1312/
        if self.has_intro:
            self.continues_normal_attack(duration=1.6)
        liberated = self.click_liberation(wait_if_cd_ready=1)
        dps = self.is_dps_config()
        # Support passes Unison; DPS consumes it with Rift Cleaver for Seal Master.
        if liberated and not dps:
            self.click_echo(time_out=0)
            return self.switch_next_char(free_intro=True)

        if liberated or self.has_intro:
            if not liberated:
                self.click_echo(time_out=0)
            if dps:
                self.click_resonance(send_click=False, time_out=1)
            self.perform_forte()
        else:
            self.continues_normal_attack(1.1)
        self.switch_next_char()

    def forte_available(self):
        return bool(self.task.find_one(Labels.suoming_forte_e))

    def perform_forte(self):
        self.continues_click_until(self.forte_available, time_out=self.FORTE_TIMEOUT)
        self.hold_forte_resonance()

    def hold_forte_resonance(self):
        key = self.get_resonance_key()
        start = time.time()
        down = False
        try:
            self.check_combat()
            while (self.time_elapsed_accounting_for_freeze(start) < self.RESONANCE_HOLD_TIMEOUT
                   and self.forte_available()):
                if down:
                    self.task.send_key_up(key)
                    self.sleep(0.1)
                self.task.send_key_down(key)
                down = True
                self.sleep(2)
            self.sleep(3)
            self.task.wait_until(self.resonance_available, time_out=self.RESONANCE_READY_TIMEOUT,
                                 pre_action=self.check_combat)
        finally:
            self.task.send_key_up(key)
        self.click_echo()
        self.sleep(0.01)
