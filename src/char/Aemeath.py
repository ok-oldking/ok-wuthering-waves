import time

from src.char.BaseChar import BaseChar, Priority

text_heavy_color = {
    'r': (250, 255),
    'g': (219, 227),
    'b': (45, 56)
}

class Aemeath(BaseChar):
    def do_perform(self):
        if not self.has_intro:
            """快速切人战斗逻辑"""
            self.click_echo(time_out=0)
            self.continues_normal_attack(1, 0.1)
            if not self.is_forte_full():
                self.click_resonance()
            return self.switch_next_char()

        """变奏入场时的战斗逻辑"""
        self.logger.debug("aemeath perform under intro")
        start = time.time()
        self.continues_normal_attack(0.5, 0.1)
        while time.time() - start < 6 and not self.is_forte_full():
            self.click(interval=0.1)
            self.sleep(0.01)
        if self.click_liberation():
            self.perform_under_liberation()
        self.click_echo(time_out=0)
        self.click(after_sleep=0.1)
        self.switch_next_char()

    def perform_under_liberation(self):
        enhance_e = 0
        start = time.time()
        while time.time() - start < 30:
            # 2次强化e后尝试重击，或者在r1状态下如果r2准备好了也尝试重击
            if enhance_e > 1 or self.liberation_available():
                if self.has_heavy_attack():
                    self.heavy_attack(0.8)
                    self.sleep(0.2)
            if self.click_liberation():
                self.sleep(0.1)
                return
            if self.has_enhance_e():
                self.logger.debug("found aemeath_e, click_resonance")
                self.click_resonance(has_animation=True, animation_min_duration=0.5)
                enhance_e += 1
                # 强化e后尽量尝试击破，提高击破覆盖率
                self.f_break()
                self.sleep(0.1)
                continue
            self.click(interval=0.1)
            self.sleep(sec=0.01, check_combat=True)

    def has_heavy_attack(self):
        if self.has_long_action():
            return True
        box = self.task.box_of_screen_scaled(
            3840, 2160, 2848, 2013, 2856, 2023, name="box_aemeath_heavy", hcenter=False
        )
        self.task.draw_boxes(box.name, box)
        percentage = self.task.calculate_color_percentage(text_heavy_color, box)
        self.logger.debug(f"aemeath text_heavy_color percentage: {percentage}")
        return percentage > 0.75

    def has_enhance_e(self):
        if self.task.find_one("aemeath_e1", threshold=0.75):
            self.logger.debug("aemeath found enhance_e1")
            return True
        if self.task.find_one("aemeath_e2", threshold=0.75):
            self.logger.debug("aemeath found enhance_e2")
            return True
        self.logger.debug("aemeath no enhance_e found")
        return False

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro:
            self.logger.info(f"switch priority max because has_intro {has_intro}")
            return Priority.MAX
        else:
            return Priority.MIN + 1

    def on_combat_end(self, chars):
        self.switch_other_char()
