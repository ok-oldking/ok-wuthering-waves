import time

from src.char.BaseChar import BaseChar


class Aemeath(BaseChar):
    LIBERATION_COOLDOWN = 25
    LIBERATION_FORCE_DURATION = 30
    LIB2_PREPARE_WINDOW = 8
    INTRO_LIBERATION_DELAY = 14

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enhance_e_cast_this_turn = False
        self.lib2_cast_this_turn = False
        self.must_cast_lib2_this_turn = False

    def lib2_available(self):
        return bool(self.task.find_one('aemeath_lib2', threshold=0.7))

    def do_perform(self):
        self.enhance_e_cast_this_turn = False
        self.lib2_cast_this_turn = False
        self.must_cast_lib2_this_turn = self.has_all_buff() and self.has_intro
        if not self.must_cast_lib2_this_turn:
            while self.has_long_action():
                if self.handle_heavy():
                    self.sleep(0.3)
            return self.switch_next_char()
        elif self.has_intro:
            self.continues_normal_attack(2.1)

        self.perform_everything()

        self.switch_next_char()

    def lib(self):
        is_lib2 = self.lib2_available()
        liberated = self.click_liberation(wait_if_cd_ready=0)
        if liberated:
            if is_lib2:
                self.lib2_cast_this_turn = True
        return liberated

    def record_enhance_e(self):
        self.enhance_e_cast_this_turn = True

    def required_action_pending(self):
        return (self.has_intro and not self.enhance_e_cast_this_turn) or (
                self.must_cast_lib2_this_turn and not self.lib2_cast_this_turn)

    def continue_after_action(self, start):
        if self.has_long_action():
            return time.time()
        if self.required_action_pending():
            return start
        return None

    def perform_everything(self):
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < 12:
            self.cycle_start()
            if self.handle_heavy():
                start = time.time()
                if not self.f_break():
                    self.sleep(0.1)
                self.check_combat()
                continue
            if self.lib():
                if self.lib2_cast_this_turn:
                    return
                action_performed = True
            elif self.enhance_e_available():
                if self.click_resonance(has_animation=True, send_click=True, animation_min_duration=0.5,
                                        time_out=1.5)[0]:
                    self.record_enhance_e()
                    self.click_echo(time_out=0)
                    self.task.next_frame()
                self.lib()
                if self.lib2_cast_this_turn:
                    return
                action_performed = True
            else:
                self.click()
                action_performed = False
            if action_performed:
                start = self.continue_after_action(start)
                if start is None:
                    return
            self.cycle_sleep()

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
        if self.heavy_wait_highlight_down():
            return True
        return False

    def on_combat_end(self, chars):
        self.switch_other_char()
