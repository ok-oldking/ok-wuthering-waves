import time
from decimal import Decimal, ROUND_HALF_UP
from ok import color_range_to_bound
from src.char.BaseChar import BaseChar, Priority
import cv2
import numpy as np

class Camellya(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_heavy = 0
        self.waiting_for_forte_drop = False
        self.forte_drop_timestamp = 0
        self.forte_diff_buffer = []

    def reset_state(self):
        super().reset_state()
        self.waiting_for_forte_drop = False

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if has_intro:
            return Priority.MAX - 1
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def wait_resonance_not_gray(self, timeout=5):
        start = time.time()
        while self.current_resonance() == 0:
            self.click()
            self.sleep(0.1)
            if time.time() - start > timeout:
                self.logger.error('wait wait_resonance_not_gray timed out')

    def on_combat_end(self, chars):
        next_char = str((self.index + 1) % len(chars) + 1)
        self.logger.debug(f'Camellya on_combat_end {self.index} switch next char: {next_char}')
        start = time.time()
        while time.time() - start < 6:
            self.task.load_chars()
            current_char = self.task.get_current_char(raise_exception=False)
            if current_char and current_char.name != "Camellya":
                break
            else:
                self.task.send_key(next_char)
            self.sleep(0.2, False)
        self.logger.debug(f'Camellya on_combat_end {self.index} switch end')

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.2)
            self.sleep(0.1)
            self.heavy_attack(4.6, until_con_full=True)
        if self.liberation_available():
            self.click_liberation(con_less_than=0.82)
        start_con = self.get_current_con()
        if start_con < 0.82:
            loop_time = 1.1
        else:
            loop_time = 4.1
        budding_start_time = time.time()
        budding = False
        heavy_att = False
        while time.time() - budding_start_time < loop_time or self.task.find_one('camellya_budding', threshold=0.7):
            if not budding:
                if self.ephemeral_ready():
                    self.ephemeral_cast()
                    budding = True
                else:
                    self.click(interval=0.1)
                    current_con = self.get_current_con()
                    if current_con < 0.82:
                        self.click_resonance()
                        self.sleep(0.1)
                        if not self.is_con_full():
                            self.click_echo()
                            return self.switch_next_char()
                        elif loop_time < 2.1:
                            loop_time += 1
                if budding:
                    self.logger.info(f'start budding')
                    self.check_target()
                    budding_start_time = time.time()
                    loop_time = 5.1
            if budding:
                current_forte = self.get_forte(True)
                if not heavy_att:
                    heavy_att = True
                    self.task.mouse_down()
                if time.time() - budding_start_time < 1.5 and self.liberation_available():
                    if self.click_liberation() and heavy_att:
                        self.logger.info(f'liberation retry heavy att')
                        self.sleep(0.2, False)
                        self.task.mouse_down()
            self.check_target(heavy_att)
            self.task.next_frame()
            if heavy_att:
                self.should_retry_heavy_attack(current_forte, True)
        self.waiting_for_forte_drop = False
        if heavy_att:
            self.task.mouse_up()
            self.sleep(0.1)
        if budding:
            self.click_resonance()
            self.sleep(0.1)
        self.click_echo()
        self.switch_next_char()

    def click_echo(self, *args):
        if self.echo_available():
            self.send_echo_key()
            return True
        
    def ephemeral_ready(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 3149, 1832, 3225, 1857, name='camellya_resonance', hcenter=True)
        red_percent = self.task.calculate_color_percentage(camellya_red_color, box)
        self.logger.debug(f'red_percent {red_percent}')
        return red_percent > 0.11

    def ephemeral_cast(self):
        self.check_combat()
        while self.ephemeral_ready():
            self.send_resonance_key()
            self.sleep(0.1)
        self.sleep(1.1)
    
    def get_forte(self, budding=False):
        box = self.task.box_of_screen_scaled(2560, 1440, 1087, 1335, 1451, 1336, name='camellya_forte', hcenter=True)
        forte_percent = 0
        if not budding:
            forte_percent = self.calculate_forte_percent(camellya_forte_color, box)
            self.logger.debug(f'forte_percent {forte_percent}')
        else:
            forte_percent = self.calculate_forte_percent(camellya_budding_forte_color, box)
            self.logger.debug(f'forte_percent_budding {forte_percent}')
        forte_percent = Decimal(str(forte_percent)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        return forte_percent
    
    def detect_stripe_region(self, gray: np.ndarray, white_ratio_range=(0.05, 0.75), 
                            fft_thresh_ratio: float = 0.3, max_fail_count: int = 3) -> tuple:
        height, width = gray.shape[:2]
        if height == 0 or width < 64 or not np.array_equal(np.unique(gray), [0, 255]):
            return -1, -1
        
        win_w = max(8, int(width * 0.045))
        step = max(1, int(width * 0.012))

        scores = []
        positions = []
        start_x = None
        end_x = None
        fail_count = 0
        x = 0
        while x + win_w <= width:
            window = gray[:, x:x+win_w]
            white_ratio = np.count_nonzero(window == 255) / window.size
            if not (white_ratio_range[0] <= white_ratio <= white_ratio_range[1]):
                score = 0
            else:
                profile = np.sum(window == 255, axis=0).astype(np.float32)
                profile -= np.mean(profile)
                spectrum = np.abs(np.fft.fft(profile))[:win_w//2]
                score = np.max(spectrum[1:])
            scores.append(score)
            positions.append((x, x + win_w))
            if score != 0:
                fail_count = 0
            else:
                fail_count += 1
                if fail_count >= max_fail_count:
                    break
            x += step

        if len(scores) == 0:
            return -1, -1
        
        scores = np.array(scores)
        max_score = np.max(scores)
        if max_score < 1e-3:
            return 0, 0
        
        fft_thresh = max_score * fft_thresh_ratio
        keep = scores >= fft_thresh

        fail_count = 0
        end_idx = 0
        for i in range(len(keep)):
            if keep[i]:
                end_idx = i
                fail_count = 0
            else:
                fail_count += 1
                if fail_count >= max_fail_count:
                    break

        start_x = 0
        if end_idx == 0:
            end_x = 0
        else:
            if positions[end_idx][1] + step >= width:
                end_x = width
            else:
                end_x = positions[end_idx][0]
        return start_x, end_x

    def calculate_forte_percent(self, forte_color, box):
        cropped = box.crop_frame(self.task.frame)
        lower_bound, upper_bound = color_range_to_bound(forte_color)
        gray = cv2.inRange(cropped, lower_bound, upper_bound)
        
        start_x, end_x = self.detect_stripe_region(gray)
        if start_x != -1:
            stripe_area = gray[:, start_x:end_x]

            white_pixels = stripe_area.size
            total_pixels = gray.size
            ratio = white_pixels / total_pixels if total_pixels > 0 else 0
        else:
            ratio = self.task.calculate_color_percentage(forte_color, box)
        self.logger.debug(f'forte_percent {ratio * 100:.2f}%')
        return ratio

    def heavy_attack(self, duration, check_combat = True, until_con_full = False):
        self.logger.info(f'start heavy_attack')
        self.task.mouse_down()
        start = time.time()
        while time.time() - start < duration:
            current_forte = self.get_forte()
            if until_con_full and self.is_con_full() or current_forte <= 0.01:
                break
            if check_combat:
                self.check_target(True)
            self.task.next_frame()
            self.should_retry_heavy_attack(current_forte)
        self.sleep(0.1, False)
        self.task.mouse_up()
        self.waiting_for_forte_drop = False

    def should_retry_heavy_attack(self, current_forte, budding = False):
        diff = current_forte - self.get_forte(budding)
        self.logger.debug(f'diff {diff}')
        if not self.waiting_for_forte_drop and 0 <= diff <= 0.01:
            self.waiting_for_forte_drop = True
            self.forte_drop_timestamp = time.time()
            self.forte_diff_buffer = []
        if self.waiting_for_forte_drop:
            self.forte_diff_buffer.append(diff)
            if np.array(self.forte_diff_buffer).sum() > 0.01:
                self.waiting_for_forte_drop = False
                self.logger.debug(f'diff {diff}')
        if self.waiting_for_forte_drop and self.time_elapsed_accounting_for_freeze(self.forte_drop_timestamp) > 0.6:
            self.waiting_for_forte_drop = False
            self.logger.info(f'retry heavy attack')
            self.task.mouse_up()
            self.sleep(0.1, False)
            self.task.mouse_down()
            self.sleep(0.1, False)
    
    def check_target(self, is_heavy_att = False):
        if not self.task.has_target():
            if is_heavy_att:
                self.logger.info(f'check_target Release')
                self.task.mouse_up()
            self.logger.info(f'check_combat')
            self.check_combat()
            self.task.next_frame()
            if is_heavy_att:
                self.logger.info(f'check_target Retry')
                self.task.mouse_down()

camellya_red_color = {
    'r': (200, 250),  # Red range
    'g': (60, 90),  # Green range
    'b': (150, 190)   # Blue range
} 

camellya_forte_color = {
    'r': (199, 255),  # Red range
    'g': (47, 93),  # Green range
    'b': (127, 149)   # Blue range
} 

camellya_budding_forte_color = {
    'r': (238, 255),  # Red range
    'g': (173, 216),  # Green range
    'b': (180, 230)   # Blue range
} 
