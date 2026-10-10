import time

from src.char.BaseChar import BaseChar, SwitchPriority


class Lucilla(BaseChar):
    LIBERATION_ANIMATION_TIME = 3.0
    LIBERATION_HEAVY_TIME = 5.0
    HEAVY_PULSE_TIME = 0.6
    RES_HOLD_TIME = 0.8
    CHARGE_TIME_OUT = 7.2
    LIBERATION_CD_SKIP = 1.5
    ECHO_WINDOW = (0.6, 4.0)
    EXTRA_BUDGET = 4.0
    HOLD_FIELD_OUTRO = {'char_suisui'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.e_count = 0
        self.check_f_on_switch = False

    def do_perform(self):
        if not self.perform_combat():
            self.switch_next_char()

    def perform_combat(self):
        start = time.time()
        self.task.wait_until(lambda: self.task.in_team()[0], time_out=0.2)
        if self.has_intro:
            # 入场动画期间的输入会被吞, 不是延迟执行
            self.sleep(self.intro_motion_freeze_duration, check_combat=False)
        self.task.next_frame()

        self.e_count = 0
        # 接穗穗延奏时手上已经有两格, 补一格即可; 空手入场要攒满三格
        target = 1 if self.has_intro else 3
        hold_field = self.has_intro and self.check_outro() in self.HOLD_FIELD_OUTRO

        while self.time_elapsed_accounting_for_freeze(start) < self.CHARGE_TIME_OUT:
            if self.e_count >= target:
                if self.perform_liberation():
                    self.switch_next_char(free_intro=self.fill_con())
                    return True
                # 大招没放出说明有一发 E 被吞了, 退一格重攒
                self.e_count = max(0, self.e_count - 1)
            elif self.time_elapsed_accounting_for_freeze(start) >= 2 and not hold_field \
                    and not self.liberation_available() \
                    and self.task.get_cd('liberation') > self.LIBERATION_CD_SKIP:
                self.logger.info('Lucilla liberation on long cd, switch to save time')
                break
            self.charge_once()
        return False

    def charge_once(self):
        if not self.resonance_available():
            self.sleep(0.15)
            return
        self.hold_resonance(self.RES_HOLD_TIME)
        # 长按不够长会退化成点按, 且完全无声: 进了 CD 才算真的放出来
        cd = self.task.get_cd('resonance')
        if cd <= 0:
            self.logger.warning(f'Lucilla E swallowed (held {self.RES_HOLD_TIME:.2f}s, '
                                f'cd still {cd:.1f}s), not counted')
            return
        self.e_count += 1
        self.logger.info(f'Lucilla E #{self.e_count}, resonance cd now {cd:.1f}s')
        self.task.next_frame()

    def hold_resonance(self, duration):
        self.task.send_key_down(self.get_resonance_key())
        try:
            self.sleep(duration, check_combat=False)
        finally:
            self.task.send_key_up(self.get_resonance_key())
        self.record_resonance_use()

    def perform_liberation(self):
        """放大招变身并输出。返回大招是否真的放出去了。"""
        if not self.task.use_liberation:
            return False

        # 不用 click_liberation: 它内部的 while not in_team() 在变身形态下会卡死。
        # 【sent 是必须的】: 图标在刚上场/动画期间会假阴性, 先看再按会一次都不按就跳出,
        # 而且后面那个 available() 仍然是 False, 连"没放出来"都报不出来 —— 整段空转
        start = time.time()
        sent = 0
        while time.time() - start < 1.5:
            if sent and not self.liberation_available():
                break  # 图标灭了 = 变身形态已激活
            self.send_liberation_key()
            sent += 1
            self.sleep(0.15, check_combat=False)
        if self.liberation_available():
            self.logger.warning(f'Lucilla liberation icon still lit after {sent} presses, not fired')
            return False

        self.record_liberation_use()
        self.logger.info(f'Lucilla perform lib ({sent} presses)')
        self.sleep(self.LIBERATION_ANIMATION_TIME, check_combat=False)
        self.pulse_heavy_attack(self.LIBERATION_HEAVY_TIME)
        # 被打断时能量会剩, 变身一结束就作废, 所以按图标打空为准
        self.pulse_until(lambda: not self.is_mouse_forte_full(), 'forte drained')
        self.logger.info(f'Lucilla perform lib end ({time.time() - start:.1f}s)')
        return True

    def pulse_heavy_attack(self, total_time):
        """脉冲重击: 每拍重新按下, 某拍被打断下一拍自动恢复。Q 在窗口内反复发。"""
        start = time.time()
        last_echo = 0
        while time.time() - start < total_time:
            elapsed = time.time() - start
            # 变身动画期间按 Q 会被吞, 形态结束后按又没了增益, 只有中间这段有效
            if self.ECHO_WINDOW[0] <= elapsed <= self.ECHO_WINDOW[1] and time.time() - last_echo >= 0.3:
                self.send_echo_key()
                last_echo = time.time()
            self.heavy_pulse()

    def pulse_until(self, cond, name):
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < self.EXTRA_BUDGET:
            if cond():
                self.logger.info(f'Lucilla {name} after {time.time() - start:.1f}s')
                return True
            self.heavy_pulse()
        self.logger.warning(f'Lucilla {name} timed out')
        return False

    def heavy_pulse(self):
        self.task.mouse_down()
        try:
            self.sleep(self.HEAVY_PULSE_TIME, check_combat=False)
        finally:
            self.task.mouse_up()
        self.sleep(0.02, check_combat=False)

    def fill_con(self):
        """确认协奏满再交棒。变身刚结束时能量环读数滞后, 直接读会读成 0。"""
        if self.task.wait_until(self.is_con_full, time_out=1.5):
            return True
        # 读数已经该稳了还没满, 说明是真的短了(被打断), 站着等没用, 得打
        self.logger.info(f'Lucilla con reads {self.get_current_con():.2f} after settle, attacking')
        if self.pulse_until(self.is_con_full, 'con filled'):
            return True
        self.logger.warning(f'Lucilla con still reads {self.get_current_con():.2f}, '
                            f'next char gets no intro')
        return False

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name in {'char_verina', 'char_shorekeeper',
                                                                    'char_suisui'}:
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)
