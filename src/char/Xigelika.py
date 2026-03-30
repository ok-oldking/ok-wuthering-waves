import time

from src.char.BaseChar import BaseChar, Priority


class Xigelika(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_perform(self):
        if not self.has_intro:
            self.click_echo(time_out=0)
        self.perform_everything()
        self.switch_next_char()

    def lib(self):
        if self.click_liberation(wait_if_cd_ready=0):
            self.f_break()
            return True

    def perform_everything(self):
        start = time.time()
        time_out = 15
        while self.time_elapsed_accounting_for_freeze(start) < time_out:
            if self.handle_heavy():
                return
            elif self.lib():
                pass
            elif self.click_resonance(send_click=False, time_out=0)[0]:
                pass
            else:
                self.click(interval=0.1)
            self.sleep(0.05)

    def heavy_wait_highlight_down(self):
        use_mouse = self.has_long_action()
        if use_mouse:
            self.task.mouse_down()
            wait = lambda: not self.has_long_action()
        else:
            if self.has_cd('resonance'):
                self.click(interval=0.1)
                self.sleep(0.05)
                return False
            self.task.send_key_down(self.get_resonance_key())
            wait = lambda: not self.is_forte_full()
        ret = self.task.wait_until(wait, time_out=1.2)
        if use_mouse:
            self.task.mouse_up()
        else:
            self.task.send_key_up(self.get_resonance_key())
        self.sleep(0.01)
        return ret

    def handle_heavy(self):
        handled = False
        start = time.time()
        while self.is_forte_full() and self.time_elapsed_accounting_for_freeze(start) < 3:
            self.heavy_wait_highlight_down()
            handled = True
        return handled

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro:
            self.logger.info(
                f'set priority as high because has_intro {has_intro}')
            return Priority.FAST_SWITCH + 1
        else:
            return super().do_get_switch_priority(current_char, has_intro, target_low_con)
