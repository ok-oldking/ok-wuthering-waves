import time

from src.char.BaseChar import BaseChar, CharType, get_default_buff_time


class Chisa(BaseChar):
    CHAINSAW_SAW_TIME = 1.3

    def is_dps_config(self):
        return self.task and self.task.char_config.get("Chisa DPS")

    def get_char_type(self):
        if self.is_dps_config():
            return CharType.MAIN_DPS
        return super().get_char_type()

    def get_buff_time(self):
        if self.is_dps_config():
            return get_default_buff_time(CharType.MAIN_DPS)
        return super().get_buff_time()

    def do_perform(self):
        if not self.is_dps_config():
            return self.do_fast_support()
        return self.do_dps_perform()

    def do_fast_support(self):
        """聚爆队辅助轴：E上标记 → 声骸 → 大招 → 进电锯模式锯几下 → 切走

        大招后立刻接强化E进入电锯模式（大招使电锯攻击+120%且+40回路能量），
        电锯攻击视为共鸣解放伤害、攒协奏最快，打满协奏触发延奏
        （聚爆层数上限+3），随后马上把输出窗口让给队友。
        """
        self.check_f_on_switch = True
        if self.has_intro:
            self.record_support_buff()
        else:
            if self.flying() and not self.liberation_available() and not self.resonance_available():
                self.wait_down()
            self.click_resonance(time_out=0.5)
        self.click_echo(time_out=0)
        if self.click_liberation():
            self.record_support_buff()
        self.enter_chainsaw_and_saw()
        return self.switch_next_char()

    def enter_chainsaw_and_saw(self):
        """回路满则长按共鸣键强化E进入电锯模式，再按住普攻锯几下攒协奏。"""
        if self.flying():
            self.wait_down()
        if self.is_forte_full():
            self.task.send_key(self.get_resonance_key(), down_time=1.2)
            self.sleep(0.15, check_combat=False)
            self.task.mouse_down()
            try:
                self.sleep(self.CHAINSAW_SAW_TIME, check_combat=False)
            finally:
                self.task.mouse_up()
            return True
        self.continues_normal_attack(0.5)
        return False

    def record_support_buff(self):
        """Track the buff granted by Chisa's Intro Skill or Resonance Liberation."""
        self.last_buff_time = time.time()

    def switch_out(self, con_full=False):
        support_buff_time = self.last_buff_time
        super().switch_out(con_full=con_full)
        if not self.is_dps_config():
            self.last_buff_time = support_buff_time

    def do_dps_perform(self):
        timeout = 2.5
        self.check_f_on_switch = True
        if self.has_intro:
            self.continues_normal_attack(0.8)
            timeout = 2.3
        if self.flying() and not self.liberation_available() and not self.resonance_available():
            self.wait_down()
        self.click_echo()
        start = time.time()
        under_liber = False
        while time.time() - start < timeout:
            if time.time() - start < 0.5 and self.click_liberation():
                start = time.time()
                under_liber = True
                timeout = 10
                self.sleep(0.2)
            if time.time() - start < 0.5 and not self.is_forte_full() and self.click_resonance()[0]:
                start = time.time()
                if timeout != 10:
                    timeout = 1.7
            if (under_liber or self.is_dps_config()) and self.is_forte_full() and self.perform_forte():
                self.check_f_on_switch = False
                return self.switch_next_char()
            self.click()
            self.check_combat()
            self.task.next_frame()
        self.switch_next_char()

    def perform_forte(self):
        if self.flying():
            self.wait_down()
        self.task.send_key(self.get_resonance_key(), down_time=1.2)
        if self.is_forte_full():
            return False
        self.heavy_attack(3.5)
        return True
