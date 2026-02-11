import time

from src.char.BaseChar import BaseChar, Priority

aemeath_yellow_color = {
    "r": (214, 255),
    "g": (116, 167),
    "b": (78, 119),
}


class Aemeath(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.perform_under_intro()
        else:
            if self.flying():
                self.wait_down()
            self.fast_attack()
        self.switch_next_char()

    def perform_under_intro(self):
        """变奏入场时的战斗逻辑"""
        self.logger.debug("perform under intro")
        start = time.time()
        while time.time() - start < 6 and not self.is_forte_full():
            self.click()
            self.sleep(0.1)
        self.f_break()
        if self.liberation_available_first() and self.click_liberation():
            self.perform_under_liber()
            return
        self.normal_attack_until_full_resonance()

    def perform_under_liber(self):
        """一段解放时的战斗逻辑"""
        self.logger.debug("perform under liberation")
        start = time.time()
        normal_attack_num = 0
        """一段解放buff持续30秒，打2次强化e，60秒内重击即可释放二段解放"""
        while time.time() - start < 60 and not self.liberation_available_second():
            self.normal_attack_until_full_resonance(under_liber=True)
            normal_attack_num += 1
            if normal_attack_num > 1 and self.check_heavy():
                self.heavy_attack(0.8)
            self.sleep(0.1)
        if self.liberation_available_second():
            self.click_liberation()
            return

    def fast_attack(self):
        """快速攻击战斗逻辑"""
        self.click_echo(time_out=0)
        self.continues_normal_attack(1, 0.2)
        self.sleep(0.1)
        if self.resonance_available():
            self.click_resonance(has_animation=True, send_click=False)
        else:
            self.click_resonance(has_animation=False, send_click=False)

    def normal_attack_until_full_resonance(self, under_liber=False):
        """普攻至共鸣技能满，释放强化e战斗逻辑"""
        start = time.time()
        while time.time() - start < 12:
            if self.resonance_available():
                self.click_resonance(has_animation=True, send_click=False)
                return
            if under_liber and self.liberation_available():
                return
            self.click()
            self.sleep(0.1)
        self.click_resonance(has_animation=False, send_click=False)

    def do_get_switch_priority(
        self, current_char: BaseChar, has_intro=False, target_low_con=False
    ):
        if has_intro:
            return Priority.MAX
        return super().do_get_switch_priority(current_char, has_intro)

    def resonance_available(self):
        """共鸣技能是否可用，通过像素判断"""
        percent = super().current_resonance_circle(aemeath_yellow_color)
        self.logger.debug(f"aemeath resonance yellow percent {percent}")
        return percent > 0.3

    def liberation_available_first(self):
        """一段解放技能是否可用，先判断白色像素，再通过黄色像素判断"""
        return self.liberation_white() and self.liberation_yellow_circle()

    def liberation_available_second(self):
        """二段解放技能是否可用，先判断白色像素，再非通过黄色像素判断"""
        return (
            self.liberation_white() and not self.liberation_yellow_circle()
        )

    # 白色像素判断解放技能是否可用，适用于一段和二段解放的情况
    def liberation_white(self):
        percent = super().current_liberation()
        self.logger.debug(f"aemeath liberation white percent {percent}")
        return percent > 0.01

    def liberation_yellow_circle(self):
        percent = super().current_liberation_circle(aemeath_yellow_color)
        self.logger.debug(f"aemeath liberation yellow percent {percent}")
        return percent > 0.8

    def check_heavy(self):
        if not self.task.in_team_and_world():
            return False
        best = self.task.find_best_match_in_box(
            self.task.get_box_by_name("box_target_enemy_long"),
            ["has_target", "no_target"],
            threshold=0.6,
        )
        self.logger.debug(f"check res {best}")
        return best

    def on_combat_end(self, chars):
        self.switch_other_char()
