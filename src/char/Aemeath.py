import time

from src.char.BaseChar import BaseChar


class Aemeath(BaseChar):
    INTRO_LIBERATION_DELAY = 15
    HEAVY_LIBERATION_DELAY = 10
    LIBERATION_FORCE_DURATION = 20

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_wait = False
        self.human_heavy = False
        self.intro_time = -1
        self.last_liber = -1
        self.last_enhance_e = -1
        self.intro_liberation_time = -1
        self.heavy_liberation_time = -1

    def record_intro_liberation(self):
        if self.intro_liberation_time < 0:
            self.intro_liberation_time = time.time()

    def record_heavy_liberation(self):
        self.heavy_liberation_time = time.time()

    def can_cast_liberation(self):
        if self.intro_liberation_time >= 0 and (
                self.time_elapsed_accounting_for_freeze(self.intro_liberation_time) >= self.INTRO_LIBERATION_DELAY):
            return True
        if self.heavy_liberation_time >= 0 and (
                self.time_elapsed_accounting_for_freeze(self.heavy_liberation_time) >= self.HEAVY_LIBERATION_DELAY):
            return True
        return self.time_elapsed_accounting_for_freeze(self.last_liber) >= self.LIBERATION_FORCE_DURATION

    def do_perform(self):
        self.intro_time = -1
        self.should_wait = False
        if self.has_intro:
            self.record_intro_liberation()
            self.task.wait_until(self.enhance_e_available, post_action=self.click_with_interval,
                                 time_out=3.5)
            if self.check_outro() in {'char_linnai', 'char_lupa'}:
                self.intro_time = 14
            if self.check_outro() in {'chang_changli', 'char_changli2'}:
                self.intro_time = 10
        self.perform_everything()
        self.switch_next_char()

    def lib(self):
        if not self.can_cast_liberation():
            return False
        if self.click_liberation(wait_if_cd_ready=0):
            self.heavy_liberation_time = -1
            self.last_liber = time.time()
            self.f_break()
            return True
        return False

    def continue_in_intro(self):
        return self.time_elapsed_accounting_for_freeze(self.last_liber) < 30 and \
            self.time_elapsed_accounting_for_freeze(self.last_perform) < self.intro_time

    def perform_everything(self):
        start = time.time()
        self.human_heavy = False
        self.should_wait = self.has_sub_dps_intro
        if not self.should_wait:
            self.should_wait = self.time_elapsed_accounting_for_freeze(self.last_enhance_e) > 6
        while self.time_elapsed_accounting_for_freeze(start) < 1.2 or (
                self.should_wait and self.time_elapsed_accounting_for_freeze(start) < 2.6):
            self.cycle_start()
            if self.handle_heavy():
                self.should_wait = True
                start = time.time()
                self.task.next_frame()
                continue
            elif self.enhance_e_available():
                if self.click_resonance(has_animation=True, send_click=True, animation_min_duration=0.5, time_out=1.5)[
                    0]:
                    self.should_wait = False
                    self.last_enhance_e = time.time()
                    self.click_echo(time_out=0)
                    self.f_break()
                if self.has_long_action() or self.lib_cd_eminent() or self.continue_in_intro():
                    self.should_wait = True
                    start = time.time()
                else:
                    self.click(after_sleep=0.01)
                    return
            elif self.lib():
                self.should_wait = False
                start = time.time()
            else:
                self.click()
            self.cycle_sleep()

    def lib_cd_eminent(self):
        cd = self.task.get_cd('liberation')
        return self.can_cast_liberation() and (0 < cd < 1.5 or self.liberation_available())

    def enhance_e_available(self):
        return self.has_long_action() or (
                (self.task.find_one('aemeath_e1', threshold=0.7) or self.task.find_one('aemeath_e2',
                                                                                       threshold=0.7)) and not self.is_human())

    def is_human(self):
        return self.task.find_one('aemeath_human',
                                  threshold=0.75)

    def heavy_wait_highlight_down(self):
        self.task.mouse_down()
        ret = self.task.wait_until(lambda: not self.has_long_action(), time_out=1.2)
        self.task.mouse_up()
        self.sleep(0.01)
        return ret

    def handle_heavy(self):
        while self.has_long_action():
            self.heavy_wait_highlight_down()
            self.record_heavy_liberation()
            return True

    def on_combat_end(self, chars):
        self.switch_other_char()
