from src.char.Healer import Healer


class Verina(Healer):

    def do_perform(self):
        self.wait_intro(click=False, time_out=1.1)
        liberated = self.click_liberation()
        if self.flying():
            self.normal_attack()
            return self.switch_next_char()
        self.click_resonance()
        self.click_echo()
        if self.is_forte_full():
            self.heavy_attack()
        elif not liberated:
            self.click_liberation(wait_if_cd_ready=1, send_click=True)
        self.switch_next_char()
