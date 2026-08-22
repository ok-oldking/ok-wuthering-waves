import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar


class Qingxiao(BaseChar):
    HEAVY_TIMEOUT = 2
    # 图标连续"暗"满该时长才确认释放(去抖)
    HEAVY_CONFIRM = 0.25

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.must_cast_lib_this_turn = False

    def do_perform(self):
        self.must_cast_lib_this_turn = self.has_all_buff() and self.has_intro

        if not self.must_cast_lib_this_turn:
            self.cast_enhanced_resonance()
            return self.switch_next_char()

        start = time.time()
        broke_on_h2 = False
        if self.must_cast_lib_this_turn:
            while self.time_elapsed_accounting_for_freeze(start) < 18:
                self.cycle_start()
                if heavy := self.handle_heavy():
                    self.f_break()
                    if heavy == Labels.qingxiao_h2:
                        # 第二次(强化)重击:图标已被 handle_heavy 确认灭(真释放)才回到这 → 开 R
                        if self.task is not None and not self.liberation_available():
                            # h2 多段命中的后半段会把 R 能量打满;等 R 图标亮(上限 1.5s)再开大
                            self.task.wait_until(lambda: self.liberation_available(), time_out=1.5)
                        self.click_liberation()
                        broke_on_h2 = True
                        break
                elif self.cast_enhanced_resonance():
                    pass
                else:
                    self.click()
                self.cycle_sleep()
            if not broke_on_h2:
                self.handle_heavy()

        if broke_on_h2 and self.task is not None:
            # R 未放出时(按钮没亮),强化重击落地动画还没结束就切会撞 not_in_team ERROR;等切人判定稳定再切
            self.task.wait_until(lambda: self.task.in_team()[0], time_out=1.0)
        self.switch_next_char()

    def enhanced_resonance_available(self):
        return bool(self.task.find_one(Labels.qingxiao_e, threshold=0.7))

    def cast_enhanced_resonance(self):
        if not self.enhanced_resonance_available():
            return False
        return self.click_resonance(
            has_animation=True,
            animation_min_duration=0.5,
            time_out=1.5,
        )[0]

    def heavy_available(self):
        return self.task.find_one(Labels.qingxiao_h1, threshold=0.7) or self.task.find_one(Labels.qingxiao_h2,
                                                                                           threshold=0.7)

    def handle_heavy(self):
        heavy = self.heavy_available()
        if not heavy:
            return False

        start = time.time()
        dark_since = None
        exited_confirm = False
        self.task.mouse_down()
        try:
            # 去抖:图标暗掉后睡确认窗,复核仍暗才算真释放
            while self.time_elapsed_accounting_for_freeze(start) < self.HEAVY_TIMEOUT:
                if self.heavy_available():
                    dark_since = None
                    self.task.next_frame()
                else:
                    if dark_since is None:
                        dark_since = time.time()
                    self.sleep(self.HEAVY_CONFIRM)
                    self.task.next_frame()
                    if not self.heavy_available():
                        exited_confirm = True
                        break
                    dark_since = None
        finally:
            self.task.mouse_up()
        self.sleep(0.01)
        if exited_confirm:
            return heavy.name
        return False
