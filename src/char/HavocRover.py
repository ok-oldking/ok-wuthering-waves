import time
from src.char.BaseChar import BaseChar, Elements


class HavocRover(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def reset_state(self):
        self.ring_index = -1
        super().reset_state()

    def do_perform(self):
        if self.ring_index == -1:
            self.task._ensure_ring_index()
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

    def perform_spectro_routine(self):
        if self.has_intro:
            self.continues_normal_attack(1)
        self.wait_down()
        self.aftertune_combo()
        self.click_echo(time_out=0.15)
        if self.is_forte_full():
            self.check_combat()
            if self.resonance_available() and self.click_resonance()[0]:
                self.continues_normal_attack(1.4)
                self.sleep(0.1)
                if not self.liberation_available():
                    return
        self.check_combat()
        if not self.click_liberation(send_click=True):
            self.click_resonance()

    def aftertune_combo(self):
        self.heavy_attack()
        self.sleep(0.4)
        self.continues_normal_attack(0.7)

    def perform_havoc_routine(self):
        if self.has_intro:
            if self.is_forte_full():
                self.heavy_attack(0.8)
        self.wait_down()
        self.click_liberation(send_click=True)
        if self.click_resonance(send_click=True)[0]:
            return
        if not self.click_echo():
            self.click()
        self.continues_normal_attack(1.1 - self.time_elapsed_accounting_for_freeze(self.last_switch_time))

    # TODO: 存在<逆势回击>导致轴长改变打不满两次<抃风儛润>的问题，应当可以用一链提供的buff使用find_one进行优化
    def perform_wind_routine(self):
        if self.has_intro:
            self.continues_normal_attack(2, after_sleep=0.05)
            self.click_liberation(send_click=True)
            self.wind_routine_wait_down()
            return
        if self.task.has_lavitator:
            self.wait_down()
        else:
            self.task.wait_until(lambda: self.current_resonance() < 0.23, post_action=self.click_with_interval,
                             time_out=1)
        self.sleep(0.01)
        if self.resonance_available() and not self.is_forte_full():
            self.click_echo()
            start = time.time()
            while time.time() - start < 0.5:
                if self.task.has_lavitator:
                    if self.flying():
                        break
                elif self.current_resonance() > 0.25:
                    break
                self.send_resonance_key()
                self.task.next_frame()
            self.continues_normal_attack(1.74, after_sleep=0.05)
        self.click_liberation(send_click=True)
        self.wind_routine_wait_down()

    def wind_routine_wait_down(self):
        if self.task.has_lavitator:
            self.wait_down()
        else:
            self.task.wait_until(lambda: self.current_resonance() < 0.23, post_action=self.click_with_interval,
                             time_out=1)
        self.sleep(0.03)
        if self.is_forte_full():
            self.send_resonance_key()

    def perform_basic_routine(self):
        if self.has_intro:
            self.continues_normal_attack(self.intro_motion_freeze_duration + 0.2)
        self.wait_down()
        self.click_echo()
        liber = self.click_liberation(send_click=True)
        res = self.click_resonance(send_click=True)[0]
        if not (liber and res):
            self.continues_normal_attack(1)

    def do_fast_perform(self):
        if self.ring_index == -1:
            self.task._ensure_ring_index()
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
            self.continues_normal_attack(0.5, after_sleep=0.05)
            return
        self.click_echo()
        if self.resonance_available() and not self.flying():
            self.send_resonance_key()
        att_time = 1 - (time.time() - self.last_perform)
        if att_time > 0:
            self.continues_normal_attack(att_time)
        if self.click_liberation(send_click=True):
            self.sleep(0.03)
        if self.is_forte_full():
            self.send_resonance_key()
