import time

from src.char.Healer import Healer


class ShoreKeeper(Healer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outrotime = -1
        self.dodge_count = 0

    def count_liberation_priority(self):
        return 2
    
    def do_perform(self):
        if self.has_intro:
            self.logger.debug('ShoreKeeper wait intro animation')
            time.sleep(0.1)
            self.task.wait_in_team_and_world(time_out=4, raise_if_not_found=False)
            self.check_combat()
        self.liberation_available() and self.wait_down()
        self.click_liberation()
        self.click_echo(time_out=0)
        if self.click_resonance(send_click=False) and self.is_mouse_forte_full():
            self.sleep(0.3)
        self.heavy_click_forte(check_fun=self.is_mouse_forte_full)
        self.switch_next_char()

    def switch_next_char(self, *args):
        if self.is_con_full():
            self.outrotime = time.time()
            self.dodge_count = 5
        return super().switch_next_char(*args)

    def auto_dodge(self, condition):
        clicked = False
        if self.time_elapsed_accounting_for_freeze(self.outrotime) < 30 and self.dodge_count > 0:
            start = time.time()
            while time.time() - start < 1.5:
                if not condition():
                    break
                self.continues_right_click(0.05)
                self.sleep(0.05)
                clicked = True
                self.task.next_frame()
        if clicked:
            self.dodge_count -= 1
            self.logger.info('ShoreKeepers auto dodge success!')
        return clicked
