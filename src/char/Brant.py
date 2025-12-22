import time

from src.char.BaseChar import BaseChar, Priority


class Brant(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.perform_anchor = 0
        self.attribute = 0
        self.char_lupa = None

    def reset_state(self):
        super().reset_state()
        self.attribute = 0
        self.char_lupa = None

    def do_perform(self):
        self.decide_teammate()
        if self.has_intro:
            self.continues_normal_attack(1.3)
            if self.check_outro() in {'char_lupa'} and self.perform_in_outro():
                return self.switch_next_char()
        if self.is_forte_full() and self.resonance_available():
            self.resonance_forte_full()
            self.last_liberation = -1
            self.perform_anchor = time.time()
            return self.switch_next_char()
        if not self.need_fast_perform() and not self.is_forte_full() and self.click_liberation():
            self.continues_normal_attack(0.8)
        if not self.still_in_liberation() and self.echo_available():
            self.click_echo()
            return self.switch_next_char()
        self.click_jump_with_click(1.3)
        if self.is_forte_full() and self.resonance_available():
            self.resonance_forte_full()
            self.perform_anchor = time.time()
            self.in_liberaction = 0
            return self.switch_next_char()
        if not self.still_in_liberation() and self.echo_available():
            self.click_echo()
        self.switch_next_char()

    def still_in_liberation(self):
        return self.time_elapsed_accounting_for_freeze(self.last_liberation) < 12

    def perform_in_outro(self):
        click = 0
        start = time.time()
        timeout = 1.5
        liber = False
        if self.still_in_liberation():
            timeout = 10
            liber = True
        while True:
            if self.is_forte_full() and self.resonance_available():
                self.logger.debug('perform anchar')
                self.resonance_forte_full()
                self.last_liberation = -1
                self.wait_down(4)
                if liber:
                    break
                    return True
            if self.liberation_available() and self.click_liberation():
                start = time.time()
                timeout = 10
                liber = True
            if time.time() - start > timeout:
                break
            if self.task.has_lavitator and not self.flying():
                self.flick_resonance()
                self.sleep(0.2)
            elif not self.task.has_lavitator:
                self.task.jump()
            self.click()
            click = 1 - click
            self.check_combat()
            self.task.next_frame()
        self.click_echo()
        return True

    def resonance_forte_full(self):
        start = time.time()
        while self.resonance_available() and self.is_forte_full():
            self.send_resonance_key()
            if time.time() - start > 1:
                break
            self.check_combat()
            self.task.next_frame()

    def click_jump_with_click(self, delay=0.1):
        click = 0
        if self.task.has_lavitator and not self.flying():
            self.flick_resonance()
            self.sleep(0.2)
            click = 1
        start = time.time()
        while True:
            if time.time() - start > delay:
                break
            if click == 0:
                self.task.jump()
            else:
                self.click()
            click = 1 - click
            self.task.next_frame()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        self.decide_teammate()
        if self.time_elapsed_accounting_for_freeze(self.perform_anchor, True) < 4:
            return Priority.MIN
        if self.still_in_liberation():
            return Priority.MAX
        if has_intro and current_char.char_name in {'char_lupa'}:
            return Priority.MAX
        base = 0
        if self.char_lupa is not None and self.char_lupa.still_in_liberation():
            base = -20
        return super().do_get_switch_priority(current_char, has_intro) + base

    def decide_teammate(self):
        if self.attribute > 0:
            return
        from src.char.Lupa import Lupa
        for _, char in enumerate(self.task.chars):
            self.logger.debug(f'teammate char: {char.char_name}')
            if isinstance(char, Lupa):
                self.char_lupa = char
                self.attribute = 1
                return
        self.attribute = 1
        return

    def flick_resonance(self, time_out=0.2, send_click=True):
        if send_click and self.resonance_available():
            self.task.wait_until(lambda: self.current_resonance() > 0, post_action=self.click_with_interval,
                                 time_out=0.2)
        if self.current_resonance() > 0 and self.resonance_available():
            self.task.wait_until(lambda: not self.resonance_available(), post_action=self.send_resonance_key,
                                 time_out=time_out)
            return True
        return False

    def wait_down(self, time_out=1.2, click=True):
        self.task.wait_until(lambda: not self.flying(), post_action=self.click_with_interval if click else None,
                             time_out=time_out)
