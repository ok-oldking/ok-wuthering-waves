import time

from src.char.BaseChar import BaseChar, Priority


class Aemeath(BaseChar):
    def do_perform(self):
        self.perform_everything()
        self.click_echo(time_out=0)
        self.f_break()
        self.click(after_sleep=0.1)
        self.switch_next_char()

    def perform_everything(self):
        use_lib = not self.has_intro
        start = time.time()
        while time.time() - start < 30:
            if use_lib and self.click_liberation():
                self.click(after_sleep=0.2)
                if self.has_long_action():
                    continue
                elif self.liberation_available():
                    continue
                else:
                    return
            elif self.task.find_one('aemeath_e1', threshold=0.6) or self.task.find_one('aemeath_e2', threshold=0.6):
                self.logger.debug('found aemeath_e, click_resonance')
                self.click_resonance(has_animation=True, animation_min_duration=0.5)
                self.click(after_sleep=0.2)
                use_lib = True
                if self.has_long_action() or self.liberation_available():
                    self.f_break()
                    continue
                else:
                    return
            elif self.has_long_action():
                self.heavy_attack(0.6)
                self.sleep(0.2)
            else:
                self.click(interval=0.1)
            self.sleep(0.01)

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro:
            self.logger.info(
                f'switch priority max because has_intro {has_intro}')
            return Priority.MAX
        else:
            return Priority.MIN + 1

    def on_combat_end(self, chars):
        self.switch_other_char()
