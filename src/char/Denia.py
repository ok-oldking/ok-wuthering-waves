from src.char.BaseChar import BaseChar
import time


class Denia(BaseChar):
    # 逻辑状态：LIB1 表示等待第一段大招，LIB2 表示第一段大招已释放。
    LIB1 = 'lib1'
    LIB2 = 'lib2'
    # 第一段大招后等待 45.png 对应的 denia_lib2 识别，避免过早执行后续动作。
    LIB2_RECOGNITION_TIMEOUT = 1.2
    # 常规后续轮次中，LIB2 的连续普攻时长。
    LIB2_NORMAL_ATTACK_TIME = 2.8
    # LIB2 动作结果不明确时，用 46.png 做 LIB1 兜底确认。
    E1_FALLBACK_TIMEOUT = 0.7
    E1_FALLBACK_REQUIRED_HITS = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # state 只记录当前 rotation 所处阶段，不依赖单次图像识别结果。
        self.state = self.LIB1

    def reset_state(self):
        super().reset_state()
        self.state = self.LIB1

    def _switch_to_main_dps(self):
        """固定切到队伍中的主C,保留底层切人流程和协奏入场处理。"""
        main_dps = next(
            (char for char in self.task.chars
             if char is not None
             and char is not self
             and char.is_main_dps),
            None,
        )
        if main_dps is None:
            self.logger.warning(
                'Denia main DPS switch target not found, use default switch selector'
            )
            self.switch_next_char()
            return False

        # BaseCombatTask 的通用选择器会在多个候选角色之间再次仲裁；
        # 临时锁定当前达妮娅的目标，确保切换落到主C。
        original_selector = self.task._choose_switch_target

        def choose_target(current_char, has_intro, target_low_con=False):
            if current_char is self:
                return main_dps
            return original_selector(current_char, has_intro, target_low_con)

        self.task._choose_switch_target = choose_target
        try:
            self.switch_next_char()
        finally:
            self.task._choose_switch_target = original_selector

        in_team, current_index, _ = self.task.in_team()
        return in_team and current_index == main_dps.index

    def lib2_available(self):
        # 45.png 对应的 COCO 类别：denia_lib2。
        return bool(self.task.find_one('denia_lib2', threshold=0.7))

    def e1_available(self):
        # 46.png 对应的 COCO 类别：denia_e1。
        return bool(self.task.find_one('denia_e1', threshold=0.7))

    def _confirm_lib1_by_e1(self):
        """在 LIB2 动作失败时，用连续两帧 denia_e1 识别兜底确认 LIB1。"""
        consecutive_hits = 0
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < self.E1_FALLBACK_TIMEOUT:
            self.cycle_start()
            self.check_combat()
            if self.e1_available():
                consecutive_hits += 1
                if consecutive_hits >= self.E1_FALLBACK_REQUIRED_HITS:
                    return True
            else:
                consecutive_hits = 0
            self.cycle_sleep()
        return False

    def _wait_for_lib2_recognition(self):
        # 以 bounded wait 等待模板出现，避免识别失败时阻塞整场战斗。
        return self.task.wait_until(
            self.lib2_available,
            time_out=self.LIB2_RECOGNITION_TIMEOUT,
        )

    def _wait_skill_ready(self, available_fn, time_out):
        # 用 cycle_start/cycle_sleep 做 0.1s 帧节流的技能就绪轮询；
        # 以 time_elapsed_accounting_for_freeze 计时，避免大招动画冻结时钟误判超时；
        # 等待期间保持普攻和战斗检查，避免角色停在原地。
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < time_out:
            self.cycle_start()
            self.check_combat()
            if available_fn():
                return True
            self.task.click()
            self.cycle_sleep()
        return available_fn()

    def _perform_lib1(self, has_intro=False):
        # 常规后续轮次的 LIB1：等待大招和共鸣就绪，再释放第一段大招。
        if not self._wait_skill_ready(self.liberation_available, 2):
            return False

        # 共鸣不可用则交给外层执行普攻后切人。
        if not self._wait_skill_ready(self.resonance_available, 2):
            return False
        # 只有通过变奏入场时，释放共鸣技能前才先普攻 0.7 秒。
        if has_intro:
            self.continues_normal_attack(0.7)
        if not self._use_lib1_resonance():
            return False

        return self.click_liberation()

    def _use_lib1_resonance(self):
        """释放 LIB1 共鸣；即使返回失败但已进 CD，也视为释放成功。"""
        for _ in range(2):
            if self.click_resonance(time_out=2)[0]:
                return True
            if self.has_cd('resonance'):
                return True
        return False

    def _perform_lib2(self, has_intro):
        # 有变奏入场的 LIB2：普攻、闪避、普攻后连续释放两次共鸣技能。
        if has_intro:
            self.continues_normal_attack(1.1)
            self.continues_right_click(0.05)
            self.check_combat()
            self.continues_normal_attack(1.1)
            self.click_resonance(time_out=2)
            self.click_resonance(time_out=2)
        else:
            # 无变奏入场：两段普攻后检查战斗，再补闪避和一段普攻。
            self.continues_normal_attack(1.1)
            self.continues_right_click(0.05)
            self.continues_normal_attack(1.1)
            self.check_combat()
            self.continues_right_click(0.05)
            self.continues_normal_attack(1.1)
            if not self.click_resonance(time_out=2)[0]:
                return False

        # 共鸣技能完成后等待 0.5 秒，再释放第二段大招。
        self.sleep(0.5)
        # 二段大招失败后普攻 1.4 秒重试，最多重试两次。
        lib_success = self.click_liberation()
        retries = 0
        while not lib_success and retries < 2:
            self.continues_normal_attack(1.1)
            lib_success = self.click_liberation()
            retries += 1
        if lib_success:
            self.sleep(0.01)

        return lib_success

    def do_perform(self):
        # 快照协奏入场标记，整条 rotation 以此为准：
        # LIB2 协奏入场走 1.4 秒普攻 + 闪避 + 1.4 秒普攻；无变奏走原流程。
        has_intro = self.has_intro
        if has_intro:
            self.wait_intro(1.2)

        if self.state == self.LIB1:
            # 所有出场统一走常规 LIB1 -> LIB2 状态机。
            if not self._perform_lib1(has_intro):
                self.continues_normal_attack(1.0)
                self._switch_to_main_dps()
                return
            self.state = self.LIB2
            self._wait_for_lib2_recognition()

        lib2_success = False
        lib1_fallback = False
        if self.state == self.LIB2:
            lib2_success = self._perform_lib2(has_intro)
            if not lib2_success:
                # 仅在第二段流程结果不明确时，才使用 denia_e1 兜底修正状态。
                lib1_fallback = self._confirm_lib1_by_e1()

        # 常规轮次：声骸后切人；二段大招成功才把逻辑状态重置为 LIB1。
        self.click_echo()
        if lib2_success or lib1_fallback:
            self.state = self.LIB1
        self._switch_to_main_dps()
