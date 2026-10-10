import time

from src.char.BaseChar import BaseChar, SwitchPriority
from src.utils.douling_energy import recognize_energy as detect_energy
from src.utils.guaxiang import recognize_guaxiang as detect_guaxiang


class Douling(BaseChar):
    NORMAL_ATTACK_INTERVAL = 0.3
    GUAXIANG_POLL_INTERVAL = 0.1
    GUAXIANG_WAIT_TIMEOUT = 3.0
    GUAXIANG_MAX_ATTEMPTS = 30
    HEAVY_SAMPLE_INTERVAL = 0.2
    POST_HEAVY_OBSERVE_DURATION = 0.4

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._segment = 1
        self._waiting_for_guaxiang = False
        self._guaxiang_error_logged = False
        self._energy_state = None
        self._energy_error_logged = False
        self._post_heavy_observer = None

    def do_perform(self):
        self.recognize_guaxiang('entry')
        if self._segment == 1:
            self._do_segment1()
        else:
            self._do_segment2()

    def recognize_guaxiang(self, sample_point='manual', *, require_current_char=False):
        """同一帧识别卦象和能量，仅在上场时记录各自结果。"""
        self._energy_state = None
        try:
            hud_visible, current_index, _ = self.task.in_team()
            if require_current_char:
                hud_visible = hud_visible and current_index == self.index
            captured_frame = self.task.frame
            frame = captured_frame.copy() if captured_frame is not None else None
            self._recognize_energy(frame, hud_visible and current_index == self.index, sample_point)
            result = detect_guaxiang(frame, hud_visible=hud_visible)
            if sample_point == 'entry':
                if result.sequence is None:
                    self.logger.info(
                        f'[DoulingRecognition] point=entry status=uncertain reason={result.reason}')
                else:
                    sequence = ','.join(result.sequence) or '[]'
                    self.logger.info(
                        f'[DoulingRecognition] point=entry count={len(result.sequence)} sequence={sequence}')
            return result.sequence
        except Exception as error:
            if not self._waiting_for_guaxiang or not self._guaxiang_error_logged:
                self.logger.warning(f'[DoulingRecognition] point={sample_point} status=uncertain error={error}')
                if self._waiting_for_guaxiang:
                    self._guaxiang_error_logged = True
            return None

    def _recognize_energy(self, frame, hud_visible, sample_point):
        self._energy_state = None
        try:
            result = detect_energy(frame, hud_visible=hud_visible)
            self._energy_state = result.state
            if sample_point == 'entry':
                if result.state is None:
                    self.logger.info(
                        f'[DoulingEnergy] point=entry status=uncertain reason={result.reason}')
                else:
                    self.logger.info(f'[DoulingEnergy] point=entry state={result.state}')
            return result.state
        except Exception as error:
            if not self._waiting_for_guaxiang or not self._energy_error_logged:
                self.logger.warning(f'[DoulingEnergy] point={sample_point} status=uncertain error={error}')
                if self._waiting_for_guaxiang:
                    self._energy_error_logged = True
            return None

    def _do_segment1(self):
        self._normal_attack_cycle(1.2)
        if self.flying():
            self.wait_down()
        self.check_combat()
        clicked = self.click_resonance(send_click=True, time_out=0.5)[0]
        if not clicked:
            self._finish_and_reset()
            return
        self.sleep(0.2)
        if self.flying():
            self.wait_down()
        self.check_combat()
        self._normal_attack_cycle(1.0)
        self._segment = 2
        self.switch_next_char()

    def _do_segment2(self):
        self.check_combat()
        self.task.jump(after_sleep=0.01)
        self.sleep(0.05)
        self.check_combat()
        if self.flying():
            self.click()
            self.sleep(0.05)
        else:
            self.wait_down()
        self.check_combat()
        if not self._normal_attack_until_four_guaxiang():
            self._segment = 1
            self.switch_next_char()
            return
        self._heavy_attack_hold(2.5)
        try:
            self.click_echo(time_out=0)
            self.click_liberation()
            self._segment = 1
            self.switch_next_char()
        except BaseException:
            self._cancel_post_heavy_observation()
            raise

    def _finish_and_reset(self):
        self.click_echo(time_out=0)
        self.click_liberation()
        self._segment = 1
        self.switch_next_char()

    def _record_heavy_recognition(self, sample_point, attempt, sample, phase_start,
                                  frame=None, refresh=True):
        self._energy_state = None
        if refresh:
            frame = self.task.next_frame()
            self.check_combat()
        sequence = self.recognize_guaxiang(sample_point, require_current_char=True) if frame is not None else None
        count = 'uncertain' if sequence is None else len(sequence)
        text = 'uncertain' if sequence is None else ','.join(sequence) or '[]'
        capture_reason = ' reason=capture_failed' if frame is None else ''
        self.logger.info(
            f'[DoulingRecognition] point={sample_point} attempt={attempt} sample={sample} '
            f'elapsed={time.monotonic() - phase_start:.3f}s count={count} sequence={text} '
            f'energy={self._energy_state or "uncertain"}{capture_reason}')

    def _cancel_post_heavy_observation(self):
        cancel = getattr(self, '_post_heavy_observer', None)
        if cancel is not None:
            cancel()
            self._post_heavy_observer = None

    def _start_post_heavy_observation(self, attempt, sample, next_sample, released_at):
        self._cancel_post_heavy_observation()
        task = self.task
        original_next_frame = task.next_frame
        had_override = 'next_frame' in vars(task)
        original_override = vars(task).get('next_frame')
        deadline = released_at + self.POST_HEAVY_OBSERVE_DURATION

        def cancel():
            if task.next_frame is next_frame:
                if had_override:
                    task.next_frame = original_override
                else:
                    del task.next_frame

        def next_frame(*args, **kwargs):
            nonlocal sample, next_sample
            try:
                frame = original_next_frame(*args, **kwargs)
            except BaseException:
                self._cancel_post_heavy_observation()
                raise
            now = time.monotonic()
            if now >= deadline or not task._in_combat:
                self._cancel_post_heavy_observation()
                return frame
            if now < next_sample:
                return frame
            sample += 1
            next_sample = now + self.HEAVY_SAMPLE_INTERVAL
            previous_energy = self._energy_state
            try:
                self._record_heavy_recognition('after_heavy', attempt, sample, released_at,
                                               frame=frame, refresh=False)
            except Exception as error:
                self._cancel_post_heavy_observation()
                self.logger.warning(f'[DoulingRecognition] point=after_heavy observer_stopped error={error}')
            finally:
                # 观察只写日志，不覆盖后续战斗正在使用的识别状态。
                self._energy_state = previous_energy
            return frame

        # 只在卜灵观察窗口内接收本次任务的新帧，到期或中断恢复原入口。
        self._post_heavy_observer = cancel
        task.next_frame = next_frame

    def on_combat_end(self, chars):
        self._cancel_post_heavy_observation()
        super().on_combat_end(chars)

    def _normal_attack_cycle(self, duration):
        start = time.time()
        while time.time() - start < duration:
            self.cycle_start()
            if self.flying():
                self.wait_down()
                break
            self.click()
            self.cycle_sleep()

    def _normal_attack_until_four_guaxiang(self):
        """限时普攻补足卦象，只有期限内确认四个才返回成功。"""
        start = time.monotonic()
        deadline = start + self.GUAXIANG_WAIT_TIMEOUT
        next_attack = start
        attempts = 0
        count = 'uncertain'
        self._waiting_for_guaxiang = True
        self._guaxiang_error_logged = False
        self._energy_error_logged = False
        self._energy_state = None
        try:
            while attempts < self.GUAXIANG_MAX_ATTEMPTS and time.monotonic() < deadline:
                poll_start = time.monotonic()
                attempts += 1
                self._energy_state = None
                frame = self.task.next_frame()
                self.check_combat()
                if time.monotonic() >= deadline:
                    break
                sequence = self.recognize_guaxiang('before_heavy') if frame is not None else None
                count = 'uncertain' if sequence is None else len(sequence)
                if time.monotonic() >= deadline:
                    break
                if sequence is not None and len(sequence) == 4:
                    elapsed = time.monotonic() - start
                    self.logger.info(
                        f'[DoulingGuaxiang] count=4 sequence={",".join(sequence)} '
                        f'energy={self._energy_state or "uncertain"} '
                        f'attempts={attempts} elapsed={elapsed:.3f}s action=continue_to_heavy')
                    return True
                if attempts >= self.GUAXIANG_MAX_ATTEMPTS:
                    break
                if time.monotonic() >= next_attack:
                    self.normal_attack()
                    # 从本次输入完成后计时，慢帧时也不补发积压普攻。
                    next_attack = time.monotonic() + self.NORMAL_ATTACK_INTERVAL
                remaining = min(poll_start + self.GUAXIANG_POLL_INTERVAL, deadline) - time.monotonic()
                if remaining > 0:
                    self.sleep(remaining)
            elapsed = time.monotonic() - start
            reason = 'timeout' if elapsed >= self.GUAXIANG_WAIT_TIMEOUT else 'max_attempts'
            self.logger.warning(
                f'[DoulingGuaxiang] action=abort reason={reason} elapsed={elapsed:.3f}s '
                f'attempts={attempts} count={count} energy={self._energy_state or "uncertain"}')
            return False
        finally:
            self._waiting_for_guaxiang = False

    def _heavy_attack_hold(self, duration):
        self._cancel_post_heavy_observation()
        retries = 3
        for attempt in range(1, retries + 1):
            self.check_combat()
            self.task.mouse_down()
            held = True
            start = time.monotonic()
            deadline = start + duration
            next_sample = start
            sample = 0
            try:
                while True:
                    now = time.monotonic()
                    if held and now >= deadline:
                        self.task.mouse_up()
                        held = False
                        released_at = time.monotonic()
                        self._start_post_heavy_observation(attempt, sample, next_sample, released_at)
                        return
                    self.check_combat()
                    if held and self.flying():
                        break
                    now = time.monotonic()
                    if now >= deadline:
                        continue
                    if now >= next_sample:
                        sample += 1
                        self._record_heavy_recognition('during_heavy', attempt, sample, start)
                        next_sample = now + self.HEAVY_SAMPLE_INTERVAL
                    remaining = min(deadline, next_sample, time.monotonic() + 0.1) - time.monotonic()
                    if remaining > 0:
                        self.sleep(remaining)
            finally:
                if held:
                    self.task.mouse_up()
            self.sleep(0.01)
            self.wait_down()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if self.time_elapsed_accounting_for_freeze(self.last_perform) < 8:
            return SwitchPriority.NO
        return SwitchPriority.NORMAL
