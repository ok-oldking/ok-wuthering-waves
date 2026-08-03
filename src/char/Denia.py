from src.char.BaseChar import BaseChar


class Denia(BaseChar):

    def do_perform(self):
        """聚爆队副C轴：E聚怪 → R1进舞形态 → 强化E×2 → 普攻攒共形能量 → R2蚀域 → 声骸 → 切走

        变奏入场后先普攻（变奏后第一次普攻从第四段开始，直接放技能会重置连段）。
        打完这套协奏接近满，延奏让爱弥斯变奏入场吃热熔增益（斑驳粉饰之沫/聚爆加深）。
        """
        self.check_f_on_switch = True
        if self.has_intro:
            self.wait_intro(1.2)
            self.click()
        if self.flying() and not self.liberation_available() and not self.resonance_available():
            self.wait_down()
        self.click_resonance(time_out=0.5)
        if self.click_liberation():
            # 舞形态：连放两个强化共鸣技能（消耗黯核，每颗增伤150%）
            self.click_resonance(has_animation=True, animation_min_duration=0.3, time_out=1.2)
            self.click_resonance(has_animation=True, animation_min_duration=0.3, time_out=1.2)
            # 普攻攒满共形能量（舞形态普攻消耗虚质粒子，充能加速）
            self.continues_normal_attack(1.5)
            # 二段大招：召唤蚀域（每4秒聚怪 + 后台热熔伤害，持续30秒）
            self.click_liberation()
        else:
            # 大招未充好：普攻补协奏后让位
            self.continues_normal_attack(1.2)
        self.click_echo(time_out=0)
        self.switch_next_char()
