import time
from src.char.BaseChar import BaseChar, SwitchPriority
class Hiyuki(BaseChar):
    """绯雪主C: 放R变身 -> 爆发宏 -> 切人。
    爆发宏分两段:
      定时段  A3 -> 闪避 -> A3 -> 长按E升空 -> 空中居合x2(第2发后点E下落)
              -> A3 -> [处决 -> A1]  (方括号内只在真有处决提示时走)
      收尾段  闪避进架势 -> 居合x3(启动轴, 2链以上)/x2(循环轴与0命启动轴) -> 预输入重击 -> 重击中按住R -> R2
    启动轴(本场第一轮)可以换版本, 见 OPENER_KIND:
      'kendo4' A3 -> 闪避 -> A3 -> 长按E升空 -> 空中居合x2 -> 点E落地
               -> A3 -> [处决 -> A续第三段] -> 收尾段(居合x2)     (0命/0+1 常规 4 居合轴, 默认)
      'ee'    R1 -> E点按升空 -> E长按落地 -> 收尾段(居合x3)       (2链以上)
      'short' A3 -> 处决(有提示时)/闪避 -> E点按升空 -> E长按落地 -> 收尾段(居合x3)
      'full'  = 原来的五居合 (2链以上寒意才够)
    省掉空中两刀、处决和两条A链, 那几处都是 ±0.1 秒级的窗口, 开场被打断最容易在那里断
    两段都按秒走: 空中居合、处决后那发A、重击接R 的容错都在 ±0.1 秒级,
    而 executor.sleep 每 0.4 秒插一次 next_frame 截图且位置不可控, 排不了这种时序。
    宽松的普攻连段仍然走框架的 continues_normal_attack。
    收尾段不读屏: 架势图标要等下一个动作才灭, 拿它判收刀只会停住再多出一发普攻。
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
    # 启动轴用哪一版, 只管本场第一轮, 循环轴不受影响:
    #   'kendo4' = 常规 4 居合轴(0命/0+1, 默认)。0 命寒意经济:
    #             R1 50 + A3x3(57x3=171) + 处决后A续第三段(32) + 双E(75x2=150) = 403,
    #             正好 4 刀(居合架势要 ≥100, 每刀扣 100)。
    #             原来的 'short' 只有 50+57+150 = 257, 0 命第三刀出不来、淬寒叠不满 3 层,
    #             强化重击解锁不了, R2 跟着断 —— 这就是 "0+1 在 R1 后对不上" 的原因。
    #   'ee'    = R1 后直接 EE 三居合(10-08 晚)。帧表: R1 给 50 寒意, 地面E/空中E 各 75、2链各再 +50,
    #             50+125+125 = 300 = 正好三刀(居合架势要 ≥100, 每刀扣 100), A3 就不用打了。
    #             【要 2 链以上】: 不到 2 链只有 200, 第三刀出不来, 用 'kendo4'
    #             【还要共效够高】: 少了 A3 那几下, R2 打完协奏不满, 变奏不出穗穗(10-08 19:00 实机)
    #   'short' = A3 -> 处决/闪避 -> EE 三居合(10-08 下午, 实机跑通过)
    #   'full'  = 原来的五居合 (2 链以上寒意才够)
    OPENER_KIND = 'kendo4'
    EE_AFTER_R1 = 0.10
    # 'ee' 版没有 A3 了, 处决也就没地方插; 改成 True 会在 R1 之后、EE 之前有提示就按一次 F
    EE_EXECUTE_FIRST = False
    # 短版的 E E 照搬绯雪单人轴(09-29 实机一次过): 预求地面E 第20F转空中、派生35F,
    # 之后按的第二个 E 才是空中E; 空中E 下落 16F 起判定、持续 30F, 落地派生 6F。
    # 8 月这条队标定过"长按 0.85s 才升空、点按飞不起来"(那时E紧跟在A链后面);
    # 10-08 'short' 版实机点按升得起来。'ee' 版 E 紧跟在 R1 后面, 要是没把人顶上天就改成 0.85
    EE_TAP = 0.03
    EE_E1_TO_E2 = 0.45
    EE_E2_HOLD = 0.75
    EE_E2_AFTER = 0.10
    # 短版 A3 之后有处决提示就用处决代替闪避。M_EXECUTE_ANIM 是按"处决后接一下A不被吞"标定的,
    # 处决动画长度又随敌人变; 后面那下E点按只有一发, 落在演出里就升不了空, 所以再等 HUD 回来
    EXEC_HUD_WAIT = 3.0
    EXEC_TO_E = 0.05
    # 收尾段, 纯定时。居合间隔要略小于居合动画(约0.5s)让点击排队, 但不能小于动画一半否则丢刀
    M_KENDO_INTERVAL = 0.45
    # 闪避之后马上接居合。只留 3 帧, 让闪避和第一刀落在不同的游戏帧里, 同一帧里只认一个
    M_DODGE_TO_KENDO = 0.05
    GROUND_KENDO_COUNT_FIRST = 3  # 启动轴(2链以上版本); 'kendo4'(0命) 用 GROUND_KENDO_COUNT, 见 opener_ground_kendo()
    GROUND_KENDO_COUNT = 2  # 循环轴
    # 收尾段全部从【闪避】算起, 按帧表排, 不读屏:
    #   第一刀出刀   闪避后 KENDO1_DELAY
    #   第 N 刀出刀  再加 (N-1)*39F  —— 帧表 居合派生帧39F(0.65): 3 刀 78F, 2 刀 39F
    #   重击起手     最后一刀再过 39F(预输入的重击在最后一刀派生那一帧起手)
    # 闪避到第一刀出刀这段帧表里没有, 实机反推: 07:10 闪避后 0.31 秒才点第一刀嫌慢(<0.31);
    # 07:29 按"点了就出刀"排、闪避后 1.40 秒按住攻击, 第三刀被顶掉(>0.10)
    KENDO1_DELAY = 0.20
    KENDO_DERIVE = 0.65
    KENDO_SPAM_INTERVAL = 0.10  # 连点, 派生帧那一刻缓存里总有一下; 刀变少就往 0.25 调
    KENDO_SPAM_LAST_GAP = 0.05  # 最后一下点击离按住攻击至少这么远, 太近两下会连成一下
    # 按住攻击(预输入重击)放在最后一刀出刀和它派生帧的正中: 早了顶掉最后一刀, 晚了重击
    # 接不上。KENDO1_DELAY 是估的, 取正中两边各留 0.3 秒, 估偏一点也不出事
    KENDO_OUT_TO_HOLD = 0.30
    # 按住 R 从重击起手算, 按下的同时松攻击。R 必须在重击起手之后才第一次按下:
    # 07:29 重击之前就按住 R, 重击后 R2 没起; 接得上的只有"起手后 0.8 秒按"这一种。
    # 旧标定: <=0.35 必顶掉重击, 0.6/0.7 偶发, 0.95 停顿明显
    HEAVY_TO_R = 0.80
    HEAVY_ANIM = 2.50  # 帧表: 强化重击 派生帧150F, 演完才进 R2 蓄力
    # 蓄力时长沿用之前实机放得出来的值: 旧 R 按住 9.05/4.05, 减去当时 R 按下到重击演完的 1.70
    R2_CHARGE_FIRST = 7.35  # 启动轴(2链以上): 能蓄 3 段(帧表 3 层 210F); 0命首轮只有 2 段, 见 R2_CHARGE_OPENER_0C
    R2_CHARGE = 2.35  # 循环轴: 只能蓄 1 段(帧表 1 层 96F)
    # 0命首轮 R2 蓄力时长: 0 命首轮只有 2 点锻雪·归刃(非战斗状态补 1 点 + 首轮强化重击 1 点),
    # 2 段蓄力; 7.35 的 3 段是 2 链以上才有的("2链可多打一层锻雪, 首轮才能满层二段大")。
    # 按作者实机值 1 段 2.35 / 3 段 7.35 线性插值得 (2.35+7.35)/2 = 4.85。
    # 锻雪归零时 R2 自动释放: 蓄久只多站场, 蓄短会把 R2 直接取消掉 —— 宁长勿短;
    # 若实测首轮只有 1 点锻雪, 把它改回 2.35 即可。
    R2_CHARGE_OPENER_0C = 4.85
    # 只给兜底路径 hold_liberation 用; 收尾段的蓄力时长看 R2_CHARGE_FIRST / R2_CHARGE / R2_CHARGE_OPENER_0C
    R2_HOLD_FIRST = 9.05
    R2_HOLD = 4.05
    R2_HOLD_OPENER_0C = 6.55  # 兜底路径用: R2_CHARGE_OPENER_0C + 1.70 (R 按下到重击演完的 1.70)
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
    # R2 之后场上没目标(这一波打完了)时, 等新怪刷出来再切穗穗的上限; 超了照切(可能整场打完了)
    WAVE_WAIT = 4.0
    TARGET_GONE_CONFIRM = 2  # 连着这么多次读不到锁定目标才算没怪, 单帧被特效挡住不算
    WAVE_LOCK_INTERVAL = 0.3  # 等新怪时按中键锁目标的间隔
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
        # 【v3.5.32 起这一句必须在 reset_state 里重申, 只写 __init__ 保不住】:
        # CharFactory.apply_team_char_classes() 换成自定义类的写法是
        # `replacement.__dict__.update(内置实例.__dict__)` —— __init__ 里所有跟内置版
        # 取值不同的字段会被整个打回内置值。BaseChar.__init__ 是 `not self.is_healer`,
        # 所以非治疗角色一律被打回 True, 框架就会在 switch_next_char() 里替她按 F。
        # reset_state() 跑在那次 update 之后(load_chars: apply_team_char_classes -> 逐个
        # reset_state), 而且每次重读队伍都会再跑一遍, 放这里才真的保得住。
        # 绯雪的处决由她自己在轴上那一处 send_key('f'), 不要框架代按。
        self.check_f_on_switch = False
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
        ground = self.opener_ground_kendo() if not self.r2_used else self.GROUND_KENDO_COUNT
        short = not self.r2_used and self.OPENER_KIND == 'short'
        ee = not self.r2_used and self.OPENER_KIND == 'ee'
        kendo4 = not self.r2_used and self.OPENER_KIND == 'kendo4'
        if ee:
            self.logger.info(f'hiyuki macro [ee opener]: R1 -> {"[execute] -> " if self.EE_EXECUTE_FIRST else ""}'
                             f'E tap -> E hold land -> dodge -> kendo x{ground} -> heavy -> R2')
        elif short:
            self.logger.info(f'hiyuki macro [short opener]: A3 -> [execute | dodge] -> E tap -> E hold land '
                             f'-> dodge -> kendo x{ground} -> heavy -> R2')
        elif kendo4:
            self.logger.info(f'hiyuki macro [kendo4 opener 0命]: A3 -> dodge -> A3 -> rise -> '
                             f'air kendo x{self.AIR_KENDO_COUNT} -> land -> A3 -> [execute] '
                             f'-> dodge -> kendo x{ground} -> heavy -> R2(2段蓄力)')
        else:
            self.logger.info(f'hiyuki macro: A3-dodge-A3 -> rise -> air kendo x{self.AIR_KENDO_COUNT} '
                             f'-> A3 -> [execute] -> dodge -> kendo x{ground} -> heavy -> R2')
        # 整段关掉脱战判定: 爆发期间常有"目标丢失"误报, 一抛异常 R2 就没了
        previous = getattr(self.task, 'skip_combat_check', False)
        self.task.skip_combat_check = True
        try:
            self.macro_start()
            if ee:
                # R1 变身演出(隐藏 HUD 240F)结束帧就是 240F, 没有更晚的派生帧, HUD 回来就能动;
                # 再留几帧, 防 HUD 读数比动作结束早一两帧。E 点按只有一发, 落在演出里就升不了空
                self.macro_wait(self.EE_AFTER_R1)
                if self.EE_EXECUTE_FIRST and self.macro_execute():
                    self.wait_hud_after_execute()
                self.macro_ee_land()
                return self.finish_with_r2()
            self.attack_chain()
            if short:
                # 有处决提示就拿处决取消 A3 后摇, 多吃一次处决伤害; 没提示照旧闪避
                if self.macro_execute():
                    self.wait_hud_after_execute()
                else:
                    self.macro_dodge(self.M_AFTER_DODGE)
                self.macro_ee_land()
                # 收尾段原样复用: 它本来就从"闪避进架势"开始, 单人轴落地后也是先闪再出刀
                return self.finish_with_r2()
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
        """闪避进架势 -> 连点居合 -> 预输入重击 -> 重击起手后按住R -> R2 蓄力。全程定时, 不读屏。
        启动轴按 OPENER_KIND: 'kendo4'(0命) 2 刀、其余 3 刀; 循环轴 2 刀。所有时刻从闪避算起
        (推算方式见 KENDO1_DELAY 上面的注释)。
        """
        count = self.opener_ground_kendo() if not self.r2_used else self.GROUND_KENDO_COUNT
        dodge_at = time.time()
        self.macro_dodge(self.M_DODGE_TO_KENDO)
        last_kendo_out = dodge_at + self.KENDO1_DELAY + (count - 1) * self.KENDO_DERIVE
        hold_at = last_kendo_out + self.KENDO_OUT_TO_HOLD
        heavy_start = last_kendo_out + self.KENDO_DERIVE
        self.macro_mark('kendo_spam')
        clicks = 0
        last_click_by = hold_at - self.KENDO_SPAM_LAST_GAP
        while True:
            self.click()
            clicks += 1
            next_click = time.time() + self.KENDO_SPAM_INTERVAL
            if next_click > last_click_by:
                break
            self.macro_wait(max(0.0, next_click - time.time()))
        self.macro_mark(f'kendo_end{clicks}')
        self.macro_wait(max(0.0, hold_at - time.time()))
        return self.hold_heavy_into_r2(heavy_start)
    def in_kendo_stance(self):
        return bool(self.task.find_one('hiyuki_left', threshold=0.5))
    def lib_heavy_available(self):
        return bool(self.task.find_one('hiyuki_lib_forte', threshold=0.7))
    def r2_press_time(self):
        if not self.r2_used and self.OPENER_KIND == 'kendo4':
            return self.R2_HOLD_OPENER_0C
        return self.R2_HOLD if self.r2_used else self.R2_HOLD_FIRST
    def opener_ground_kendo(self):
        """启动轴地面居合刀数。'kendo4'(0命) 空中 2 刀 + 地面 2 刀 = 4 居合;
        'ee'/'short'/'full'(2 链以上) 地面 3 刀。"""
        return self.GROUND_KENDO_COUNT if self.OPENER_KIND == 'kendo4' else self.GROUND_KENDO_COUNT_FIRST
    def opener_r2_charge(self):
        """首轮 R2 蓄力时长。'kendo4'(0命) 首轮只有 2 点锻雪·归刃, 走 2 段(4.85);
        'ee'/'short'/'full'(2 链以上) 首轮 3 段(7.35)。"""
        if not self.r2_used and self.OPENER_KIND == 'kendo4':
            return self.R2_CHARGE_OPENER_0C
        return self.R2_CHARGE_FIRST
    def hold_heavy_into_r2(self, heavy_start):
        """按住攻击预输入终结重击 -> 重击起手后松攻击、按住R -> 蓄满自动释放 -> 松R。
        调用时刻就是该按住攻击的时刻; heavy_start 是推算出的重击起手时刻:
          heavy_start + HEAVY_TO_R                  松攻击, 按下 R(只按一次, 一直按住)
          heavy_start + HEAVY_ANIM + 蓄力时长       松 R。蓄满会自动释放, 这个时刻只要盖得住
        等待用 macro_wait: BaseChar.sleep 每 0.4 秒插一次截图, 结尾还会把
        skip_combat_check 置回 False, 蓄力那几秒会重新暴露在脱战误判里。
        """
        charge = self.R2_CHARGE if self.r2_used else self.opener_r2_charge()
        start = time.time()
        release_r = heavy_start + self.HEAVY_ANIM + charge
        self.task.mouse_down()
        self.macro_mark('heavy')
        try:
            self.macro_wait(max(0.0, heavy_start + self.HEAVY_TO_R - time.time()))
        finally:
            self.task.mouse_up()
        # R 只按下一次然后一直按住, 中途【不重发】: 每一发 WM_KEYDOWN 游戏都当一次新按下,
        # 长按判定被反复打断, 蓄力永远起不来, 松开那一刻才当短按放出去 —— 07:36 之前
        # 每 0.2 秒重发一次, 一轮都没蓄上。长按 E 升空(macro_hold_e)就是按一次 + 等 + 松
        key = self.get_liberation_key()
        r_down_at = time.time()
        self.task.send_key_down(key)
        self.macro_mark('R_down')
        self.logger.info(f'hiyuki macro timeline: {self.macro_timeline()}')
        try:
            self.macro_wait(max(0.0, release_r - time.time()))
        finally:
            self.task.send_key_up(key)
        press_time = time.time() - r_down_at
        self.r2_used = True
        self.record_liberation_use()
        self.task.in_liberation = True
        self.task.wait_until(lambda: self.task.in_team()[0], time_out=self.POST_LIB2_TEAM_WAIT)
        self.task.in_liberation = False
        self.add_freeze_duration(start, time.time() - start)
        self.lib2_count = 0
        self.logger.info(f'hiyuki macro: R2 released (held {press_time:.1f}s)')
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
    def wait_hud_after_execute(self):
        """处决之后等队伍 HUD 回来(= 演出结束、能接输入了)再往下走。只花时间, 不发键。"""
        start = time.time()
        while time.time() - start < self.EXEC_HUD_WAIT:
            if self.task.in_team()[0]:
                break
            self.macro_wait(0.03)
        self.macro_mark(f'hud_back+{time.time() - start:.2f}')
        self.macro_wait(self.EXEC_TO_E)
    def macro_ee_land(self):
        """短版启动轴: E 点按升空 -> E 长按落地。"""
        e = self.get_resonance_key()
        self.task.send_key(e, down_time=self.EE_TAP)
        self.record_resonance_use()
        self.macro_mark('E1')
        self.macro_wait(self.EE_E1_TO_E2)
        self.macro_hold_e(self.EE_E2_HOLD, self.EE_E2_AFTER)
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
        sent = False
        start = time.time()
        while self.task.in_team()[0] and time.time() - start < self.HOLD_LIB_TIME_OUT:
            if self.liberation_available():
                self.task.send_key_down(self.get_liberation_key())
                sent = True
                break
            if self.task.get_cd('liberation') > self.HOLD_LIB_CD_WAIT:
                break
            self.sleep(0.05, check_combat=False)
        if not sent:
            return False
        # 按下一次一直按住, 不重发: 重发的每一下都是新按下, 蓄力起不来(见 hold_heavy_into_r2)
        self.macro_wait(self.r2_press_time())
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
            # assume_intro 要跟着原来那次一起传: 补救这一下也是紧接在 R2 后面的,
            # 协奏读数照样滞后。之前写死 False, 补救成功也会告诉穗穗"你空手上场"
            self.logger.warning(f'hiyuki leave failed ({e}), trying direct switch')
            if not self.direct_switch(assume_intro=skip_outro):
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
        continues_normal_attack/click, 大招之后不想要那几下多余的A。
        【不因为"队伍读不出来"就放弃】: R2 刚结束那几秒头像栏是读不到的
        (in_team() 假、队伍识别退化成 unknown), switch_target() 会同时落空。
        以前那样直接 return False, 调用方就退回框架切人 —— 而框架切人在同一个
        读不到头像的窗口里必然抛 not in_team, 一路把战斗判定打断, 穗穗的变奏记账
        就整个丢了。所以目标解析不出来时改成盲发写死的槽位键, 切成之后再补记账。
        """
        target = self.switch_target()
        slot = self.DIRECT_SWITCH_INDEX if target is None else target.index + 1
        if slot - 1 == self.index:
            self.logger.warning(f'hiyuki direct switch: slot {slot} is myself, '
                                f'team={self.team_roster()}')
            return False
        # 刚放完大招时直接认定协奏满: 读数滞后会把 has_intro 误判成 False,
        # 那样穗穗会以为自己空手入场跑去走开场流程
        has_intro = True if assume_intro else self.wait_con_full()
        # 大招动画期间就按住普攻并狂发切人键, 不干等动画演完: 按住普攻让动画一结束
        # 攻击立刻接上; 切人键在动画期间发出去看似白发, 但换来"能切的第一帧就切走"
        deadline = self.LIB_ANIM_WAIT + self.LEAVE_SWITCH_TIMEOUT
        start = time.time()
        switched = False
        ambiguous = 0
        own = self.index if 0 <= self.index < 3 else None
        # 【场上没怪就先别切】(10-08 用户): R2 打死这一波、新怪还没刷出来时切过去, 穗穗的变奏打空,
        # 协奏一点没回, 放完 R 也不满, 切洛瑟菈就没有变奏。17:28 / 17:29 两次都是绯雪切走后 0.02s
        # 框架就报 target lost, 新怪在 0.9~1.5s 后才被锁到。绯雪协奏是满的, 留着等新怪出来再切。
        # 所以切人键要等"判完有没有怪"才发 —— 演出里提前发的键会在能动的第一帧被接受, 等不到判断
        gate = None  # None=还没判, 'go'=可以切了
        no_target = 0
        waited_at = None
        next_mid = 0.0
        gate_note = ''
        self.task.mouse_down()
        try:
            while time.time() - start < deadline:
                # 【成立条件: 目标那格没有数字牌, 并且绯雪自己那格读得到数字牌】, 不用 in_team()。
                # in_team() 拿"第一个读不到数字牌的格子"当在场的人, 数字牌被挡住的那格也算 ——
                # 10-08 17:16/17:19 两次 R2 打死 boss, 1 号位数字牌被挡、读成"穗穗在场", 这里当场
                # 停了发键, 人还是绯雪, 之后 5 秒是穗穗的代码在操控她(按住攻击 = 那几下 A)。
                # 读得到绯雪自己的数字牌才证明她真的下场了, 遮挡骗不到这一条
                labels = self.slot_labels()
                if not labels[slot - 1]:
                    if own is None or labels[own]:
                        note = f', ignored {ambiguous} ambiguous reads' if ambiguous else ''
                        self.logger.info(f'hiyuki direct switched to slot {slot} '
                                         f'(intro={has_intro}, {time.time() - start:.1f}s{note}{gate_note})')
                        switched = True
                        break
                    if any(labels):
                        ambiguous += 1  # 目标那格和自己那格都没数字牌: 有一格是被挡住的, 分不清谁在场
                now = time.time()
                if gate is None:
                    if any(labels):
                        # 头像栏回来了 = 演出结束, 这时才判得了有没有怪
                        if self.target_visible():
                            gate = 'go'
                            if waited_at is not None:
                                gate_note = f', waited {now - waited_at:.1f}s for the next wave'
                        else:
                            no_target += 1
                            if no_target >= self.TARGET_GONE_CONFIRM:
                                if waited_at is None:
                                    waited_at = now
                                    deadline += self.WAVE_WAIT
                                    self.task.mouse_up()  # 没怪可打, 别按着空挥
                                    self.logger.info('hiyuki: no target after R2, holding the outro '
                                                     'until the next wave shows up')
                                if now - waited_at >= self.WAVE_WAIT:
                                    gate = 'go'
                                    gate_note = f', no target for {self.WAVE_WAIT:.0f}s, switched anyway'
                                elif now >= next_mid:
                                    self.task.middle_click()  # 和框架 retarget 一样按中键锁新目标
                                    next_mid = now + self.WAVE_LOCK_INTERVAL
                    elif now - start >= self.LIB_ANIM_WAIT:
                        gate = 'go'  # 头像栏一直读不到: 判不了, 照原来盲发(见上面 docstring)
                        gate_note = ', HUD never came back, blind'
                if gate == 'go':
                    self.task.send_key(slot)
                self.sleep(0.12, check_combat=False)
        finally:
            self.task.mouse_up()
        if not switched:
            self.logger.warning(f'hiyuki direct switch to slot {slot} failed')
            return False
        if target is None:
            # 盲发那条路: 人已经过去了, 现在头像栏也读得到了(上面那次数字牌读数是真的),
            # 重读一次队伍把对象认出来。必须在打 has_intro 之前读 ——
            # load_chars() 末尾会对每个角色 reset_state(), 顺序反了标记当场被抹掉
            self.task.load_chars()
            target = self.char_at_index(slot - 1)
        if target is None or target is self:
            self.logger.warning(f'hiyuki switched to slot {slot} but could not resolve the char, '
                                f'team={self.team_roster()}')
            return True  # 人确实切过去了, 不能再让调用方去 switch_next_char()
        self.handoff_to(target, has_intro)
        return True
    def target_visible(self):
        """锁定目标在不在。照 CombatCheck.has_target() 的前三个读框, 去掉它最后那个兜底分支 ——
        那个分支会 sleep(1) 再连按两次 ESC, 不能在轴里调。"""
        t = self.task
        try:
            has_name, no_name = t.get_target_names()
            for box in (t.get_box_by_name(has_name).scale(1.1), t.get_box_by_name('box_target_enemy_long'),
                        t.get_box_by_name('target_box_long2')):
                best = t.find_best_match_in_box(box, [has_name, no_name], threshold=0.6)
                if best:
                    return best.name == has_name
        except Exception as e:
            # 别的 ok-ww 版本这几个读框/方法可能改名了: 当成有怪, 退回"不等下一波、直接切"
            if not getattr(self, '_target_visible_warned', False):
                self._target_visible_warned = True
                self.logger.warning(f'hiyuki target_visible unsupported in this ok-ww version ({e!r}), '
                                    f'assuming a target is there')
            return True
        return False
    def slot_labels(self):
        """队伍栏「1」「2」「3」数字牌各自读没读到(在场的人那一格没有)。阈值和 in_team() 一样。"""
        return [bool(self.task.find_one(f'char_{i}_text', threshold=0.8)) for i in (1, 2, 3)]
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
        """交棒对象: 先按角色名找(不假设队伍顺序), 找不到再退回写死的槽位。
        【槽位那条路必须排除自己】: 以前不查, 绯雪自己站 1 号位时它返回的就是本人,
        direct_switch 在 50 毫秒内静默 return False —— 日志上只表现为"没走直接切人",
        没有任何线索。解析不出来时打一条队伍名单, 这类问题只有这一行能一次定位。
        """
        for char in self.task.chars:
            if char is not None and char is not self and char.char_name == self.SWITCH_TARGET_NAME:
                return char
        slot_char = self.char_at_index(self.DIRECT_SWITCH_INDEX - 1)
        if slot_char is not None:
            return slot_char
        self.logger.warning(f'hiyuki switch target unresolved '
                            f'(name={self.SWITCH_TARGET_NAME} slot={self.DIRECT_SWITCH_INDEX}), '
                            f'team={self.team_roster()}')
        return None
    def char_at_index(self, index):
        return next((c for c in self.task.chars
                     if c is not None and c is not self and c.index == index), None)
    def team_roster(self):
        return [None if c is None else (c.index, str(c.char_name)) for c in self.task.chars]
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
