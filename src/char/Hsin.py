import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar


class Hsin(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib2_cast_this_turn = False

    def do_perform(self):
        self.lib2_cast_this_turn = False
        self.logger.debug(f'Hsin perform start: has_intro={self.has_intro}')
        self.perform_everything()
        self.logger.debug(f'Hsin switch_next_char start: lib2_cast={self.lib2_cast_this_turn}')
        self.switch_next_char()
        self.logger.debug('Hsin switch_next_char end')

    def perform_everything(self):
        duration = 12 if self.has_intro else 6
        start = time.time()
        self.logger.debug(f'Hsin rotation start: duration={duration}')
        while self.time_elapsed_accounting_for_freeze(start) < duration:
            self.cycle_start()
            self.logger.debug(
                f'Hsin cycle: elapsed={self.time_elapsed_accounting_for_freeze(start):.2f}, '
                f'wall_elapsed={time.time() - start:.2f}')
            self.logger.debug('Hsin resonance start')
            resonance_start = time.time()
            if self.resonance_available():
                resonance = self.click_resonance(has_animation=False, send_click=True, animation_min_duration=0.5,
                                                time_out=0)
            else:
                resonance = (False, 0, False)
                self.logger.debug('Hsin resonance skipped: unavailable')
            self.logger.debug(f'Hsin resonance check/cast duration={time.time() - resonance_start:.3f}s')
            self.logger.debug(f'Hsin resonance end: result={resonance}')
            if resonance[0]:
                pass
            elif self.lib():
                if self.lib2_cast_this_turn:
                    self.logger.debug('Hsin rotation end: lib2 cast')
                    return
            elif self.handle_heavy(start, duration):
                pass
            else:
                self.logger.debug('Hsin echo start')
                echoed = self.click_echo(time_out=0)
                self.logger.debug(f'Hsin echo end: cast={echoed}')
                if not echoed:
                    self.logger.debug('Hsin normal attack start')
                    self.click()
                    self.logger.debug('Hsin normal attack end')
            self.logger.debug('Hsin cycle_sleep start')
            self.cycle_sleep()
            self.logger.debug('Hsin cycle_sleep end')
        self.logger.debug('Hsin rotation end: duration reached')

    def lib(self):
        self.logger.debug('Hsin liberation start')
        is_lib2 = bool(self.task.find_one(Labels.hsin_lib2, threshold=0.7))
        has_feature = is_lib2 or bool(self.task.find_one(Labels.hsin_lib1, threshold=0.7))
        available = self.liberation_available()
        self.logger.debug(f'Hsin liberation indicator: feature={has_feature}, lib2={is_lib2}, available={available}')
        if not has_feature or not available:
            self.logger.debug('Hsin liberation end: feature missing or unavailable')
            return False
        liberated = self.click_liberation(wait_if_cd_ready=0)
        if liberated and is_lib2:
            self.lib2_cast_this_turn = True
        self.logger.debug(f'Hsin liberation end: cast={liberated}, lib2={is_lib2}')
        return liberated

    def heavy_available(self):
        return bool(self.task.find_one(Labels.hsin_h1, threshold=0.7)
                    or self.task.find_one(Labels.hsin_h2, threshold=0.7))

    def heavy_wait_highlight_down(self, time_out):
        self.logger.debug(f'Hsin heavy hold start: timeout={time_out:.2f}')
        self.check_combat()
        self.task.mouse_down()
        try:
            ret = self.task.wait_until(lambda: not self.heavy_available(), time_out=time_out)
        finally:
            self.task.mouse_up()
            self.logger.debug('Hsin heavy hold: mouse released')
        self.sleep(0.01)
        self.logger.debug(f'Hsin heavy hold end: indicator_disappeared={ret}')
        return ret

    def handle_heavy(self, start, duration):
        self.logger.debug('Hsin heavy check start')
        if not self.heavy_available():
            self.logger.debug('Hsin heavy end: unavailable')
            return False
        remaining = duration - self.time_elapsed_accounting_for_freeze(start)
        if remaining <= 0:
            self.logger.debug('Hsin heavy end: duration reached')
            return False
        self.heavy_wait_highlight_down(min(1.2, remaining))
        self.logger.debug(f'Hsin heavy end: remaining_before_hold={remaining:.2f}')
        return True
