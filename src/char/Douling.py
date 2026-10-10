import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, SwitchPriority
from src.task.BaseWWTask import isolate_gua_strokes

GEN = 'G'  # 艮
ZHEN = 'Z'  # 震


class Douling(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._segment = 1

    def do_perform(self):
        if self._segment == 1:
            self._do_segment1()
        else:
            self._do_segment2()

    def _do_segment1(self):
        self._normal_attack_cycle(1.2)
        if self.flying():
            self.wait_down()
        self.check_combat()
        clicked = self.click_resonance(send_click=True, time_out=0.5)[0]
        if not clicked:
            self._finish_and_reset()
            return
        self.sleep(0.2)
        if self.flying():
            self.wait_down()
        self.check_combat()
        self._normal_attack_cycle(1.0)
        self._segment = 2
        self.switch_next_char()

    def _do_segment2(self):
        self.check_combat()
        self.task.jump(after_sleep=0.01)
        self.sleep(0.05)
        self.check_combat()
        if self.flying():
            self.click()
            self.sleep(0.05)
        else:
            self.wait_down()
        self.check_combat()
        self._heavy_attack_hold(2.5)
        self.click_echo(time_out=0)
        self.click_liberation()
        self._segment = 1
        self.switch_next_char()

    def _finish_and_reset(self):
        self.click_echo(time_out=0)
        self.click_liberation()
        self._segment = 1
        self.switch_next_char()

    def _normal_attack_cycle(self, duration):
        start = time.time()
        while time.time() - start < duration:
            self.cycle_start()
            if self.flying():
                self.wait_down()
                break
            self.click()
            self.cycle_sleep()

    def gua(self):
        """Reads the hexagram row (卦象) above the skill bar, left to right, e.g. 'GZZZ' (G = 艮, Z = 震).

        Returns '' when no hexagram can be read.
        """
        box = self.task.box_of_screen_scaled(3840, 2160, 1664, 1776, 2138, 1869, name='douling_gua', hcenter=True)
        found = []
        for label, kind in ((Labels.douling_gen, GEN), (Labels.douling_zhen, ZHEN)):
            for b in self.task.find_feature(label, box=box, threshold=0.65, frame_processor=isolate_gua_strokes):
                found.append((b.confidence, b.x, b.width, kind))
        kept = []
        for f in sorted(found, reverse=True):
            # both glyphs can match the same slot weakly, keep the better one
            if all(abs(f[1] - k[1]) > f[2] * 0.6 for k in kept):
                kept.append(f)
        return ''.join(k[3] for k in sorted(kept, key=lambda k: k[1]))

    def _heavy_attack_hold(self, duration):
        gua = self.gua()
        if len(gua) == 1:
            # one hexagram is not enough for an enhanced heavy, holding would cast 鬼门占卦 (self damage) instead
            return
        retries = 3
        for _ in range(retries):
            self.check_combat()
            self.task.mouse_down()
            start = time.time()
            interrupted = False
            spent = 0
            while time.time() - start < duration:
                if self.flying():
                    interrupted = True
                    break
                if gua:
                    # each enhanced heavy consumes two hexagrams, release once fewer than two are left
                    self.task.next_frame()
                    spent = spent + 1 if len(self.gua()) < 2 else 0
                    if spent >= 2:
                        break
                else:
                    self.sleep(0.1)
            self.task.mouse_up()
            self.sleep(0.01)
            if not interrupted:
                return
            self.wait_down()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if self.time_elapsed_accounting_for_freeze(self.last_perform) < 8:
            return SwitchPriority.NO
        return SwitchPriority.NORMAL
