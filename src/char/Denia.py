'''
Author: LK
version:
Date: 2026-06-22 15:46:12
LastEditors: your name
LastEditTime: 2026-06-28 14:43:03
Description:
'''
from src.char.BaseChar import BaseChar
import time


class Denia(BaseChar):

    def _wait_skill_ready(self, available_fn, time_out):
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < time_out:
            self.cycle_start()
            self.check_combat()
            if available_fn():
                return True
            self.task.click()
            self.cycle_sleep()
        return available_fn()

    def do_perform(self):
        if self.has_intro:
            self.wait_intro(1.2)

        # 大招兜底：不可用则普攻等最多2s，仍不亮就普攻两下切人
        if not self._wait_skill_ready(self.liberation_available, 2):
            self.continues_normal_attack(1.4)
            self.switch_next_char()
            return

        # 共鸣兜底：不可用则普攻等最多2s，仍不亮就普攻两下切人
        if not self._wait_skill_ready(self.resonance_available, 2):
            self.continues_normal_attack(1.4)
            self.switch_next_char()
            return
        self.click_resonance()
        self.sleep(0.5)

        # 一段大招：失败则普攻两下切人
        if not self.click_liberation():
            self.continues_normal_attack(1.4)
            self.switch_next_char()
            return

        # 一段大招成功：完整 NA 连段
        self.continues_normal_attack(2.8)
        self.continues_right_click(0.05)
        self.check_combat()
        self.continues_normal_attack(1.4)

        # 二次共鸣快败：成功才走二段大招
        if self.click_resonance(time_out=2)[0]:
            self.sleep(0.5)
            # 二段大招：失败则普攻两下重试，最多重试两次
            lib_success = self.click_liberation()
            retries = 0
            while not lib_success and retries < 2:
                self.continues_normal_attack(1.4)
                lib_success = self.click_liberation()
                retries += 1
            if lib_success:
                self.sleep(0.01)

        # 声骸 + 切人
        self.click_echo()
        self.switch_next_char()
