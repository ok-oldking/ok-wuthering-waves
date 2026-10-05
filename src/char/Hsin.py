import time

import cv2
import numpy as np

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
        self.perform_everything()
        self.switch_next_char()

    def perform_everything(self):
        start = time.time()
        duration = 12 if self.has_intro else 6
        while True:
            phase_start = self.finisher_start if self.finisher_start is not None else start
            phase_duration = 18 if self.finisher_start is not None else duration
            if self.time_elapsed_accounting_for_freeze(phase_start) >= phase_duration:
                self.logger.debug(f'Hsin rotation timeout: finisher={self.finisher_start is not None}, '
                                  f'enhanced_e={self.finisher_e_sent}, h2={self.h2_completed}')
                return
            self.cycle_start()
            # H2 completion survives a temporarily unavailable R2; do not resume E/Q.
            if self.h2_completed:
                if self.lib(after_heavy=True):
                    return
                self.cycle_sleep()
                continue
            if self.task.find_one(Labels.hsin_lib2, threshold=0.7):
                self.lib()
                if self.lib2_cast_this_turn:
                    return
            heavy_type = self.heavy_available()
            if heavy_type == 2:
                if self.handle_heavy(heavy_type) and self.wait_for_lib2(after_heavy=True):
                    return
                self.cycle_sleep()
                continue
            # After R1, charge with normals; never send ordinary E during unlocking.
            if self.finisher_start is not None:
                if not self.finisher_e_sent and self.enhanced_e_ready():
                    self.cast_enhanced_e()
                else:
                    self.click()
                self.cycle_sleep()
                continue
            if self.resonance_available():
                resonance = self.click_resonance(has_animation=False, send_click=True, time_out=0)
            else:
                resonance = (False, 0, False)
            if resonance[0]:
                pass
            elif self.lib():
                if self.lib2_cast_this_turn:
                    return
            elif heavy_type:
                self.handle_heavy(heavy_type)
            elif self.finisher_start is not None:
                self.click()
            elif not self.click_echo(time_out=0):
                self.click()
            self.cycle_sleep()

    def enhanced_e_ready(self) -> bool:
        # Look for the thin gold perimeter, excluding the icon, CD digits and broad effects.
        box = self.task.get_box_by_name('box_resonance')
        margin = round(box.width * 0.24)
        side = box.width + 2 * margin
        crop = box.copy(x_offset=-margin, y_offset=round((box.height - side) / 2),
                        width_offset=2 * margin, height_offset=side - box.height).crop_frame(self.task.frame)
        if crop.size == 0:
            return False
        crop = cv2.resize(crop, (100, 100))
        gold = cv2.inRange(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV), (15, 25, 170), (40, 255, 255)) > 0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        thin = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, np.ones((7, 7), np.uint8)) > 25
        y, x = np.ogrid[:100, :100]
        radius = (x - 50) ** 2 + (y - 50) ** 2
        ring = (radius > 36 ** 2) & (radius < 46 ** 2)
        sectors = ((np.arctan2(y - 50, x - 50) + np.pi) * 8 / (2 * np.pi)).astype(int) % 8
        return sum(bool(np.mean((gold & thin)[ring & (sectors == i)]) > 0.07) for i in range(8)) >= 6

    def cast_enhanced_e(self) -> bool:
        start = time.time()
        last_send = -1.0
        gone_since = None
        while time.time() - start < 1.5:
            self.check_combat()
            now = time.time()
            if self.enhanced_e_ready():
                gone_since = None
                if now - last_send >= 0.25:
                    self.send_resonance_key()
                    last_send = now
            elif last_send >= 0:
                if gone_since is None:
                    gone_since = now
                elif now - gone_since >= 0.25:
                    self.finisher_e_sent = True
                    self.record_resonance_use()
                    self.logger.debug('Hsin enhanced E consumed; continue normal attacks')
                    return True
            self.task.next_frame()
        self.logger.debug('Hsin enhanced E not confirmed; retry when ready')
        return False

    def lib(self, after_heavy: bool = False) -> bool:
        # A confirmed H2 allows the generic R icon; the helper still must confirm animation.
        is_lib2 = after_heavy or bool(self.task.find_one(Labels.hsin_lib2, threshold=0.7))
        has_feature = is_lib2 or bool(self.task.find_one(Labels.hsin_lib1, threshold=0.7))
        if not has_feature or not self.liberation_available():
            return False
        liberated = bool(self.click_liberation(wait_if_cd_ready=0))
        self.logger.debug(f'Hsin liberation: lib2={is_lib2}, cast={liberated}')
        if liberated:
            if is_lib2:
                self.lib2_cast_this_turn = True
            elif self.finisher_start is None:
                # Start the finishing budget after R1 animation, accounting for subsequent freezes.
                self.finisher_start = time.time()
        return liberated

    def heavy_available(self) -> int:
        if self.task.find_one(Labels.hsin_h2, threshold=0.7):
            return 2
        if self.task.find_one(Labels.hsin_h1, threshold=0.7):
            return 1
        return 0

    def heavy_wait_highlight_down(self, time_out: float) -> bool:
        self.check_combat()
        self.task.mouse_down()
        try:
            confirmed = bool(self.task.wait_until(
                lambda: not self.heavy_available(), time_out=time_out,
                settle_time=0.25, pre_action=self.check_combat))
        finally:
            self.task.mouse_up()
        self.sleep(0.01)
        return confirmed

    def handle_heavy(self, heavy_type: int = 0) -> bool:
        heavy_type = heavy_type or self.heavy_available()
        if not heavy_type:
            return False
        # An already-started hold gets its full window, even near the rotation deadline.
        confirmed = self.heavy_wait_highlight_down(1.2)
        self.logger.debug(f'Hsin heavy: type={heavy_type}, confirmed={confirmed}')
        if confirmed and heavy_type == 2:
            self.h2_completed = True
        return confirmed

    def wait_for_lib2(self, after_heavy: bool = False) -> bool:
        return bool(self.task.wait_until(
            lambda: (after_heavy or bool(self.task.find_one(Labels.hsin_lib2, threshold=0.7)))
                    and self.lib(after_heavy=after_heavy) and self.lib2_cast_this_turn,
            time_out=1.5, pre_action=self.check_combat))
