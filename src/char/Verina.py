import time

from src.char.BaseChar import BaseChar


class Verina(BaseChar):
    """Verina 自动战斗(辅助/治疗): 3A -> 大招 -> E -> 声骸 -> (重击) -> 跳跃 -> 2A;
    协奏满或超时则立即切人。"""

    NORMAL_ATTACK_TIME: float = 0.6
    JUMP_ATTACK_TIME: float = 0.5
    HEAVY_ATTACK_TIME: float = 0.7
    RECOVER_TIME: float = 0.8
    FIELD_TIME: float = 6.0
    HEAVY_ATTACK_INTERVAL: float = 8.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = -1

    def do_perform(self):
        self.perform_combat()
        self.switch_next_char()
        
    def perform_combat(self):
        """3A -> 大招 -> E -> 声骸 -> (重击) -> 跳跃 -> 2A; 协奏满/超时则提前结束去切人。"""
        self.start = time.time()

        self.continues_normal_attack(self.NORMAL_ATTACK_TIME)

        # 依次放 大招 -> E -> 声骸; -> 每步前检查协奏满/超时, 命中则提前结束去切人.
        for cast_skill in (self.cast_liberation, self.cast_resonance, self.cast_echo):
            if self.should_stop():
                return
            cast_skill()

        if self.should_stop():
            return

        self.task.wait_until(lambda: self.task.in_team()[0], time_out=2.0)
        self.sleep(self.RECOVER_TIME)
        
        if self.is_mouse_forte_full() and self.can_heavy_attack():
            self.heavy_attack(self.HEAVY_ATTACK_TIME)
            self.last_heavy = time.time()
        self.task.jump(after_sleep=0.01)
        self.continues_normal_attack(self.JUMP_ATTACK_TIME)

    def cast_resonance(self):
        """共鸣(E)可用则放。"""
        if self.resonance_available():
            self.click_resonance(send_click=True, time_out=0)

    def cast_liberation(self):
        """解放(大招)可用则放。"""
        if self.liberation_available():
            self.click_liberation()

    def cast_echo(self):
        """声骸可用则放。"""
        if self.echo_available():
            self.click_echo(time_out=0)

    def should_stop(self):
        """连招是否应提前结束去切人: 协奏满(攒够入场技) 或 在场超时。"""
        return self.is_con_full() or self.field_time_out()

    def can_heavy_attack(self):
        """距上次重击是否已超过最小间隔(扣除冻结时间)。"""
        return self.time_elapsed_accounting_for_freeze(self.last_heavy) >= self.HEAVY_ATTACK_INTERVAL

    def field_time_out(self):
        """在场时间是否已超过上限(扣除冻结时间)。"""
        return self.time_elapsed_accounting_for_freeze(self.start) >= self.FIELD_TIME
