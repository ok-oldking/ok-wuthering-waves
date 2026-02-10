import time
from src.char.BaseChar import BaseChar


class Mornye(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = 0

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.33)
        self.check_f_on_switch = True
        if self.on_air():
            self.click_liberation()
            self.on_air_actions()
            if self.liberation_available():
                self.click_liberation()
            else:
                self.click_echo()
        else:
            if self.combo_limit():
                self.logger.debug("perform quick actions")
                ## 地面奶一下，防止主C死亡
                self.click_resonance()
                if not self.click_echo():
                    self.continues_normal_attack(0.1)
                return self.switch_next_char()
            self.not_on_air_actions()
        self.switch_next_char()

    def on_air(self):
        return self.has_long_action2()

    def on_air_actions(self):
        self.logger.debug("on_air start attacking")
        start = time.time()
        while (
            time.time() - start < 10
            and self.on_air()
            and not self.is_mouse_forte_full()
        ):
            self.click()
            self.click_resonance()
            self.check_combat()
            self.sleep(0.1)
        # 可能会被打断，或者强制落地，这时候就不继续重置重击了
        if self.on_air() and self.heavy_click_forte(check_fun=self.is_mouse_forte_full):
            self.logger.debug("on air and mouse forte full, heavy attack")
            self.last_heavy = time.time()
            self.check_f_on_switch = False
        self.logger.debug("finished attacking on_air")

    def not_on_air_actions(self):
        self.logger.debug("not on_air start attacking")
        start = time.time()
        while time.time() - start < 10 and not self.on_air():
            self.click()
            self.click_resonance()
            self.check_combat()
            self.sleep(0.1)
            if self.is_mouse_forte_full():
                self.heavy_attack()
                self.sleep(0.3)

    def on_combat_end(self, chars):
        self.switch_other_char()

    def combo_limit(self):
        return self.time_elapsed_accounting_for_freeze(self.last_heavy) < 20
