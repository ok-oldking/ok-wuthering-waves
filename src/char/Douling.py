import time

from src.char.BaseChar import BaseChar, SwitchPriority
from src.utils.guaxiang import recognize_guaxiang as detect_guaxiang


class Douling(BaseChar):
    NORMAL_ATTACK_INTERVAL = 0.3
    GUAXIANG_POLL_INTERVAL = 0.1
    GUAXIANG_WAIT_TIMEOUT = 3.0
    GUAXIANG_MAX_ATTEMPTS = 30

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._segment = 1
        self._waiting_for_guaxiang = False
        self._guaxiang_error_logged = False

    def do_perform(self):
        self.recognize_guaxiang('entry')
        if self._segment == 1:
            self._do_segment1()
        else:
            self._do_segment2()

    def recognize_guaxiang(self, sample_point='manual'):
        """识别当前帧的卦象，仅在上场时记录结果。"""
        try:
            hud_visible = self.task.in_team()[0]
            captured_frame = self.task.frame
            frame = captured_frame.copy() if captured_frame is not None else None
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
        self.click_echo(time_out=0)
        self.click_liberation()
        self._segment = 1
        self.switch_next_char()

    def _finish_and_reset(self):
        self.click_echo(time_out=0)
        self.click_liberation()
        self._segment = 1
        self.switch_next_char()

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
        try:
            while attempts < self.GUAXIANG_MAX_ATTEMPTS and time.monotonic() < deadline:
                poll_start = time.monotonic()
                attempts += 1
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
                f'attempts={attempts} count={count}')
            return False
        finally:
            self._waiting_for_guaxiang = False

    def _heavy_attack_hold(self, duration):
        retries = 3
        for _ in range(retries):
            self.check_combat()
            self.task.mouse_down()
            start = time.time()
            interrupted = False
            while time.time() - start < duration:
                if self.flying():
                    interrupted = True
                    break
                self.sleep(0.1)
            self.task.mouse_up()
            self.sleep(0.01)
            if not interrupted:
                return
            self.wait_down()

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if self.time_elapsed_accounting_for_freeze(self.last_perform) < 8:
            return SwitchPriority.NO
        return SwitchPriority.NORMAL
