import time

from src.char.BaseChar import BaseChar, SwitchPriority


class Hiyuki(BaseChar):
    """绯雪 —— 主C。

    站场流程:
      放Q → 按住攻击键等R亮 → 放R变身(预求我身·见心) → 爆发宏 → 直接切人

    爆发宏(变身后, 分两段):
      [定时段] A3 → 闪避取消 → A3 → 长按E升空 → 空中居合×2(第2发之后点按E下落)
               → A3 →〔处决 → A1〕整组只在真有处决提示时才走
      [保底段] 闪避进居合架势 → 居合×3 → 长按终结重击·枯霜 → R2·归刃

    定时段全程按秒走, 不找图 —— 反应式循环每轮五六次找图, 居合会被开销撑开。
    保底段反过来全程看图不看秒: 被打断、寒意见底、处决时停把节奏推歪, 都在这里补回来,
    只要还站得住就一定交出【3 居合 + 终结重击 + R】。

    机制: 一套完整普攻回满【寒意】, 每段居合消耗 100 寒意 + 1 层【武霜·居合】,
    3 段居合叠满 3 层【淬寒·枯霜】才解锁终结重击, 终结重击给 1 点【锻雪·归刃】,
    最后长按 R2 消耗它。R2 是蓄力技, 每场第一轮攒得到 3 次蓄力, 之后每轮只有 1 次。

    居合的段数本场不是均分的: 6链第一轮够打 5 段(空中2 + 地面3), 之后每轮只够 4 段
    (空中2 + 地面2)。所以地面那组按 r2_used 分两档 —— 跟 R2 蓄力时长用的是同一个开关,
    因为它俩说的是同一件事: 这是不是本场第一轮。

    处决(F)带全局时停, 会把定时段整段推歪, 所以它被放在定时段的最后一个动作,
    后面紧跟的就是全看图的保底段 —— 时停推歪多少都无所谓。另外 F 同时是拾取/交互键,
    没有处决提示时空按会点到场景物件, 所以一定要先确认提示再按。

    深塔这种混合内容里, 有顿感条的波次才有处决。处决和它后面那发A是【一组】:
    处决打断A链, 那发A重接第三段回寒意; 没处决时补那发A就是硬接第四段, 紧接着又被
    闪避切掉。所以没提示时两个一起跳, A3 打完直接闪避进居合。
    """

    # ---- 站场 ----
    FIELD_TIME_OUT: float = 16.0  # 单次站场总预算 (秒)
    INTRO_HOLD_TIMEOUT: float = 8.0  # 上场后按住攻击键等R亮的上限 (秒)
    # 带变奏进场时, 至少按住攻击键这么久才开始读大招图标 (秒)。
    # 入场动画期间 HUD 读数不可信 —— 实测出现过"holding 0.4s 就说大招好了", 紧接着
    # "clicked liberation but no effect", 然后一路点普攻到超时。
    # 0.9 取自框架自己对入场动画的估计 (BaseChar.intro_motion_freeze_duration)
    INTRO_SETTLE: float = 0.9
    STANDARD_LIB_CD_MAX: float = 3.5  # lib1 CD ≤ 此值才进 perform_standard
    POST_LIB_SETTLE: float = 0.0  # 放完大招到切人前的缓冲 (秒)
    # perform_standard 每轮按住攻击键多久就回来重查一次 (秒)。
    # 切成小片只是为了不错过声骸/共鸣的可用窗口 —— 大招一亮它会立刻返回, 不会白按满
    STANDARD_HOLD_SLICE: float = 1.0
    HEAVY_FORTE_TIME_OUT: float = 1.2  # 强化重击的等待上限 (BaseChar 写死 2 秒, 太长)

    # ---- 爆发宏: 定时段 ----
    # 平A连点的间隔 (秒)。【这不是"每段之间等多久"】: 连段推进由动画决定, A3 特效出来
    # 之前多按的那几下会被输入缓冲吃掉, 不会多打出段数。所以快速连点只会让每一段一到
    # 可取消点就立刻接上, 比"点一下等半秒"更早到 A3 —— 原来 0.50 是在白等
    M_A_INTERVAL: float = 0.15
    # 一条A链从【第一下点击】到【A3特效出现】的时间 (秒)。
    # 所有收招键(闪避 / 长按E / 处决)等的都是这个 —— 不是"最后一下点击之后再等多久"。
    # 特效一出来寒意就到手了, 后面的收招可以直接删掉。
    #
    # 【给短了的失败日志抓不到】: a1@ a2@ a3@ 照样按时打印, 那记的是"发出去几下"不是
    # "打出来几下"。A3 没出来 = 寒意没回满 = 后面居合出不来 = 保底段跑补救(两三秒),
    # 比省下的那点时间贵得多。所以往下调要小步, 而且要看画面确认三下特效都在。
    #
    # 实战标定: 1.35 / 1.30 / 1.25 都能出 A3; 1.10 没等到特效就闪避了。
    # 1.20 是继续往下试的一档, 下界夹在 1.10 和 1.20 之间
    M_A_CHAIN: float = 1.20
    # 处决之后那【单独一下】A 到收招的时间 (秒)。它不是一条新连段, 是接着打第三段,
    # 所以用不到 M_A_CHAIN 那么久
    M_A_ONE: float = 0.55
    M_AFTER_DODGE: float = 0.35  # 闪避到下一个输入 (秒), 要够闪避位移演完
    DODGE_USE_MOUSE: bool = True  # 闪避用鼠标右键; False 则用键位配置里的 Dodge Key
    # 长按E的时长 (秒)。要够游戏判成长按, 否则退化成点按 = 飞不起来 / 落地不进架势
    M_HOLD_E_RISE: float = 0.85
    M_HOLD_E_LAND: float = 0.85  # 反应式回落里还在用
    RISE_E_WAIT: float = 1.2  # 升空前等E转好的上限 (秒)
    M_AFTER_RISE: float = 0.28  # 飞天到第一发空中居合 (秒), 压太小第一发会被吞
    # 空中最后一发居合到点按E下落的间隔 (秒)。给小了就是拿 E 把这一刀取消掉,
    # 居合没打出来, 寒意没扣, 淬寒也少一层
    M_KENDO_LAND: float = 0.55
    # 按住攻击键(= 终结重击打出)之后隔多久按住 R (秒)。
    # R 的时刻【必须相对重击算, 不能相对居合算】—— 它要落在重击动画里:
    #   给早了 → 重击动画还没立住, R 当场就放, 终结重击整个没打
    #   给晚了 → 重击演完了 R 才按, 中间停一下
    #
    # 实战标定: 0 / 0.2 / 0.35 必被顶掉; 0.6 / 0.7 偶发被顶; 0.8 稳(接R剩一点点停顿);
    # 0.95 更稳但停顿明显。
    #
    # 这个值曾经和 M_KENDO_TO_HOLD 合并成一个"从最后一刀居合算起"的绝对时刻 ——
    # 那是"最后一刀点完立刻按住"时期的写法。后来 M_KENDO_TO_HOLD 一路退回 0.90,
    # 合并的那个数却没跟着走, 于是 R 变成只隔 0.45 秒就按, 重击又被顶没了。
    # 所以现在拆开、并且让 R 的时刻由这两个数【算出来】, 动哪个都不会再漏
    HEAVY_TO_R: float = 0.80
    # 地面居合之间的间隔 (秒) —— 固定刀数, 点满就停手。
    #
    # 这个值要【略小于居合动画长度】: 点击会排队, 早按下的那一下会被缓冲住, 等前一刀
    # 演完立刻接上, 中间零空档 —— 跟手操狂点是一个效果。比动画长(0.52)的话, 每刀演完
    # 要干等一小会儿才轮到下一下点击, 表现就是"居合之间一顿一顿的"。
    #
    # 硬下界是【动画长度的一半】: 设动画 A、间隔 I, 若 2I < A, 第2、3下点击会落在同一段
    # 动画里, 而缓冲只存一个, 先到的那下直接被丢 —— 少一刀。A 约 0.5 秒, 所以别低于 0.26。
    # (早先 0.45 丢第三刀不是这个原因, 是被当时后面那个 0.55 的短空档顶掉的)
    #
    # 【改这个值必须同步改 M_KENDO_TO_HOLD】: 间隔压小之后最后一刀排队更久才演,
    # 而那个值是从"最后一下点击"算起的。每个间隔省多少, 就往末尾加回多少
    M_KENDO_INTERVAL: float = 0.45
    # 最后一刀居合点完到【按住攻击键】之间的保护间隔 (秒)。
    #
    # 这一段是必须的, 而且跟间隔是两回事: 最后那下点击还排在输入缓冲里没开始演,
    # 紧跟着一个长按下去, 会被当成重击输入把那一刀顶掉 —— 跟"R 顶掉重击"是同一类。
    #
    # 实战标定 —— 两侧的失败方式不一样, 窗口夹在 0.50 和 0.90 之间:
    #   0.05 / 0.18        → 第三刀居合被吃 (长按顶掉了还在队列里的那一刀)
    #   0.50 / 0.70 / 0.80 → 三刀都出, 但【重击没了】
    #   0.90               → 三刀都出, 重击也出 (当时 M_KENDO_INTERVAL=0.52)
    #   1.04               → 当前值。间隔从 0.52 压到 0.45, 两个间隔共省 0.14 秒,
    #                        最后一刀因此排队更久才演, 这里如数加回来, 末尾的绝对时刻不变
    #
    # 注意 0.50~0.80 那三次"失败"是被污染的: 当时 R 的时刻绑死在 last_kendo+1.35,
    # 于是这个值越大, R 距离按住攻击键就越近(0.80 时只剩 0.55 秒), 是 R 顶掉了重击,
    # 未必是长按落在居合动画里。R 现在改成相对按住攻击键算了, 这几档值得重新试
    #
    # 0.50 那次说明了一件事: 长按【不像点击那样能被输入缓冲接住】—— 落在居合动画里
    # 就直接丢了, 必须等那一刀演完再按。所以这个值的下界是"最后一刀居合演完"。
    #
    # 它同时决定重击【什么时候打出来】, 所以 R 的时刻是接在它后面算的:
    # last_kendo + M_KENDO_TO_HOLD + HEAVY_TO_R —— 动这个值不用再手动补 R
    M_KENDO_TO_HOLD: float = 1.04
    # 架势图标灭掉(= 最后一刀释放)之后, 隔多久按住攻击键 (秒)。
    # 慢放实测: 图标是在【释放那一刻】灭的, 从灭到动画演完还有 0.3~0.4 秒。
    # 所以这里只需要覆盖动画尾巴 —— 点击到释放之间那段不确定的排队, 由"等图标灭"
    # 自动吸收掉了, 不用再像 M_KENDO_TO_HOLD 那样按最坏情况盲等
    KENDO_RELEASE_TO_HOLD: float = 0.35
    # 居合最多点几下 (安全阀)。正常由架势图标决定停手, 这个只在图标一直读不到时兜底,
    # 免得一直点下去把普攻也点出来
    KENDO_MAX_CLICKS: int = 4
    # 空中居合接居合的间隔 (秒)。必须比地面那个大 —— 空中居合的动作更长, 用地面的 0.45
    # 会把第二刀整个吃掉(实测只出一刀)。0.60 是之前确认过"空中两刀都出得来"的值
    M_AIR_KENDO_INTERVAL: float = 0.60
    AIR_KENDO_COUNT: int = 2  # 空中居合次数
    M_AFTER_PLUNGE: float = 0.90  # 点按E后到落地能接普攻的时间 (秒): 下落 + 落地收招
    # 松开E到落地砸击走完、能接居合的时间 (秒)。反应式回落里还在用
    M_LAND_RECOVER: float = 0.20
    GROUND_A_COUNT: int = 3  # 落地后接的平A段数

    # ---- 处决 (F击破) ----
    EXECUTE_ENABLED: bool = True  # 关掉就完全跳过处决, 定时段直接进保底段
    M_EXECUTE_PROMPT_WAIT: float = 0.8  # 等处决提示消失(= 处决真的触发了)的上限 (秒)
    # 处决动画(全局时停)的时长 (秒)。时停期间画面是静止的, 找图分不出"演到哪了",
    # 只能按秒等。给短了后面那发A会被吞; 给长了只是白站着, 所以宁可给富余。
    #
    # 1.30 时实测 F 到那发A只隔 1.49 秒, 表现是"有时候"F 之后直接就闪避了 ——
    # 那发A落在时停里被吞掉, 只剩后面进居合的闪避。处决动画长度随敌人变,
    # 所以是时好时坏。1.6 是往富余那边给
    M_EXECUTE_ANIM: float = 1.60

    # ---- 爆发宏: 保底段 (全程看图) ----
    # 地面居合段数。6链绥雪本场第一轮多给一次居合(全场 5 段: 空中2 + 地面3),
    # 之后每轮只够地面 2 段。多点的那一下是空刀: 不进淬寒, 还会把架势点没,
    # 然后要多花两三秒走补救 —— 实测第二、三轮都是这么白扔的
    GROUND_KENDO_COUNT_FIRST: int = 3  # 本场第一轮
    GROUND_KENDO_COUNT: int = 2  # 之后每轮
    # 打完计划的居合之后, 等终结重击图标画出来的上限 (秒)。
    # 图标要一小会儿才渲染, 立刻判会误判成"没解锁"、白跑一趟补救(补普攻+闪避+再一刀,
    # 两三秒就没了)。实测 18 轮里 6 轮跑了补救, 其中几轮补完 lib_forte 就是 True ——
    # 那几轮纯属图标晚了一步, 是可以靠这个值省掉的
    LIB_FORTE_SETTLE: float = 0.6
    M_DODGE_TO_KENDO: float = 0.30  # 闪避到第一发居合 (秒)
    STANCE_WAIT: float = 0.8  # 闪避后等居合架势标记出现的上限 (秒)
    TAIL_TIME_OUT: float = 6.0  # 保底段补救的总预算 (秒), 超了就直接去放R
    KENDO_RETRY_STRIDE: int = 3  # 补救时连点几下居合还没解锁就改去补普攻+重进架势
    # R2 能量不满时补普攻的时间上限 (秒) —— 补到能开 R 为止, 不是"补几下就算了"。
    # 能量不够时 R 按下去是空的, 后面还要照着 R2_HOLD 干按四五秒, 那一轮的 R2
    # 整个没了, 日志里还照样报 released。所以宁可多站几秒也要把它补出来。
    # 之前写死"最多补 4 下", 实测出现过补满 4 下还是不够、然后空放的情况
    R2_ENERGY_WAIT: float = 6.0
    M_ENERGY_A_INTERVAL: float = 0.35  # 补能量时的普攻间隔 (秒)
    R2_REPEAT_INTERVAL: float = 0.2  # 按住期间重发按键的间隔 (秒), 防掉键
    # R 按住多久 (秒) —— 直接就是蓄力时长, 不再由别的数减出来。
    # 这样写是为了让按 R 的时机怎么调都【不】影响蓄力: 以前是"松R的绝对时刻减去
    # 按R的时刻", 每动一次按R的时机都得反向补一次, 补漏了蓄力就悄悄缩水
    R2_HOLD_FIRST: float = 9.05  # 每场第一轮 (3 次蓄力)
    R2_HOLD: float = 4.05  # 之后每轮 (1 次蓄力)

    # ---- 反应式回落 (宏没走通时) ----
    LIB2_KENDO_COUNT: int = 3  # 居合计数达此值才放 lib2
    HOLD_LIB_TIME_OUT: float = 8.0  # 长按大招的总超时 (秒)
    HOLD_LIB_CD_WAIT: float = 1.5
    POST_LIB2_TEAM_WAIT: float = 1.0  # 长按R2后等队伍UI (变身形态下常年误判, 别给太长)
    WAIT_LOCK_TIME_OUT: float = 2.0  # 大招前等重新锁定敌人的上限 (秒)

    # ---- 离场 ----
    # 协奏不满就不走: 穗穗的 MUST 要求"主C带着延奏离场", 空手走人这一切会落到洛瑟菈头上,
    # 洛瑟菈打完又切回绯雪 —— 绯洛来回乱切、穗穗一直进不来
    OUTRO_HARD_LIMIT: float = 25.0  # 绝对安全阀 (秒)
    OUTRO_STALL_TIME: float = 6.0  # 协奏这么久没涨就认输离场 (秒)
    CON_TOP_UP_CHAIN: float = 0.5  # 补协奏的普攻粒度 (秒)
    # 开始补协奏之前先给能量环留的渲染时间 (秒)。大招放完时协奏其实已经满了但读数滞后,
    # 立刻去读会读到 0, 于是白打一两下才发现早满了
    CON_SETTLE_WAIT: float = 0.8
    CON_SETTLE_POLL: float = 0.1
    # 交棒对象: 优先按角色名找(不假设队伍顺序), 名字找不到才退回这个槽位 (1-based)
    SWITCH_TARGET_NAME: str = 'char_suisui'
    DIRECT_SWITCH_INDEX: int = 1
    LIB_ANIM_WAIT: float = 4.0  # 切人前先等大招动画演完的上限 (秒)
    LEAVE_SWITCH_TIMEOUT: float = 3.5  # 直接切人等 in_team 确认的上限 (秒)
    LEAVE_KEY_INTERVAL: float = 0.12
    HANDOFF_CON_WAIT: float = 0.5  # 交接时等协奏读数稳定的上限 (秒)
    HANDOFF_CON_POLL: float = 0.1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib_permission = True
        self.lib2_count = 0  # 反应式回落里记录居合判定次数
        self.just_transformed = False  # 本次站场是否刚放出 lib1 变身
        self.r2_used = False  # 本场战斗是否已经放过 R2 —— 决定 R2 按住多久
        self.macro_t0 = 0.0  # 本轮宏的起点, 用来打时间轴
        self.macro_marks = []  # 本轮宏每个输入发出的时刻
        # 关掉框架的"切人时自动按F"。默认值是 not is_healer, 对主C是 True ——
        # 于是 BaseCombatTask.switch_next_char() 会在每次交棒时替她按掉处决。
        # 实测就是它把 F 提前用掉的: 洛瑟菈交棒给绯雪那一刻按了, 等绯雪走到轴上
        # 那个 F 的位置时已经 skip F (f_break=False bar_full=False) 了。
        # 全队的 F 现在只在 macro_execute() 那一个点按
        self.check_f_on_switch = False

    def switch_out(self, con_full=False):
        super().switch_out(con_full)
        self.lib2_count = 0
        self.just_transformed = False

    def reset_state(self):
        """框架重读队伍时调用 —— 归刃层数按场累计, 这里跟着归零。

        不能用 on_combat_end(): 那个只对战斗结束时【在场】的角色调用, 而绯雪放完 R2
        就切走了, 场上是穗穗 —— 她的 on_combat_end 永远不执行, r2_used 一直是 True,
        第一轮那档蓄力就永远不生效。reset_state() 是所有角色都会调的。
        """
        super().reset_state()
        self.r2_used = False

    # ------------------------------------------------------------------ 主流程

    def do_perform(self):
        # 声骸放最前面: 后面按住等到R亮就直接变身返回了, 放在循环里会被跳过
        self.click_echo(time_out=0)

        # 上场后一律"按住攻击键等R亮", 不看有没有吃到变奏 ——
        # 有没有变奏只影响心念起点(R亮得快慢), 手法本身一样。
        # 带变奏进场时必须先按住 INTRO_SETTLE 秒再读大招图标: 入场动画期间 HUD 读数
        # 不可信, liberation_available() 会假阳性, 于是 click_liberation 空放
        # ("clicked liberation but no effect"), 而 perform_standard 会掉进
        # "else: click()" 那条分支一路点普攻到 16 秒超时 —— 表现就是"入场后不停a"
        if self.has_intro or not self.liberation_available():
            self.hold_attack_until_lib(min_hold=self.INTRO_SETTLE if self.has_intro else 0.0)

        if self.has_long_action() and self.task.get_cd('liberation') <= self.STANDARD_LIB_CD_MAX:
            self.perform_standard()

        lib_ok = False
        # 宏的触发条件只看"这次站场变身了没有"。
        # 挂在 has_long_action2() 下面的话, 变身瞬间那个判定常常是 False, 整段爆发会被跳过
        if self.just_transformed:
            self.just_transformed = False
            lib_ok = self.transform_macro()

        if not lib_ok and self.has_long_action2():
            lib_ok = self.perform_lib()
        if not lib_ok and self.lib_permission and self.liberation_available():
            lib_ok = self.hold_liberation()
        if lib_ok:
            # check_combat=False 是关键: R2 打完那一刻目标往往刚死/丢失, 带战斗判定的 sleep
            # 会抛 NotInCombatException, 于是 leave() 一次都跑不到、整个 run 循环退出,
            # 下一轮 do_perform 又从 hold_attack_until_lib 开始按住攻击键
            self.sleep(self.POST_LIB_SETTLE, check_combat=False)

        # 放完大招就直接切, 不查协奏(读数滞后, 查了反而白打几下)
        self.leave(skip_outro=lib_ok)

    def hold_attack_until_lib(self, min_hold=0.0, timeout=None):
        """按住攻击键直到大招(R)亮起 —— 不放E, 不闪避。

        常世身下心念满时的【强化重击·寒簇】就是长按攻击键打出来的, 而它正是解锁大招的前置。

        Args:
            min_hold (float): 至少按住这么久才开始读大招图标 (秒)。带变奏进场时传
                INTRO_SETTLE —— 入场动画期间那个图标会假阳性。这段时间不浪费:
                照样按住攻击键攒心念。
        """
        timeout = self.INTRO_HOLD_TIMEOUT if timeout is None else timeout
        start = time.time()
        self.task.mouse_down()
        try:
            while self.time_elapsed_accounting_for_freeze(start) < timeout:
                if self.time_elapsed_accounting_for_freeze(start) < min_hold:
                    self.sleep(0.1)
                    continue
                if self.liberation_available():
                    self.logger.info(f'hiyuki: liberation up after '
                                     f'{self.time_elapsed_accounting_for_freeze(start):.1f}s of holding '
                                     f'(intro={self.has_intro})')
                    return True
                self.sleep(0.1)
        finally:
            self.task.mouse_up()
        self.logger.info('hiyuki: liberation still not up after holding, fall back to standard')
        return False

    def perform_standard(self):
        """常世身: 按住攻击键攒心念 → 放 lib1 变身。

        【这里一下普攻都不点】。心念靠长按攻击键打出的强化重击·寒簇来攒, 点普攻攒得慢,
        而且实战表现就是"变奏入场没直接重击, 反而多 A 了几下"。

        上游原版在两处点普攻, 都换成按住了:
          - `wait_until(liberation_available, post_action=click_with_interval)`
            —— 等大招亮的那 2 秒里一直点A;
          - `else: click(interval=0.1)` —— 回路没满时点A。
        这条支路本身就是"大招图标读到了却放不出来"时才会走到的(入场那几帧 HUD 会假阳性,
        日志 "clicked liberation but no effect"), 那时候要做的就是继续按住攒, 不是站着点A。

        上游还有一句 `self.task.click(key="right")`(闪避)也删了 —— 表现是"洛瑟菈交棒给
        绯雪, 绯雪莫名闪一下", 既不必要又把刚起来的连段断掉。
        """
        while self.has_long_action() and self.field_elapsed() < self.FIELD_TIME_OUT:
            # 先查大招: R 已经亮了就直接变身, 不再多按一下 E
            if self.liberation_available() and self.click_liberation(click_f=False):
                self.logger.debug('hiyuki perform lib1')
                self.just_transformed = True
                return

            self.click_echo(time_out=0)
            self.click_resonance(send_click=False, time_out=0, click_f=False)

            # 按住一小段就回来重查 —— 切成小片是为了不错过声骸/共鸣的可用窗口,
            # 长度由 STANDARD_HOLD_SLICE 控制。大招亮起会让它提前返回
            self.hold_attack_until_lib(timeout=self.STANDARD_HOLD_SLICE)
            self.sleep(0.05)

    def field_elapsed(self):
        """从被切上场算起已经站了多久 (last_perform 由 BaseChar.perform 打点)。"""
        return self.time_elapsed_accounting_for_freeze(self.last_perform)

    # ------------------------------------------------------------------ 爆发宏

    def transform_macro(self):
        """变身后的爆发。

        前半段(到处决为止)按秒走, 不找图 —— 反应式循环每轮要跑五六次找图再 sleep,
        居合会被这些开销撑开。后半段交给 finish_with_r2(), 那里全程看图。

        Returns:
            bool: 是否已经把 R2 放出去了。
        """
        ground_kendo = self.GROUND_KENDO_COUNT_FIRST if not self.r2_used else self.GROUND_KENDO_COUNT
        self.logger.info(f'hiyuki macro: A3-dodge-A3 -> hold E rise -> kendo x{self.AIR_KENDO_COUNT} '
                         f'(tap E on last) -> A{self.GROUND_A_COUNT} -> [execute -> A1] '
                         f'-> dodge -> kendo x{ground_kendo} -> final heavy -> R2')

        self.macro_start()
        self.macro_attacks()
        self.macro_dodge(self.M_AFTER_DODGE)  # 闪避打断

        self.macro_attacks()
        self.macro_rise()  # 升空进架势

        for i in range(self.AIR_KENDO_COUNT):
            last = i == self.AIR_KENDO_COUNT - 1
            self.macro_kendo(self.M_KENDO_LAND if last else self.M_AIR_KENDO_INTERVAL)
        # "第二发居合的同时点按E下落": 手感上的同时, 落到宏里是"这一刀挥出去之后紧接着按E"。
        # 真按在同一瞬间, E 会把居合取消掉 —— 那一刀根本没打出来。
        # 点按, 不是长按: 长按会变成落地进架势那一套
        self.macro_tap_e(self.M_AFTER_PLUNGE)

        self.macro_attacks()
        if self.macro_execute():
            # 只有处决真打出来才补这一发 —— 处决把A链打断了, 它重接第三段, 正好回寒意。
            # 没处决时补它就是硬接第四段, 紧接着又被闪避切掉, 白费一个身位
            self.macro_attacks(self.M_A_ONE, clicks=1)

        return self.finish_with_r2()

    # ------------------------------------------------------------------ 保底段

    def finish_with_r2(self):
        """闪避进居合架势 → 居合 → 终结重击 → R2。

        居合打几刀【不预先决定】, 由架势图标说了算: 一直点, 图标一灭就说明最后一刀已经
        释放出去了。实战里能打几刀是不确定的(3刀/2刀, 被打断时甚至只有1刀), 按计数硬打
        要么留刀在手里, 要么多点出一下普攻。

        图标是在【释放那一刻】灭的, 不是动画结束才灭 —— 慢放确认过, 从灭到动画演完还有
        0.3~0.4 秒。这一点很值钱: 它把"按住攻击键"的计时基准从【点击】换成了【释放】。
        点击到释放之间隔着一段不确定的排队, 盲等就必须按最坏情况给(M_KENDO_TO_HOLD 1.04
        秒), 而从释放起算只需要覆盖动画尾巴(KENDO_RELEASE_TO_HOLD 0.35 秒), 排队多久
        都自动吸收掉。

        图标有假阴性(日志里出现过"人在架势里却读不到"), 读丢就会少打一刀 ——
        由 recover_kendo() 按终结重击图标兜底, 两个信号互为保险。

        Returns:
            bool: 是否已经把 R2 放出去了。
        """
        start = time.time()
        planned = self.GROUND_KENDO_COUNT_FIRST if not self.r2_used else self.GROUND_KENDO_COUNT
        self.enter_kendo_stance()

        clicked = 0
        released = None
        while clicked < self.KENDO_MAX_CLICKS:
            self.macro_kendo(self.M_KENDO_INTERVAL)
            clicked += 1
            # 查图标的时机是【下一次点击之前】: 图标已经有整整一个间隔去更新,
            # 比"点完立刻查"可靠得多, 也就不会多点出那一下普攻
            if not self.in_kendo_stance():
                released = time.time()
                break

        if released is not None:
            hold_at = released + self.KENDO_RELEASE_TO_HOLD
        else:
            # 图标一直没灭: 要么读丢了, 要么刀数撞上安全阀。退回盲等那一套,
            # 从最后一下点击算起(刚才已经等过一个间隔, 扣掉)
            self.logger.info('hiyuki macro: kendo icon never went dark, falling back to timed hold')
            hold_at = time.time() + max(0.0, self.M_KENDO_TO_HOLD - self.M_KENDO_INTERVAL)

        total = clicked
        # 先给图标一点渲染时间再判 —— 直接判会把"刚解锁但还没画出来"当成没解锁。
        # 亮着的时候这一步只花一帧, 不会啃掉上面算出来的 hold_at
        if not self.task.wait_until(self.lib_heavy_available, time_out=self.LIB_FORTE_SETTLE):
            total += self.recover_kendo(start)
            hold_at = time.time() + self.M_KENDO_TO_HOLD  # 补救打乱了节奏, 重新起算
        self.logger.info(f'hiyuki macro: {total} ground kendo (planned {planned}, '
                         f'first_round={not self.r2_used}, icon_released={released is not None}), '
                         f'lib_forte={bool(self.lib_heavy_available())}')
        return self.hold_heavy_into_r2(hold_at)

    def recover_kendo(self, start):
        """终结重击还没亮就接着补, 直到亮起或者用完 TAIL_TIME_OUT 预算。

        没亮无非两个原因: 被打断吞了几下居合, 或者寒意见底居合根本没出来。两者在画面上
        分不清 —— 后者还会顺带让"架势标记"变得不可信 —— 所以不去猜, 直接按连点次数轮换:
        连点 KENDO_RETRY_STRIDE 下还没亮, 就当没进架势 / 没寒意, 补一套普攻再闪避重进。

        Returns:
            int: 额外补出的居合段数。
        """
        extra = 0
        since_reset = 0
        while not self.lib_heavy_available():
            if self.time_elapsed_accounting_for_freeze(start) >= self.TAIL_TIME_OUT:
                self.logger.warning('hiyuki macro: lib forte never lit up, going to R anyway')
                break
            if since_reset >= self.KENDO_RETRY_STRIDE or not self.in_kendo_stance():
                self.logger.info('hiyuki macro: kendo not landing, refill and re-enter stance')
                self.macro_attacks()  # 回寒意
                self.enter_kendo_stance()
                since_reset = 0
            self.macro_kendo()
            extra += 1
            since_reset += 1
        return extra

    def enter_kendo_stance(self):
        """闪避进居合架势, 等架势标记出现。

        等不到也照样往下走 —— 标记只是加速信号, 真正的判据是终结重击亮没亮,
        那个在 recover_kendo 里兜。
        """
        self.macro_dodge(self.M_DODGE_TO_KENDO)
        if self.task.wait_until(self.in_kendo_stance, time_out=self.STANCE_WAIT):
            return True
        self.logger.info('hiyuki macro: kendo stance not detected after dodge')
        return False

    def in_kendo_stance(self):
        """是否在居合架势里 (架势标记在就说明每下普攻都是一段居合)。"""
        return bool(self.task.find_one('hiyuki_left', threshold=0.5))

    def r2_press_time(self):
        """R 按住多久 (秒) —— 本场第一轮蓄三段, 之后每轮一段。"""
        return self.R2_HOLD if self.r2_used else self.R2_HOLD_FIRST

    def energy_ready(self):
        """R2 的能量满没满。

        大招是能量门控不是 CD 门控: 读 box_liberation 亮没亮, 别去读 CD 数字 ——
        大招图标上根本没有数字, has_cd('liberation') 永远是假的。
        """
        return self.current_liberation() > 0

    def top_up_energy(self):
        """R2 能量不够就一直补普攻, 补到能开 R 为止, 够了立刻停手。

        这是整条轴最后那道保底: 3 段居合把终结重击解锁了、重击也打出去了, 但偶尔
        R 的能量还差一点。那时候按 R 是按了个寂寞, 后面还要照着 R2_HOLD 干按
        4.9 ~ 9.9 秒, 一整轮站场就这么没了, 日志里还照样报 "R2 released" ——
        从外面完全看不出来。

        所以这里【不设次数上限】, 只有时间上限(R2_ENERGY_WAIT): 补到能开为止。
        之前写死"最多补 4 下", 实测出现过补满 4 下还是不够、然后空放的情况。
        能量本来就够时只花一次取色, 一下A都不会多打。

        位置必须在终结重击【之前】: R 是在重击动画里按下的, 到那一刻才发现能量不够
        就已经晚了 —— 补也来不及, 重击已经打出去了。

        Returns:
            int: 补了几下普攻。0 = 能量本来就够, 一下都没打。
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
                self.logger.info(f'hiyuki macro: R2 energy full after {n} extra attack(s), '
                                 f'{self.time_elapsed_accounting_for_freeze(start):.1f}s')
                return n
        self.logger.warning(f'hiyuki macro: R2 energy still not full after {n} attacks / '
                            f'{self.R2_ENERGY_WAIT:.1f}s, releasing anyway')
        return n

    def hold_heavy_into_r2(self, hold_at):
        """按住攻击键打出终结重击 → 重击动画里按住 R 蓄力 → R2。

        机制(前面按错过两次, 记在这):
          淬寒满时, 按住攻击键的【第一下】就直接放出终结重击 —— 攻击键这边没有任何
          蓄力过程, 所以既不需要按住多久, 松手也不是"打出重击"的那一刻。
          蓄力全部发生在【终结重击的动画期间, R 被按住的那段】: 6链第一轮能蓄三段,
          之后每轮只有一段, 对应 R2_HOLD_FIRST / R2_HOLD。

        试过"最后一刀居合点完立刻按住攻击键", 想让长按被缓冲接住做到零空档 —— 不行:
        长按【不像点击那样能被缓冲】, 落在居合动画里就直接丢了, 重击根本不出。
        所以按住的时刻必须等那一刀演完 —— 由调用方算好传进来。

        R 的时刻相对【按住攻击键那一刻】算, 不是相对居合算 —— 它要落在重击动画里:
          - R 早了 → 重击动画还没立住, R 当场就放了, 终结重击整个没打;
          - R 晚了 → 重击早就打完了, 中间白站一截才起 R2。

        Args:
            hold_at (float): 打算按住攻击键的时刻(墙钟)。已经过了就立刻按。
        """
        # 补过能量的话, 上面算的按住时刻作废 —— 那几下普攻自己要收招,
        # 按原时刻早就过期了, 长按会落在普攻动画里被丢, 重击又没了
        if self.top_up_energy():
            hold_at = time.time() + self.M_A_ONE
        self.logger.info(f'hiyuki macro timeline: {self.macro_timeline()}')
        self.logger.info('hiyuki macro: hold attack (final heavy) -> hold R to charge')
        press_time = self.r2_press_time()

        self.macro_wait(max(0.0, hold_at - time.time()))
        start = time.time()
        self.task.mouse_down()  # 按住攻击键 = 终结重击打出
        try:
            # R 相对【按住攻击键那一刻】算, 落在重击动画里
            self.macro_wait(self.HEAVY_TO_R)
            self.task.send_key_down(self.get_liberation_key())  # 动画期间按住R开始蓄力
        finally:
            self.task.mouse_up()  # 重击已经放出去了, 攻击键留着没用

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
        self.logger.info(f'hiyuki macro: R2 released (R held {press_time:.1f}s, '
                         f'pressed {self.HEAVY_TO_R:.2f}s after heavy, '
                         f'total {time.time() - start:.1f}s)')
        return True

    def macro_start(self):
        """开一条新的宏时间轴。"""
        self.macro_t0 = time.time()
        self.macro_marks = []

    def macro_mark(self, name):
        """记一笔输入发出的时刻 (秒, 相对宏起点)。

        整套走完打成一行 —— 对着录像就能看出是哪一下被吞了: 日志里某个输入的时刻
        比画面上那一段动作的起点还早, 就是它把前一段取消掉了。
        """
        self.macro_marks.append(f'{name}@{time.time() - self.macro_t0:.2f}')

    def macro_timeline(self):
        return ' '.join(self.macro_marks)

    def macro_wait(self, sec):
        """精确等待: 直接用 time.sleep 绕过执行器。

        self.sleep() 每 0.4 秒会插进一次截图 + 战斗判定 (CombatCheck.sleep_check_interval),
        插入位置不可控, 排不了帧级时序。代价是这几百毫秒内任务无法响应暂停/停止。
        """
        if sec > 0:
            time.sleep(sec)

    def macro_attacks(self, chain_time=None, clicks=None):
        """连点普攻推进一条连段, 【全程】点到 A3 特效出现为止。

        必须整段一直点, 不能"点几下就停手等着": 输入缓冲只存一个输入, 前面挤着点的那几下
        会被同一段动画一起吃掉, 队列一空后面的段就没人触发了。
        实测"0.15秒点3下然后干等到1.10秒"就是这个下场 —— A2 之后队列空掉, A3 根本没出来。

        收招时刻由 chain_time 决定, 是从【第一下点击】算起的绝对时间, 跟点了几下无关:
        连段推进由动画决定, 点得再快 A3 该什么时候出还是什么时候出。

        Args:
            chain_time (float): 从第一下点击到收招的总时长 (秒)。默认 M_A_CHAIN。
            clicks (int): 最多点几下, 默认不限(整段连点)。
                处决之后那一下是"接着打第三段"、只要一下, 必须传 1 ——
                不限的话会连点五下把连段推到第四第五段去, 那不是这条轴要的东西。
        """
        chain_time = self.M_A_CHAIN if chain_time is None else chain_time
        start = time.time()
        n = 0
        while True:
            self.click()
            n += 1
            self.macro_mark(f'a{n}')
            remaining = chain_time - (time.time() - start)
            if remaining <= 0 or (clicks is not None and n >= clicks):
                break
            self.macro_wait(min(self.M_A_INTERVAL, remaining))
        self.macro_wait(max(0.0, chain_time - (time.time() - start)))

    def macro_rise(self):
        """长按E升空。

        空中那两刀全指着这一下, 白按一次整段就没了 —— 而且从日志上看不出来:
        E_down/E_up 只证明键发出去了, 不证明人飞起来了。所以按之前把E的CD读出来记进日志,
        下一轮就能分清"E在转CD"和"E按了但被A3收招吃掉"这两种完全不同的毛病。

        读CD走的是技能栏OCR, 只在这一个点读一次, 大概几十毫秒 —— 它会把 E_down 往后推
        一点点, 时间轴上看得见。真被推得太多就把这个检查关掉(RISE_E_WAIT 设成 0 不够,
        得连 get_cd 一起去掉)。
        """
        cd = self.task.get_cd('resonance')
        if cd > 0 and self.RISE_E_WAIT > 0:
            self.logger.warning(f'hiyuki macro: resonance on cd {cd:.1f}s at rise, waiting')
            self.task.wait_until(lambda: self.task.get_cd('resonance') <= 0,
                                 post_action=self.click, time_out=self.RISE_E_WAIT)
        self.logger.info(f'hiyuki macro: rise (resonance cd was {cd:.1f}s)')
        self.macro_hold_e(self.M_HOLD_E_RISE, self.M_AFTER_RISE)

    def macro_dodge(self, settle):
        """闪避。

        默认走鼠标右键 —— 上游 Hiyuki 和守岸人的自动闪避都是右键。如果游戏里把右键
        解绑了, 把 DODGE_USE_MOUSE 设成 False, 改用键位配置里的 Dodge Key。
        """
        if self.DODGE_USE_MOUSE:
            self.task.click(key='right')
        else:
            self.task.send_key(self.task.key_config.get('Dodge Key'))
        self.macro_mark('dodge')
        self.macro_wait(settle)

    def macro_hold_e(self, hold, settle):
        """长按共鸣技能键。时长必须跨过长按判定门槛, 否则会被当成点按。"""
        self.task.send_key_down(self.get_resonance_key())
        self.macro_mark('E_down')
        self.macro_wait(hold)
        self.task.send_key_up(self.get_resonance_key())
        self.record_resonance_use()
        self.macro_mark('E_up')
        self.macro_wait(settle)

    def macro_tap_e(self, settle):
        """点按共鸣技能键 (空中 = 下落)。按下时长必须短过长按门槛。"""
        self.task.send_key(self.get_resonance_key())
        self.record_resonance_use()
        self.macro_mark('E_tap')
        self.macro_wait(settle)

    def macro_kendo(self, settle=None):
        """架势中点一下普攻 = 一发居合。

        默认按"后面还要接下一刀"的间隔走; 后面接的不是居合时传 M_KENDO_LAND。
        """
        self.click()
        self.macro_mark('kendo')
        self.macro_wait(self.M_KENDO_INTERVAL if settle is None else settle)

    def macro_execute(self):
        """处决(F击破)。没有处决提示就直接跳过。

        不空按 F: F 同时是拾取/交互键, 场景里有可交互物件时空按会点到它。
        框架的 can_break 只在带战斗判定的 sleep 里刷新, 而定时段用的是裸 time.sleep,
        所以这里自己抓一帧现查。

        Returns:
            bool: 处决是否真的按出去了。
        """
        if not self.EXECUTE_ENABLED:
            return False
        if not self.execute_available():
            return False

        start = time.time()
        self.task.send_key('f')
        self.macro_mark('F')
        self.task.can_break = False  # 自己按掉的, 别让切人时再按一次

        # 提示消失 = 处决确实触发了; 之后的时停画面是静止的, 找图看不出演到哪, 只能按秒等
        self.task.wait_until(lambda: not self.execute_prompt(), time_out=self.M_EXECUTE_PROMPT_WAIT)
        self.macro_wait(self.M_EXECUTE_ANIM)
        self.add_freeze_duration(start, time.time() - start)
        self.logger.info(f'hiyuki macro: execute done in {time.time() - start:.1f}s')
        return True

    def execute_available(self):
        """这一帧屏幕上有没有【现在就能按】的处决提示。

        只认屏幕中央那个 F 提示。框架另外两个信号都不能拿来当判据:

          - `task.can_break`: 粘滞标记, 只在 CombatCheck.f_break() 真按下去或者整场重置时
            才清。战斗判定线程在别的角色场上看到过一次击破就一直是 True —— 实测挂着它跑,
            五轮五次都在同一秒按了 F, 画面上根本没有处决。
          - `f_break_full`: 顿感条满 ≠ 现在能按 F。条满了但处决窗口还没开就按下去, 就是
            "提前按F": 这一下不会进处决, 而是被当成拾取/交互吃掉, 后面整段跟着乱。

        bar_full 仍然读出来打进日志, 但只作诊断 —— 看到 `f_break=False bar_full=True`
        就说明那一刻正是"条满了但还按不得", 跳过是对的。
        """
        self.task.next_frame()
        prompt = bool(self.execute_prompt())
        if prompt and not self.task.is_pick_f():
            return True
        bar_full = bool(self.task.find_one('f_break_full', threshold=0.92))
        self.logger.info(f'hiyuki macro: skip F (f_break={prompt} bar_full={bar_full})')
        return False

    def execute_prompt(self):
        """屏幕中央的处决 F 提示还在不在 (框大小抄自 CombatCheck.check_f_break)。"""
        box = self.task.box_of_screen(0.2, 0.2, 0.75, 0.8, hcenter=True, vcenter=True)
        return bool(self.task.find_one('f_break', box=box, target_height=720))

    # ------------------------------------------------------------------ 反应式回落

    def perform_lib(self):
        """宏没走通时的兜底: 上游原版的反应式循环。

        居合靠 hiyuki_left 分支打出来 —— 检测到架势标记就持续点普攻直到标记消失。
        """
        timeout = self.FIELD_TIME_OUT
        while self.has_long_action2() and self.field_elapsed() < timeout:
            self.click_echo(time_out=0)

            lib_heavy_avail = self.lib_heavy_available()
            is_timeout = self.field_elapsed() >= timeout - 0.5

            if self.lib_permission and self.liberation_available() and (
                    self.lib2_count >= self.LIB2_KENDO_COUNT or is_timeout):
                if self.hold_liberation():
                    self.logger.info(f'hiyuki perform lib2 (count: {self.lib2_count}, '
                                     f'timeout: {is_timeout})')
                    self.lib2_count = 0
                    return True

            res_resonance = self.click_resonance(send_click=False, time_out=0, click_f=False)
            if res_resonance and res_resonance[0]:
                if is_timeout:
                    break
                self.macro_hold_e(self.M_HOLD_E_LAND, self.M_LAND_RECOVER)
            elif lib_heavy_avail:
                if is_timeout:
                    break
                if self.wait_locked(self.WAIT_LOCK_TIME_OUT):
                    self.heavy_forte_fast(self.lib_heavy_available)
                if self.task.wait_until(self.liberation_available, post_action=self.click, time_out=0.5):
                    if self.wait_locked(self.WAIT_LOCK_TIME_OUT) and self.hold_liberation():
                        self.lib2_count = 0
                        return True
                self.lib2_count += 1
                self.sleep(0.1)
            elif self.in_kendo_stance():
                # 居合架势: 标记在就一直点普攻, 每一下都是一段居合
                self.task.wait_until(lambda: not self.in_kendo_stance(),
                                     post_action=self.click, time_out=3.0)
                if is_timeout:
                    break
                self.sleep(0.1)
            elif bool(self.task.find_one('hiyuki_right', threshold=0.5)):
                self.task.click(key="right", interval=1.0)
                self.sleep(0.1)
            else:
                self.click()
            self.sleep(0.05)

        if self.lib_permission and self.liberation_available():
            if self.hold_liberation():
                self.logger.warning('hiyuki perform lib2 (final fallback)')
                self.lib2_count = 0
                return True
        return False

    def hold_liberation(self):
        """长按大招键放 lib2 (只在宏没走通时用到)。

        相对原版三处修补:
          1. 返回 True 必须代表"确实按下去了" —— 原版无论有没有按都返回 True,
             上层会以为 lib2 已经放出而直接切人, 白扔一次爆发;
          2. 补 record_liberation_use() —— 否则 get_cd('liberation') 一直是旧值;
          3. 循环退出后继续按住蓄力 —— 循环条件是 liberation_available(), R2 一放出去
             它立刻变 False, 循环当场退出、松开 R 键, 等于一点都没蓄。
        """
        if not self.task.use_liberation:
            return False

        last_click = 0
        sent = False
        start = time.time()
        while self.task.in_team()[0] and (
                self.liberation_available() or self.task.get_cd('liberation') <= self.HOLD_LIB_CD_WAIT) \
                and time.time() - start < self.HOLD_LIB_TIME_OUT:
            if time.time() - start > last_click:
                self.task.send_key_down(self.get_liberation_key())
                sent = True
                last_click += 0.2
            self.sleep(0.05, check_combat=False)

        if sent:
            press_time = self.r2_press_time()
            charge_start = time.time()
            last = 0.0
            while time.time() - charge_start < press_time:
                if time.time() - charge_start >= last:
                    self.task.send_key_down(self.get_liberation_key())
                    last += self.R2_REPEAT_INTERVAL
                self.sleep(0.05, check_combat=False)
            self.r2_used = True
            self.logger.info(f'hold_liberation: charged {press_time:.1f}s')

        self.task.in_liberation = True
        self.task.send_key_up(self.get_liberation_key())

        if not sent:
            self.task.in_liberation = False
            self.logger.debug('hold_liberation sent nothing')
            return False

        self.task.wait_until(lambda: self.task.in_team()[0], time_out=self.POST_LIB2_TEAM_WAIT)
        self.task.in_liberation = False
        self.record_liberation_use()
        self.add_freeze_duration(start, time.time() - start)
        self.logger.info(f'hold_liberation end {time.time() - start:.1f}s')
        return True

    # ------------------------------------------------------------------ 离场

    def leave(self, skip_outro=False):
        """唯一的离场口。

        整段关掉脱战判定 —— 打完爆发时常出现"目标丢失 -> 判定脱战"的误报,
        那时 check_combat() 一抛异常, 切人就再也执行不到了。
        """
        previous = getattr(self.task, 'skip_combat_check', False)
        self.task.skip_combat_check = True
        try:
            if skip_outro:
                self.logger.info('hiyuki switching right after liberation, skip con check')
                if self.direct_switch(assume_intro=True):
                    return
            else:
                self.ensure_outro()
            self.switch_next_char()
        except Exception as e:
            self.logger.warning(f'hiyuki leave failed ({e}), trying direct switch')
            if not self.direct_switch():
                raise
        finally:
            self.task.skip_combat_check = previous

    def ensure_outro(self):
        """协奏不满就不离场: 继续输出直到打满, 满了立刻停手去切人。

        两个安全阀防卡死: 协奏卡住不涨(OUTRO_STALL_TIME) 或站够绝对上限(OUTRO_HARD_LIMIT)。
        """
        # 先等读数稳定: 大招刚放完时协奏往往已经满了, 只是能量环还没渲染回来
        settle = time.time()
        while time.time() - settle < self.CON_SETTLE_WAIT:
            if self.is_con_full():
                return True
            self.sleep(self.CON_SETTLE_POLL)

        start = time.time()
        best_con = self.get_current_con()
        last_gain = time.time()
        self.logger.info(f'hiyuki con {best_con:.2f}, topping up before outro')

        while True:
            if self.is_con_full():
                self.logger.info(f'hiyuki con full after '
                                 f'{self.time_elapsed_accounting_for_freeze(start):.1f}s, switching now')
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
            res_resonance = self.click_resonance(send_click=False, time_out=0, click_f=False)
            if res_resonance and res_resonance[0]:
                self.macro_hold_e(self.M_HOLD_E_LAND, self.M_LAND_RECOVER)
                self.macro_kendo()
                continue
            if self.is_mouse_forte_full():
                self.heavy_forte_fast(self.is_mouse_forte_full)
                continue
            self.continues_normal_attack(self.CON_TOP_UP_CHAIN, until_con_full=True)

    def direct_switch(self, assume_intro=False):
        """按数字键直接切给交棒对象, 并自己补上框架的交接记账。

        不走 switch_next_char(): 那个函数内部有三处 continues_normal_attack / click,
        大招之后不想要那几下多余的 A。
        """
        target = self.switch_target()
        if target is None or target is self:
            return False
        slot = target.index + 1
        # 刚放完大招时直接认定协奏是满的 —— 读数滞后会把 has_intro 误判成 False,
        # 那样穗穗会以为自己空手入场, 跑去走开场那套"按住攻击键"的流程
        has_intro = True if assume_intro else self.wait_con_full()

        # 大招动画期间就按住普攻并且开始狂发切人键, 不再干等动画演完:
        #   - 按住普攻: 动画一结束控制权回来, 攻击立刻接上, 中间不留空窗;
        #   - 狂发切人键: 动画期间 in_team() 读不出来, 键发出去看似是白发, 但代价只是
        #     多发几次, 换来的是"能切的第一帧就切走"。原来那段先等再发, 白白多站一截。
        # 松手时机: 切成之后立刻松 —— 接场的穗穗自己会重新按住走她的长按轴
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
                self.sleep(self.LEAVE_KEY_INTERVAL, check_combat=False)
        finally:
            self.task.mouse_up()
        self.logger.warning(f'hiyuki direct switch to slot {slot} failed')
        return False

    def handoff_to(self, target, has_intro):
        """把场上角色交接给 target —— 复刻 switch_next_char() 内部那套记账。

        直接按数字键切人绕开了框架的交接逻辑, 必须自己补上, 否则:
          - 没人的 is_current_char 是 True → get_current_char() 返回 None → 下一帧崩溃;
          - has_intro / last_outro_time 不更新, 下一个角色拿不到变奏。
        """
        self.task.in_liberation = False
        self.switch_out(con_full=has_intro)
        target.is_current_char = True
        target.has_intro = has_intro
        if has_intro and hasattr(target, 'note_intro_handoff'):
            # has_intro 是易失的: reset_state() 每次重读队伍都会清掉它, 而战斗判定一抖动
            # 就会重进战斗、重读队伍。所以再给对方打一个它自己保管的持久标记
            target.note_intro_handoff()
        target.last_switch_in_time = time.time()
        if has_intro:
            now = time.time()
            self.task.add_freeze_duration(now, target.intro_motion_freeze_duration, -100)
            self.last_outro_time = now

    def wait_con_full(self):
        """短暂轮询协奏是否满 —— 必须在【按切人键之前】读。

        切走之后能量环显示的已经是新角色的了, 那时再读永远读不到自己的协奏。
        """
        start = time.time()
        while time.time() - start < self.HANDOFF_CON_WAIT:
            if self.is_con_full():
                return True
            self.sleep(self.HANDOFF_CON_POLL, check_combat=False)
        self.logger.info('hiyuki: con not full before switch, next char gets no intro')
        return False

    def switch_target(self):
        """交棒对象: 先按角色名找, 找不到再退回写死的槽位。

        按名字找是为了不假设队伍顺序 —— 别人的队里穗穗未必在 1 号位。
        本队两条路指向同一个人, 所以这层是纯增量, 不改变现有行为;
        名字也找不到、槽位也取不到时返回 None, 调用方会退回框架的 switch_next_char()。
        """
        for char in self.task.chars:
            if char is not None and char is not self and char.char_name == self.SWITCH_TARGET_NAME:
                return char
        return self.char_at_slot(self.DIRECT_SWITCH_INDEX)

    def char_at_slot(self, slot):
        """按队伍位置 (1-based) 取角色, 越界返回 None。"""
        index = slot - 1
        for char in self.task.chars:
            if char is not None and char.index == index:
                return char
        return None

    # ------------------------------------------------------------------ 工具

    def lib_heavy_available(self):
        """终结重击·枯霜是否已解锁 (3 层淬寒满)。"""
        return bool(self.task.find_one('hiyuki_lib_forte', threshold=0.7))

    def heavy_forte_fast(self, check_fun, time_out=None):
        """强化重击, 等待上限可调。

        BaseChar.heavy_click_forte 的 wait_until 写死 2 秒, 回路一直没打掉时就白按满 2 秒。
        """
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
        """等到重新锁定敌人再返回 True; 期间持续普攻, 既维持锁定又不空转。"""
        return bool(self.task.wait_until(self.has_long_action2, post_action=self.click, time_out=time_out))

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name in {'char_linnai', 'char_lucilla'}:
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)
