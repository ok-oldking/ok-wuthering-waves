import time  # noqa
from enum import IntEnum, StrEnum  # noqa
from typing import Any  # noqa

import cv2  # noqa
import numpy as np  # noqa

from ok import Config, Logger  # noqa
from src import text_white_color  # noqa

SKILL_TIME_OUT = 10


class Priority(IntEnum):
    """定义切换角色的优先级枚举。"""
    MIN = -999999999  # 最低优先级
    SWITCH_CD = -1000  # 切换冷却中
    CURRENT_CHAR = -100  # 当前角色
    CURRENT_CHAR_PLUS = CURRENT_CHAR + 1  # 当前角色稍高优先级 (特殊情况)
    SKILL_AVAILABLE = 100  # 有可用技能
    ALL_IN_CD = 0  # 所有技能冷却中
    NORMAL = 10  # 普通优先级
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

    def wait_down(self):
        """等待角色从空中落下到地面。"""
        start = time.time()
        while self.flying() and time.time() - start < 2.5:
            self.task.click(interval=0.2)
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
        """休眠指定时间 (代理到 task.sleep_check_combat)。

        Args:
            sec (float): 休眠秒数。
            check_combat (bool, optional): 是否检查战斗状态。默认为 True。
        """
        if sec > 0:
            self.task.sleep_check_combat(sec + self.sleep_adjust, check_combat=check_combat)

    def alert_skill_failed(self):
        self.task.log_error(f'Click skill failed, check if the keybinding is correct in ok-ww settings!',
                            notify=True)
        self.task.screenshot('click_resonance too long, breaking')

    def click_resonance(self, post_sleep=0, has_animation=False, send_click=True, animation_min_duration=0,
                        check_cd=False):
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
        animated = False
        start = time.time()
        while True:
            if time.time() - start > SKILL_TIME_OUT:
                self.task.in_liberation = False
                self.alert_skill_failed()
                break
            if has_animation:
                if not self.task.in_team()[0]:
                    self.task.in_liberation = True
                    animated = True
                    if time.time() - resonance_click_time > 6:
                        self.task.in_liberation = False
                        self.logger.error(f'resonance animation too long, breaking')
                    self.task.next_frame()
                    self.check_combat()
                    continue
                else:
                    self.task.in_liberation = False
            self.check_combat()
            now = time.time()
            current_resonance = self.current_resonance()
            if not self.resonance_available(current_resonance, check_cd=check_cd) and (
                    not has_animation or now - start > animation_min_duration):
                self.logger.debug(f'click_resonance not available break')
                break
            self.logger.debug(f'click_resonance resonance_available click {current_resonance}')

            if now - last_click > 0.1:
                if send_click and (current_resonance == 0 or last_op == 'resonance'):
                    self.task.click()
                    last_op = 'click'
                    continue
                if current_resonance > 0 and self.resonance_available(current_resonance):
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
        if animated:
            self.add_freeze_duration(resonance_click_time, duration)
        self.logger.debug(f'click_resonance end clicked {clicked} duration {duration} animated {animated}')
        return clicked, duration, animated

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
            time_out (float, optional): 操作超时时间。默认为 1。

        Returns:
            bool: 如果成功点击则返回 True。
        """
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

    def click_liberation(self, con_less_than=-1, send_click=False, wait_if_cd_ready=0):
        """尝试点击并释放共鸣解放。

        Args:
            con_less_than (float, optional): 仅当协奏值小于此值时释放。默认为 -1 (不检查)。
            send_click (bool, optional): 进入动画后是否发送普通点击。默认为 False。
            wait_if_cd_ready (float, optional): 如果技能冷却即将完成, 等待多少秒。默认为 0。
            timeout (int, optional): 操作超时时间 (秒)。默认为 5。

        Returns:
            bool: 如果成功释放则返回 True。
        """
        if con_less_than > 0:
            if self.get_current_con() > con_less_than:
                return False
        self.logger.debug(f'click_liberation start')
        start = time.time()
        last_click = 0
        clicked = False
        while time.time() - start < wait_if_cd_ready and not self.liberation_available() and not self.has_cd(
                'liberation'):
            self.logger.debug(f'click_liberation wait ready {wait_if_cd_ready}')
            if send_click:
                self.click(interval=0.1)
            self.task.next_frame()
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
            return clicked
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
        priority = 0
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

    def resonance_available(self, current=None, check_ready=False, check_cd=False):
        """判断共鸣技能是否可用。

        Args:
            current (float, optional): 可选的, 当前共鸣技能UI白色像素百分比。默认为 None。
            check_ready (bool, optional): 是否检查技能UI是否完全点亮。默认为 False。
            check_cd (bool, optional): 是否严格检查冷却时间。默认为 False。

        Returns:
            bool: 如果可用则返回 True。
        """
        return self.available('resonance')

    def available(self, box):
        if self.is_current_char:
            return self.task.available(box)
        else:
            return not self.task.has_cd(box, self.index)

    def echo_available(self):
        """判断声骸技能是否可用。

        Args:
            current (float, optional): 可选的, 当前声骸技能UI白色像素百分比。默认为 None。

        Returns:
            bool: 如果可用则返回 True。
        """
        return self.available('echo')

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

    def liberation_available(self):
        """判断共鸣解放是否可用。

        Returns:
            bool: 如果可用则返回 True。
        """
        return self.available('liberation')

    def __str__(self):
        """返回角色类名作为其字符串表示。"""
        return self.__repr__()

    def normal_attack_until_can_switch(self):
        """普通攻击直到可以切人。"""
        self.task.click()
        while self.time_elapsed_accounting_for_freeze(self.last_perform) < 1.1:
            self.task.click(interval=0.1)

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
        self.logger.debug('heavy attack end')

    def current_tool(self):
        """获取当前探索工具UI白色像素百分比。"""
        return self.task.calculate_color_percentage(text_white_color, self.task.get_box_by_name('edge_levitator'))

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

    # def count_rectangle_forte(self, left=0.42, right=0.57):
    # """计算矩形共鸣回路充能格数 (已注释)。"""
    #     # Perform image cropping once, as it's independent of saturation ranges
    #     cropped_image_base = self.task.box_of_screen(left, 0.927, right, 0.931).crop_frame(self.task.frame)
    #
    #     if cropped_image_base is None or cropped_image_base.size == 0 or \
    #             cropped_image_base.shape[0] == 0 or cropped_image_base.shape[1] == 0:
    #         self.task.log_debug("Initial cropped image is empty or invalid.")
    #         return (None, None), 0
    #
    #     max_items_found = -1  # Initialize to -1 to distinguish from finding 0 items
    #
    #     current_s_lower = 0
    #     current_s_upper = 40
    #     increment_step = 10
    #
    #     while current_s_upper <= 255:
    #         # Ensure lower saturation is less than upper saturation (should be true with current logic)
    #         if current_s_lower >= current_s_upper:
    #             # self.task.log_debug(
    #             #     f"Skipping invalid saturation range: lower_S={current_s_lower}, upper_S={current_s_upper}")
    #             current_s_lower += increment_step
    #             current_s_upper += increment_step
    #             continue
    #
    #         image = cropped_image_base.copy()  # Use a fresh copy of the cropped image for each iteration
    #
    #         # debug_image = image.copy()
    #         debug_image = None
    #
    #         hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    #
    #         # Define gray range with current saturation values
    #         # Hue range is 0-179 for OpenCV. Value range fixed as per original.
    #         lower_gray = np.array([0, current_s_lower, 140])
    #         upper_gray = np.array([179, current_s_upper, 255])
    #
    #         mask = cv2.inRange(hsv, lower_gray, upper_gray)
    #
    #         if debug_image is not None:
    #             self.task.screenshot(f"forte_mask_S{current_s_lower}_{current_s_upper}", mask)
    #
    #         kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    #         mask_opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open, iterations=1)
    #
    #         # if debug_image is not None:
    #         #     self.task.screenshot(f"forte_mask2_S{current_s_lower}_{current_s_upper}", mask_opened)
    #
    #         kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    #         mask_processed = cv2.dilate(mask_opened, kernel_dilate, iterations=1)
    #
    #         # if debug_image is not None:
    #         #     self.task.screenshot(f"forte_mask3_S{current_s_lower}_{current_s_upper}", mask_processed)
    #
    #         contours, _ = cv2.findContours(mask_processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    #
    #         potential_rects = []
    #         min_area = 0.000001
    #         max_area = 0.00002
    #         min_aspect_ratio_wh = 0.2
    #         max_aspect_ratio_wh = 1.5
    #
    #         for cnt in contours:
    #             area_raw = cv2.contourArea(cnt)
    #             normalized_area = 0
    #             if self.task.screen_width > 0 and self.task.screen_height > 0:
    #                 normalized_area = area_raw / (self.task.screen_width * self.task.screen_height)
    #             else:
    #                 self.task.log_debug("Screen width or height is zero, cannot normalize area.")
    #                 # normalized_area remains 0, likely filtering out the contour
    #
    #             x, y, w, h = cv2.boundingRect(cnt)
    #             aspect_ratio_wh = float(w) / h if h != 0 else float('inf') if w != 0 else 0
    #
    #             # Verbose logging for each contour can be enabled if needed
    #             # self.task.log_debug(
    #             #     f'S_range:[{current_s_lower},{current_s_upper}] Cnt: x={x},y={y},w={w},h={h},image.shape[1]:{image.shape[0]} Area(N): {normalized_area:.7f}, AR: {aspect_ratio_wh:.2f}')
    #
    #             if min_area < normalized_area < max_area and h > image.shape[0] * 0.8:
    #                 if min_aspect_ratio_wh < aspect_ratio_wh < max_aspect_ratio_wh:
    #                     potential_rects.append((x, y, w, h))
    #                     if debug_image is not None:
    #                         cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 255), 1)  # Cyan for potential
    #                 elif debug_image is not None:
    #                     cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 0, 255), 1)  # Red for failed AR
    #             elif debug_image is not None:
    #                 cv2.rectangle(debug_image, (x, y), (x + w, y + h), (255, 0, 0), 1)  # Blue for failed area
    #
    #         current_iteration_final_count = 0
    #         if not potential_rects:
    #             if debug_image is not None:
    #                 self.task.screenshot(f"debug_image_S{current_s_lower}_{current_s_upper}_no_potential", debug_image)
    #             # current_iteration_final_count remains 0
    #         else:
    #             sorted_rects = sorted(potential_rects, key=lambda r: r[0], reverse=True)
    #             final_counted_rects_list = []
    #             last_counted_rect_params = None
    #
    #             cropped_image_width = image.shape[1]
    #             if cropped_image_width == 0:  # Should have been caught by the initial cropped_image_base check
    #                 current_s_lower += increment_step
    #                 current_s_upper += increment_step
    #                 continue  # Proceed to next saturation range
    #
    #             for i in range(len(sorted_rects)):
    #                 current_rect_params = sorted_rects[i]
    #                 x_curr, y_curr, w_curr, h_curr = current_rect_params
    #
    #                 if w_curr == 0 and min_aspect_ratio_wh > 0:
    #                     continue
    #
    #                 if last_counted_rect_params is None:
    #                     if x_curr > 0.9 * cropped_image_width:
    #                         last_counted_rect_params = current_rect_params
    #                         current_iteration_final_count = 1
    #                         final_counted_rects_list.append(current_rect_params)
    #                     else:
    #                         if debug_image is not None:
    #                             cv2.rectangle(debug_image, (x_curr, y_curr), (x_curr + w_curr, y_curr + h_curr),
    #                                           (128, 0, 128), 1)  # Purple for first rejected
    #                         break
    #                 else:
    #                     x_last, y_last, w_last, h_last = last_counted_rect_params
    #                     gap = x_last - (x_curr + w_curr)
    #                     distance_threshold = 4 * w_curr
    #                     x_gap_condition_met = (0 <= gap <= distance_threshold)
    #
    #                     y_center_last = y_last + h_last / 2.0
    #                     y_center_curr = y_curr + h_curr / 2.0
    #                     y_center_distance = abs(y_center_curr - y_center_last)
    #
    #                     y_alignment_condition_met = (y_center_distance < w_curr) if w_curr > 0 else (
    #                             y_center_distance == 0)
    #
    #                     if x_gap_condition_met and y_alignment_condition_met:
    #                         last_counted_rect_params = current_rect_params
    #                         current_iteration_final_count += 1
    #                         final_counted_rects_list.append(current_rect_params)
    #                     else:
    #                         break
    #
    #             if debug_image is not None:
    #                 for rect_params in final_counted_rects_list:
    #                     x_f, y_f, w_f, h_f = rect_params
    #                     cv2.rectangle(debug_image, (x_f, y_f), (x_f + w_f, y_f + h_f), (0, 255, 0),
    #                                   2)  # Green for final counted
    #                 self.task.screenshot(f"debug_image_S{current_s_lower}_{current_s_upper}_final", debug_image)
    #
    #         # Update best result if current iteration is better
    #         if current_iteration_final_count > max_items_found:
    #             max_items_found = current_iteration_final_count
    #             best_s_lower_final = current_s_lower
    #             best_s_upper_final = current_s_upper
    #             self.task.log_debug(
    #                 f"New best S-range: [{best_s_lower_final}, {best_s_upper_final}], Count: {max_items_found}")
    #
    #         # Move to the next saturation range
    #         current_s_lower += increment_step
    #         current_s_upper += increment_step
    #
    #     if max_items_found == -1:  # No items (count > 0) were found in any iteration
    #         # self.task.log_debug("No forte items found across all tested saturation ranges.")
    #         return 0
    #     else:
    #         # self.task.log_debug(
    #         #     f"Optimal S-range: [{best_s_lower_final}, {best_s_upper_final}] with Count: {max_items_found}")
    #         return max_items_found


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
