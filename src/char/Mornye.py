import time
from src.char.BaseChar import BaseChar, Priority


class Mornye(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = 0

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.33)
        self.check_f_on_switch = True
        if not self.on_air():
            if self.combo_limit():
                self.logger.debug("perform quick actions")
                if self.click_echo():
                    return self.switch_next_char()
                elif self.click_resonance()[0]:
                    """地面奶一下，防止主C死亡"""
                    return self.switch_next_char()
                else:
                    self.continues_normal_attack(0.1)
                    return self.switch_next_char()
            self.not_on_air_actions()

        if self.on_air():
            self.on_air_actions()
        self.switch_next_char()

    def on_air(self):
        return self.has_long_action2()

    def on_air_actions(self):
        detect_ready = self.echo_available()
        self.logger.debug("on_air start attacking")
        start = time.time()
        while (
                time.time() - start < 10
                and self.on_air()
        ):
            if self.detect_elbow_strike(detect_ready):
                self.logger.debug("Detected an elbow strike, attempting to reset.")
                self.task.wait_until(lambda: not self.detect_elbow_strike(detect_ready), 
                                     post_action=lambda: self.continues_right_click(0.05), time_out=1.5)
            self.click_liberation()               
            if self.on_air() and self.is_mouse_forte_full():
                self.logger.debug("mouse forte full, heavy attack")
                if self.heavy_click_forte(check_fun=lambda: self.is_mouse_forte_full() and not self.detect_elbow_strike(detect_ready)):
                    if self.detect_elbow_strike(detect_ready):
                        continue
                    elif not self.task.wait_until(lambda: self.is_con_full(), time_out=1.5):
                        self.logger.debug("not condition full, try clicking echo")
                        self.click_echo(duration=0.2)
                    self.last_heavy = time.time()
                    self.check_f_on_switch = False
                    break
            self.click_resonance()
            self.click()
            self.sleep(0.01)
        self.logger.debug("finished attacking on_air")

    def not_on_air_actions(self):
        self.logger.debug("not on_air start attacking")
        start = time.time()
        try_douge = True
        while time.time() - start < 10 and not self.on_air():
            self.click()
            self.click_resonance()
            self.check_combat()
            self.sleep(0.1)
            if self.is_mouse_forte_full():
                if try_douge:
                    self.task.click(key="right")
                    try_douge = False
                self.heavy_attack()
                self.sleep(0.3)

    def on_combat_end(self, chars):
        self.switch_other_char()

    def combo_limit(self):
        return self.time_elapsed_accounting_for_freeze(self.last_heavy) < 23
        
    def detect_elbow_strike(self, ready):
        return ready and not self.available('echo', check_color=True)

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro and current_char.char_name in {'char_aemeath'}:
            return Priority.MAX
        return super().do_get_switch_priority(current_char, has_intro)
