import re
import time
from decimal import Decimal, ROUND_UP, ROUND_DOWN

import cv2
import numpy as np

from ok import Logger, Config
from ok import color_range_to_bound
from ok import safe_get
from ok.feature.Box import get_bounding_box
from src import text_white_color
from src.char import BaseChar
from src.char.BaseChar import Priority, dot_color  # noqa
from src.char.CharFactory import get_char_by_pos
from src.char.Healer import Healer
from src.combat.CombatCheck import CombatCheck
from src.task.BaseWWTask import isolate_white_text_to_black, binarize_for_matching

logger = Logger.get_logger(__name__)
cd_regex = re.compile(r'\d{1,2}\.\d')
# 复苏弹窗：与 ONNXPaddleOcr(native) 在实机截图上对齐；标题易被裁成「苏物品」，正文含「恢复意识」「60秒」「共鸣者」「命值」等。
revive_popup_title_re = re.compile(
    r'(选择复苏物品|选择复苏|复苏物品|苏物品|revive)', re.IGNORECASE)
revive_popup_body_a_re = re.compile(r'(恢复意识|即时恢复|指定共鸣者)', re.IGNORECASE)
revive_popup_body_b_re = re.compile(r'(60秒|每60|共鸣者|命值|生命值|多人游戏)', re.IGNORECASE)
revive_popup_confirm_re = re.compile(r'(确认|confirm)', re.IGNORECASE)
exit_confirm_confirm_re = re.compile(r'^(确认|confirm)$', re.IGNORECASE)
exit_confirm_cancel_re = re.compile(r'^(取消|cancel)$', re.IGNORECASE)
recovery_settle_s = 1.5


class NotInCombatException(Exception):
    """未处于战斗状态异常。"""
    pass


class CharDeadException(NotInCombatException):
    """角色死亡异常。"""
    pass


class CombatAbortedAfterRevive(NotInCombatException):
    """阵亡后已尝试退出副本并传送回血，战斗循环应中止并由上层重试。"""


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
        if self.scene.cd_refreshed:
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
        self.scene.cd_refreshed = True
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

    def revive_action(self):
        """Common Forgery/Simulation recovery flow with strict step confirmations."""
        self._run_structured_revive_flow(flow_tag='revive_action', skip_exit_confirm_steps=False)

    def _run_structured_revive_flow(self, flow_tag='revive_action', skip_exit_confirm_steps=False):
        self.log_info(f'{flow_tag}: recovering after character death')
        max_retries = 2
        last_error = None
        prev_skip_combat_check = self.skip_combat_check
        self.skip_combat_check = True
        try:
            for attempt in range(max_retries):
                try:
                # Step 1: close revive popup (single action), confirm it is gone.
                    if not self._step_close_revive_popup_once():
                        raise RuntimeError('step1 close revive popup failed')
                    if not skip_exit_confirm_steps:
                        # Step 2: press ESC once, confirm exit dialog appears.
                        if not self._step_open_exit_confirm_dialog_once():
                            raise RuntimeError('step2 open exit-confirm dialog failed')
                        # Step 3: click confirm once, confirm back to world.
                        if not self._step_confirm_exit_once():
                            raise RuntimeError('step3 confirm exit failed')
                # Step 4: reuse weekly entrance route and confirm in-world.
                    if not self.go_to_weekly_entrance_for_recovery():
                        raise RuntimeError('step4 go weekly entrance failed')
                # Step 5: open map once, confirm map state.
                    if not self._step_open_map_once():
                        raise RuntimeError('step5 open map failed')
                # Step 6: click left waypoint once and travel once.
                    if not self._step_fast_travel_left_waypoint_once():
                        raise RuntimeError('step6 fast travel left waypoint failed')
                    raise CombatAbortedAfterRevive(f'{flow_tag} recovered after character death')
                except CombatAbortedAfterRevive:
                    raise
                except Exception as e:
                    last_error = e
                    self.log_error(f'{flow_tag}: recovery failed attempt {attempt + 1}/{max_retries}', e)
                    self._force_reset_to_main_after_recovery_failure()
            if last_error:
                self.log_error(f'{flow_tag}: all retries failed', last_error)
            raise CombatAbortedAfterRevive(f'{flow_tag} recovery attempted with partial failure')
        finally:
            self.skip_combat_check = prev_skip_combat_check

    def exit_realm_to_world(self, time_out=120, retries=2):
        """复用 DomainTask 的稳定退副本流程：ESC -> 确认离开 -> 等待回世界。"""
        if not self.in_realm():
            return self.wait_in_team_and_world(time_out=min(30, time_out), raise_if_not_found=False)
        for attempt in range(retries):
            # 避免 after_sleep 触发 sleep_check 在非战斗态抛异常。
            self.send_key('esc')
            self.sleep(1)
            self._dismiss_exit_confirm_popup(prefer_confirm=True)
            self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=False,
                                    time_out=3, click_after_delay=0.5, threshold=0.7)
            self.wait_click_feature('claim_cancel_button_hcenter_vcenter', relative_x=2,
                                    raise_if_not_found=False, settle_time=1, time_out=2)
            if self.wait_in_team_and_world(time_out=time_out, raise_if_not_found=False):
                return True
            if not self.in_realm():
                return True
            self.log_info(f'exit_realm_to_world retry {attempt + 1}/{retries}')
        return False

    def _dismiss_exit_confirm_popup(self, prefer_confirm: bool):
        """Handle the '确认离开' modal that may appear after ESC.

        - prefer_confirm=True: click confirm (Forgery/Simulation recovery wants to exit)
        - prefer_confirm=False: click cancel (used by Tacet-specific logic)
        """
        if not self.wait_feature('gray_confirm_exit_button', raise_if_not_found=False, time_out=0.2):
            return False
        if prefer_confirm:
            self.log_info('exit-confirm popup detected, confirm exit')
            # Click the confirm button feature directly to avoid coordinate drift.
            self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=False,
                                    threshold=0.7, time_out=1.5, click_after_delay=0.2, after_sleep=0)
        else:
            self.log_info('exit-confirm popup detected, cancel exit')
            self.wait_click_feature('cancel_button_hcenter_vcenter', relative_x=-1, raise_if_not_found=False,
                                    threshold=0.7, time_out=1.5, click_after_delay=0.2, after_sleep=0)
        self.sleep(1)
        # Confirm dialog should be gone; if still present, try OCR-based click as a last resort.
        if not self.wait_feature('gray_confirm_exit_button', raise_if_not_found=False, time_out=0.2):
            return True

        match = exit_confirm_confirm_re if prefer_confirm else exit_confirm_cancel_re
        # Only scan the lower part of the modal where the buttons are.
        buttons = self.ocr(0.15, 0.62, 0.95, 0.90, match=match)
        if buttons:
            self.log_info(f'exit-confirm popup ocr fallback click {buttons[0].name}')
            self.click_box(buttons[0], after_sleep=0.2)
            self.sleep(1)
        return not bool(self.wait_feature('gray_confirm_exit_button', raise_if_not_found=False, time_out=0.2))

    def _force_reset_to_main_after_recovery_failure(self):
        self.log_info('revive_action: force reset to main')
        # If we failed while map is open, close it first to avoid ESC opening/closing other modals.
        if self._is_map_open_for_recovery():
            self.send_key('m')
            self._recovery_pause(recovery_settle_s)
        for _ in range(3):
            self.send_key('esc')
            self._recovery_pause(recovery_settle_s)
            self._dismiss_exit_confirm_popup(prefer_confirm=False)
            if self.in_team_and_world():
                return
        self.ensure_main(esc=True, time_out=60)

    def _is_map_open_for_recovery(self):
        """Best-effort check: whether the big map UI is open."""
        if self.feature_exists('map_setting_gear') and self.find_one('map_setting_gear', threshold=0.7):
            return True
        if self.feature_exists('map_search') and self.find_one('map_search', threshold=0.7):
            return True
        if self.feature_exists('map_my_location') and self.find_one('map_my_location', threshold=0.7):
            return True
        box = self.box_of_screen(0.05, 0.05, 0.95, 0.95)
        return bool(self.find_feature('map_way_point', box=box, threshold=0.7) or
                    self.find_feature('map_way_point_big', box=box, threshold=0.7))

    def _recovery_pause(self, timeout):
        """Pause during recovery without triggering in-combat sleep checks."""
        old = self.skip_combat_check
        self.skip_combat_check = True
        try:
            self.sleep(timeout)
        finally:
            self.skip_combat_check = old

    def _step_close_revive_popup_once(self):
        self.log_info('revive_action step1: close revive popup')
        if close_btn := self.find_one('btn_dialog_close', threshold=0.75):
            self.click(close_btn, move_back=True, after_sleep=0)
        else:
            self.click_relative(0.935, 0.205, move_back=True, after_sleep=0)
        self._recovery_pause(recovery_settle_s)
        return not self.has_revive_popup()

    def _step_open_exit_confirm_dialog_once(self):
        self.log_info('revive_action step2: open exit-confirm dialog')
        # If the dialog is already present (e.g., triggered by a prior ESC), do not press ESC again.
        if self.wait_feature('gray_confirm_exit_button', raise_if_not_found=False, time_out=0.2):
            return True
        self.send_key('esc')
        self._recovery_pause(recovery_settle_s)
        return bool(self.wait_feature('gray_confirm_exit_button', raise_if_not_found=False, time_out=recovery_settle_s))

    def _step_confirm_exit_once(self):
        self.log_info('revive_action step3: confirm exit')
        self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=False,
                                threshold=0.7, time_out=1.5, click_after_delay=0.2, after_sleep=0)
        self._recovery_pause(recovery_settle_s)
        if self.wait_feature('gray_confirm_exit_button', raise_if_not_found=False, time_out=recovery_settle_s):
            return False
        return bool(self.wait_in_team_and_world(time_out=60, raise_if_not_found=False))

    def has_revive_popup(self):
        """检测是否出现复苏物品/复活确认类弹窗。

        区域与关键字按 native Paddle OCR 在「选择复苏物品」弹窗截图上的结果标定：
        标题宜单独扫左上一带；正文占中部大块；「确认」按钮在 native 下常漏检，不作为必要条件。
        """
        title = self.ocr(0.03, 0.05, 0.52, 0.28, match=revive_popup_title_re)
        body_lo, body_hi, body_l, body_r = 0.06, 0.72, 0.06, 0.92
        body_a = self.ocr(body_l, body_lo, body_r, body_hi, match=revive_popup_body_a_re)
        body_b = self.ocr(body_l, body_lo, body_r, body_hi, match=revive_popup_body_b_re)
        body = bool(body_a and body_b)
        confirm = self.ocr(0.45, 0.70, 0.98, 0.96, match=revive_popup_confirm_re)
        detected = bool(title or body or confirm)
        if title or body_a or body_b or confirm:
            self.log_debug(
                f'revive popup ocr title={bool(title)} body_a={bool(body_a)} body_b={bool(body_b)} '
                f'body_pair={body} confirm={bool(confirm)} -> {detected}')
        return detected

    def close_revive_popup(self):
        """优先点击关闭复苏弹窗，避免通过 ESC 连续退层。"""
        if not self._has_stable_revive_popup():
            return True

        # 1) 通用右上角关闭按钮（若该弹窗存在 close icon）。
        if close_btn := self.find_one('btn_dialog_close', threshold=0.75):
            self.click(close_btn, move_back=True, after_sleep=0.3)
            if self.wait_until(lambda: not self.has_revive_popup(), time_out=1.5, raise_if_not_found=False):
                return True

        # 2) 根据截图，弹窗外侧背景可关闭弹窗，优先尝试左右两侧空白区。
        for x, y in ((0.03, 0.50), (0.97, 0.50), (0.50, 0.95)):
            self.click_relative(x, y, move_back=True, after_sleep=0.25)
            if self.wait_until(lambda: not self.has_revive_popup(), time_out=1.2, raise_if_not_found=False):
                return True

        # 3) Fallback: click the top-right "X" area inside modal (for UI variants without template).
        # The revive modal in 16:9 places the close icon near the top-right corner of the popup.
        self.click_relative(0.935, 0.205, move_back=True, after_sleep=0.3)
        if self.wait_until(lambda: not self.has_revive_popup(), time_out=1.2, raise_if_not_found=False):
            return True

        # 3) 仅作为兜底，最后尝试一次 ESC。
        if not self.has_revive_popup():
            return True
        self.send_key('esc')
        return bool(self.wait_until(lambda: not self.has_revive_popup(), time_out=1.5, raise_if_not_found=False))

    def _has_stable_revive_popup(self):
        """Require two consecutive detections to reduce OCR false positives."""
        if not self.has_revive_popup():
            return False
        # Avoid sleep() here: it may trigger combat state checks while the modal is blocking.
        self.next_frame()
        self.next_frame()
        return self.has_revive_popup()

    def go_to_weekly_entrance_for_recovery(self):
        """Reuse the weekly-book route used by daily task to reach the weekly entrance."""
        from src.Labels import Labels

        self.log_info('revive_action: go to weekly entrance')
        self.ensure_main(time_out=80)
        gray_book_weekly = self.openF2Book(Labels.gray_book_weekly)
        if not gray_book_weekly:
            self.log_error('revive_action: can not find gray_book_weekly')
            return False
        self.click_box(gray_book_weekly, after_sleep=1)
        btn = self.find_one(Labels.boss_proceed, box=self.box_of_screen(0.91, 0.3, 0.95, 0.41), threshold=0.8)
        if btn is None:
            self.log_error('revive_action: can not find weekly boss_proceed')
            self.ensure_main(time_out=10)
            return False
        self.click_box(btn, after_sleep=1)
        self.wait_click_travel()
        self.wait_in_team_and_world(time_out=120)
        self.sleep(1)
        return True

    def teleport_to_heal_via_weekly_entrance(self, raise_if_not_found=True):
        """Stabilized heal route: weekly entrance first, then open map and teleport to nearest waypoint."""
        if not self.go_to_weekly_entrance_for_recovery():
            if raise_if_not_found:
                raise RuntimeError('Can not reach weekly entrance before heal teleport')
            return False
        self.sleep(1)
        return self.teleport_to_heal(esc=False, raise_if_not_found=raise_if_not_found)

    def _step_open_map_once(self):
        self.log_info('revive_action step5: open map')
        self.send_key('m')
        # Single action only, but allow time for slow devices/UI to render.
        return bool(self.wait_until(self._is_map_open_for_recovery, time_out=recovery_settle_s, raise_if_not_found=False))

    def _step_fast_travel_left_waypoint_once(self):
        """Step6: more reliable travel by reusing the 'nearest waypoint' selection logic."""
        self.log_info('revive_action step6: fast travel nearest waypoint')
        return self._fast_travel_nearest_waypoint_on_open_map()

    def _fast_travel_nearest_waypoint_on_open_map(self):
        """Select a waypoint like teleport_to_heal(), but assumes the map is already open."""
        if not self._is_map_open_for_recovery():
            return False
        waypoint_box = self.box_of_screen(0.1, 0.1, 0.9, 0.9)
        max_attempts = 3
        for attempt in range(max_attempts):
            threshold = max(0.6, 0.7 - attempt * 0.04)
            teleport = self.find_best_match_in_box(waypoint_box, ['map_way_point', 'map_way_point_big'], threshold)
            if not teleport:
                if attempt < max_attempts - 1:
                    self.click_relative(0.94, 0.33, after_sleep=0.4)  # slight zoom and retry
                    self._recovery_pause(recovery_settle_s)
                    continue
                return False

            self.click(teleport, after_sleep=1)
            travel = self.wait_feature(['fast_travel_custom', 'gray_teleport', 'remove_custom'],
                                       raise_if_not_found=False, time_out=2.5, settle_time=0.3)
            if not travel:
                pop_up = self.find_feature('map_way_point', box='map_way_point_pop_up_box')
                if pop_up:
                    self.click(pop_up, after_sleep=0.8)
                    travel = self.wait_feature(['fast_travel_custom', 'gray_teleport', 'remove_custom'],
                                               raise_if_not_found=False, time_out=2.5, settle_time=0.3)
            if travel and self.click_traval_button():
                self.wait_in_team_and_world(time_out=20)
                self.sleep(2)
                return True
            if attempt < max_attempts - 1:
                self.log_info(f'revive_action step6: no travel button after waypoint click, retry {attempt + 1}')
                self.click_relative(0.94, 0.33, after_sleep=0.4)
                self._recovery_pause(recovery_settle_s)
        return False

    def teleport_to_heal(self, esc=True, raise_if_not_found=True):
        """传送回城治疗。"""
        if esc:
            self.sleep(1)
            self.info['Death Count'] = self.info.get('Death Count', 0) + 1
            self.send_key('esc', after_sleep=2)
        self.log_info('click m to open the map')
        self.send_key('m', after_sleep=2)
        waypoint_box = self.box_of_screen(0.1, 0.1, 0.9, 0.9)
        max_attempts = 3
        for attempt in range(max_attempts):
            # 避免命中地图事件点后无「传送」按钮：每次失败后轻度缩放并重选锚点。
            threshold = 0.7 - attempt * 0.04
            threshold = max(0.6, threshold)
            teleport = self.find_best_match_in_box(waypoint_box, ['map_way_point', 'map_way_point_big'], threshold)
            if not teleport:
                if attempt < max_attempts - 1:
                    self.click_relative(0.94, 0.33, after_sleep=0.4)
                    continue
                if raise_if_not_found:
                    raise RuntimeError(f'Can not find a teleport to heal')
                return False

            self.click(teleport, after_sleep=1)
            travel = self.wait_feature(['fast_travel_custom', 'gray_teleport', 'remove_custom'],
                                       raise_if_not_found=False, time_out=2.5, settle_time=0.3)
            if not travel:
                pop_up = self.find_feature('map_way_point', box='map_way_point_pop_up_box')
                if pop_up:
                    self.click(pop_up, after_sleep=0.8)
                    travel = self.wait_feature(['fast_travel_custom', 'gray_teleport', 'remove_custom'],
                                               raise_if_not_found=False, time_out=2.5, settle_time=0.3)
            if travel and self.click_traval_button():
                self.wait_in_team_and_world(time_out=20)
                self.sleep(2)
                return True
            if attempt < max_attempts - 1:
                self.log_info(f'teleport_to_heal: no travel button after waypoint click, retry {attempt + 1}')
                self.click_relative(0.94, 0.33, after_sleep=0.4)

        if raise_if_not_found:
            raise RuntimeError(f'Can not find the travel button')
        return False

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
        if wait_combat_time > 0:
            self.wait_until(self.in_combat, time_out=wait_combat_time, raise_if_not_found=raise_if_not_found)
        self.load_chars()
        self.info['Combat Count'] = self.info.get('Combat Count', 0) + 1
        try:
            while self.in_combat():
                logger.debug(f'combat_once loop {self.chars}')
                self.get_current_char().perform()
        except CharDeadException as e:
            raise e
        except CombatAbortedAfterRevive:
            raise
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
        from src.char.ShoreKeeper import ShoreKeeper
        last_click = 0
        start = time.time()
        while True:
            # 复苏弹窗打开时 in_combat 常为假，若先 check_combat 会抛脱战异常，永远走不到 OCR。
            confirm = self.wait_feature('revive_confirm_hcenter_vcenter', threshold=0.8, time_out=0.2,
                                        raise_if_not_found=False)
            if confirm or self.has_revive_popup():
                self.log_info('char dead popup detected while switching')
                self.revive_action()
            if not (isinstance(switch_to, ShoreKeeper) and has_intro):
                self.check_combat()
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
            self.next_frame()

        if post_action:
            logger.debug(f'post_action {post_action}')
            post_action(switch_to, has_intro)
        logger.info(f'switch_next_char end {(current_char.last_switch_time - start):.3f}s')

    def find_mouse_forte(self):
        return self.find_one('mouse_forte', horizontal_variance=0.025, vertical_variance=0.015, threshold=0.7,
                             frame_processor=binarize_for_matching)

    def find_e_forte(self):
        return self.find_one('e_forte', horizontal_variance=0.025, threshold=0.6,
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
        if self.skip_combat_check:
            return
        # self.log_debug(f'sleep_check {self._in_combat}')
        if self._in_combat:
            self.next_frame()
            if not self.in_combat():
                self.raise_not_in_combat('sleep check not in combat')

    def check_combat(self):
        """检查当前是否处于战斗状态, 如果不是则抛出异常。"""
        if self._in_combat and not self.in_combat():
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
            self.info_set('Chars', self.chars)
            for c in self.chars:
                self.log_info(f'loaded chars success {c} {c.confidence}')
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
