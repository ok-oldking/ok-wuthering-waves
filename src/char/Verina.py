import time

from src.char.BaseChar import BaseChar


class Verina(BaseChar):
    """Verina 自动战斗(辅助/治疗): 3A -> E -> 大招 -> 声骸 -> (重击) -> 跳跃 -> 2A;
    协奏满或超时则立即切人。"""

    # 开场普攻(3A)时长 (秒)
    NORMAL_ATTACK_TIME: float = 1.0
    # 跳后收尾普攻时长 (秒)
    JUMP_ATTACK_TIME: float = 0.8
    # 重击时长 (秒)
    HEAVY_ATTACK_TIME: float = 0.7
    # 声骸/大招收招后摇 (秒): 等过去再跳, 否则跳跃/普攻被动画吞掉(代码执行了但游戏忽略输入)
    RECOVER_TIME: float = 0.8
    # 在场总时长上限 (秒): 超过则跳过剩余连招直接切人, 防赖场
    FIELD_TIME: float = 7.0
    # 重击最小间隔 (秒): 防止重击过于频繁
    HEAVY_ATTACK_INTERVAL: float = 8.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = -1

    def do_perform(self):
        self.perform_combat()
        self.switch_next_char()

    def perform_combat(self):
        """3A -> E -> 大招 -> 声骸 -> (重击) -> 跳跃 -> 2A; 协奏满/超时则提前结束去切人。"""
        self.start = time.time()

        self.continues_normal_attack(self.NORMAL_ATTACK_TIME)

        # 依次放 E -> 大招 -> 声骸; 每步前检查协奏满/超时, 命中则提前结束去切人.
        for cast_skill in (self.cast_resonance, self.cast_liberation, self.cast_echo):
            if self.should_stop():
                return
            cast_skill()

        if self.should_stop():
            return

        # 收尾: 等收招动画结束(画面恢复+后摇)再动作, 否则重击/跳跃/普攻被动画吞.
        self.task.wait_until(lambda: self.task.in_team()[0], time_out=2.0)
        self.sleep(self.RECOVER_TIME)
        # 重击: 能量满且距上次重击 >= HEAVY_ATTACK_INTERVAL 才打.
        if self.is_mouse_forte_full() and self.can_heavy_attack():
            self.heavy_attack(self.HEAVY_ATTACK_TIME)
            self.last_heavy = time.time()
        # 跳跃(取消后摇)接一小段普攻, 然后由 do_perform 切人.
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
