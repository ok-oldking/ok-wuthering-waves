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
        if self.ring_index == Elements.HAVOC:
            self.perform_havoc_routine()
        elif self.ring_index == Elements.SPECTRO:
            self.perform_spectro_routine()
        else:
            self.perform_basic_routine()
        self.switch_next_char()

    def perform_spectro_routine(self):
        if self.has_intro:
            self.wait_intro()
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
            self.wait_intro()
        if self.liberation_available():
            if self.is_forte_full():
                if self.resonance_available():
                    self.click_resonance(send_click=True, post_sleep=0.75)
                self.heavy_attack(0.8)
            self.click_liberation(send_click=True)
        if self.click_resonance(send_click=True)[0]:
            return
        if not self.click_echo():
            self.click()
        self.continues_normal_attack(1.1 - self.time_elapsed_accounting_for_freeze(self.last_switch_time))

    def perform_basic_routine(self):
        if self.has_intro:
            self.continues_normal_attack(self.intro_motion_freeze_duration)
        if self.echo_available():
            self.click_echo(time_out=0.2)
        liber = self.click_liberation(send_click=True)
        res = self.click_resonance(send_click=True)[0]
        if not (liber and res):
            self.continues_normal_attack(1)