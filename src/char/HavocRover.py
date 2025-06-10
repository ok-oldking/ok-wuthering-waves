import time
from src.char.BaseChar import BaseChar, Elements


class HavocRover(BaseChar):
    def __init__(self, *args, **kwargs):
        self.liber_available = False
        super().__init__(*args, **kwargs)

    def reset_state(self):
        self.ring_index = -1
        self.liber_available = False
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
        else:
            self.perform_basic_routine()
        self.switch_next_char()

    def perform_spectro_routine(self):
        if self.has_intro:
            self.continues_normal_attack(self.intro_motion_freeze_duration)
        self.wait_down()
        self.aftertune_combo()
        if self.echo_available():
            self.click_echo(time_out=0.2)
        if self.is_forte_full():
            self.check_combat()
            if self.resonance_available() and self.click_resonance()[0]:
                self.continues_normal_attack(1.4)
                self.sleep(0.1)
                if not self.liberation_available():
                    return
        self.check_combat()
        if self.liberation_available():
            self.click_liberation()
        else:
            self.click_resonance()

    def aftertune_combo(self):
        self.heavy_attack()
        self.sleep(0.4)
        self.continues_normal_attack(0.7)

    def perform_havoc_routine(self):
        if self.has_intro:
            self.continues_normal_attack(self.intro_motion_freeze_duration)
        if self.liber_available or self.liberation_available():
            if self.is_forte_full():
                self.check_combat()
                self.task.mouse_down()
                start = time.time()
                while True:
                    current = time.time()
                    if current - start > 0.5 and not self.is_forte_full() or current - start > 2:
                        break
                    self.task.next_frame()
                self.task.mouse_up()
            else:
                self.wait_down()
            self.click_liberation(send_click=True)
        self.wait_down()
        if self.click_resonance(send_click=True)[0]:
            self.liber_available = self.liberation_available()
            return
        if not self.click_echo():
            self.click()
        self.continues_normal_attack(0.9)
        self.liber_available = self.liberation_available()

    def perform_basic_routine(self):
        self.wait_intro()
        if self.echo_available():
            self.click_echo(time_out=0.2)
        liber = self.click_liberation(send_click=True)
        res = self.click_resonance(send_click=True)[0]
        if not (liber and res):
            self.continues_normal_attack(1)