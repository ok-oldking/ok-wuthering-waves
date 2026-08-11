import time

from src.char.BaseChar import BaseChar, SwitchPriority


class Hiyuki(BaseChar):
    """绯雪主C: 放R变身 -> 爆发宏 -> 切人。

    爆发宏分两段:
      定时段  A3 -> 闪避 -> A3 -> 长按E升空 -> 空中居合x2(第2发后点E下落)
              -> A3 -> [处决 -> A1]  (方括号内只在真有处决提示时走)
      保底段  闪避进架势 -> 居合 -> 终结重击 -> R2

    定时段按秒走: 空中居合、处决后那发A、重击接R 的容错都在 ±0.1 秒级,
    而 executor.sleep 每 0.4 秒插一次 next_frame 截图且位置不可控, 排不了这种时序。
    宽松的普攻连段仍然走框架的 continues_normal_attack。
    保底段全程看图: 被打断/寒意见底/处决时停推歪节奏都在这里补回来。
    """

    FIELD_TIME_OUT = 16.0
    INTRO_HOLD_TIMEOUT = 8.0
    STANDARD_LIB_CD_MAX = 3.5
    STANDARD_HOLD_SLICE = 1.0
    HEAVY_FORTE_TIME_OUT = 1.2

    # 定时段。标定: A3链 1.10 太早(特效没出就闪避), 1.20~1.35 都出
    M_A_CHAIN = 1.20
    M_A_INTERVAL = 0.15
    M_A_ONE = 0.55  # 处决后那发A: 接第三段, 不是新连段
    M_AFTER_DODGE = 0.35
    M_HOLD_E_RISE = 0.85  # 要够长按判定, 否则退化成点按飞不起来
    M_HOLD_E_LAND = 0.85
    M_AFTER_RISE = 0.28  # 压小第一发空中居合会被吞
    M_AIR_KENDO_INTERVAL = 0.60  # 空中动作更长, 用地面的 0.45 会吃掉第二刀
    M_KENDO_LAND = 0.55  # 小了就是拿E把最后一刀取消掉
    M_AFTER_PLUNGE = 0.90
    M_LAND_RECOVER = 0.20
    M_EXECUTE_ANIM = 1.60  # 时停期间画面静止, 找图无效只能按秒等
    AIR_KENDO_COUNT = 2
    RISE_E_WAIT = 1.2

    # 保底段。间隔要略小于居合动画(约0.5s)让点击排队, 但不能小于动画一半否则丢刀
    M_KENDO_INTERVAL = 0.45
    M_KENDO_TO_HOLD = 1.04  # 盲等回退用; 长按不进输入缓冲, 落在居合动画里会被丢
    KENDO_RELEASE_TO_HOLD = 0.35  # 架势图标灭=已释放, 之后只剩0.3~0.4秒动画尾巴
    KENDO_MAX_CLICKS = 4
    HEAVY_TO_R = 0.80  # 标定: <=0.35 必顶掉重击, 0.6/0.7 偶发, 0.95 停顿明显
    GROUND_KENDO_COUNT_FIRST = 3  # 6链本场第一轮多一刀
    GROUND_KENDO_COUNT = 2
    LIB_FORTE_SETTLE = 0.6  # 等图标渲染, 否则会把"刚解锁没画出来"当成没解锁
    M_DODGE_TO_KENDO = 0.30
    STANCE_WAIT = 0.8
    TAIL_TIME_OUT = 6.0
    KENDO_RETRY_STRIDE = 3
    R2_ENERGY_WAIT = 6.0  # 能量不够时R是空放, 后面还要干按4~9秒, 必须补到能开
    M_ENERGY_A_INTERVAL = 0.35
    R2_REPEAT_INTERVAL = 0.2
    R2_HOLD_FIRST = 9.05  # 本场第一轮蓄3段
    R2_HOLD = 4.05  # 之后每轮1段

    LIB2_KENDO_COUNT = 3
    HOLD_LIB_TIME_OUT = 8.0
    HOLD_LIB_CD_WAIT = 1.5
    POST_LIB2_TEAM_WAIT = 1.0
    WAIT_LOCK_TIME_OUT = 2.0

    OUTRO_HARD_LIMIT = 25.0
    OUTRO_STALL_TIME = 6.0
    CON_TOP_UP_CHAIN = 0.5
    SWITCH_TARGET_NAME = 'char_suisui'
    DIRECT_SWITCH_INDEX = 1
    LIB_ANIM_WAIT = 4.0
    LEAVE_SWITCH_TIMEOUT = 3.5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib_permission = True
        self.lib2_count = 0
        self.just_transformed = False
        self.r2_used = False  # 本场是否放过R2, 决定蓄力档位和地面居合刀数
        self.macro_t0 = 0.0
        self.macro_marks = []
        # 关掉框架的切人自动按F: 默认 not is_healer 对主C是True, 会在每次交棒时
        # 替她按掉处决, 等她走到轴上那个F位时已经 skip F 了
        self.check_f_on_switch = False

    def switch_out(self, con_full=False):
        super().switch_out(con_full)
        self.lib2_count = 0
        self.just_transformed = False

    def reset_state(self):
        # 不能用 on_combat_end: 绯雪放完R2就切走, 战斗结束时在场的是穗穗,
        # 她的 on_combat_end 永不执行, r2_used 会一直是 True
        super().reset_state()
        self.r2_used = False

    def do_perform(self):
        self.click_echo(time_out=0)

        # 带变奏入场时先按住 intro_motion_freeze_duration 秒再读大招图标:
        # 入场动画期间 HUD 假阳性 -> click_liberation 空放 -> 一路点普攻到超时
        if self.has_intro or not self.liberation_available():
            self.hold_attack_until_lib(
                min_hold=self.intro_motion_freeze_duration if self.has_intro else 0.0)

        if self.has_long_action() and self.task.get_cd('liberation') <= self.STANDARD_LIB_CD_MAX:
            self.perform_standard()

        lib_ok = False
        # 只看"这次站场变身了没有"。挂在 has_long_action2() 下面的话,
        # 变身瞬间那个判定常常是 False, 整段爆发会被跳过
        if self.just_transformed:
            self.just_transformed = False
            lib_ok = self.transform_macro()

        if not lib_ok and self.has_long_action2():
            lib_ok = self.perform_lib()
        if not lib_ok and self.lib_permission and self.liberation_available():
            lib_ok = self.hold_liberation()

        self.leave(skip_outro=lib_ok)

    def hold_attack_until_lib(self, min_hold=0.0, timeout=None):
        """按住攻击键直到大招亮起。心念靠长按打出的强化重击攒, 点普攻攒得慢。"""
        timeout = self.INTRO_HOLD_TIMEOUT if timeout is None else timeout
        start = time.time()
        self.task.mouse_down()
        try:
            while self.time_elapsed_accounting_for_freeze(start) < timeout:
                if self.time_elapsed_accounting_for_freeze(start) >= min_hold \
                        and self.liberation_available():
                    return True
                self.sleep(0.1)
        finally:
            self.task.mouse_up()
        return False

    def perform_standard(self):
        """常世身: 按住攻击键攒心念 -> 放大招变身。这里一下普攻都不点。"""
        while self.has_long_action() and self.field_elapsed() < self.FIELD_TIME_OUT:
            if self.liberation_available() and self.click_liberation(click_f=False):
                self.just_transformed = True
                return
            self.click_echo(time_out=0)
            self.click_resonance(send_click=False, time_out=0, click_f=False)
            self.hold_attack_until_lib(timeout=self.STANDARD_HOLD_SLICE)
            self.sleep(0.05)

    def field_elapsed(self):
        return self.time_elapsed_accounting_for_freeze(self.last_perform)

    def transform_macro(self):
        """变身后的爆发。Returns: R2 是否放出去了。"""
        ground = self.GROUND_KENDO_COUNT_FIRST if not self.r2_used else self.GROUND_KENDO_COUNT
        self.logger.info(f'hiyuki macro: A3-dodge-A3 -> rise -> air kendo x{self.AIR_KENDO_COUNT} '
                         f'-> A3 -> [execute] -> dodge -> kendo x{ground} -> heavy -> R2')
        # 整段关掉脱战判定: 爆发期间常有"目标丢失"误报, 一抛异常 R2 就没了
        previous = getattr(self.task, 'skip_combat_check', False)
        self.task.skip_combat_check = True
        try:
            self.macro_start()
            self.attack_chain()
            self.macro_dodge(self.M_AFTER_DODGE)
            self.attack_chain()
            self.macro_rise()

            for i in range(self.AIR_KENDO_COUNT):
                last = i == self.AIR_KENDO_COUNT - 1
                self.macro_kendo(self.M_KENDO_LAND if last else self.M_AIR_KENDO_INTERVAL)
            # "第二发居合的同时点E下落"落到宏里是"这一刀挥出去之后紧接着按E",
            # 真按在同一瞬间 E 会把居合取消掉。点按不是长按
            self.macro_tap_e(self.M_AFTER_PLUNGE)

            self.attack_chain()
            if self.macro_execute():
                # 只有处决真打出来才补: 处决打断A链, 这一发重接第三段回寒意。
                # 没处决时补它就是硬接第四段, 紧接着又被闪避切掉
                self.click()
                self.macro_mark('a_after_f')
                self.macro_wait(self.M_A_ONE)
            return self.finish_with_r2()
        finally:
            self.task.skip_combat_check = previous

    def attack_chain(self):
        """一条普攻连段, 点到 A3 特效出现。收招时刻从第一下点击算起, 跟点了几下无关。"""
        self.continues_normal_attack(self.M_A_CHAIN, interval=self.M_A_INTERVAL)
        self.macro_mark('a3')

    def finish_with_r2(self):
        """闪避进架势 -> 居合 -> 终结重击 -> R2。

        居合刀数不预先决定, 由架势图标说了算: 一直点, 图标一灭说明最后一刀已释放。
        图标是在释放那一刻灭的(慢放确认), 所以按住攻击键的基准从"点击"换成了"释放",
        点击到释放之间那段不确定的排队被自动吸收掉。
        """
        start = time.time()
        self.enter_kendo_stance()

        clicked = 0
        released = None
        while clicked < self.KENDO_MAX_CLICKS:
            self.macro_kendo(self.M_KENDO_INTERVAL)
            clicked += 1
            # 查图标放在下一次点击之前: 图标已经有整整一个间隔去更新
            if not self.in_kendo_stance():
                released = time.time()
                break

        if released is not None:
            hold_at = released + self.KENDO_RELEASE_TO_HOLD
        else:
            hold_at = time.time() + max(0.0, self.M_KENDO_TO_HOLD - self.M_KENDO_INTERVAL)

        if not self.task.wait_until(self.lib_heavy_available, time_out=self.LIB_FORTE_SETTLE):
            self.recover_kendo(start)
            hold_at = time.time() + self.M_KENDO_TO_HOLD  # 补救打乱了节奏, 重新起算
        self.logger.info(f'hiyuki macro: {clicked} kendo, released={released is not None}, '
                         f'lib_forte={bool(self.lib_heavy_available())}')
        return self.hold_heavy_into_r2(hold_at)

    def recover_kendo(self, start):
        """终结重击没亮就接着补。没亮无非被打断吞刀 或 寒意见底居合没出来,
        两者画面上分不清, 所以按连点次数轮换: 连点几下还没亮就补普攻重进架势。"""
        since_reset = 0
        while not self.lib_heavy_available():
            if self.time_elapsed_accounting_for_freeze(start) >= self.TAIL_TIME_OUT:
                self.logger.warning('hiyuki macro: lib forte never lit up, going to R anyway')
                return
            if since_reset >= self.KENDO_RETRY_STRIDE or not self.in_kendo_stance():
                self.attack_chain()
                self.enter_kendo_stance()
                since_reset = 0
            self.macro_kendo()
            since_reset += 1

    def enter_kendo_stance(self):
        """闪避进架势。等不到标记也照样往下走, 真正的判据是终结重击亮没亮。"""
        self.macro_dodge(self.M_DODGE_TO_KENDO)
        return bool(self.task.wait_until(self.in_kendo_stance, time_out=self.STANCE_WAIT))

    def in_kendo_stance(self):
        return bool(self.task.find_one('hiyuki_left', threshold=0.5))

    def lib_heavy_available(self):
        return bool(self.task.find_one('hiyuki_lib_forte', threshold=0.7))

    def r2_press_time(self):
        return self.R2_HOLD if self.r2_used else self.R2_HOLD_FIRST

    def energy_ready(self):
        """大招是能量门控不是CD门控: 图标上没有数字, has_cd('liberation') 永远是假的。"""
        return self.current_liberation() > 0

    def top_up_energy(self):
        """R2 能量不够就补普攻, 补到能开为止。不设次数上限, 只有时间上限。

        位置必须在终结重击之前: R 是在重击动画里按下的, 到那时才发现不够就晚了。
        Returns: 补了几下, 0 = 本来就够。
        """
        if self.energy_ready():
            return 0
        start = time.time()
        n = 0
        while self.time_elapsed_accounting_for_freeze(start) < self.R2_ENERGY_WAIT:
            self.click()
            n += 1
            self.macro_mark(f'energy_a{n}')
            self.macro_wait(self.M_ENERGY_A_INTERVAL)
            if self.energy_ready():
                self.logger.info(f'hiyuki macro: R2 energy full after {n} extra attack(s)')
                return n
        self.logger.warning(f'hiyuki macro: R2 energy still not full after {n}, releasing anyway')
        return n

    def hold_heavy_into_r2(self, hold_at):
        """按住攻击键打出终结重击 -> 重击动画里按住R蓄力 -> R2。

        淬寒满时按住攻击键的第一下就直接放出终结重击, 攻击键这边没有蓄力过程;
        蓄力全发生在重击动画期间 R 被按住的那段。
        R 的时刻相对"按住攻击键那一刻"算, 必须落在重击动画里: 早了 R 当场就放
        重击整个没打, 晚了重击演完中间停一下。

        Args:
            hold_at: 打算按住攻击键的墙钟时刻, 已经过了就立刻按。
        """
        # 补过能量的话原时刻作废: 那几下普攻自己要收招, 长按会落在普攻动画里被丢
        if self.top_up_energy():
            hold_at = time.time() + self.M_A_ONE
        press_time = self.r2_press_time()

        self.macro_wait(max(0.0, hold_at - time.time()))
        start = time.time()
        self.task.mouse_down()
        self.macro_mark('heavy')
        try:
            self.macro_wait(self.HEAVY_TO_R)
            self.task.send_key_down(self.get_liberation_key())
            self.macro_mark('R_down')
        finally:
            self.task.mouse_up()
        # 时间轴打在这里而不是重击之前 —— 否则 heavy/R_down 两个标记不在里面,
        # "重击和R之间发生了什么"这类问题就查不了
        self.logger.info(f'hiyuki macro timeline: {self.macro_timeline()}')

        r2_start = time.time()
        last = self.R2_REPEAT_INTERVAL
        while time.time() - r2_start < press_time:
            if time.time() - r2_start >= last:
                self.task.send_key_down(self.get_liberation_key())  # 重发防掉键
                last += self.R2_REPEAT_INTERVAL
            self.sleep(0.05, check_combat=False)
        self.task.send_key_up(self.get_liberation_key())

        self.r2_used = True
        self.record_liberation_use()
        self.task.in_liberation = True
        self.task.wait_until(lambda: self.task.in_team()[0], time_out=self.POST_LIB2_TEAM_WAIT)
        self.task.in_liberation = False
        self.add_freeze_duration(start, time.time() - start)
        self.lib2_count = 0
        self.logger.info(f'hiyuki macro: R2 released (held {press_time:.1f}s, '
                         f'{self.HEAVY_TO_R:.2f}s after heavy)')
        return True

    def macro_wait(self, sec):
        """精确等待。

        不走 executor.sleep: 它每 sleep_check_interval(0.4s) 会无条件插一次
        next_frame 截图(skip_combat_check 只跳过判定逻辑, 跳不过截图), 插入位置不可控。
        空中居合/重击接R 的容错在 ±0.1 秒级, 排不了这种时序。
        切成 0.1 秒一片并在片间检查任务是否被停用, 精度保持在 10 毫秒。
        """
        end = time.time() + sec
        while True:
            left = end - time.time()
            if left <= 0:
                return
            time.sleep(min(0.1, left))
            self.task.executor.check_enabled(check_pause=False)

    def macro_start(self):
        self.macro_t0 = time.time()
        self.macro_marks = []

    def macro_mark(self, name):
        """记一笔输入发出的时刻。对着录像就能看出是哪一下被吞了:
        某个输入的时刻比画面上那段动作的起点还早, 就是它把前一段取消掉了。"""
        self.macro_marks.append(f'{name}@{time.time() - self.macro_t0:.2f}')

    def macro_timeline(self):
        return ' '.join(self.macro_marks)

    def macro_rise(self):
        """长按E升空。空中那两刀全指着这一下, 白按一次整段就没了, 而日志上看不出来
        (E_down/E_up 只证明键发出去了), 所以把CD读出来记进日志区分两种毛病。"""
        cd = self.task.get_cd('resonance')
        if cd > 0 and self.RISE_E_WAIT > 0:
            self.logger.warning(f'hiyuki macro: resonance on cd {cd:.1f}s at rise, waiting')
            self.task.wait_until(lambda: self.task.get_cd('resonance') <= 0,
                                 post_action=self.click, time_out=self.RISE_E_WAIT)
        self.macro_hold_e(self.M_HOLD_E_RISE, self.M_AFTER_RISE)

    def macro_dodge(self, settle):
        self.task.click(key='right')
        self.macro_mark('dodge')
        self.macro_wait(settle)

    def macro_hold_e(self, hold, settle):
        self.task.send_key_down(self.get_resonance_key())
        self.macro_mark('E_down')
        try:
            # macro_wait 现在会在任务被停用时抛异常, 长按必须放在 finally 里松开
            self.macro_wait(hold)
        finally:
            self.task.send_key_up(self.get_resonance_key())
        self.record_resonance_use()
        self.macro_mark('E_up')
        self.macro_wait(settle)

    def macro_tap_e(self, settle):
        self.task.send_key(self.get_resonance_key())
        self.record_resonance_use()
        self.macro_mark('E_tap')
        self.macro_wait(settle)

    def macro_kendo(self, settle=None):
        self.click()
        self.macro_mark('kendo')
        self.macro_wait(self.M_KENDO_INTERVAL if settle is None else settle)

    def macro_execute(self):
        """处决。没有提示就跳过 —— F 同时是拾取键, 空按会点到场景物件。
        框架的 can_break 只在带战斗判定的 sleep 里刷新, 定时段用不到, 所以自己抓帧现查。
        Returns: 处决是否真按出去了。
        """
        if not self.execute_available():
            return False
        start = time.time()
        self.task.send_key('f')
        self.macro_mark('F')
        self.task.can_break = False  # 自己按掉的, 别让切人时再按一次
        # 提示消失=确实触发; 之后时停画面静止, 找图看不出演到哪只能按秒等
        self.task.wait_until(lambda: not self.execute_prompt(), time_out=0.8)
        self.macro_wait(self.M_EXECUTE_ANIM)
        self.add_freeze_duration(start, time.time() - start)
        return True

    def execute_available(self):
        """只认屏幕中央那个F提示。另外两个信号都不能当判据:
        can_break 是粘滞标记(别的角色场上看到一次击破就一直是True, 实测五轮五次空按F);
        f_break_full 是顿感条满, 条满但处决窗口没开时按下去会被当成拾取吃掉。
        """
        self.task.next_frame()
        prompt = bool(self.execute_prompt())
        if prompt and not self.task.is_pick_f():
            return True
        bar_full = bool(self.task.find_one('f_break_full', threshold=0.92))
        self.logger.info(f'hiyuki macro: skip F (f_break={prompt} bar_full={bar_full})')
        return False

    def execute_prompt(self):
        box = self.task.box_of_screen(0.2, 0.2, 0.75, 0.8, hcenter=True, vcenter=True)
        return bool(self.task.find_one('f_break', box=box, target_height=720))

    def perform_lib(self):
        """宏没走通时的兜底: 原版的反应式循环。"""
        timeout = self.FIELD_TIME_OUT
        while self.has_long_action2() and self.field_elapsed() < timeout:
            self.click_echo(time_out=0)
            lib_heavy_avail = self.lib_heavy_available()
            is_timeout = self.field_elapsed() >= timeout - 0.5

            if self.lib_permission and self.liberation_available() and (
                    self.lib2_count >= self.LIB2_KENDO_COUNT or is_timeout):
                if self.hold_liberation():
                    self.lib2_count = 0
                    return True

            res = self.click_resonance(send_click=False, time_out=0, click_f=False)
            if res and res[0]:
                if is_timeout:
                    break
                self.macro_hold_e(self.M_HOLD_E_LAND, self.M_LAND_RECOVER)
            elif lib_heavy_avail:
                if is_timeout:
                    break
                if self.wait_locked(self.WAIT_LOCK_TIME_OUT):
                    self.heavy_forte_fast(self.lib_heavy_available)
                if self.task.wait_until(self.liberation_available, post_action=self.click,
                                        time_out=0.5):
                    if self.wait_locked(self.WAIT_LOCK_TIME_OUT) and self.hold_liberation():
                        self.lib2_count = 0
                        return True
                self.lib2_count += 1
                self.sleep(0.1)
            elif self.in_kendo_stance():
                self.task.wait_until(lambda: not self.in_kendo_stance(),
                                     post_action=self.click, time_out=3.0)
                if is_timeout:
                    break
                self.sleep(0.1)
            elif bool(self.task.find_one('hiyuki_right', threshold=0.5)):
                self.task.click(key='right', interval=1.0)
                self.sleep(0.1)
            else:
                self.click()
            self.sleep(0.05)

        if self.lib_permission and self.liberation_available() and self.hold_liberation():
            self.lib2_count = 0
            return True
        return False

    def hold_liberation(self):
        """长按大招键放R2。相对原版三处修补: 返回值要代表真的按下去了;
        补 record_liberation_use(); 循环退出后继续按住蓄力(循环条件是
        liberation_available(), R2一放出去它立刻变False, 当场松手等于一点没蓄)。
        """
        if not self.task.use_liberation:
            return False

        last_click = 0
        sent = False
        start = time.time()
        while self.task.in_team()[0] and (
                self.liberation_available()
                or self.task.get_cd('liberation') <= self.HOLD_LIB_CD_WAIT) \
                and time.time() - start < self.HOLD_LIB_TIME_OUT:
            if time.time() - start > last_click:
                self.task.send_key_down(self.get_liberation_key())
                sent = True
                last_click += 0.2
            self.sleep(0.05, check_combat=False)

        if not sent:
            self.task.send_key_up(self.get_liberation_key())
            return False

        press_time = self.r2_press_time()
        charge_start = time.time()
        last = 0.0
        while time.time() - charge_start < press_time:
            if time.time() - charge_start >= last:
                self.task.send_key_down(self.get_liberation_key())
                last += self.R2_REPEAT_INTERVAL
            self.sleep(0.05, check_combat=False)
        self.r2_used = True

        self.task.in_liberation = True
        self.task.send_key_up(self.get_liberation_key())
        self.task.wait_until(lambda: self.task.in_team()[0], time_out=self.POST_LIB2_TEAM_WAIT)
        self.task.in_liberation = False
        self.record_liberation_use()
        self.add_freeze_duration(start, time.time() - start)
        self.logger.info(f'hold_liberation end {time.time() - start:.1f}s')
        return True

    def leave(self, skip_outro=False):
        """唯一的离场口。整段关掉脱战判定: 打完爆发常有"目标丢失->判定脱战"的误报,
        那时 check_combat() 一抛异常切人就再也执行不到了。"""
        previous = getattr(self.task, 'skip_combat_check', False)
        self.task.skip_combat_check = True
        try:
            if skip_outro and self.direct_switch(assume_intro=True):
                return
            if not skip_outro:
                self.ensure_outro()
            self.switch_next_char()
        except Exception as e:
            self.logger.warning(f'hiyuki leave failed ({e}), trying direct switch')
            if not self.direct_switch():
                raise
        finally:
            self.task.skip_combat_check = previous

    def ensure_outro(self):
        """协奏不满就不离场。两个安全阀: 协奏卡住不涨, 或站够绝对上限。"""
        # 先等读数稳定: 大招刚放完时协奏往往已经满了, 只是能量环还没渲染回来
        if self.task.wait_until(self.is_con_full, time_out=0.8):
            return True

        start = time.time()
        best_con = self.get_current_con()
        last_gain = time.time()
        while True:
            if self.is_con_full():
                return True
            if self.time_elapsed_accounting_for_freeze(start) >= self.OUTRO_HARD_LIMIT:
                self.logger.warning('hiyuki hit outro hard limit, switching without outro')
                return False
            con = self.get_current_con()
            if con > best_con + 0.01:
                best_con = con
                last_gain = time.time()
            elif time.time() - last_gain > self.OUTRO_STALL_TIME:
                self.logger.warning(f'hiyuki con stuck at {con:.2f}, switching without outro')
                return False

            if self.echo_available():
                self.click_echo(time_out=0)
                continue
            res = self.click_resonance(send_click=False, time_out=0, click_f=False)
            if res and res[0]:
                self.macro_hold_e(self.M_HOLD_E_LAND, self.M_LAND_RECOVER)
                self.macro_kendo()
                continue
            if self.is_mouse_forte_full():
                self.heavy_forte_fast(self.is_mouse_forte_full)
                continue
            self.continues_normal_attack(self.CON_TOP_UP_CHAIN, until_con_full=True)

    def direct_switch(self, assume_intro=False):
        """按数字键直接切给交棒对象。不走 switch_next_char(): 那个内部有三处
        continues_normal_attack/click, 大招之后不想要那几下多余的A。"""
        target = self.switch_target()
        if target is None or target is self:
            return False
        slot = target.index + 1
        # 刚放完大招时直接认定协奏满: 读数滞后会把 has_intro 误判成 False,
        # 那样穗穗会以为自己空手入场跑去走开场流程
        has_intro = True if assume_intro else self.wait_con_full()

        # 大招动画期间就按住普攻并狂发切人键, 不干等动画演完: 按住普攻让动画一结束
        # 攻击立刻接上; 切人键在动画期间发出去看似白发, 但换来"能切的第一帧就切走"
        deadline = self.LIB_ANIM_WAIT + self.LEAVE_SWITCH_TIMEOUT
        start = time.time()
        self.task.mouse_down()
        try:
            while time.time() - start < deadline:
                in_team, current_index, _ = self.task.in_team()
                if in_team and current_index == target.index:
                    self.logger.info(f'hiyuki direct switched to slot {slot} '
                                     f'(intro={has_intro}, {time.time() - start:.1f}s)')
                    self.handoff_to(target, has_intro)
                    return True
                self.task.send_key(slot)
                self.sleep(0.12, check_combat=False)
        finally:
            self.task.mouse_up()
        self.logger.warning(f'hiyuki direct switch to slot {slot} failed')
        return False

    def handoff_to(self, target, has_intro):
        """复刻 switch_next_char() 内部那套交接记账。直接按数字键切人绕开了框架逻辑,
        不补的话没人的 is_current_char 是 True, get_current_char() 返回 None 会崩。

        Args:
            has_intro: 离场时协奏是否满, 必须在按切人键之前读好 ——
                切走之后能量环显示的已经是新角色的了。
        """
        self.task.in_liberation = False
        self.switch_out(con_full=has_intro)
        target.is_current_char = True
        target.has_intro = has_intro
        if has_intro and hasattr(target, 'note_intro_handoff'):
            # has_intro 是易失的: reset_state() 每次重读队伍都会清掉它,
            # 而战斗判定一抖动就会重进战斗重读队伍。给对方一个它自己保管的持久标记
            target.note_intro_handoff()
        target.last_switch_in_time = time.time()
        if has_intro:
            now = time.time()
            self.task.add_freeze_duration(now, target.intro_motion_freeze_duration, -100)
            self.last_outro_time = now

    def wait_con_full(self):
        return bool(self.task.wait_until(self.is_con_full, time_out=0.5))

    def switch_target(self):
        """交棒对象: 先按角色名找(不假设队伍顺序), 找不到再退回写死的槽位。"""
        for char in self.task.chars:
            if char is not None and char is not self and char.char_name == self.SWITCH_TARGET_NAME:
                return char
        index = self.DIRECT_SWITCH_INDEX - 1
        return next((c for c in self.task.chars if c is not None and c.index == index), None)

    def heavy_forte_fast(self, check_fun, time_out=None):
        """强化重击。BaseChar.heavy_click_forte 的 wait_until 写死2秒, 回路一直没打掉时白按满。"""
        time_out = self.HEAVY_FORTE_TIME_OUT if time_out is None else time_out
        if not check_fun():
            return False
        self.task.mouse_down()
        try:
            success = self.task.wait_until(lambda: not check_fun(), time_out=time_out)
        finally:
            self.task.mouse_up()
        self.sleep(0.05)
        return bool(success)

    def wait_locked(self, time_out):
        return bool(self.task.wait_until(self.has_long_action2, post_action=self.click,
                                         time_out=time_out))

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name in {'char_linnai', 'char_lucilla'}:
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)
