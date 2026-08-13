"""队伍级出招逻辑基类。

当某个队伍预设配置了 team code 时,战斗循环会用该预设对应的
BaseTeamCombat 子类的 perform() 完全替代三个角色的独立 perform(),
即"队伍级操作逻辑"优先级最高。
"""

import time

from ok import Logger

logger = Logger.get_logger(__name__)


class BaseTeamCombat:
    """队伍级出招逻辑基类。

    子类必须实现 perform();每 tick(战斗循环迭代)调用一次,
    用实例属性跨 tick 记住进度。可通过 self.chars 访问三个角色对象
    (可能为 None),通过 self.task 访问任务(截图/按键/日志等)。
    """

    def __init__(self, task, chars):
        self.task = task
        self.chars = chars or [None, None, None]

    # ---------- 角色访问 ----------

    def char(self, index):
        """第 index(0 基)个角色对象,越界或缺失返回 None。"""
        if index < 0 or index >= len(self.chars):
            return None
        return self.chars[index]

    @property
    def current_char(self):
        """当前在场角色。"""
        for c in self.chars:
            if c is not None and c.is_current_char:
                return c
        return None

    def is_current(self, index):
        c = self.char(index)
        return c is not None and c.is_current_char

    @property
    def current_index(self):
        """当前在场角色的槽位(0 基);无人时返回 None。"""
        c = self.current_char
        return c.index if c is not None else None

    def switch_to(self, index):
        """直接切换到第 index 个角色,不经过优先级选人。

        与 switch_next_char 不同,目标由脚本自己决定,适合轮换逻辑。
        不做入场技判断(想用入场技请用 f_break / wait_intro)。
        等待检测到切换完成,超时返回 False 并记录错误日志。

        Returns:
            bool: 是否切换成功。
        """
        target = self.char(index)
        if target is None:
            return False
        if target.is_current_char:
            return True
        timeout = getattr(self.task, 'switch_char_time_out', 10)
        start = time.time()
        last_click = 0
        while time.time() - start < timeout:
            self.task.check_combat()
            in_team, current_index, _ = self.task.in_team()
            if not in_team:
                self.task.raise_not_in_combat('switch_to: not in team')
            if current_index == target.index:
                break
            now = time.time()
            if now - last_click > 0.1:
                self.task.send_key(target.index + 1)
                self.task.sleep(0.001)
                self.task.click()
                self.task.sleep(0.001)
                last_click = now
            self.task.next_frame()
        else:
            self.log_error(f'switch_to {index} timed out')
            return False
        current = self.current_char
        if current is not None and current is not target:
            current.switch_out()
            current.is_current_char = False
        target.is_current_char = True
        target.last_switch_in_time = time.time()
        if hasattr(self.task, 'in_liberation'):
            self.task.in_liberation = False
        return True

    # ---------- 动作转发 ----------

    def click(self, index, *args, **kwargs):
        c = self.char(index)
        return c.click(*args, **kwargs) if c is not None else None

    def click_resonance(self, index, *args, **kwargs):
        c = self.char(index)
        return c.click_resonance(*args, **kwargs) if c is not None else None

    def click_liberation(self, index, *args, **kwargs):
        c = self.char(index)
        return c.click_liberation(*args, **kwargs) if c is not None else None

    def click_echo(self, index, *args, **kwargs):
        c = self.char(index)
        return c.click_echo(*args, **kwargs) if c is not None else None

    def heavy_click_forte(self, index, check_fun=None):
        c = self.char(index)
        return c.heavy_click_forte(check_fun=check_fun) if c is not None else None

    def switch_next_char(self, index, *args, **kwargs):
        """让第 index 个角色执行下一次切换(内部按 get_switch_priority 选目标)。"""
        c = self.char(index)
        return c.switch_next_char(*args, **kwargs) if c is not None else None

    def switch_out(self, index, con_full=False):
        c = self.char(index)
        return c.switch_out(con_full=con_full) if c is not None else None

    def wait_intro(self, index, **kwargs):
        c = self.char(index)
        return c.wait_intro(**kwargs) if c is not None else None

    def wait_down(self, index, click=True):
        c = self.char(index)
        return c.wait_down(click=click) if c is not None else None

    # ---------- 状态查询 ----------

    def is_available(self, index, percent, box_name):
        c = self.char(index)
        return c.is_available(percent, box_name) if c is not None else False

    def has_cd(self, index, box_name):
        c = self.char(index)
        return c.has_cd(box_name) if c is not None else True

    def has_buff(self, index):
        c = self.char(index)
        return c.has_buff() if c is not None else False

    def has_all_buff(self, index):
        c = self.char(index)
        return c.has_all_buff() if c is not None else False

    def resonance_available(self, index):
        c = self.char(index)
        return c.resonance_available() if c is not None else False

    def echo_available(self, index):
        c = self.char(index)
        return c.echo_available() if c is not None else False

    def liberation_available(self, index=None):
        """第 index 个角色的共鸣解放是否就绪。

        当前在场角色直接检测技能区高亮;不在场的角色依赖
        task.update_lib_portrait_icon() 刷新的头像解放标记
        (战斗循环每 tick 会调用,脚本里也可主动调用 next_frame)。
        """
        index = index if index is not None else self.current_index
        c = self.char(index)
        if c is None:
            return False
        if c.is_current_char:
            return c.liberation_available()
        self.task.update_lib_portrait_icon()
        return bool(getattr(c, '_liberation_available', False))

    def con_percent(self, index=None):
        """协奏值 0~1;仅在当前在场角色上可测,其他槽位返回 None。"""
        index = index if index is not None else self.current_index
        c = self.char(index)
        if c is None or not c.is_current_char:
            return None
        return c.get_current_con()

    def con_full(self, index=None):
        """协奏值是否已满;仅在当前在场角色上可测。"""
        index = index if index is not None else self.current_index
        c = self.char(index)
        if c is None or not c.is_current_char:
            return False
        return c.is_con_full()

    def cd_remaining(self, index, box_name):
        """第 index 个角色指定技能的剩余冷却秒数。

        box_name: 'resonance' / 'echo' / 'liberation'。
        """
        c = self.char(index)
        if c is None:
            return 0
        return self.task.get_cd(box_name, c.index)

    def char_is(self, index, char_name):
        """第 index 个槽位是否是指定角色类(如 'Verina')。"""
        c = self.char(index)
        return c is not None and c.char_name == char_name

    def next_frame(self):
        """推进到下一帧并刷新状态(循环里记得调用,避免卡死在自身逻辑)。"""
        self.task.next_frame()

    def check_combat(self):
        """战斗状态检查(不在战斗时抛异常,由任务统一兜底)。"""
        self.task.check_combat()

    def log_info(self, msg):
        fn = getattr(self.task, 'log_info', None)
        if fn is not None:
            fn(msg)
        else:
            logger.info(msg)

    def log_debug(self, msg):
        fn = getattr(self.task, 'log_debug', None)
        if fn is not None:
            fn(msg)
        else:
            logger.debug(msg)

    def log_error(self, msg):
        fn = getattr(self.task, 'log_error', None)
        if fn is not None:
            fn(msg)
        else:
            logger.error(msg)

    # ---------- 其他 ----------

    def sleep(self, sec, check_combat=True):
        if not check_combat:
            self.task.skip_combat_check = True
        self.task.sleep(sec)
        self.task.skip_combat_check = False

    def use_tool_box(self, index):
        c = self.char(index)
        return c.use_tool_box() if c is not None else None

    def perform(self):
        """每 tick 调用一次,子类必须实现。"""
        raise NotImplementedError("team logic must implement perform()")