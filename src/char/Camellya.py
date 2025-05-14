import time
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP
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
        self.last_forte = 0

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
            if self.resonance_available():
                self.click_resonance()
        else:
            loop_time = 4.6
        budding_start_time = time.time()
        budding = False
        heavy_att = False
        freeze_forte_check = False
        freeze_forte_time = 0
        self.last_forte = 0
        while time.time() - budding_start_time < loop_time or self.task.find_one('camellya_budding', threshold=0.7):
            if not budding:
                if self.ephemeral_ready() and self.is_con_full():
                    self.ephemeral_cast()
                    budding = True
                else:
                    self.click(interval=0.1)
                    current_con = self.get_current_con()
                    if current_con < 0.82:
                        if not self.is_con_full():
                            self.click_echo()
                            return self.switch_next_char()
                        elif loop_time < 3.1:
                            loop_time += 1
                if budding:
                    self.logger.info(f'start budding')
                    self.check_target()
                    budding_start_time = time.time()
                    loop_time = 5.1
            if budding:
                if not heavy_att:
                    heavy_att = True
                    self.task.mouse_down()
                if time.time() - budding_start_time < 1.5 and self.liberation_available():
                    if self.click_liberation() and heavy_att:
                        self.logger.info(f'liberation retry heavy att')
                        self.task.mouse_up()
                        self.sleep(0.2, False)
                        self.task.mouse_down()
            self.check_target(heavy_att)
            self.task.next_frame()
            if freeze_forte_check and time.time() - freeze_forte_time >= 0.2:
                freeze_forte_check = False
            if not freeze_forte_check and heavy_att:
                if self.should_retry_heavy_attack(budding) < 0:
                    freeze_forte_check = True
                    freeze_forte_time = time.time()
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
        box = self.task.box_of_screen_scaled(3840, 2160, 3100, 1840, 3289, 2029, name='camellya_resonance', hcenter=True)
        red_percent = self.calculate_color_percentage_in_masked(camellya_red_color, box, 0.395, 0.496)
        self.logger.debug(f'red_percent {red_percent}')
        return red_percent > 0.1
    
    def calculate_color_percentage_in_masked(self, target_color, box, mask_r1_ratio=0.0, mask_r2_ratio=0.0):
        cropped = box.crop_frame(self.task.frame).copy()
        if cropped is None or cropped.size == 0:
            return 0.0
        h, w = cropped.shape[:2]

        center = (w // 2, h // 2)
        r1, r2 = h*mask_r1_ratio, h*mask_r2_ratio
        r1 = Decimal(str(r1)).quantize(Decimal('0'), rounding=ROUND_DOWN)
        r2 = Decimal(str(r2)).quantize(Decimal('0'), rounding=ROUND_UP)
        if r1 > 0:
            cv2.circle(cropped, center, int(r1), 0, -1)
        if r2 > 0:
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(mask, center, int(r2), 255, -1)
            cropped = cv2.bitwise_and(cropped, cropped, mask=mask)
            
        if cropped.ndim == 3:
            non_black_mask = np.all(cropped != 0, axis=2)
        else:
            return 0.0
            
        free_space = np.count_nonzero(non_black_mask)
        if free_space == 0:
            return 0.0

        lower_bound, upper_bound = color_range_to_bound(target_color)
        gray = cv2.inRange(cropped, lower_bound, upper_bound)
        colored_pixels = np.count_nonzero(gray == 255)

        color_percent = colored_pixels / free_space
        return color_percent

    def ephemeral_cast(self):
        self.check_combat()
        while self.ephemeral_ready():
            self.send_resonance_key()
            self.sleep(0.1)
        self.sleep(1.1)
    
    def get_forte(self, budding=False):
        box = self.task.box_of_screen_scaled(3840, 2160, 1630, 2002, 2176, 2004, name='camellya_forte', hcenter=True)
        forte_percent = 0
        if not budding:
            forte_percent = self.calculate_forte_percent(camellya_forte_color, box)
        else:
            forte_percent = self.calculate_forte_percent(camellya_budding_forte_color, box)
        forte_percent = Decimal(str(forte_percent)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        if forte_percent >= 0:
            self.logger.debug(f'forte_percent {forte_percent * 100:.2f}% budding {budding}')
        return forte_percent

    def detect_stripe_region(self, gray: np.ndarray, white_ratio_range=(0.05, 0.75), 
                            fft_thresh_ratio: float = 0.45, max_fail_count: int = 1) -> tuple:
        height, width = gray.shape[:2]
        if height == 0 or width < 64 or not np.any((gray == 0) | (gray == 255)):
            return -1, -1
        if not np.any((gray == 255)):
            return 0, 0
        
        def remove_short_stripes(gray: np.ndarray, threshold=3) -> np.ndarray:
            if threshold < 1:
                return gray
            
            result = gray.copy()
            height, width = gray.shape

            for y in range(height):
                row = gray[y]
                x = 0
                while x < width:
                    if row[x] == 255:
                        start = x
                        while x < width and row[x] == 255:
                            x += 1
                        length = x - start
                        if length < threshold:
                            result[y, start:x] = 0
                    else:
                        x += 1
            return result
        
        win_w = max(8, int(width * 0.045))
        step = max(1, int(width * 0.012))
        gray = remove_short_stripes(gray, int(width * 0.009))

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
            x += step

        if len(scores) == 0:
            return -1, -1
        
        scores = np.array(scores)
        max_score = np.max(scores)
        fft_thresh = max(1.5, max_score * fft_thresh_ratio)

        if max_score < 1e-3:
            return 0, 0
        
        keep = scores >= fft_thresh

        fail_count = 0
        end_idx = 0
        for i in range(len(keep)):
            if keep[i]:
                end_idx = i
                fail_count = 0
            else:
                a, b = positions[i]
                window = gray[:, a:b]
                white_ratio = np.count_nonzero(window == 255) / window.size
                if white_ratio < 0.375:
                    if np.any(scores[i+1:] > fft_thresh):
                        return -2, -2
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
        if start_x == -2:
            self.logger.debug(f'calculate_forte_percent failed due to interference')
            return -1
        if start_x != -1:
            stripe_area = gray[:, start_x:end_x]
            white_pixels = stripe_area.size
            total_pixels = gray.size
            ratio = white_pixels / total_pixels if total_pixels > 0 else 0
        else:
            self.logger.debug(f'using calculate_color_percentage')
            ratio = self.task.calculate_color_percentage(forte_color, box) * 2
            ratio = ratio if ratio <= 1 else 1
        return ratio

    def heavy_attack(self, duration, check_combat = True, until_con_full = False):
        self.logger.info(f'start heavy_attack')
        self.last_forte = 0
        freeze_forte_check = False
        freeze_forte_time = 0
        self.task.mouse_down()
        start = time.time()
        while time.time() - start < duration:
            if until_con_full and self.is_con_full() or 0 <= self.get_forte() <= 0.01:
                break
            if check_combat:
                self.check_target(True)
            self.task.next_frame()
            if freeze_forte_check and time.time() - freeze_forte_time >= 0.2:
                freeze_forte_check = False
            if not freeze_forte_check:
                if self.should_retry_heavy_attack() < 0:
                    freeze_forte_check = True
                    freeze_forte_time = time.time()
        self.sleep(0.1, False)
        self.task.mouse_up()
        self.waiting_for_forte_drop = False

    def should_retry_heavy_attack(self, budding = False):
        current_forte = self.get_forte(budding)
        if current_forte < 0:
            return -1
        diff = self.last_forte - current_forte
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
        self.last_forte = current_forte
        return 0
    
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
    'r': (239, 240),  # Red range
    'g': (76, 77),  # Green range
    'b': (173, 174)   # Blue range
} 

camellya_forte_color = {
    'r': (193, 255),  # Red range
    'g': (46, 93),  # Green range
    'b': (127, 163)   # Blue range
} 

camellya_budding_forte_color = {
    'r': (220, 255),  # Red range
    'g': (161, 213),  # Green range
    'b': (168, 225)   # Blue range
}
