import time
from src.char.BaseChar import BaseChar, Elements


class HavocRover(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def reset_state(self):
        self.ring_index = -1
        super().reset_state()

    def do_perform(self):
        self.init()
        if not self.has_intro:
            self.sleep(0.01)
        if self.ring_index == Elements.HAVOC:
            self.intro_motion_freeze_duration = 0.64
            self.perform_havoc_routine()
        elif self.ring_index == Elements.SPECTRO:
            self.intro_motion_freeze_duration = 0.92
            self.perform_spectro_routine()
        elif self.ring_index == Elements.WIND:
            self.intro_motion_freeze_duration = 0.52
            self.perform_wind_routine()
        else:
            self.perform_basic_routine()
        self.switch_next_char()

    def init(self):
        if self.ring_index == -1:
            self.task._ensure_ring_index()
            if self.ring_index == Elements.WIND:
                self.init_wind()

    def perform_spectro_routine(self):
        if self.has_intro:
            self.continues_normal_attack(1)
        self.wait_down()
        self.spectro_routine_aftertune_combo()
        self.click_echo(time_out=0)
        if self.is_forte_full():
            self.check_combat()
            if self.resonance_available() and self.click_resonance()[0]:
                self.continues_normal_attack(1.4)
                self.sleep(0.1)
        self.check_combat()
        if not self.click_liberation(send_click=True):
            self.click_resonance()

    def spectro_routine_aftertune_combo(self):
        self.heavy_attack()
        self.sleep(0.4)
        self.continues_normal_attack(0.7)

    def perform_havoc_routine(self):
        self.wait_down()
        self.heavy_click_forte()
        self.click_liberation(send_click=True)
        if self.click_resonance(send_click=True)[0]:
            return
        if not self.click_echo():
            self.click()
        self.continues_normal_attack(1.1 - self.time_elapsed_accounting_for_freeze(self.last_switch_time))

    def init_wind(self):
        from src.char.Cartethyia import Cartethyia
        from src.char.Phoebe import Phoebe
        self.use_skyfall_severance = False
        if self.task.has_char(Cartethyia) and self.task.has_char(Phoebe):
            self.use_skyfall_severance = True

    def perform_wind_routine(self):
        if self.has_intro:
            if self.wind_routine_click_while_flying(2):
                self.click_liberation(send_click=True)
                self.wind_routine_wait_down()
                return
        self.wind_routine_wait_down(check_forte_full=False)
        if self.resonance_available() and not self.is_forte_full():
            self.click_echo(time_out=0)
            start = time.time()
            flying = False
            while time.time() - start < 1:
                self.send_resonance_key(interval=0.1)
                self.task.next_frame()
                self.click(interval=0.1)
                if flying := self.wind_routine_flying():
                    break
            if not self.use_skyfall_severance:
                if flying:
                    self.wind_routine_click_while_flying(1.74)
            else:
                if flying:
                    self.wind_routine_click_while_flying(1.6)
                if self.click_resonance(send_click=False)[0]:
                    self.wind_routine_click_while_flying(1)
        self.click_liberation(send_click=True)
        self.wind_routine_wait_down()

    def wind_routine_click_while_flying(self, duration, interval=0.1):
        start = time.time()
        while time.time() - start < duration:
            if not self.wind_routine_flying():
                return False
            self.click(interval=0.1)
            self.sleep(interval)
        return True

    def wind_routine_flying(self):
        if self.task.has_lavitator:
            return self.flying()
        elif self.current_resonance() > 0.25:
            return True

    def wind_routine_wait_down(self, check_forte_full=True):
        if self.wind_routine_flying():
            if self.task.has_lavitator:
                self.wait_down()
            else:
                self.task.wait_until(lambda: self.current_resonance() < 0.23,
                                     post_action=lambda: self.click(interval=0.1, after_sleep=0.01), time_out=2.5)
        if check_forte_full:
            self.sleep(0.03)
            if self.is_forte_full():
                self.send_resonance_key()
        else:
            self.sleep(0.01)
        return True

    def perform_basic_routine(self):
        if self.has_intro:
            self.continues_normal_attack(self.intro_motion_freeze_duration + 0.2)
        self.wait_down()
        self.click_echo()
        liber = self.click_liberation(send_click=True)
        res = self.click_resonance(send_click=True)[0]
        if not (liber or res):
            self.continues_normal_attack(1)

    def do_fast_perform(self):
        self.init()
        if not self.has_intro:
            self.sleep(0.01)
        if self.ring_index == Elements.WIND:
            self.fast_perform_wind_routine()
        else:
            self.do_perform()
            return
        self.switch_next_char()

    def fast_perform_wind_routine(self):
        if self.has_intro:
            if self.wind_routine_click_while_flying(0.5):
                return
        if self.wind_routine_flying():
            self.click_liberation(send_click=True)
            self.wind_routine_wait_down(check_forte_full=False)
            self.sleep(0.03)
        if self.is_forte_full():
            self.send_resonance_key()
            return
        self.click_echo(time_out=0)
        if self.resonance_available() and not self.wind_routine_flying():
            self.send_resonance_key()
            self.sleep(0.1)
        att_time = 1 - (time.time() - self.last_perform)
        if att_time > 0 and self.wind_routine_flying():
            self.wind_routine_click_while_flying(att_time)
        if self.use_skyfall_severance:
            self.click_resonance(send_click=False)
        if self.click_liberation(send_click=True):
            self.sleep(0.03)
        if self.is_forte_full():
            self.send_resonance_key()
