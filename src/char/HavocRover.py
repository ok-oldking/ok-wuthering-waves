import time
from ok import Logger
from src.char.BaseChar import BaseChar, Elements, SwitchPriority

_ROVER_FORM_NAMES = {
    Elements.SPECTRO: 'Rover: Spectro',
    Elements.WIND: 'Rover: Aero',
    Elements.HAVOC: 'Rover: Havoc',
}


class HavocRover(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zani_liber_insert = False
        self._force_switch_me = False
        self._bind_form_logger()

    def reset_state(self):
        self.ring_index = -1
        self.zani_liber_insert = False
        self._force_switch_me = False
        super().reset_state()
        self._bind_form_logger()

    @property
    def display_name(self):
        return _ROVER_FORM_NAMES.get(self.ring_index, 'Rover')

    def __repr__(self):
        return self.display_name

    def _bind_form_logger(self):
        self.logger = Logger.get_logger(self.display_name)

    def ensure_display_form(self):
        if self.ring_index >= 0:
            return
        if not self.is_current_char:
            return
        if hasattr(self.task, '_ensure_ring_index'):
            self.task._ensure_ring_index()
            self._bind_form_logger()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if self._force_switch_me:
            return SwitchPriority.MUST
        for char in self.task.chars:
            if char is not None and char is not self and getattr(char, "_force_switch_me", False):
                return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def _force_switch_to(self, target):
        if target is None:
            return super().switch_next_char()
        for char in self.task.chars:
            if char is not None:
                char._force_switch_me = char is target
        try:
            return super().switch_next_char()
        finally:
            for char in self.task.chars:
                if char is not None:
                    char._force_switch_me = False

    def do_perform(self):
        if self.zani_liber_insert:
            return self._do_zani_liber_insert()
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

    def _do_zani_liber_insert(self):
        """赞妮大招插入：E + Q + 大招，然后切回赞妮。"""
        self.zani_liber_insert = False
        self.logger.info("rover: zani liber insert short axis (E+Q+R)")
        self.init()
        if self.has_intro:
            self.continues_normal_attack(0.2)
        self.wait_down()
        if self.resonance_available():
            self.click_resonance(send_click=True)
            self.sleep(0.05)
        if self.echo_available():
            self.click_echo(time_out=0)
            self.sleep(0.05)
        attempts = 0
        recovery_elapsed = 0
        result = "disabled"
        if self.task.use_liberation:
            attempts = 1
            if self.click_liberation(send_click=True):
                result = "first-success"
            else:
                result = "retry-timeout"
                retry_start = time.time()
                while time.time() - retry_start < 2:
                    remaining = 2 - (time.time() - retry_start)
                    self.continues_normal_attack(min(0.25, remaining))
                    recovery_elapsed = min(time.time() - retry_start, 2)
                    if recovery_elapsed >= 2:
                        break
                    attempts += 1
                    if self.click_liberation(send_click=True, wait_if_cd_ready=0):
                        result = "retry-success"
                        break
        self.logger.info(f"rover: liber insert result={result} attempts={attempts} recovery={recovery_elapsed:.2f}s")
        from src.char.Zani import Zani

        zani = self.task.has_char(Zani)
        return self._force_switch_to(zani)

    def init(self):
        if self.ring_index == -1:
            self.task._ensure_ring_index()
            self._bind_form_logger()
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
        self.heavy_click_forte(check_fun = self.is_mouse_forte_full)
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
        elif self.current_resonance() > 0.15:
            return True

    def wind_routine_wait_down(self, check_forte_full=True):
        if self.wind_routine_flying():
            if self.task.has_lavitator:
                self.wait_down()
            else:
                self.task.wait_until(lambda: self.current_resonance() < 0.15,
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
        if self.zani_liber_insert:
            return self._do_zani_liber_insert()
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
