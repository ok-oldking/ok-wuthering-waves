import time  # noqa
from enum import IntEnum, StrEnum  # noqa
from typing import Any  # noqa

import cv2  # noqa
import numpy as np  # noqa

from ok import Config, Logger  # noqa
from src import text_white_color  # noqa

SKILL_TIME_OUT = 15


class Priority(IntEnum):
    """定义切换角色的优先级枚举。"""
    MIN = -999999999  # 最低优先级
    SWITCH_CD = -1000  # 切换冷却中
    CURRENT_CHAR = -100  # 当前角色
    CURRENT_CHAR_PLUS = CURRENT_CHAR + 1  # 当前角色稍高优先级 (特殊情况)
    SKILL_AVAILABLE = 100  # 有可用技能
    BASE_MINUS_1 = -1
    BASE = 0
    MAX = 9999999999  # 最高优先级
    FAST_SWITCH = MAX - 100  # 快速切换优先级 (例如应对特殊机制)


class Role(StrEnum):
    """定义角色定位枚举。"""
    DEFAULT = 'Default'  # 默认/未知定位
    SUB_DPS = 'Sub DPS'  # 副输出
    MAIN_DPS = 'Main DPS'  # 主输出
    HEALER = 'Healer'  # 治疗者


class Elements(IntEnum):
    SPECTRO = 0
    ELECTRIC = 1
    FIRE = 2
    ICE = 3
    WIND = 4
    HAVOC = 5


role_values = [role for role in Role]  # 角色定位枚举值的列表


class BaseChar:
    """角色基类，定义了游戏角色的通用属性和行为。"""

    def __init__(self, task, index, res_cd=20, echo_cd=20, liberation_cd=25, char_name=None, confidence=1,
                 ring_index=-1):
        """初始化角色基础属性。

        Args:
            task (BaseCombatTask): 所属的战斗任务对象。
            index (int): 角色在队伍中的索引 (0, 1, 2)。
            res_cd (int, optional): 共鸣技能冷却时间 (秒)。默认为 20。
            echo_cd (int, optional): 声骸技能冷却时间 (秒)。默认为 20。
            liberation_cd (int, optional): 共鸣解放冷却时间 (秒)。默认为 25。
            char_name (str, optional): 角色名称。默认为 None。
        """
        self.priority = Priority.BASE
        self.white_off_threshold = 0.01
        self.echo_cd = echo_cd
        self.task = task
        self.liberation_cd = liberation_cd
        self.sleep_adjust = 0
        self.char_name = char_name
        self.index = index
        self.ring_index = ring_index  # for con check
        self.last_switch_time = -1
        self.last_res = -1
        self.last_echo = -1
        self.last_liberation = -1
        self.has_intro = False
        self.res_cd = res_cd
        self.is_current_char = False
        self._liberation_available = False
        self._resonance_available = False
        self._echo_available = False
        self.full_ring_area = 0
        self.last_perform = 0
        self.current_con = 0
        self.has_tool_box = False
        self.intro_motion_freeze_duration = 0.9
        self.last_outro_time = -1
        self.confidence = confidence
        self.logger = Logger.get_logger(self.name)
        self.check_f_on_switch = True

    def flying_based_on_resonance(self):
        if not self.has_cd('resonance') and not self.task.box_highlighted('resonance'):
            return True

    def skip_combat_check(self):
        """是否在某些操作中跳过战斗状态检查。

        Returns:
            bool: 如果跳过则返回 True。
        """
        return False

    def use_tool_box(self):
        """如果角色装备了探索工具箱, 则使用它。"""
        if self.has_tool_box:
            self.task.send_key(self.task.key_config['Tool Key'])
            self.has_tool_box = False

    @property
    def name(self):
        """获取角色类名作为其名称。

        Returns:
            str: 角色类名字符串。
        """
        return f"{self.__class__.__name__}"

    def __eq__(self, other):
        """比较两个角色对象是否相同 (基于名称和索引)。"""
        if isinstance(other, BaseChar):
            return self.name == other.name and self.index == other.index
        return False

    def perform(self):
        """执行当前角色的主要战斗行动序列。"""
        self.last_perform = time.time()
        if self.need_fast_perform():
            self.do_fast_perform()
        else:
            self.do_perform()
        self.logger.debug(f'set current char false {self.index}')

    def wait_down(self, click=True):
        """等待角色从空中落下到地面。"""
        if not self.task.has_lavitator and self.has_intro:
            if click:
                self.continues_normal_attack(self.intro_motion_freeze_duration)
            else:
                self.sleep(self.intro_motion_freeze_duration)
        else:
            start = time.time()
            while self.flying() and time.time() - start < 2.5:
                if click:
                    self.task.click(interval=0.2)
                else:
                    self.sleep(0.2)
                self.task.next_frame()
                # self.logger.debug('wait_down')

    def wait_intro(self, time_out=1.2, click=True):
        """等待角色入场动画结束。

        Args:
            time_out (float, optional): 等待超时时间 (秒)。默认为 1.2。
            click (bool, optional): 等待期间是否持续点击。默认为 True。
        """
        if self.has_intro:
            self.task.wait_until(self.down, post_action=self.click_with_interval if click else None, time_out=time_out)

    def down(self):
        """判断角色是否已落地 (通过技能是否可用判断)。

        Returns:
            bool: 如果已落地则返回 True。
        """
        return (self.current_resonance() > 0 and not self.has_cd('resonance')) or (
                self.current_liberation() > 0 and not self.has_cd('liberation'))

    def click_with_interval(self, interval=0.1):
        """以指定间隔执行点击操作。

        Args:
            interval (float, optional): 点击间隔。默认为 0.1。
        """
        self.click(interval=interval)

    def click(self, *args: Any, **kwargs: Any):
        """执行一次点击操作 (代理到 task.click)。"""
        self.task.click(*args, **kwargs)

    def do_perform(self):
        """执行角色的标准战斗行动。"""
        if self.has_intro:
            self.logger.debug('has_intro wait click 1.2 sec')
            self.continues_normal_attack(1.2, click_resonance_if_ready_and_return=True)
        self.click_liberation(con_less_than=1)
        if self.click_resonance()[0]:
            return self.switch_next_char()
        if self.click_echo():
            return self.switch_next_char()
        self.continues_normal_attack(0.31)
        self.switch_next_char()

    def do_fast_perform(self):
        """执行角色的快速战斗行动 (通常在需要快速切换时)。"""
        self.do_perform()

    def has_cd(self, box_name):
        """检查指定技能是否在冷却中 (代理到 task.has_cd)。

        Args:
            box_name (str): 技能UI区域名称。

        Returns:
            bool: 如果在冷却则返回 True。
        """
        return self.task.has_cd(box_name)

    def is_available(self, percent, box_name):
        """判断技能是否可用 (基于UI百分比和冷却状态)。

        Args:
            percent (float): 技能UI白色像素百分比。
            box_name (str): 技能UI区域名称。

        Returns:
            bool: 如果可用则返回 True。
        """
        return percent == 0 or not self.has_cd(box_name)

    def switch_out(self):
        """角色被切换下场时的状态更新。"""
        self.last_switch_time = time.time()
        self.is_current_char = False
        self.has_intro = False
        if self.current_con == 1:
            self.logger.info(f'switch_out at full con set current_con to 0')
            self.current_con = 0

    def __repr__(self):
        """返回角色类名作为其字符串表示。"""
        return self.__class__.__name__

    def switch_next_char(self, post_action=None, free_intro=False, target_low_con=False):
        """切换到下一个角色 (代理到 task.switch_next_char)。

        Args:
            post_action (callable, optional): 切换后执行的动作。默认为 None。
            free_intro (bool, optional): 是否强制认为拥有入场技。默认为 False。
            target_low_con (bool, optional): 是否优先切换到低协奏值角色。默认为 False。
        """
        self.is_forte_full()
        self.has_intro = False
        self._liberation_available = self.liberation_available()
        self.use_tool_box()
        self.task.switch_next_char(self, post_action=post_action, free_intro=free_intro,
                                   target_low_con=target_low_con)

    def sleep(self, sec, check_combat=True):
        if not check_combat:
            self.task.skip_combat_check = True
        self.task.sleep(sec)
        self.task.skip_combat_check = False

    def alert_skill_failed(self):
        self.task.log_error(f'Click skill failed, check if the keybinding is correct in ok-ww settings!',
                            notify=True)
        self.task.screenshot('click_resonance too long, breaking')

    def click_resonance(self, post_sleep=0, has_animation=False, send_click=True, animation_min_duration=0,
                        check_cd=False, time_out=0):
        """尝试点击并释放共鸣技能。

        Args:
            post_sleep (float, optional): 释放技能后的休眠时间。默认为 0。
            has_animation (bool, optional): 技能是否有释放动画。默认为 False。
            send_click (bool, optional): 在释放技能前是否发送普通点击。默认为 True。
            animation_min_duration (float, optional): 动画的最短持续时间。默认为 0。
            check_cd (bool, optional): 是否严格检查冷却时间。默认为 False。

        Returns:
            tuple: (是否成功点击 (bool), 技能持续时间 (float), 是否检测到动画 (bool))。
        """
        clicked = False
        self.logger.debug(f'click_resonance start')
        last_click = 0
        last_op = 'click'
        resonance_click_time = 0
        start = time.time()
        animation_start = 0
        if time_out == 0:
            the_time_out = SKILL_TIME_OUT
        else:
            the_time_out = time_out
        while True:
            if time.time() - start > the_time_out:
                self.task.in_liberation = False
                if the_time_out == 0:
                    self.alert_skill_failed()
                break
            elif self.task.in_liberation and time.time() - start > 6:
                self.task.in_liberation = False
                break
            if has_animation:
                if not self.task.in_team()[0]:
                    self.task.in_liberation = True
                    animation_start = time.time()
                    the_time_out = SKILL_TIME_OUT
                    if time.time() - resonance_click_time > 6:
                        self.task.in_liberation = False
                        self.logger.error(f'resonance animation too long, breaking')
                    self.task.next_frame()
                    self.check_combat()
                    continue
                elif self.task.in_liberation:
                    self.task.in_liberation = False
                    self.logger.debug(f'click_resonance animated break')
                    break

            self.check_combat()
            now = time.time()
            if not self.resonance_available() and (
                    not has_animation or now - start > animation_min_duration):
                self.logger.debug(f'click_resonance not available break')
                break
            self.logger.debug(f'click_resonance resonance_available click')

            if now - last_click > 0.1:
                if send_click and last_op == 'resonance':
                    self.task.click()
                    last_op = 'click'
                    continue
                if self.resonance_available():
                    if resonance_click_time == 0:
                        clicked = True
                        resonance_click_time = now
                        self.update_res_cd()
                    last_op = 'resonance'
                    self.send_resonance_key()
                    if has_animation:  # sleep if there will be an animation like Jinhsi
                        self.sleep(0.2, check_combat=False)
                last_click = now
            self.task.next_frame()
        self.task.in_liberation = False
        if clicked:
            self.sleep(post_sleep)
        duration = time.time() - resonance_click_time if resonance_click_time != 0 else 0
        if animation_start > 0:
            self.add_freeze_duration(resonance_click_time, time.time() - animation_start)
        self.logger.debug(f'click_resonance end clicked {clicked} duration {duration} animated {animation_start > 0}')
        return clicked, duration, animation_start > 0

    def send_resonance_key(self, post_sleep=0, interval=-1, down_time=0.01):
        """发送共鸣技能按键。

        Args:
            post_sleep (float, optional): 发送后的休眠时间。默认为 0。
            interval (float, optional): 按键按下和释放的间隔。默认为 -1 (使用默认值)。
            down_time (float, optional): 按键按下的持续时间。默认为 0.01。
        """
        self._resonance_available = False
        self.task.send_key(self.get_resonance_key(), interval=interval, down_time=down_time, after_sleep=post_sleep)

    def send_echo_key(self, after_sleep=0, interval=-1, down_time=0.01):
        """发送声骸技能按键。

        Args:
            after_sleep (float, optional): 发送后的休眠时间。默认为 0。
            interval (float, optional): 按键按下和释放的间隔。默认为 -1 (使用默认值)。
            down_time (float, optional): 按键按下的持续时间。默认为 0.01。
        """
        self._echo_available = False
        self.task.send_key(self.get_echo_key(), interval=interval, down_time=down_time, after_sleep=after_sleep)

    def heavy_click_forte(self, check_fun=None):
        """ 如果回路可用, 重击点击回路直到不可用
        """
        if check_fun is None:
            check_fun = self.is_forte_full
        if check_fun():
            self.task.mouse_down()
            success = self.task.wait_until(lambda: not check_fun(), time_out=2)
            self.task.mouse_up()
            self.sleep(0.05)
            return success

    def send_liberation_key(self, after_sleep=0, interval=-1, down_time=0.01):
        """发送共鸣解放按键。

        Args:
            after_sleep (float, optional): 发送后的休眠时间。默认为 0。
            interval (float, optional): 按键按下和释放的间隔。默认为 -1 (使用默认值)。
            down_time (float, optional): 按键按下的持续时间。默认为 0.01。
        """
        self._liberation_available = False
        self.task.send_key(self.get_liberation_key(), interval=interval, down_time=down_time, after_sleep=after_sleep)

    def update_res_cd(self):
        """更新共鸣技能的最后使用时间。"""
        current = time.time()
        if current - self.last_res > self.res_cd:  # count the first click only
            self.last_res = time.time()

    def update_liberation_cd(self):
        """更新共鸣解放的最后使用时间。"""
        current = time.time()
        if current - self.last_liberation > (self.liberation_cd - 2):  # count the first click only
            self.last_liberation = time.time()

    def update_echo_cd(self):
        """更新声骸技能的最后使用时间。"""
        current = time.time()
        if current - self.last_echo > self.echo_cd:  # count the first click only
            self.last_echo = time.time()

    def click_echo(self, duration=0, sleep_time=0, time_out=1):
        """尝试点击并释放声骸技能。

        Args:
            duration (float, optional): 技能期望的持续按键时间 (用于持续型声骸)。默认为 0。
            sleep_time (float, optional): 释放后的休眠时间 (似乎未使用)。默认为 0。
            time_out (float, optional): 操作超时时间，召唤型声骸可设为 0。默认为 1。

        Returns:
            bool: 如果成功点击则返回 True。
        """
        if time_out == 0 and self.echo_available():
            self.send_echo_key()
            self.update_echo_cd()
            self.logger.debug('flick echo')
            return True
        if self.task.is_open_world_auto_combat() and self.ring_index == Elements.FIRE:
            self.logger.debug(f'open world do not use motorcycle echo')
            return False
        self.logger.debug(f'click_echo start duration: {duration}')
        if self.has_cd('echo'):
            self.logger.debug('click_echo has cd return ')
            return False
        clicked = False
        start = time.time()
        last_click = 0
        time_out += duration
        while True:
            if time.time() - start > time_out:
                self.logger.info("click_echo time out")
                return False
            self.check_combat()
            if not self.echo_available() and (duration == 0 or not clicked):
                break
            now = time.time()
            if duration > 0 and start != 0:
                if now - start > duration:
                    break
            if now - last_click > 0.1:
                if not clicked:
                    self.update_echo_cd()
                    clicked = True
                self.send_echo_key()
                last_click = now
            if now - start > SKILL_TIME_OUT:
                self.logger.error(f'click_echo too long {clicked}')
                self.alert_skill_failed()
                break
            self.task.next_frame()
        self.logger.debug(f'click_echo end {clicked}')
        return clicked

    def is_open_world_auto_combat(self):
        return self.task.is_open_world_auto_combat()

    def check_combat(self):
        """检查战斗状态 (代理到 task.check_combat)。"""
        self.task.check_combat()

    def reset_state(self):
        """重置角色的战斗相关状态 (如入场技标记)。"""
        self.has_intro = False
        self.current_con = 0
        self.has_tool_box = False
        self._liberation_available = False
        self._echo_available = False
        self._resonance_available = False

    def click_liberation(self, con_less_than=-1, send_click=False, wait_if_cd_ready=0.1):
        """尝试点击并释放共鸣解放。

        Args:
            con_less_than (float, optional): 仅当协奏值小于此值时释放。默认为 -1 (不检查)。
            send_click (bool, optional): 进入动画后是否发送普通点击。默认为 False。
            wait_if_cd_ready (float, optional): 如果技能冷却即将完成, 等待多少秒。默认为 0。

        Returns:
            bool: 如果成功释放则返回 True。
        """
        if not self.task.use_liberation:
            return False
        if con_less_than > 0:
            if self.get_current_con() > con_less_than:
                return False
        self.logger.debug(f'click_liberation start')
        start = time.time()
        last_click = 0
        clicked = False
        if not self.task.in_liberation:
            while self.liberation_available():  # clicked and still in team wait for animation
                self.logger.debug(f'click_liberation liberation_available click')
                if send_click:
                    self.click(interval=0.1)
                now = time.time()
                if now - last_click > 0.1:
                    self.send_liberation_key()
                    if not clicked:
                        clicked = True
                    last_click = now
                if time.time() - start > SKILL_TIME_OUT:
                    self.alert_skill_failed()
                    self.task.raise_not_in_combat('too long clicking a liberation')
                self.task.next_frame()
            if clicked:
                if self.task.wait_until(lambda: not self.task.in_team()[0], time_out=0.4,
                                        post_action=self.click_with_interval):
                    self.task.in_liberation = True
                    self.logger.debug(f'not in_team successfully casted liberation')
                else:
                    self.task.in_liberation = False
                    self.logger.error(f'clicked liberation but no effect')
                    return False
            else:
                start = time.time()
                while not self.has_cd('liberation') and time.time() - start < wait_if_cd_ready:
                    self.send_liberation_key(after_sleep=0.05)
                    if self.task.wait_until(lambda: not self.task.in_team()[0], time_out=0.1):
                        self.task.in_liberation = True
                        self.logger.debug(f'not in_team successfully casted liberation')
                if not self.task.in_liberation:
                    return False
        start = time.time()
        while not self.task.in_team()[0]:
            self.task.in_liberation = True
            if not clicked:
                clicked = True
            if send_click:
                self.click(interval=0.1)
            if time.time() - start > 7:
                self.task.in_liberation = False
                self.task.raise_not_in_combat('too long a liberation, the boss was killed by the liberation')
            self.task.next_frame()
        duration = time.time() - start
        self.add_freeze_duration(start, duration)
        self.update_liberation_cd()
        self.task.in_liberation = False
        self._liberation_available = False
        if clicked:
            self.logger.info(f'click_liberation end {duration}')
        return clicked

    def on_combat_end(self, chars):
        """当战斗结束时, 角色可能需要执行的特定清理逻辑。

        Args:
            chars (list[BaseChar]): 队伍中所有角色的列表。
        """
        pass

    def add_freeze_duration(self, start, duration=-1.0, freeze_time=0.1):
        """添加冻结持续时间 (代理到 task.add_freeze_duration)。"""
        self.task.add_freeze_duration(start, duration, freeze_time)

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        """计算扣除冻结时间后经过的时间 (代理到 task.time_elapsed_accounting_for_freeze)。"""
        return self.task.time_elapsed_accounting_for_freeze(start, intro_motion_freeze)

    def get_liberation_key(self):
        """获取共鸣解放按键 (代理到 task.get_liberation_key)。"""
        return self.task.get_liberation_key()

    def get_echo_key(self):
        """获取声骸技能按键 (代理到 task.get_echo_key)。"""
        return self.task.get_echo_key()

    def get_resonance_key(self):
        """获取共鸣技能按键 (代理到 task.get_resonance_key)。"""
        return self.task.get_resonance_key()

    def get_switch_priority(self, current_char, has_intro, target_low_con):
        """获取切换到此角色的优先级。

        Args:
            current_char (BaseChar): 当前场上角色。
            has_intro (bool): 当前场上角色是否拥有入场技 (通常因协奏值满)。
            target_low_con (bool): 队伍策略是否倾向于切换到低协奏值角色。

        Returns:
            Priority: 优先级数值。
        """
        priority = self.do_get_switch_priority(current_char, has_intro, target_low_con)
        if priority < Priority.MAX and time.time() - self.last_switch_time < 0.9 and not has_intro:
            return Priority.SWITCH_CD  # switch cd
        else:
            return priority

    def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
        """计算切换到此角色的基础优先级 (不考虑切换CD)。

        Args:
            current_char (BaseChar): 当前场上角色。
            has_intro (bool, optional): 当前场上角色是否拥有入场技。默认为 False。
            target_low_con (bool, optional): 队伍策略是否倾向于切换到低协奏值角色。默认为 False。

        Returns:
            int: 基础优先级数值。
        """
        priority = self.priority
        if self.count_liberation_priority() and self.liberation_available():
            priority += self.count_liberation_priority()
        if self.count_resonance_priority() and self.resonance_available():
            priority += self.count_resonance_priority()
        if self.count_forte_priority():
            priority += self.count_forte_priority()
        if self.echo_available():
            priority += self.count_echo_priority()
        if priority > 0:
            priority += Priority.SKILL_AVAILABLE
        priority += self.count_base_priority()
        return priority

    def count_base_priority(self):
        """计算角色的基础优先级值。"""
        return 0

    def count_liberation_priority(self):
        """计算共鸣解放技能对切换优先级的贡献值。"""
        return 1

    def count_resonance_priority(self):
        """计算共鸣技能对切换优先级的贡献值。"""
        return 10

    def count_echo_priority(self):
        """计算声骸技能对切换优先级的贡献值。"""
        return 1

    def count_forte_priority(self):
        """计算共鸣回路技能对切换优先级的贡献值。"""
        return 0

    def resonance_available(self):
        """判断共鸣技能是否可用。

        Args:
            current (float, optional): 可选的, 当前共鸣技能UI白色像素百分比。默认为 None。
            check_ready (bool, optional): 是否检查技能UI是否完全点亮。默认为 False。
            check_cd (bool, optional): 是否严格检查冷却时间。默认为 False。

        Returns:
            bool: 如果可用则返回 True。
        """
        return self.available('resonance', check_color=False)

    def available(self, box, check_color=True, check_cd=True):
        if self.is_current_char:
            return self.task.available(box, check_color=check_color, check_cd=check_cd)
        else:
            return not self.task.has_cd(box, self.index)

    def echo_available(self):
        """判断声骸技能是否可用。

        Args:
            current (float, optional): 可选的, 当前声骸技能UI白色像素百分比。默认为 None。

        Returns:
            bool: 如果可用则返回 True。
        """
        return self.available('echo', check_color=False)

    def extra_action_available(self):
        """判断最左边的额外技能是否可用。

        Args:
            current (float, optional): 可选的, 当前声骸技能UI白色像素百分比。默认为 None。

        Returns:
            bool: 如果可用则返回 True。
        """
        return self.available('extra_action', check_color=True, check_cd=False)

    def is_con_full(self):
        if self.current_con == 1:
            return True
        """判断当前协奏值是否已满 (代理到 task.is_con_full)。"""
        return self.task.is_con_full()

    def get_current_con(self):
        if self.current_con == 1:
            return 1
        """获取当前协奏值百分比 (代理到 task.get_current_con)。"""
        self.current_con = self.task.get_current_con()
        return self.current_con

    def is_mouse_forte_full(self):
        """判断使用重击角色的forte是否满, 使用找图更加精确
            Returns:
                bool: 如果充满/可用则返回 True。
        """
        return self.task.find_mouse_forte()

    def is_forte_full(self):
        """判断共鸣回路是否已充满/可用。

        Returns:
            bool: 如果充满/可用则返回 True。
        """
        box = self.task.box_of_screen_scaled(3840, 2160, 2251, 1993, 2311, 2016, name='forte_full', hcenter=True)
        white_percent = self.task.calculate_color_percentage(forte_white_color, box)
        # num_labels, stats = get_connected_area_by_color(box.crop_frame(self.task.frame), forte_white_color,
        #                                                 connectivity=8)
        # total_area = 0
        # for i in range(1, num_labels):
        #     # Check if the connected co  mponent touches the border
        #     left, top, width, height, area = stats[i]
        #     total_area += area
        # white_percent = total_area / box.width / box.height
        # if self.task.debug:
        #     self.task.screenshot(f'{self}_forte_{white_percent}')
        # self.logger.debug(f'is_forte_full {white_percent}')
        box.confidence = white_percent
        self.task.draw_boxes('forte_full', box)
        return white_percent > 0.08

    def liberation_available(self, check_color=True):
        """判断共鸣解放是否可用。

        Returns:
            bool: 如果可用则返回 True。
        """
        return self.available('liberation', check_color=check_color)

    def __str__(self):
        """返回角色类名作为其字符串表示。"""
        return self.__repr__()

    def normal_attack_until_can_switch(self):
        """普通攻击直到可以切人。"""
        self.task.click()
        while self.time_elapsed_accounting_for_freeze(self.last_perform) < 1.1:
            self.task.click(interval=0.1)

    def wait_switch_cd(self):
        since_last_switch = self.time_elapsed_accounting_for_freeze(self.last_perform)
        if since_last_switch < 1:
            self.logger.debug(f'wait_switch_cd {since_last_switch}')
            self.continues_normal_attack(1 - since_last_switch)

    def continues_normal_attack(self, duration, interval=0.1, after_sleep=0, click_resonance_if_ready_and_return=False,
                                until_con_full=False):
        """持续进行普通攻击一段时间。

        Args:
            duration (float): 持续时间 (秒)。
            interval (float, optional): 每次攻击的间隔时间。默认为 0.1。
            click_resonance_if_ready_and_return (bool, optional): 如果共鸣技能可用, 是否立即释放并返回。默认为 False。
            until_con_full (bool, optional): 是否持续攻击直到协奏值满。默认为 False。
        """
        start = time.time()
        while time.time() - start < duration:
            if click_resonance_if_ready_and_return and self.resonance_available():
                return self.click_resonance()
            if until_con_full and self.is_con_full():
                return
            self.task.click()
            self.sleep(interval)
        self.sleep(after_sleep)

    def continues_click(self, key, duration, interval=0.1):
        """持续发送指定按键一段时间。

        Args:
            key (str): 要发送的按键。
            duration (float): 持续时间 (秒)。
            interval (float, optional): 每次发送按键的间隔。默认为 0.1。
        """
        start = time.time()
        while time.time() - start < duration:
            self.task.send_key(key, interval=interval)

    def continues_right_click(self, duration, interval=0.1, direction_key=None):
        """持续进行鼠标右键点击操作一段时间，可选同时按住方向键。

        Args:
            duration (float): 持续时间 (秒)。
            interval (float, optional): 每次发送按键的间隔。默认为 0.1。
            direction_key (str, optional): 如果指定，则在点击期间同时按下此键（如 'w'、'a'、's'、'd'）。
        """
        if direction_key is not None:
            self.task.send_key_down(direction_key)
            self.task.next_frame()
        start = time.time()
        while time.time() - start < duration:
            self.task.click(interval=interval, key="right")
        if direction_key is not None:
            self.task.send_key_up(direction_key)

    def normal_attack(self):
        """执行一次普通攻击。"""
        self.logger.debug('normal attack')
        self.check_combat()
        self.task.click()

    def heavy_attack(self, duration=0.6):
        """执行一次重攻击。

        Args:
            duration (float, optional): 重攻击按键按下的持续时间。默认为 0.6。
        """
        self.check_combat()
        self.logger.debug('heavy attack start')
        self.task.mouse_down()
        self.sleep(duration)
        self.task.mouse_up()
        self.sleep(0.01)
        self.logger.debug('heavy attack end')

    def current_resonance(self):
        """获取当前共鸣技能UI白色像素百分比。"""
        return self.task.calculate_color_percentage(text_white_color,
                                                    self.task.get_box_by_name('box_resonance'))

    def current_echo(self):
        """获取当前声骸技能UI白色像素百分比。"""
        return self.task.calculate_color_percentage(text_white_color,
                                                    self.task.get_box_by_name('box_echo'))

    def current_liberation(self):
        """获取当前共鸣解放UI白色像素百分比。"""
        return self.task.calculate_color_percentage(text_white_color, self.task.get_box_by_name('box_liberation'))

    def flying(self):
        """通过控物判断是否在空中"""
        if not self.task.has_lavitator:
            return False
        percent = self.task.calculate_color_percentage(text_white_color, self.task.get_box_by_name('edge_levitator'))
        return percent < 0.1

    def need_fast_perform(self):
        """判断是否需要执行快速行动序列 (通常为了快速切换给高优先级队友)。

        Returns:
            bool: 如果需要则返回 True。
        """
        current_char = self.task.get_current_char(raise_exception=False)
        for i, char in enumerate(self.task.chars):
            if char == current_char:
                pass
            else:
                priority = char.do_get_switch_priority(current_char=current_char, has_intro=False, target_low_con=False)
                if priority >= Priority.FAST_SWITCH:
                    self.logger.info(f'In lock with {char}')
                    return True
        return False

    def check_outro(self):
        """协奏入场时判断延奏来源

        Returns:
            string:非协奏入场返回'null'，否则范围角色名如'char_sanhua'
        """
        if not self.has_intro:
            return 'null'
        time = 0
        outro = 'null'
        for i, char in enumerate(self.task.chars):
            if char == self:
                pass
            elif char.last_switch_time > time:
                time = char.last_switch_time
                outro = char.char_name
        self.logger.info(f'erned outro from {outro}')
        return outro

    def is_first_engage(self):
        """判断角色是否为触发战斗时的登场角色。"""
        result = (0 <= self.last_perform - self.task.combat_start < 0.1)
        if result:
            self.logger.info(f'first engage')
        return result

    def wait_switch(self):
        """检查是否要暂缓切人。"""
        return False

    def switch_other_char(self):
        next_char = str((self.index + 1) % len(self.task.chars) + 1)
        from src.task.AutoCombatTask import AutoCombatTask
        if isinstance(self.task, AutoCombatTask):
            self.logger.debug('AutoCombatTask, skip switch_other_char')
            return
        self.logger.debug(f'{self.char_name} on_combat_end {self.index} switch next char: {next_char}')
        start = time.time()
        while time.time() - start < 6:
            self.task.load_chars()
            current_char = self.task.get_current_char(raise_exception=False)
            if current_char and current_char.name != self.name:
                break
            else:
                self.task.send_key(next_char)
            self.sleep(0.2, False)
        self.logger.debug(f'switch_other_char on_combat_end {self.index} switch end')

    def has_long_action(self):
        """是否有长动作条"""
        return self.task.find_one(self.task.get_target_names()[0], box='box_target_enemy_long', threshold=0.6)

    def has_long_action2(self):
        """是否有长动作条"""
        return self.task.find_one(self.task.get_target_names()[0], box='target_box_long2', threshold=0.6)

    def f_break(self, check_f_on_switch=False):
        """使用F进行击破
           若self.check_f_on_switch为False则不在切走前自动按F,须在逻辑中手动添加。
           另外击破动画带全局时停且目前无法识别动画,可能会出现计时问题
        """
        if check_f_on_switch and not self.check_f_on_switch:
            return
        self.task.f_break()


forte_white_color = {  # 用于检测共鸣回路UI元素可用状态的白色颜色范围。
    'r': (244, 255),  # Red range
    'g': (246, 255),  # Green range
    'b': (250, 255)  # Blue range
}

dot_color = {  # 用于检测技能冷却CD提示点 (通常在技能图标下方) 的颜色范围。
    'r': (195, 255),  # Red range
    'g': (195, 255),  # Green range
    'b': (195, 255)  # Blue range
}
