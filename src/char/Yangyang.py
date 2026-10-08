from src.char.BaseChar import BaseChar


class Yangyang(BaseChar):
    """Aero battery/sub-DPS rotation."""

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(0.6)
        self.wait_down()

        self.click_resonance(send_click=True, time_out=1)
        if self.is_mouse_forte_full():
            self.heavy_click_forte(self.is_mouse_forte_full)
        self.click_echo(time_out=0)
        if self.click_liberation(send_click=True, wait_if_cd_ready=0):
            self.continues_normal_attack(0.5)
        else:
            self.continues_normal_attack(0.8, click_resonance_if_ready_and_return=True)
        self.switch_next_char()
