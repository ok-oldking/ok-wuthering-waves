import time

from ok import Box

from src.char.BaseChar import BaseChar, SwitchPriority
from src.utils.guaxiang import recognize_guaxiang as detect_guaxiang


class Douling(BaseChar):
    NORMAL_ATTACK_INTERVAL = 0.3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._segment = 1
        self._waiting_for_guaxiang = False

    def do_perform(self):
        self.recognize_guaxiang('entry')
        if self._segment == 1:
            self._do_segment1()
        else:
            self._do_segment2()

    def recognize_guaxiang(self, sample_point='manual'):
        """识别当前帧的卦象并记录结果；不改变战斗轴。"""
        start = time.perf_counter()
        try:
            hud_visible = self.task.in_team()[0]
            captured_frame = self.task.frame
            frame = captured_frame.copy() if captured_frame is not None else None
            result = detect_guaxiang(frame, hud_visible=hud_visible)
            elapsed_ms = (time.perf_counter() - start) * 1000
            screenshot_name = 'unavailable'
            if frame is not None:
                screenshot_name = f'guaxiang/{sample_point}_{time.time_ns()}'
                try:
                    self.task.screenshot(screenshot_name, frame=frame, show_box=False)
                except Exception as error:
                    self.logger.warning(f'[DoulingScreenshot] name={screenshot_name} error={error}')
                    screenshot_name = 'failed'
            context = f'point={sample_point} screenshot_name={screenshot_name}'
            if result.sequence is None:
                self.logger.info(
                    f'[DoulingRecognition] status=uncertain reason={result.reason} '
                    f'elapsed_ms={elapsed_ms:.2f} {context}')
            else:
                sequence = ','.join(result.sequence) or '[]'
                self.logger.info(
                    f'[DoulingRecognition] count={len(result.sequence)} sequence={sequence} '
                    f'elapsed_ms={elapsed_ms:.2f} {context}')
            if getattr(self.task, 'debug', False):
                regions = [Box(*result.region, name='douling_guaxiang_region')] if result.region else []
                self.task.draw_boxes('douling_guaxiang_region', regions)
                boxes = [Box(*item.box, confidence=item.score,
                             name=f'{item.color} match={item.score:.2f} color={item.color_score:.2f}')
                         for item in result.detections]
                self.task.draw_boxes('douling_guaxiang_matches', boxes)
            return result.sequence
        except Exception as error:
            self.logger.warning(f'[DoulingRecognition] status=uncertain error={error}')
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
        self._normal_attack_until_four_guaxiang()
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

    def _tap_normal(self):
        self.normal_attack()
        self.sleep(self.NORMAL_ATTACK_INTERVAL)

    def _normal_attack_until_four_guaxiang(self):
        """持续普攻补足卦象，只有确认四个后才允许重击。"""
        self._waiting_for_guaxiang = True
        try:
            while True:
                frame = self.task.next_frame()
                self.check_combat()
                sequence = self.recognize_guaxiang('before_heavy') if frame is not None else None
                if sequence is not None and len(sequence) == 4:
                    self.logger.info('[DoulingGuaxiang] count=4 action=continue_to_heavy')
                    return
                count = 'uncertain' if sequence is None else len(sequence)
                self.logger.info(f'[DoulingGuaxiang] count={count} action=normal_attack')
                self._tap_normal()
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
