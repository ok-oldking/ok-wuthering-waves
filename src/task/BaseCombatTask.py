import re
import time
from decimal import Decimal, ROUND_UP, ROUND_DOWN

import cv2
import numpy as np

from ok import Logger, Config
from ok import color_range_to_bound
from ok import safe_get
from src import text_white_color
from src.char import BaseChar
from src.char.BaseChar import Priority, dot_color  # noqa
from src.char.CharFactory import get_char_by_pos
from src.char.Healer import Healer
from src.combat.CombatCheck import CombatCheck
from src.task.BaseWWTask import isolate_white_text_to_black, binarize_for_matching

logger = Logger.get_logger(__name__)
cd_regex = re.compile(r'\d{1,2}\.\d')


class NotInCombatException(Exception):
    """未处于战斗状态异常。"""
    pass


class CharDeadException(NotInCombatException):
    """角色死亡异常。"""
    pass


class BaseCombatTask(CombatCheck):
    """基础战斗任务类，封装了游戏"鸣潮"中角色自动化操作的通用逻辑。"""
    hot_key_verified = False  # 热键是否已验证
    con_full_size = None  # 不同角色协奏值充满时的大小记录
    freeze_durations = []  # 记录冻结/卡肉的持续时间
    if con_full_size is None:
        con_full_size = Config("_con_full_size", {
            "0": 0,
            "1": 0,
            "2": 0,
            "3": 0,
            "4": 0,
            "5": 0,
        })

    def __init__(self, *args, **kwargs):
        """初始化战斗任务。

        Args:
            *args: 传递给父类的参数。
            **kwargs: 传递给父类的关键字参数。
        """
        super().__init__(*args, **kwargs)
        self.chars = [None, None, None]  # 角色列表
        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']  # 角色文本标识符列表
        self.mouse_pos = None  # 当前鼠标位置
        self.combat_start = 0  # 战斗开始时间戳

        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']
        self.add_text_fix({'Ｅ': 'e'})
        self.use_liberation = True

    def add_freeze_duration(self, start, duration=-1.0, freeze_time=0.1):
        """添加冻结持续时间。用于精确计算技能冷却等。

        Args:
            start (float): 冻结开始时间。
            duration (float, optional): 冻结持续时间。如果为-1.0, 则根据当前时间计算。默认为 -1.0。
            freeze_time (float, optional): 认为发生冻结的最小持续时间。默认为 0.1。
        """
        if duration < 0:
            duration = time.time() - start
        if start > 0 and duration > freeze_time:
            current_time = time.time()
            self.freeze_durations = [item for item in self.freeze_durations if item[0] > current_time - 60]
            self.freeze_durations.append((start, duration, freeze_time))

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        """计算扣除冻结时间后经过的时间。

        Args:
            start (float): 开始时间戳。
            intro_motion_freeze (bool, optional): 是否考虑角色入场动画的特殊冻结。默认为 False。

        Returns:
            float: 扣除冻结后实际经过的时间 (秒)。
        """
        if start < 0:
            return 10000
        to_minus = 0
        for freeze_start, duration, freeze_time in self.freeze_durations:
            if start < freeze_start:
                if intro_motion_freeze:
                    if freeze_time == -100:
                        freeze_time = 0
                elif freeze_time == -100:
                    continue
                to_minus += duration - freeze_time
        if to_minus != 0:
            self.log_debug(f'time_elapsed_accounting_for_freeze to_minus {to_minus}')
        return time.time() - start - to_minus

    def send_key_and_wait_animation(self, key, check_function, total_wait=7, enter_animation_wait=0.6):
        """发送按键并等待动画完成。

        Args:
            key (str): 要发送的按键。
            check_function (callable): 检查动画是否结束的函数，返回 True 表示动画已结束。
            total_wait (int, optional): 总等待超时时间 (秒)。默认为 7。
            enter_animation_wait (float, optional): 进入动画的等待时间 (秒)。默认为 0.6。
        """
        start = time.time()
        animation_start = 0
        while time.time() - start < total_wait:
            if check_function():
                if animation_start > 0:
                    self._in_liberation = False
                    logger.debug(f'animation ended')
                    return
                else:
                    if time.time() - start > enter_animation_wait:
                        logger.info(f'send_key_and_wait_animation failed to enter animation')
                        return
                    logger.debug(f'animation not started send key {key}')
                    self.send_key(key, after_sleep=0.1)
            else:
                if animation_start == 0:
                    animation_start = time.time()
                    logger.debug(f'animation started: {animation_start}')
                self._in_liberation = True
            self.next_frame()
        logger.info(f'send_key_and_wait_animation timed out {key}')

    def refresh_cd(self):
        if self.cd_refreshed:
            return
        index = self.get_current_char().index
        cds = self.cds.get(index)
        if cds is None:
            cds = {}
            self.cds[index] = cds
        cds['time'] = time.time()
        cds['resonance'] = 0
        cds['liberation'] = 0
        cds['echo'] = 0
        texts = self.ocr(0.81, 0.86, 0.97, 0.93, frame_processor=isolate_white_text_to_black, match=cd_regex)
        for text in texts:
            cd = convert_cd(text)
            if text.x < self.width_of_screen(0.86):
                cds['resonance'] = cd
            elif text.x > self.width_of_screen(0.91):
                cds['liberation'] = cd
            else:
                cds['echo'] = cd
        self.cd_refreshed = True
        self.log_debug(f'cd refreshed: {cds} {time.time() - cds["time"]}')

    def get_cd(self, box_name, char_index=None):
        self.refresh_cd()
        if char_index is None:
            char_index = self.get_current_char().index
        if cds := self.cds.get(char_index):
            time_elapsed = self.time_elapsed_accounting_for_freeze(cds['time'])
            return cds[box_name] - time_elapsed
        else:
            return 0

    def next_frame(self):
        self.cd_refreshed = False
        return super().next_frame()

    def sleep(self, *args, **kwargs):
        self.cd_refreshed = False
        super().sleep(*args, **kwargs)

    def revive_action(self):
        pass

    def teleport_to_heal(self, esc=True):
        """传送回城治疗。"""
        if esc:
            self.sleep(1)
            self.info['Death Count'] = self.info.get('Death Count', 0) + 1
            self.send_key('esc', after_sleep=2)
        self.log_info('click m to open the map')
        self.send_key('m', after_sleep=2)

        teleport = self.find_best_match_in_box(self.box_of_screen(0.1, 0.1, 0.9, 0.9),
                                               ['map_way_point', 'map_way_point_big'], 0.7)
        if not teleport:
            raise RuntimeError(f'Can not find a teleport to heal')
        self.click(teleport, after_sleep=1)
        travel = self.wait_feature('gray_teleport', raise_if_not_found=True, time_out=3)
        if not travel:
            pop_up = self.find_feature('map_way_point', box='map_way_point_pop_up_box')
            if pop_up:
                self.click(pop_up, after_sleep=1)
                travel = self.wait_feature('gray_teleport', raise_if_not_found=True, time_out=3)
        if not travel:
            raise RuntimeError(f'Can not find the travel button')
        self.click_box(travel, relative_x=1.5)
        self.wait_in_team_and_world(time_out=20)
        self.sleep(2)

    def raise_not_in_combat(self, message, exception_type=None):
        """抛出未在战斗状态的异常。

        Args:
            message (str): 异常信息。
            exception_type (Exception, optional): 要抛出的异常类型。默认为 NotInCombatException。
        """
        logger.error(message)
        if self.reset_to_false(reason=message):
            logger.error(f'reset to false failed: {message}')
        if exception_type is None:
            exception_type = NotInCombatException
        raise exception_type(message)

    def available(self, name, check_color=True, check_cd=True):
        """检查指定名称的技能或动作是否可用 (通过颜色百分比和冷却时间判断)。

        Args:
            name (str): 技能或动作的名称 (例如 'resonance', 'echo')。

        Returns:
            bool: 如果可用则返回 True, 否则 False。
        """
        if check_color:
            current = self.box_highlighted(name)
        else:
            current = 1
        if current > 0 and (not check_cd or not self.has_cd(name)):
            return True

    def box_highlighted(self, name):
        current = self.calculate_color_percentage(text_white_color,
                                                  self.get_box_by_name(f'box_{name}'))
        if current > 0:
            current = 1
        else:
            current = 0
        return current

    def combat_once(self, wait_combat_time=200, raise_if_not_found=True):
        """执行一次完整的战斗流程。

        Args:
            wait_combat_time (int, optional): 等待进入战斗状态的超时时间 (秒)。默认为 200。
            raise_if_not_found (bool, optional): 如果未找到战斗状态是否抛出异常。默认为 True。
        """
        self.wait_until(self.in_combat, time_out=wait_combat_time, raise_if_not_found=raise_if_not_found)
        self.load_chars()
        self.info['Combat Count'] = self.info.get('Combat Count', 0) + 1
        try:
            while self.in_combat():
                logger.debug(f'combat_once loop {self.chars}')
                self.get_current_char().perform()
        except CharDeadException as e:
            raise e
        except NotInCombatException as e:
            logger.info(f'combat_once out of combat break {e}')
        self.combat_end()
        self.wait_in_team_and_world(time_out=10, raise_if_not_found=False)

    def run_in_circle_to_find_echo(self, circle_count=3):
        """通过绕圈移动来尝试拾取声骸。

        Args:
            circle_count (int, optional): 绕圈的次数。默认为 3。

        Returns:
            bool: 如果成功拾取到声骸则返回 True, 否则 False。
        """
        directions = ['w', 'a', 's', 'd']
        step = 0.8
        duration = 0.8
        total_index = 0
        for count in range(circle_count):
            logger.debug(f'running first circle_count{circle_count} circle {total_index} duration:{duration}')
            for direction in directions:
                if total_index > 2 and (total_index + 1) % 2 == 0:
                    if not (count == circle_count - 1 and direction == directions[-1]):
                        duration += step

                if self.send_key_and_wait_f(direction, False, time_out=duration, running=True,
                                            target_text=self.absorb_echo_text()):
                    if self.pick_f():
                        return True
                total_index += 1

    def switch_next_char(self, current_char, post_action=None, free_intro=False, target_low_con=False):
        """切换到下一个最优角色。

        Args:
            current_char (BaseChar): 当前角色对象。
            post_action (callable, optional): 切换后执行的动作 (回调函数)。默认为 None。
            free_intro (bool, optional): 是否强制认为拥有入场技 (通常在协奏值满时)。默认为 False。
            target_low_con (bool, optional): 是否优先切换到协奏值较低的角色。默认为 False。
        """
        max_priority = Priority.MIN
        switch_to = current_char
        has_intro = free_intro
        current_con = 0
        self.update_lib_portrait_icon()
        if not has_intro:
            current_con = current_char.get_current_con()
            if current_con > 0.8 and current_con != 1:
                logger.info(f'switch_next_char current_con {current_con:.2f} almost full, sleep and check again')
                self.sleep(0.05)
                self.next_frame()
                current_con = current_char.get_current_con()
            if current_con == 1:
                has_intro = True
        low_con = 200

        for i, char in enumerate(self.chars):
            if char == current_char:
                priority = Priority.CURRENT_CHAR
            else:
                priority = char.get_switch_priority(current_char, has_intro, target_low_con)
                logger.debug(
                    f'switch_next_char priority: {char} {priority} {char.current_con} target_low_con {target_low_con}')
            if target_low_con:
                if char.current_con < low_con and char != current_char:
                    low_con = char.current_con
                    switch_to = char
            elif priority == max_priority:
                if char.last_perform < switch_to.last_perform:
                    logger.debug(f'switch priority equal, determine by last perform')
                    switch_to = char
            elif priority > max_priority:
                max_priority = priority
                switch_to = char
        if switch_to == current_char:
            logger.warning(f"{current_char} can't find next char to switch to, performing too fast add a normal attack")
            current_char.continues_normal_attack(0.2)
            return current_char.switch_next_char()
        switch_to.has_intro = has_intro
        logger.info(
            f'switch_next_char {current_char} -> {switch_to} has_intro {switch_to.has_intro} current_con {current_con}')
        # if self.debug:
        #     self.screenshot(f'switch_next_char_{current_con}')
        last_click = 0
        start = time.time()
        while True:
            now = time.time()
            current_char.f_break(check_f_on_switch=True)
            _, current_index, _ = self.in_team()
            if current_index == current_char.index:
                self.update_lib_portrait_icon()
                if not switch_to.has_intro:
                    switch_to.has_intro = current_char.is_con_full()

            if now - last_click > 0.1:
                self.send_key(switch_to.index + 1)
                self.sleep(0.001)
                last_click = now
                self.log_debug('switch not detected, send click')
                self.click()
                self.sleep(0.001)
            in_team, current_index, size = self.in_team()
            if not in_team:
                logger.info(f'not in team while switching chars_{current_char}_to_{switch_to} {now - start}')
                # if self.debug:
                #     self.screenshot(f'not in team while switching chars_{current_char}_to_{switch_to} {now - start}')
                confirm = self.wait_feature('revive_confirm_hcenter_vcenter', threshold=0.8, time_out=2)
                if confirm:
                    self.log_info(f'char dead')
                    if not self.revive_action():
                        self.raise_not_in_combat(f'char dead', exception_type=CharDeadException)
                if now - start > self.switch_char_time_out:
                    self.raise_not_in_combat(
                        f'switch too long failed chars_{current_char}_to_{switch_to}, {now - start}')
                self.next_frame()
                continue
            if current_index != switch_to.index:
                if now - start > 10:
                    if self.debug:
                        self.screenshot(f'switch_not_detected_{current_char}_to_{switch_to}')
                    self.raise_not_in_combat('failed switch chars')
            else:
                self.in_liberation = False
                current_char.switch_out()
                switch_to.is_current_char = True
                if has_intro:
                    current_time = time.time()
                    self.add_freeze_duration(current_time, switch_to.intro_motion_freeze_duration, -100)
                    current_char.last_outro_time = current_time
                break

        if post_action:
            logger.debug(f'post_action {post_action}')
            post_action(switch_to, has_intro)
        logger.info(f'switch_next_char end {(current_char.last_switch_time - start):.3f}s')

    def find_mouse_forte(self):
        return self.find_one('mouse_forte', horizontal_variance=0.025, threshold=0.6,
                             frame_processor=binarize_for_matching)

    def get_liberation_key(self):
        """获取共鸣解放技能的按键。

        Returns:
            str: 共鸣解放技能的按键字符串。
        """
        return self.key_config['Liberation Key']

    def get_echo_key(self):
        """获取声骸技能的按键。

        Returns:
            str: 声骸技能的按键字符串。
        """
        return self.key_config['Echo Key']

    def get_resonance_key(self):
        """获取共鸣技能的按键。

        Returns:
            str: 共鸣技能的按键字符串。
        """
        return self.key_config['Resonance Key']

    def has_resonance_cd(self):
        """检查共鸣技能是否在冷却中。

        Returns:
            bool: 如果在冷却中则返回 True, 否则 False。
        """
        return self.has_cd('resonance')

    def has_cd(self, box_name, char_index=None):
        """检查指定UI区域是否处于冷却状态 (通过检测特定颜色的点和数字)。

        Args:
            box_name (str): UI区域的名称 (例如 'resonance', 'echo', 'liberation')。

        Returns:
            bool: 如果在冷却中则返回 True, 否则 False。
        """
        return self.get_cd(box_name, char_index) > 0

    def get_current_char(self, raise_exception=False) -> BaseChar:
        """获取当前操作的角色对象。

        Args:
            raise_exception (bool, optional): 如果找不到当前角色是否抛出异常。默认为 True。

        Returns:
            BaseChar: 当前角色对象 (`BaseChar`) 或 None。
        """
        for char in self.chars:
            if char and char.is_current_char:
                return char
        if raise_exception and not self.in_team()[0]:
            self.raise_not_in_combat('can find current char!!')
        # self.load_chars()
        return None

    def combat_end(self):
        """战斗结束时调用的清理方法。"""
        current_char = self.get_current_char(raise_exception=False)
        if current_char:
            self.get_current_char().on_combat_end(self.chars)

    def sleep_check(self):
        """休眠指定时间, 并在休眠前后检查战斗状态。

        Args:
            timeout (float): 休眠的秒数。
            check_combat (bool, optional): 是否在休眠前检查战斗状态。默认为 True。
        """
        # self.log_debug(f'sleep_check {self._in_combat}')
        if self._in_combat:
            self.next_frame()
            if not self.in_combat():
                self.raise_not_in_combat('sleep check not in combat')

    def check_combat(self):
        """检查当前是否处于战斗状态, 如果不是则抛出异常。"""
        if not self.in_combat():
            # if self.debug:
            #     self.screenshot('not_in_combat_calling_check_combat')
            self.raise_not_in_combat('combat check not in combat')

    def set_key(self, key, box):
        best = self.find_best_match_in_box(box, ['t', 'e', 'r', 'q'], threshold=0.7)
        logger.debug(f'set_key best match {key}: {best}')
        if best and best.name != self.key_config[key]:
            self.key_config[key] = best.name
            self.log_info(f'set_key {key} to {best.name}')

    def load_hotkey(self, force=False):
        """加载或自动设置游戏内技能热键。

        Args:
            force (bool, optional): 是否强制重新加载热键。默认为 False。
        """
        if not self.hot_key_verified or force:
            self.hot_key_verified = True
            scale = 1.2
            # self.set_key('Resonance Key', self.get_box_by_name('e').scale(scale))
            self.set_key('Echo Key', self.get_box_by_name('r').scale(scale))
            self.set_key('Liberation Key', self.get_box_by_name('q').scale(scale))
            # self.set_key('Tool Key', self.get_box_by_name('t').scale(scale))

            self.info_set('Liberation Key', self.get_liberation_key())
            # self.info_set('Resonance Key', self.get_resonance_key())
            self.info_set('Echo Key', self.get_echo_key())
            # self.info_set('Tool Key', self.key_config['Tool Key'])
        return self.key_config

    def has_char(self, char_cls):
        for char in self.chars:
            if isinstance(char, char_cls):
                return char

    def load_chars(self):
        """加载队伍中的角色信息。"""
        self.load_hotkey()
        in_team, current_index, count = self.in_team()
        if not in_team:
            return
        # self.log_info('load chars')
        self.chars[0] = get_char_by_pos(self, self.get_box_by_name('box_char_1'), 0, safe_get(self.chars, 0))
        self.chars[1] = get_char_by_pos(self, self.get_box_by_name('box_char_2'), 1, safe_get(self.chars, 1))

        if count == 3:
            new_char = get_char_by_pos(self, self.get_box_by_name('box_char_3'), 2, safe_get(self.chars, 2))
            if len(self.chars) == 2:
                self.chars.append(new_char)
            else:
                self.chars[2] = new_char
        else:
            if len(self.chars) == 3:
                self.chars = self.chars[:2]
            logger.info(f'team size changed to 2')

        healer_count = 0
        for char in self.chars:
            if char is not None:
                char.reset_state()
                if isinstance(char, Healer):
                    healer_count += 1
                if char.index == current_index:
                    char.is_current_char = True
                else:
                    char.is_current_char = False
        self.combat_start = time.time()
        if len(self.chars) >= 2:
            return True

    @staticmethod
    def should_update(the_char, old_char):
        """判断是否应该更新角色对象 (例如, 识别到新角色或角色类型变化)。

        Args:
            the_char (BaseChar): 新的角色对象。
            old_char (BaseChar): 旧的角色对象。

        Returns:
            bool: 如果需要更新则返回 True, 否则 False。
        """
        return (type(the_char) is BaseChar and old_char is None) or (
                type(the_char) is not BaseChar and old_char != the_char)

    def box_resonance(self):
        """获取共鸣技能冷却UI区域的盒子对象。

        Returns:
            Box: 盒子对象。
        """
        return self.get_box_by_name('box_resonance_cd')

    def get_resonance_cd_percentage(self):
        """获取共鸣技能冷却UI区域白色像素百分比。

        Returns:
            float: 白色像素百分比。
        """
        return self.calculate_color_percentage(white_color, self.get_box_by_name('box_resonance_cd'))

    def get_resonance_percentage(self):
        """获取共鸣技能UI区域可用状态的白色像素百分比。

        Returns:
            float: 白色像素百分比。
        """
        return self.calculate_color_percentage(white_color, self.get_box_by_name('box_resonance'))

    def is_con_full(self):
        """检查当前角色的协奏值是否已满。

        Returns:
            bool: 如果协奏值已满则返回 True, 否则 False。
        """
        return self.get_current_con() == 1

    def _ensure_ring_index(self):
        """确保当前角色协奏值环的颜色索引已识别。

        Returns:
            int: 协奏值环的颜色索引。
        """
        if self.get_current_char().ring_index < 0:
            box = self.get_con_box()

            best_index = 0
            best_percentage = 0
            for i in range(len(con_colors)):
                percent = self.calculate_color_percentage(con_colors[i], box)
                if percent > best_percentage:
                    best_percentage = percent
                    best_index = i
            self.get_current_char().ring_index = best_index
            self.log_debug(
                f'_ensure_ring_index {self.get_current_char()} to {self.get_current_char().ring_index} {con_templates[best_index]}')
        return self.get_current_char().ring_index

    def get_con_box(self):
        """获取协奏值能量环的UI区域盒子对象。

        Returns:
            Box: 盒子对象。
        """
        return self.box_of_screen_scaled(3840, 2160, 1431, 1942, 1557, 2068, name='con_full',
                                         hcenter=True)

    def get_current_con(self):
        """获取当前角色的协奏值百分比。

        Returns:
            float: 协奏值百分比 (0.0 到 1.0)。
        """
        box = self.get_con_box()
        box.confidence = 0

        max_area = 0
        percent = 0
        max_is_full = False
        target_index = self._ensure_ring_index()

        cropped = box.crop_frame(self.frame)
        for i in range(len(con_colors)):
            if target_index != -1 and i != target_index:
                continue
            color_range = con_colors[i]
            area, is_full = self.count_rings(cropped, color_range,
                                             1500 / 3840 / 2160 * self.screen_width * self.screen_height)
            if is_full:
                max_is_full = is_full
            if area > max_area:
                max_area = int(area)
        if max_is_full:
            percent = 1
        if max_is_full:
            self.con_full_size[str(target_index)] = max_area

        if percent != 1 and self.con_full_size[str(target_index)] > 0:
            percent = max_area / self.con_full_size[str(target_index)]
        if not max_is_full and percent >= 1:
            self.logger.warning(
                f'is_con_full not full but percent greater than 1, set to 0.99, {percent} {max_is_full}')
            percent = 0.99
        if percent > 1:
            self.logger.error(f'is_con_full percent greater than 1, set to 1, {percent} {max_is_full}')
            percent = 1

        box.confidence = percent
        self.draw_boxes(f'is_con_full_{self}', box)
        if percent > 1:
            percent = 1
        return percent

    def count_rings(self, image, color_range, min_area):
        """在指定图像区域内计算特定颜色范围的能量环数量和状态。

        Args:
            image (numpy.ndarray): 要分析的图像 (通常是协奏值UI区域的截图)。
            color_range (dict): 目标颜色范围。
            min_area (float): 认为是有效能量环的最小面积。

        Returns:
            tuple: (检测到的区域面积 (int), 是否为完整环 (bool))。
        """
        # Define the color range
        lower_bound, upper_bound = color_range_to_bound(color_range)
        masked_image = image.copy()
        h, w = image.shape[:2]
        center = (w // 2, h // 2)

        # draw mask
        r1, r2 = h * 0.35119, h * 0.42261
        r1 = Decimal(str(r1)).quantize(Decimal('0'), rounding=ROUND_DOWN)
        r2 = Decimal(str(r2)).quantize(Decimal('0'), rounding=ROUND_UP)

        ring_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(ring_mask, center, int(r2), 255, -1)
        cv2.circle(ring_mask, center, int(r1), 0, -1)
        masked_image = cv2.bitwise_and(masked_image, masked_image, mask=ring_mask)

        # Perform closing operation (Dilation followed by Erosion)
        raw_mask = cv2.inRange(masked_image, lower_bound, upper_bound)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, kernel)
        closed_mask[center[1] - 1:center[1] + 2, center[0] + 1:] = \
            raw_mask[center[1] - 1:center[1] + 2, center[0] + 1:]

        # Find connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(closed_mask, connectivity=8)

        # Function to check if a component forms a ring
        def is_full_ring(component_mask):
            # Find contours
            contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if len(contours) != 1:
                return False
            contour = contours[0]

            # Check if the contour is closed by checking if the start and end points are the same
            # if cv2.arcLength(contour, True) > 0:
            #     return True
            # Approximate the contour with polygons.
            epsilon = 0.05 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            # Check if the polygon is closed (has no gaps) and has a reasonable number of vertices for a ring.
            if not cv2.isContourConvex(approx) or len(approx) < 4:
                return False

            # All conditions met, likely a close ring.
            return True

        # output_image = image.copy()
        # Iterate over each component
        ring_count = 0
        is_full = False
        the_area = 0
        for label in range(1, num_labels):
            x, y, width, height, area = stats[label, :5]
            bounding_box_area = width * height
            component_mask = (labels == label).astype(np.uint8) * 255
            # color = colors[label % len(colors)]
            # mask = labels == label
            # output_image[mask] = color
            if bounding_box_area >= min_area:
                # Select a color from the list based on the label index
                if is_full_ring(component_mask):
                    is_full = True
                the_area = area
                ring_count += 1

        # Save or display the image with contours
        # cv2.imwrite(fr'test\count_rings_{is_full}_{self.screen_width}_mask.png', output_image)
        # cv2.imwrite(fr'test\count_rings_{is_full}_{self.screen_width}.png', masked_image)
        if ring_count > 1:
            is_full = False
            the_area = 0
            self.logger.warning(f'is_con_full found multiple rings {ring_count}')

        return the_area, is_full

    def update_lib_portrait_icon(self):
        # self.ensure_con_lib_boxes()
        for i in range(len(self.chars)):
            char_index = i + 1
            char = self.chars[i]
            if not char.is_current_char and char.ring_index >= 0 and not char._liberation_available:
                box = self.get_box_by_name("lib_mark_char_{}".format(char_index))
                match = self.find_one(lib_ready_templates[char.ring_index], box=box, threshold=0.8)
                if match:
                    char._liberation_available = True
                    self.log_debug('checking liberation_available by template {} {}'.format(char, match))
                    # self.screenshot('liberation_available_{}_{}_{}'.format(char, match.name, match.confidence))


white_color = {  # 用于检测UI元素可用状态的白色颜色范围。
    'r': (253, 255),  # Red range
    'g': (253, 255),  # Green range
    'b': (253, 255)  # Blue range
}

con_colors = [  # 不同角色属性的协奏值能量环的颜色范围列表。
    {
        'r': (205, 235),
        'g': (190, 222),  # for yellow spectro
        'b': (90, 130)
    },
    {
        'r': (150, 190),  # Red range
        'g': (95, 140),  # Green range for purple electric
        'b': (210, 249)  # Blue range
    },
    {
        'r': (200, 230),  # Red range
        'g': (100, 130),  # Green range    for red fire
        'b': (75, 105)  # Blue range
    },
    {
        'r': (60, 95),  # Red range
        'g': (150, 180),  # Green range    for blue ice
        'b': (210, 245)  # Blue range
    },
    {
        'r': (70, 110),  # Red range
        'g': (215, 250),  # Green range    for green wind
        'b': (155, 190)  # Blue range
    },
    {
        'r': (190, 220),  # Red range
        'g': (65, 105),  # Green range    for havoc
        'b': (145, 175)  # Blue range
    }
]

con_templates = [  # 协奏值能量环的模板名称列表 (对应 `con_colors`)。
    'con_spectro',
    'con_electric',
    'con_fire',
    'con_ice',
    'con_wind',
    'con_havoc',
]

lib_ready_templates = [  # 头像右边大招可用对号
    'lib_ready_spectro',  # 3
    'lib_ready_electric',  # 3
    'lib_ready_fire',  # 2
    'lib_ready_ice',  # 2
    'lib_ready_wind',  # 1
    'lib_ready_havoc',  # 3
]

con_full_templates = [  # 头像右边表示当前角色 协奏满
    'con_full_spectro',  # 3
    'con_full_electric',  # 3
    'con_full_fire',  # 2
    'con_full_ice',  # 2
    'con_full_wind',  # 1
    'con_full_havoc',  # 3
]


def convert_cd(text):
    """
    Strips a string to only keep the first part that matches the regex pattern.
    Args:
      text: The input string.
      pattern: The regex pattern to match.
    Returns:
      The first matching substring, or None if no match is found.
    """
    try:
        return float(text.name)
    except ValueError:
        match = re.search(cd_regex, text.name)
        if match:
            return float(match.group(0))
        else:
            return 1
