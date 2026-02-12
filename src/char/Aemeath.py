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
        start = time.time()
        while time.time() - start < 30:
            if self.click_liberation():
                if self.has_long_action():
                    continue
                else:
                    return
            elif self.task.find_one('aemeath_e1') or self.task.find_one('aemeath_e2'):
                self.logger.debug('found aemeath_e, click_resonance')
                self.task.screenshot('aemeath_e')
                self.click_resonance(has_animation=True, animation_min_duration=0.5)
                if self.has_long_action():
                    continue
                else:
                    return
            elif self.has_long_action():
                self.f_break()
                self.heavy_attack(0.8)
            else:
                self.click(interval=0.1)
            self.sleep(0.01)

    # def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
    #     if has_intro:
    #         return Priority.MAX
    #     return super().do_get_switch_priority(current_char, has_intro)

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro:
            self.logger.info(
                f'switch priority max because has_intro {has_intro}')
            return Priority.MAX
        else:
            return Priority.MIN + 1

    def on_combat_end(self, chars):
        self.switch_other_char()
