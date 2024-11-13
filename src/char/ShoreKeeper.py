from src.char.Healer import Healer


class ShoreKeeper(Healer):

    def do_perform(self):
        if self.has_intro:
            self.logger.debug('ShoreKeeper wait intro animation')
            self.sleep(1)
            self.task.wait_in_team_and_world(time_out=4, raise_if_not_found=False)
            self.check_combat()
        self.click_liberation()
        self.click_resonance(send_click=False)
        self.click_echo()
        if self.is_forte_full():
            self.heavy_attack()
        self.switch_next_char()
