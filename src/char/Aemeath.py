import time

from src.char.BaseChar import BaseChar, Priority


class Aemeath(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_perform(self):
        self.perform_everything()
        self.switch_next_char()

    def lib(self):
        if self.click_liberation():
            self.f_break()
            return True

    def perform_everything(self):
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < 10:
            if self.lib():
                if self.has_long_action():
                    continue
                elif self.lib():
                    continue
                else:
                    return
            elif self.task.find_one('aemeath_e1', threshold=0.8) or self.task.find_one('aemeath_e2', threshold=0.8):
                if self.click_resonance(has_animation=True, send_click=True, animation_min_duration=0.5):
                    self.click_echo(time_out=0)
                    self.f_break()
                    self.click(after_sleep=0.1)
                if self.has_long_action() or self.lib():
                    continue
                else:
                    return
            elif self.handle_heavy():
                pass
            else:
                self.click(interval=0.1)
            self.sleep(0.01)

    def handle_heavy(self):
        if self.has_long_action():
            while self.task.find_one('aemeath_human_heavy'):
                self.send_resonance_key()
                self.sleep(0.1)
            self.heavy_attack(0.6)
            self.sleep(0.1)
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
