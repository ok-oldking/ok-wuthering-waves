import time

from src.char.BaseChar import BaseChar, SwitchPriority


class Aemeath(BaseChar):
    LIBERATION_COOLDOWN = 25
    LIBERATION_FORCE_DURATION = 30
    LIB2_PREPARE_WINDOW = 8
    INTRO_LIBERATION_DELAY = 14

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_wait = False
        self.intro_time = -1
        self.last_liber = -1
        self.last_enhance_e = -1
        self.intro_liberation_time = -1
        self.pending_lib2 = False

    def lib2_cooldown_anchor(self):
        if self.last_liber >= 0:
            return self.last_liber
        combat_start = getattr(self.task, 'combat_start', -1)
        return combat_start if combat_start > 0 else -1

    def lib2_cooldown_left(self):
        anchor = self.lib2_cooldown_anchor()
        if anchor < 0:
            return 0
        elapsed = self.time_elapsed_accounting_for_freeze(anchor)
        return max(0, self.LIBERATION_COOLDOWN - elapsed)

    def liberation_cooldown_left(self):
        if self.last_liber < 0:
            return 0
        elapsed = self.time_elapsed_accounting_for_freeze(self.last_liber)
        return max(0, self.LIBERATION_COOLDOWN - elapsed)

    def lib1_unlock_anchor(self):
        if self.last_liber >= 0:
            return self.last_liber
        return getattr(self.task, 'combat_start', -1)

    def record_intro_liberation(self):
        self.intro_liberation_time = time.time()

    def intro_lib1_ready(self):
        return self.intro_liberation_time >= 0 and (
                self.time_elapsed_accounting_for_freeze(self.intro_liberation_time)
                <= self.INTRO_LIBERATION_DELAY)

    def lib1_unlocked(self):
        if self.intro_lib1_ready():
            return True
        anchor = self.lib1_unlock_anchor()
        return anchor >= 0 and (
                self.time_elapsed_accounting_for_freeze(anchor) >= self.LIBERATION_FORCE_DURATION)

    def can_cast_lib1(self):
        return self.liberation_cooldown_left() <= 0 and self.lib1_unlocked()

    def can_cast_liberation(self):
        return self.can_cast_lib1()

    def lib2_available(self):
        return bool(self.task.find_one('aemeath_lib2', threshold=0.7))

    def preparing_lib2(self):
        return self.lib2_cooldown_anchor() >= 0 and (
                self.lib2_cooldown_left() < self.LIB2_PREPARE_WINDOW)

    def should_wait_for_lib2(self):
        return self.pending_lib2 or self.preparing_lib2()

    def should_wait_for_enhance_e(self):
        return self.time_elapsed_accounting_for_freeze(self.last_enhance_e) > 12

    def record_enhance_e(self):
        self.last_enhance_e = time.time()

    def record_heavy_liberation(self):
        self.pending_lib2 = True

    def record_liberation(self, is_lib2):
        if is_lib2:
            self.pending_lib2 = False
            self.last_liber = time.time()
            self.last_enhance_e = self.last_liber
        else:
            self.intro_liberation_time = -1

    def do_perform(self):
        self.intro_time = -1
        self.should_wait = False
        if self.has_intro:
            self.record_intro_liberation()
            self.continues_normal_attack(1.2)
            if self.check_outro() in {'char_linnai', 'char_lupa'}:
                self.intro_time = 14
            if self.check_outro() in {'chang_changli', 'char_changli2'}:
                self.intro_time = 10
        self.perform_everything()
        self.switch_next_char()

    def lib(self):
        is_lib2 = self.lib2_available()
        if not is_lib2 and not self.can_cast_lib1():
            return False
        if not self.click_liberation(wait_if_cd_ready=0):
            return False
        self.record_liberation(is_lib2)
        self.f_break()
        return True

    def continue_in_intro(self):
        return self.time_elapsed_accounting_for_freeze(self.last_liber) < 30 and \
            self.time_elapsed_accounting_for_freeze(self.last_perform) < self.intro_time

    def perform_everything(self):
        start = time.time()
        self.should_wait = self.should_wait_for_lib2() or self.should_wait_for_enhance_e()
        if not self.should_wait:
            self.should_wait = self.has_intro and self.liberation_cooldown_left() < 12
        while self.time_elapsed_accounting_for_freeze(start) < 1.2 or (
                self.should_wait and self.time_elapsed_accounting_for_freeze(start) < 3.6):
            self.cycle_start()
            if self.handle_heavy():
                self.f_break()
                start = time.time()
                self.should_wait = self.should_wait_for_lib2()
                self.task.next_frame()
                continue
            if self.intro_lib1_ready() and self.lib():
                start = time.time()
                self.should_wait = self.should_wait_for_lib2()
            elif self.enhance_e_available():
                if self.click_resonance(has_animation=True, send_click=True, animation_min_duration=0.5,
                                        time_out=1.5)[0]:
                    self.record_enhance_e()
                    self.click_echo(time_out=0)
                    self.f_break()
                    self.task.next_frame()
                if (
                        self.intro_lib1_ready() and self.can_cast_lib1() and self.liberation_available()) or self.has_long_action():
                    start = time.time()
                else:
                    self.click(after_sleep=0.01)
                    return
            elif self.lib():
                start = time.time()
                self.should_wait = self.should_wait_for_lib2()
                continue
            else:
                self.click()
            self.cycle_sleep()

    def lib_cd_eminent(self):
        cd = self.task.get_cd('liberation')
        return self.lib1_unlocked() and (0 < cd < 1.5 or self.liberation_available())

    def enhance_e_available(self):
        return self.task.find_one('aemeath_e1', threshold=0.7) or self.task.find_one('aemeath_e2',
                                                                                     threshold=0.7)

    def heavy_wait_highlight_down(self):
        self.task.mouse_down()
        ret = self.task.wait_until(lambda: not self.has_long_action(), time_out=1.2)
        self.task.mouse_up()
        self.sleep(0.01)
        return ret

    def handle_heavy(self):
        if not self.has_long_action():
            return False
        prepares_lib2 = self.preparing_lib2()
        if self.heavy_wait_highlight_down():
            if prepares_lib2:
                self.record_heavy_liberation()
            return True
        return False

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if self.should_wait_for_lib2():
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def on_combat_end(self, chars):
        self.switch_other_char()
