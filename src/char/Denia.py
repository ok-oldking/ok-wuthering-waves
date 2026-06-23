from src.char.BaseChar import BaseChar


class Denia(BaseChar):

    def do_perform(self):
        # 等待入场动画结束
        if self.has_intro:
            self.wait_intro(1.2)
        self.click_resonance()
        self.sleep(0.5)
        # 第一段大招
        self.click_liberation()
        # 普攻四下
        self.continues_normal_attack(2.8)
        # 闪避
        self.continues_right_click(0.05)
        # 普攻两下
        self.continues_normal_attack(1.4)
        # 放两次共鸣技能（第一次成功才放第二次）
        if self.click_resonance()[0]:
            self.click_resonance()
        # 第二段大招
        self.click_liberation()
        self.click_echo()
        self.switch_next_char()
