from src.char.BaseChar import BaseChar, SwitchPriority
import time


class Denia(BaseChar):

    # 成功打完 rotation 切走后，至少经过此秒数才允许切回 Denia
    REENTRY_COOLDOWN = 20
    # 逃生舱：当前角色站场超过此秒数时，即使 Denia 仍在冷却中也放行，
    # 避免队友死亡/卡死导致全员 NO 软卡死
    ESCAPE_FIELD_TIME = 15

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 成功完成 rotation 的时刻（切走前赋值），作为切回冷却的锚点；
        # 失败路径不赋值，故失败切走后可立即切回
        self._last_success_time = -1

    def _wait_skill_ready(self, available_fn, time_out):
        # 用 cycle_start/cycle_sleep 做 0.1s 帧节流的技能就绪轮询；
        # 以 time_elapsed_accounting_for_freeze 计时，避免大招动画冻结时钟误判超时
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < time_out:
            self.cycle_start()
            self.check_combat()
            if available_fn():
                return True
            self.task.click()
            self.cycle_sleep()
        return available_fn()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        # 冷却期内默认返回 NO 硬阻止切回 Denia；
        # 逃生舱：当前角色站场 > ESCAPE_FIELD_TIME 时放行，防止队伍卡死
        if self._last_success_time >= 0 and \
                self.time_elapsed_accounting_for_freeze(self._last_success_time) < self.REENTRY_COOLDOWN:
            if current_char and current_char.last_switch_in_time > 0 and \
                    self.time_elapsed_accounting_for_freeze(
                        current_char.last_switch_in_time) > self.ESCAPE_FIELD_TIME:
                return super().get_switch_priority(current_char, has_intro, target_low_con)
            return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)

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

        # 声骸 + 切人；记录成功完成时刻，用于切回冷却
        self.click_echo()
        self._last_success_time = time.time()
        self.switch_next_char()
