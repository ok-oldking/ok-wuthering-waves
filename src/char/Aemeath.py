import time

from src.char.BaseChar import BaseChar, Priority


class Aemeath(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_none_normal = time.time()

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.2)
        self.perform_everything()
        self.switch_next_char()

    def lib(self):
        if self.click_liberation():
            self.f_break()
            return True

    def perform_everything(self):
        self.last_none_normal = time.time()
        while self.time_elapsed_accounting_for_freeze(self.last_none_normal) < 3:
            old_none_normal = self.last_none_normal
            self.last_none_normal = time.time()
            if self.task.find_one('aemeath_e1', threshold=0.8) or self.task.find_one('aemeath_e2', threshold=0.8):
                if self.click_resonance(has_animation=True, send_click=True, animation_min_duration=0.5, time_out=1.5):
                    self.click_echo(time_out=0)
                    self.f_break()
                    self.switch_mech()
                    self.click(after_sleep=0.1)
                if self.has_long_action() or self.lib():
                    continue
                else:
                    self.click()
                    return
            elif self.lib():
                if self.has_long_action():
                    continue
                elif self.lib():
                    continue
                else:
                    continue
            elif self.handle_heavy():
                pass
            else:
                self.switch_mech()
                self.click(interval=0.1)
                self.last_none_normal = old_none_normal
            self.sleep(0.01)

    def switch_mech(self):
        start = time.time()
        while not self.liberation_available() and time.time() - start < 3 and self.task.find_one('aemeath_human',
                                                                                                 threshold=0.8):
            self.send_resonance_key()
            self.sleep(0.1)

    def heavy_wait_highlight_down(self):
        self.task.mouse_down()
        ret = self.task.wait_until(lambda: not self.has_long_action, time_out=1.2)
        self.task.mouse_down()
        self.sleep(0.05)
        return ret

    def handle_heavy(self):
        while self.has_long_action():
            self.heavy_wait_highlight_down()
            self.last_none_normal = time.time()
            return True

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro:
            self.logger.info(
                f'switch priority max because has_intro {has_intro}')
            return Priority.MAX
        else:
            return super().do_get_switch_priority(current_char, has_intro, target_low_con)

    def on_combat_end(self, chars):
        self.switch_other_char()
