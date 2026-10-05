import time

from src.Labels import Labels
from src.char.BaseChar import BaseChar


class Hsin(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib2_cast_this_turn: bool = False
        self.finisher_start: float | None = None
        self.finisher_e_sent: bool = False
        self.h2_completed: bool = False

    def do_perform(self):
        self.lib2_cast_this_turn = False
        self.finisher_start = None
        self.finisher_e_sent = False
        self.h2_completed = False
        self.logger.debug(f'Hsin perform start: has_intro={self.has_intro}')
        self.perform_everything()
        self.logger.debug(f'Hsin switch_next_char start: lib2_cast={self.lib2_cast_this_turn}')
        self.switch_next_char()
        self.logger.debug('Hsin switch_next_char end')

    def perform_everything(self):
        start = time.time()
        duration = 12 if self.has_intro else 6
        last_e_ready = None
        self.logger.debug(f'Hsin rotation start: duration={duration}')
        while True:
            phase_start = self.finisher_start if self.finisher_start is not None else start
            phase_duration = 18 if self.finisher_start is not None else duration
            if self.time_elapsed_accounting_for_freeze(phase_start) >= phase_duration:
                self.logger.debug(f'Hsin rotation timeout: finisher={self.finisher_start is not None}, '
                                  f'enhanced_e={self.finisher_e_sent}, h2={self.h2_completed}')
                if not self.h2_completed:
                    self.logger.debug('Hsin heavy end: duration reached')
                self.logger.debug('Hsin rotation end: duration reached')
                self.logger.info(f'Hsin rotation end: timeout, finisher={self.finisher_start is not None}, '
                                 f'enhanced_e={self.finisher_e_sent}, h2={self.h2_completed}')
                return
            self.cycle_start()
            self.logger.debug(
                f'Hsin cycle: elapsed={self.time_elapsed_accounting_for_freeze(phase_start):.2f}, '
                f'wall_elapsed={time.time() - start:.2f}, finisher={self.finisher_start is not None}, '
                f'duration={phase_duration}')
            # H2 completion survives a temporarily unavailable R2; do not resume E/Q.
            if self.h2_completed:
                if self.lib(after_heavy=True):
                    self.logger.debug('Hsin rotation end: lib2 cast')
                    return
                self.logger.debug('Hsin cycle_sleep start')
                self.cycle_sleep()
                self.logger.debug('Hsin cycle_sleep end')
                continue
            if self.task.find_one(Labels.hsin_lib2, threshold=0.7):
                self.lib()
                if self.lib2_cast_this_turn:
                    self.logger.debug('Hsin rotation end: lib2 cast')
                    return
            heavy_type = self.heavy_available()
            if heavy_type == 2:
                remaining = phase_duration - self.time_elapsed_accounting_for_freeze(phase_start)
                confirmed = self.handle_heavy(heavy_type)
                self.logger.debug(f'Hsin heavy end: remaining_before_hold={remaining:.2f}')
                if confirmed and self.wait_for_lib2(after_heavy=True):
                    self.logger.debug('Hsin rotation end: lib2 cast')
                    return
                self.logger.debug('Hsin cycle_sleep start')
                self.cycle_sleep()
                self.logger.debug('Hsin cycle_sleep end')
                continue
            # The live prompt controls E; a transient disappearance must not lock out retries.
            if self.finisher_start is not None:
                ready = self.enhanced_e_ready()
                if ready != last_e_ready:
                    self.logger.info(f'Hsin enhanced E prompt: ready={ready}, '
                                     f'previously_confirmed={self.finisher_e_sent}')
                    last_e_ready = ready
                if ready:
                    if self.finisher_e_sent:
                        self.logger.info('Hsin enhanced E prompt returned; retry E')
                    self.finisher_e_sent = False
                    self.cast_enhanced_e()
                else:
                    self.logger.debug(f'Hsin enhanced E skipped: consumed={self.finisher_e_sent}')
                    self.logger.debug('Hsin normal attack start')
                    self.click()
                    self.logger.debug('Hsin normal attack end')
                self.logger.debug('Hsin cycle_sleep start')
                self.cycle_sleep()
                self.logger.debug('Hsin cycle_sleep end')
                continue
            self.logger.debug('Hsin resonance start')
            resonance_start = time.time()
            if self.resonance_available():
                resonance = self.click_resonance(has_animation=False, send_click=True, time_out=0)
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
            elif heavy_type:
                remaining = phase_duration - self.time_elapsed_accounting_for_freeze(phase_start)
                self.handle_heavy(heavy_type)
                self.logger.debug(f'Hsin heavy end: remaining_before_hold={remaining:.2f}')
            elif self.finisher_start is not None:
                self.logger.debug('Hsin normal attack start')
                self.click()
                self.logger.debug('Hsin normal attack end')
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

    def enhanced_e_ready(self) -> bool:
        return bool(self.is_e_forte_full())

    def cast_enhanced_e(self) -> bool:
        self.logger.debug('Hsin enhanced E start')
        self.logger.info('Hsin enhanced E start: generic prompt ready')
        start = time.time()
        last_send = -1.0
        sends = 0
        gone_since = None
        while time.time() - start < 1.5:
            self.check_combat()
            now = time.time()
            if self.enhanced_e_ready():
                gone_since = None
                if now - last_send >= 0.25:
                    self.send_resonance_key()
                    last_send = now
                    sends += 1
                    self.logger.info(f'Hsin enhanced E key: send={sends}, elapsed={now - start:.3f}s')
            elif last_send >= 0:
                if gone_since is None:
                    gone_since = now
                elif now - gone_since >= 0.25:
                    self.finisher_e_sent = True
                    self.record_resonance_use()
                    self.logger.debug('Hsin enhanced E consumed; continue normal attacks')
                    self.logger.info(f'Hsin enhanced E result: confirmed=True, sends={sends}, '
                                     f'elapsed={time.time() - start:.3f}s')
                    return True
            self.task.next_frame()
        self.logger.debug('Hsin enhanced E not confirmed; retry when ready')
        self.logger.info(f'Hsin enhanced E result: confirmed=False, sends={sends}, '
                         f'elapsed={time.time() - start:.3f}s')
        return False

    def lib(self, after_heavy: bool = False) -> bool:
        self.logger.debug('Hsin liberation start')
        # A confirmed H2 allows the generic R icon; the helper still must confirm animation.
        is_lib2 = after_heavy or bool(self.task.find_one(Labels.hsin_lib2, threshold=0.7))
        has_feature = is_lib2 or bool(self.task.find_one(Labels.hsin_lib1, threshold=0.7))
        available = self.liberation_available() if has_feature else None
        self.logger.debug(f'Hsin liberation indicator: feature={has_feature}, lib2={is_lib2}, available={available}')
        if not has_feature or not available:
            self.logger.debug('Hsin liberation end: feature missing or unavailable')
            return False
        liberated = bool(self.click_liberation(wait_if_cd_ready=0))
        self.logger.debug(f'Hsin liberation: lib2={is_lib2}, cast={liberated}')
        if liberated:
            if is_lib2:
                self.lib2_cast_this_turn = True
            elif self.finisher_start is None:
                # Start the finishing budget after R1 animation, accounting for subsequent freezes.
                self.finisher_start = time.time()
                self.logger.debug('Hsin finisher start: duration=18')
                self.logger.info('Hsin finisher start: R1 confirmed, duration=18')
        self.logger.debug(f'Hsin liberation end: cast={liberated}, lib2={is_lib2}')
        return liberated

    def heavy_available(self) -> int:
        if self.task.find_one(Labels.hsin_h2, threshold=0.7):
            return 2
        if self.task.find_one(Labels.hsin_h1, threshold=0.7):
            return 1
        return 0

    def heavy_wait_highlight_down(self, time_out: float) -> bool:
        self.logger.debug(f'Hsin heavy hold start: timeout={time_out:.2f}')
        self.check_combat()
        self.task.mouse_down()
        try:
            confirmed = bool(self.task.wait_until(
                lambda: not self.heavy_available(), time_out=time_out,
                settle_time=0.25, pre_action=self.check_combat))
        finally:
            self.task.mouse_up()
            self.logger.debug('Hsin heavy hold: mouse released')
        self.sleep(0.01)
        self.logger.debug(f'Hsin heavy hold end: indicator_disappeared={confirmed}')
        return confirmed

    def handle_heavy(self, heavy_type: int = 0) -> bool:
        self.logger.debug('Hsin heavy check start')
        heavy_type = heavy_type or self.heavy_available()
        if not heavy_type:
            self.logger.debug('Hsin heavy end: unavailable')
            return False
        # An already-started hold gets its full window, even near the rotation deadline.
        confirmed = self.heavy_wait_highlight_down(1.2)
        self.logger.debug(f'Hsin heavy: type={heavy_type}, confirmed={confirmed}')
        if confirmed and heavy_type == 2:
            self.h2_completed = True
        return confirmed

    def wait_for_lib2(self, after_heavy: bool = False) -> bool:
        self.logger.debug(f'Hsin lib2 wait start: after_heavy={after_heavy}')
        confirmed = bool(self.task.wait_until(
            lambda: (after_heavy or bool(self.task.find_one(Labels.hsin_lib2, threshold=0.7)))
                    and self.lib(after_heavy=after_heavy) and self.lib2_cast_this_turn,
            time_out=1.5, pre_action=self.check_combat))
        self.logger.debug(f'Hsin lib2 wait end: cast={confirmed}, pending={self.h2_completed and not confirmed}')
        return confirmed
