from src.char.Healer import Healer


class Douling(Healer):

    def do_perform(self):
        self.wait_down()
        self.click_liberation(con_less_than=1)
        self.click_resonance()
        self.click_echo()
        if self.extra_action_available():
            self.logger.debug('Douling heavy attack')
            self.heavy_attack()
        self.switch_next_char()
