import time

from src.char.BaseChar import BaseChar, Priority


class Aemeath(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_wait = False
        self.human_heavy = False

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1)
        elif not self.liberation_available():
            self.switch_mech()
        self.perform_everything()
        self.switch_next_char()

    def lib(self):
        if self.click_liberation():
            self.f_break()
            return True

    def perform_everything(self):
        start = time.time()
        self.human_heavy = False
        self.should_wait = self.has_intro
        while self.time_elapsed_accounting_for_freeze(start) < 2.2 or (
                self.should_wait and self.time_elapsed_accounting_for_freeze(start) < 10):
            if self.handle_heavy():
                self.should_wait = True
                start = time.time()
            elif self.lib():
                self.should_wait = True
                start = time.time()
                if self.is_human():
                    self.switch_mech()
                    return
            elif self.enhance_e_available():
                if self.click_resonance(has_animation=True, send_click=True, animation_min_duration=0.5, time_out=1.5):
                    self.should_wait = False
                    self.click_echo(time_out=0)
                    self.f_break()
                    self.switch_mech()
                    self.click(after_sleep=0.1)
                if self.has_long_action() or self.lib_cd_eminent():
                    self.should_wait = True
                    start = time.time()
                else:
                    self.click()
                    return
            else:
                self.switch_mech()
                self.click(interval=0.1)
            self.sleep(0.01)

    def lib_cd_eminent(self):
        cd = self.task.get_cd('liberation')
        return 0 < cd < 1.5 or self.liberation_available()

    def enhance_e_available(self):
        return (self.task.find_one('aemeath_e1', threshold=0.7) or self.task.find_one('aemeath_e2',
                                                                                      threshold=0.7)) and not self.is_human()

    def switch_mech(self):
        start = time.time()
        while not self.liberation_available() and time.time() - start < 3 and self.is_human():
            self.send_resonance_key()
            self.sleep(0.1)

    def is_human(self):
        return self.task.find_one('aemeath_human',
                                  threshold=0.75)

    def heavy_wait_highlight_down(self):
        self.task.mouse_down()
        ret = self.task.wait_until(lambda: not self.has_long_action, time_out=1.2)
        self.task.mouse_up()
        self.sleep(0.01)
        return ret

    def handle_heavy(self):
        while self.has_long_action():
            self.heavy_wait_highlight_down()
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
