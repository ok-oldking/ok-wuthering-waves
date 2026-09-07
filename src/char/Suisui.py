import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar, Elements, SwitchPriority


class Suisui(BaseChar):
    """穗穗: 效应体系专辅, 本体几乎无伤害, 全部价值压在「延奏」那一下。

    濯雨时只有 15 秒(游戏侧计时, 不受动画冻结影响), 退出时芳菲信直接清零 ——
    这是整套代码最硬的约束。延奏 600 档才给下一个角色 50% 攻击, 400 档只有 12%。

    站场分两条轴, 只有开头不同, 从"等第一格回路能量满"起完全一样:
      启动轴  按住攻击键 -> 等E亮 -> 按E「醒春潮」进濯雨时 -> v
      循环轴  (主C大招后变奏入场, 变奏技能本身已把她推进濯雨时) 按住攻击键 -> v
      v  等第一格满 -> 按E落地 -> 等0.95秒 -> 切主C入场, 到位立刻狂点把场子要回来
         -> 回到穗穗: Q -> [保底: 三格回路能量满才准放R] -> R -> 切下一个

    攻击键是鼠标、E/Q/数字键是键盘, 互不冲突, 所以整条轴中途一次都不松手, 只在放R前松开。
    切人期间也保持按住 —— 点击落在谁身上就由谁打出来, 主C出场那两下A就是这么来的。

    大招压到最后放: 30 秒领域几乎全部覆盖后面两个角色的输出窗口。
    """

    MISTY_WINDOW = 15.0  # 濯雨时总时长, 用墙钟
    LIB_CAST_RESERVE = 3.0  # 窗口末尾预留给"放大招+切人"

    OPEN_E_WAIT_TIMEOUT = 10.0
    OPEN_POLL = 0.1
    # 醒春潮之后隔多久按落地E。醒春潮把她顶上天, E 只在上升/滞空有效, 进入下落就没反应。
    # 标定: 3.0/3.1 已在下落段完全不出; 2.0/2.2/2.4 能出但偏早。窗口夹在 2.4~3.0
    FIRST_BAR_TIME = 2.8
    # 循环轴按落地E的时机。【计时起点和启动轴不同】: 这里从她被切上场那一刻算起,
    # 中间没有醒春潮, 开头约 0.9 秒是变奏入场动画, 两个值没有可比性。
    # 标定: 3.1/2.9/2.7 已在下落段完全没反应; 2.6 能出但只比失败区低 0.1 秒。
    # 早了只是第一格没攒满(wait_forte3 兜得住), 晚了是整轮报废(E没生效->人还在空中
    # ->切主C超时2秒), 两边不对称, 所以往早的一侧靠
    FIRST_BAR_TIME_INTRO = 2.6
    # 用【头像认出切人完成那一刻】当循环轴的计时锚点, 而不是 do_perform 被调用那一刻 ——
    # 两者之间隔着框架的交接记账、上个角色 leave() 的返回、任务循环再调到穗穗, 这段是变长的。
    # 这个上限只保留"防时间戳过期"的本职: 实测 gap 是双峰的(0.04~0.12 和 0.74~0.98),
    # 试过压到 0.35 去掐掉大的那一簇, 结果证明方向错了 —— 那一簇的锚点是对的
    SWITCH_ANCHOR_MAX = 1.5
    # 按E落地到开始切主C的间隔。要够长按攻击键真的A出去一段 —— 切走时连段已经起来了,
    # 切回来才会接着往下打, 而不是从第一段重新开始
    E_LAND_TO_SWITCH = 0.95
    BACK_TO_R = 0.1  # 切回来按完Q到开R; 保底闸(wait_forte3)排在这后面
    POST_LIB_SETTLE = 0.15  # 大招动画刚结束时能量环没渲染回来, 立刻切人会把协奏读成0

    # 借主C一下: 切过去到位立刻把场子要回来。框架的 current_char 不跟着变,
    # 所以必须自己确认 index 归位; 任何一步没切成就当没发生过
    DPS_TOUCH_OUT_TIMEOUT = 2.0
    DPS_TOUCH_BACK_TIMEOUT = 3.0  # 回程给得宽: 可能撞上游戏的切人硬直, 得一直重发等放行
    # 重发数字键的间隔。太小(0.12): 切换生效到 in_team() 读出来之间有两三帧延迟,
    # 这期间多发的键会排队, 等切回穗穗之后再触发一次(表现是主C在错误的节点又切进来)。
    # 太大(0.35): 第一次没生效要多等 0.35 秒才补发, 来回从 1.2~1.3 涨到 1.4~1.5。
    # 【别再加密】: 试过 0.08, 回程快了 0.1 秒但 forte3 从 0.4 退化到 1.9 —— PostMessage 的
    # send_key() 每次都投一条 WM_ACTIVATE, 窗口收到就会把按住的左键松开
    SWITCH_KEY_RESEND = 0.22
    SWITCH_KEY_RESEND_BACK = 0.22
    SWITCH_POLL = 0.05  # 查 in_team 要比重发密, 好尽快发现切成了

    FORTE3_WAIT = 8.0  # 等三格满的上限, 超了照放不误
    FORTE3_THRESHOLD = 0.75  # 原来 0.6 太松会误判
    FORTE3_CONFIRM = 2  # 连续命中这么多次才认, 单帧误判不算
    MIN_MISTY_BEFORE_LIB = 3.0  # 刚进濯雨时物理上不可能满, 这时的命中一定是误判

    SWITCH_TARGET_NAME = 'char_lucilla'
    DIRECT_SWITCH_INDEX = 2
    HANDOFF_CON_WAIT = 0.8
    # 上一次延奏后多久内不让别人把她切回来。取自上游实测: 25秒轴下队里有主C时24秒, 没有时26秒
    MAIN_DPS_OUTRO_LOCKOUT = 24.0
    OUTRO_LOCKOUT = 26.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_outro = -1
        self.misty_start = -1  # 本次进入濯雨时的墙钟时间
        self._forte3_hits = 0
        # 别人用 handoff_to() 直接切给我时打的标记。不能只靠 has_intro ——
        # reset_state() 每次重读队伍都会清它, 而战斗判定一抖动就会重进战斗重读队伍,
        # 于是穗穗以为自己空手入场, 跑去走开场流程(表现就是切过去一直在蓄力重击)
        self.intro_pending = False
        if self.ring_index < 0:
            # CharFactory 里穗穗没写 ring_index, 环色会被现场猜; 万一第一次判定发生在
            # 濯雨时特效糊住能量环时会锁死错值, 而离场判定完全依赖 is_con_full()
            self.ring_index = Elements.ICE

    def do_perform(self):
        if self.flying():
            self.wait_down()

        if self.has_intro or self.intro_pending:
            # 变奏技能已经消耗水云息把她推进濯雨时了, 不用再攒
            self.intro_pending = False
            self.enter_misty_state()
            return self.hold_axis(opening=False)

        self.intro_pending = False
        if self.in_misty():
            # 上一轮被中途切走但濯雨时还在走: 第一格早就满了, 直接接后半段
            self.logger.info(f'suisui resuming misty, {self.misty_left():.1f}s left')
            return self.hold_axis(opening=False, skip_first_bar=True)

        return self.hold_axis(opening=True)

    def hold_axis(self, opening=False, skip_first_bar=False):
        """启动轴 / 循环轴。攻击键从头按到尾, 只在放R前松手。

        【按住期间绝对不要再调 mouse_down()】—— 哪怕只是"补按一下保险"。
        PostMessage 后端的 mouse_down() 内部会走 update_mouse_pos() -> try_activate(),
        每次都投一条 WM_ACTIVATE, 窗口收到就会把已经按住的状态打断。
        实测代价: 在切人循环里每发一次切人键补按一次, forte3 从 0.5 秒退化到 2 秒往上。
        一次 mouse_down 就够了, 它会一直有效, 包括跨过切人。
        """
        axis = 'opening' if opening else 'loop'
        self.logger.info(f'suisui {axis} axis: hold attack -> E(land) -> dps touch -> Q -> forte3 -> R')
        axis_start = time.time() if opening else self.switch_in_anchor()
        self.task.mouse_down()
        try:
            if opening:
                self.hold_until(self.e_ready, self.OPEN_E_WAIT_TIMEOUT, 'e ready')
                self.send_resonance_key()  # 醒春潮: 消耗水云息进濯雨时
                self.enter_misty_state()
                if not skip_first_bar:
                    self.sleep(self.FIRST_BAR_TIME, check_combat=False)
                self.send_resonance_key()  # 按E落地
            elif not skip_first_bar:
                # 循环轴用绝对时刻: FIRST_BAR_TIME_INTRO 是慢放量出来的
                # "变奏入场 -> 该按E"的间隔, 基准必须是上场那一刻
                self.sleep(max(0.0, axis_start + self.FIRST_BAR_TIME_INTRO - time.time()),
                           check_combat=False)
                self.send_resonance_key()
            else:
                self.send_resonance_key()  # 续打那条路: 第一格早满了, 直接按E落地
            self.sleep(self.E_LAND_TO_SWITCH, check_combat=False)

            if self.dps_touch() == 'out':
                # 【只在 'out' 这一种失败上补】: 没切过去 = 人还在空中、也还在自己身上,
                # 这时补一发E是安全的。平时不能盲补 —— 地面补E会把她重新顶上天;
                # 'back' 那种失败人已经在主C身上, 发键就是发给主C
                self.logger.info('suisui: still airborne, re-sending E and retrying the touch')
                self.send_resonance_key()
                self.sleep(self.E_LAND_TO_SWITCH, check_combat=False)
                self.dps_touch()

            self.send_echo_key()  # Q
            self.sleep(self.BACK_TO_R, check_combat=False)
            self.wait_forte3()  # 保底: 三格回路能量满才准放R
        finally:
            self.task.mouse_up()

        cast = self.cast_field()
        if cast:
            self.sleep(self.POST_LIB_SETTLE, check_combat=False)
        else:
            self.logger.warning('suisui: liberation not ready at R time, leaving without field')
        self.leave(assume_intro=cast)

    def leave(self, assume_intro=False):
        """离场: 优先按数字键直接切, 绕开 switch_next_char() 内部那一下多余的普攻。

        Args:
            assume_intro: 直接认定协奏是满的。只有"刚放完R"那条路能这么认 ——
                那时协奏基本一定满, 而能量环读数滞后会把 has_intro 误判成 False。
        """
        if not self.direct_switch(assume_intro=assume_intro):
            self.switch_next_char()

    def wait_forte3(self):
        """保底: 三格回路能量(芳菲信600)没满就接着按住打, 满了立刻停手。

        但等待有物理上限: 濯雨时一关芳菲信【直接清零】, 再等永远等不到。
        所以窗口只剩 LIB_CAST_RESERVE 时必须停手去放R —— 那不是放弃保底,
        是继续等已经不可能成功了。
        """
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < self.FORTE3_WAIT:
            if self.forte3_available():
                self.logger.info(f'suisui forte3 full after '
                                 f'{self.time_elapsed_accounting_for_freeze(start):.1f}s')
                return True
            left = self.misty_left()
            if 0 < self.misty_start and left <= self.LIB_CAST_RESERVE:
                self.logger.warning(f'suisui: misty closing ({left:.1f}s left) without forte3, '
                                    f'casting R now before the gauge wipes')
                return False
            self.sleep(0.1, check_combat=False)
        self.logger.warning(f'suisui forte3 still not full after {self.FORTE3_WAIT:.1f}s, casting anyway')
        return False

    def switch_in_anchor(self):
        """循环轴的计时基准: 头像认出"切人完成"的那一刻(handoff_to 写的 last_switch_in_time)。

        日志里那个 gap 就是它和 do_perform 被调用之间的延迟。
        gap 忽大忽小 = 锚对了; gap 每轮都差不多 = 方差另有来源。
        """
        now = time.time()
        anchored = self.last_switch_in_time
        gap = now - anchored if anchored > 0 else -1
        if 0 <= gap <= self.SWITCH_ANCHOR_MAX:
            self.logger.info(f'suisui: anchored on switch-in, {gap:.2f}s ago')
            return anchored
        self.logger.info(f'suisui: switch-in timestamp unusable (gap {gap:.2f}s), using now')
        return now

    def e_ready(self):
        """E亮了没有 —— 两个信号取先亮的那个。e_forte 是框架通用的"E充满"标记,
        suisui_e1 是她自己那张E技能格图标。取"或"只可能更早不可能更晚。"""
        return bool(self.is_e_forte_full()) or bool(self.task.find_one(Labels.suisui_e1))

    def hold_until(self, cond, timeout, name):
        """按住攻击键期间轮询某个条件。按下/松开由调用方管。"""
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < timeout:
            if cond():
                self.logger.info(f'suisui opening: {name} ready after '
                                 f'{self.time_elapsed_accounting_for_freeze(start):.1f}s')
                return True
            self.sleep(self.OPEN_POLL)
        self.logger.info(f'suisui opening: timed out waiting for {name} ({timeout:.1f}s)')
        return False

    def enter_misty_state(self):
        self.misty_start = time.time()
        self._forte3_hits = 0

    def in_misty(self):
        return self.misty_start > 0 and self.misty_left() > self.LIB_CAST_RESERVE

    def misty_left(self):
        """濯雨时还剩多少秒。用墙钟: 这是游戏侧的15秒, 不能扣动画冻结时间。"""
        if self.misty_start <= 0:
            return -1
        return self.MISTY_WINDOW - (time.time() - self.misty_start)

    def dps_touch(self):
        """切主C入场, 到位之后立刻把场子要回来。

        要的只是"主C进场"这个事件本身, 不是让她打输出 —— 所以切过去一帧都不等。
        回程可能撞上切人硬直, switch_to_index 会一直重发直到放行。整个来回攻击键都按住。

        Returns:
            'ok'   来回都成功
            'out'  没切过去。几乎只有一个原因: 落地E没生效人还在空中。
                   这是【唯一】可以补一发E重试的情况 —— 人还在自己身上
            'back' 切过去了但没切回来。这时发任何键都是发给主C的, 绝对不能补E
            'none' 队里没有主C
        """
        dps = self.main_dps_teammate()
        if dps is None:
            return 'none'

        start = time.time()
        here = self.index
        if not self.switch_to_index(dps.index, timeout=self.DPS_TOUCH_OUT_TIMEOUT):
            self.logger.info('suisui: failed to switch to dps, skip')
            return 'out'
        out_done = time.time()
        if not self.switch_to_index(here, timeout=self.DPS_TOUCH_BACK_TIMEOUT,
                                    resend=self.SWITCH_KEY_RESEND_BACK):
            self.logger.warning('suisui: failed to switch back from dps, leave it to the framework')
            return 'back'
        # 来回两程分开记: 总时长两条轴一样, 想知道慢的是哪一程
        self.logger.info(f'suisui: dps touch done in {time.time() - start:.1f}s '
                         f'(out {out_done - start:.2f}s, back {time.time() - out_done:.2f}s)')
        return 'ok'

    def switch_to_index(self, index, timeout=None, resend=None):
        """按数字键切到指定队伍位置, 重发到 in_team 确认切过去了为止。

        【轮询快、重发慢】: 以前共用一个 0.12 秒的节奏, 于是切换已经生效但 in_team()
        还没反映出来的那两三帧里又多发了几次同一个键, 那些键排在队里会在已经切回穗穗
        之后再触发一次。不管攻击键 —— 调用方全程按住, 这里不该动它。
        """
        timeout = self.DPS_TOUCH_OUT_TIMEOUT if timeout is None else timeout
        resend = self.SWITCH_KEY_RESEND if resend is None else resend
        start = time.time()
        last_send = 0.0
        while time.time() - start < timeout:
            in_team, current_index, _ = self.task.in_team()
            if in_team and current_index == index:
                return True
            if time.time() - last_send >= resend:
                self.task.send_key(index + 1)
                last_send = time.time()
            self.sleep(self.SWITCH_POLL, check_combat=False)
        return False

    def direct_switch(self, assume_intro=False):
        """按数字键直接切给交棒对象, 并按框架约定标记离场。"""
        target = self.switch_target()
        if target is None or target is self:
            return False
        has_intro = True if assume_intro else self.wait_con_full()
        if not self.switch_to_index(target.index):
            self.logger.warning(f'suisui direct switch to slot {target.index + 1} failed')
            return False
        self.logger.info(f'suisui direct switched to slot {target.index + 1} (intro={has_intro})')
        self.handoff_to(target, has_intro)
        return True

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
        # 这一行是框架 _choose_switch_target() 里设的, 漏了它接场角色的 has_intro
        # 永远是 False
        target.has_intro = has_intro
        if has_intro and hasattr(target, 'note_intro_handoff'):
            target.note_intro_handoff()
        target.last_switch_in_time = time.time()
        if has_intro:
            now = time.time()
            self.task.add_freeze_duration(now, target.intro_motion_freeze_duration, -100)
            self.last_outro_time = now

    def wait_con_full(self):
        """短暂轮询协奏是否满。不能只读一次: 放完大招那一刻协奏其实已经满了,
        但能量环读数滞后, 读成 0 就会把 has_intro 判成 False。"""
        if self.task.wait_until(self.is_con_full, time_out=self.HANDOFF_CON_WAIT):
            return True
        self.logger.info('suisui: con not full before switch, next char gets no intro')
        return False

    def switch_target(self):
        """交棒对象: 先按角色名找(不假设队伍顺序), 找不到再退回写死的槽位。"""
        for char in self.task.chars:
            if char is not None and char is not self and char.char_name == self.SWITCH_TARGET_NAME:
                return char
        index = self.DIRECT_SWITCH_INDEX - 1
        return next((c for c in self.task.chars if c is not None and c.index == index), None)

    def cast_field(self):
        """共鸣解放「山河水境」: 30秒领域, 效应上限+3。"""
        if not self.liberation_available():
            return False
        # click_f=False: 这个参数默认 True, 意思是"大招动画期间每 0.1 秒发一次F"。
        # 她的R动画 4.3 秒, 等于替全队按掉四十来次处决 —— 主C轴上那个F位就是被这些
        # 自动F提前吃掉的。全队的处决只归主C自己那一个点管
        if self.click_liberation(wait_if_cd_ready=0.3, click_f=False):
            self.logger.info('suisui field deployed')
            return True
        return False

    def forte3_available(self):
        """芳菲信是否满600。两道保险防误判导致提前开R: 连续命中才认;
        刚进濯雨时不足 MIN_MISTY_BEFORE_LIB 秒直接判否(物理上不可能满)。"""
        if 0 < self.misty_start and (time.time() - self.misty_start) < self.MIN_MISTY_BEFORE_LIB:
            return False
        if not self.task.find_one(Labels.suisui_forte3, threshold=self.FORTE3_THRESHOLD):
            self._forte3_hits = 0
            return False
        self._forte3_hits += 1
        return self._forte3_hits >= self.FORTE3_CONFIRM

    def switch_out(self, con_full=False):
        if con_full or self.current_con == 1:
            self.last_outro = time.time()  # 只有协奏满离场才真的放出了延奏
            self.misty_start = -1  # 延奏会退出濯雨时
        super().switch_out(con_full=con_full)

    def note_intro_handoff(self):
        """被别人用直接切人的方式交接进场时调用 —— 记下"我是带着变奏上来的"。"""
        self.intro_pending = True

    def on_combat_end(self, chars):
        # 只清当前这场战斗的状态, 不清 last_outro 这类时间戳(它自己会过期,
        # 主动清零反而会让锁定期失效)。也不要放进 reset_state(): 那个钩子每次
        # 重新识别队伍都会触发, 会在战斗中途把濯雨时的计时和锁定期一起抹掉
        self.misty_start = -1

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        main_dps = self.main_dps_teammate()
        lockout = self.MAIN_DPS_OUTRO_LOCKOUT if main_dps else self.OUTRO_LOCKOUT
        if self.time_elapsed_accounting_for_freeze(self.last_outro) < lockout \
                and self.has_other_candidate(current_char):
            return SwitchPriority.NO

        if main_dps is not None:
            # 队里有主C: 只接主C的延奏(闭环起新一轮)。要求 has_intro 是有意的 ——
            # 她的变奏技能本身就把她推进濯雨时, 没有变奏的入场要先花 4~6 秒攒水云息。
            # 其他所有情况让位, 尤其是洛瑟菈那一棒: 她的延奏是留给主C的
            if current_char is not None and current_char.is_main_dps and has_intro:
                return SwitchPriority.MUST
            if self.has_other_candidate(current_char):
                return SwitchPriority.NO
        return SwitchPriority.MUST

    def main_dps_teammate(self):
        return next((char for char in self.task.chars
                     if char is not None and char is not self and char.is_main_dps), None)

    def has_other_candidate(self, current_char):
        """返回 NO 之前确认还有别人能上, 否则切人逻辑会卡在原地空转。"""
        return any(char is not None and char is not self and char is not current_char
                   for char in self.task.chars)
