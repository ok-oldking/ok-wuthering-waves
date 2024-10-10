import time

import cv2
import numpy as np

import re
from ok.color.Color import get_connected_area_by_color, color_range_to_bound
from ok.config.ConfigOption import ConfigOption
from ok.feature.FindFeature import FindFeature
from ok.logging.Logger import get_logger
from ok.ocr.OCR import OCR
from ok.util.list import safe_get
from src import text_white_color
from src.char import BaseChar
from src.char.BaseChar import Priority, dot_color
from src.char.CharFactory import get_char_by_pos
from src.combat.CombatCheck import CombatCheck
from src.task.BaseWWTask import BaseWWTask

logger = get_logger(__name__)


class NotInCombatException(Exception):
    pass


class CharDeadException(NotInCombatException):
    pass


key_config_option = ConfigOption('Game Hotkey Config', {
    'HotKey Verify': True,
    'Echo Key': 'q',
    'Liberation Key': 'r',
    'Resonance Key': 'e',
}, description='In Game Hotkey for Skills')


class BaseCombatTask(BaseWWTask, FindFeature, OCR, CombatCheck):

    def __init__(self):
        super().__init__()
        CombatCheck.__init__(self)
        self.chars = [None, None, None]
        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']
        self.key_config = self.get_global_config(key_config_option)

        self.mouse_pos = None
        self.combat_start = 0

        self.char_texts = ['char_1_text', 'char_2_text', 'char_3_text']

    def send_key_and_wait_animation(self, key, check_function, total_wait=10, animation_wait=5):
        start = time.time()
        animation_start = 0
        while time.time() - start < total_wait and (
                animation_start == 0 or time.time() - animation_start < animation_wait):
            if check_function():
                if animation_start > 0:
                    self.in_liberation = False
                    return
                else:
                    self.send_key(key, interval=0.2)
            else:
                if animation_start == 0:
                    animation_start = time.time()
                self.in_liberation = True
                self.next_frame()
        logger.info(f'send_key_and_wait_animation timed out {key}')

    def teleport_to_heal(self):
        self.info['Death Count'] = self.info.get('Death Count', 0) + 1
        self.send_key('esc')
        self.sleep(1)
        self.log_info('click m to open the map')
        self.send_key('m')
        self.sleep(2)
        for i in range(4):
            self.click_relative(0.94, 0.29, after_sleep=0.5)
            logger.info(f'click zoom')
        self.click_relative(0.91, 0.77, after_sleep=1)
        self.click_relative(0.63, 0.17, after_sleep=1, name="first_map")
        self.log_info('click change map')
        self.click_relative(0.77, 0.15, after_sleep=1)
        self.click_relative(0.48, 0.26, after_sleep=1)
        logger.info(f'click heal')
        travel = self.wait_feature('gray_teleport', raise_if_not_found=True, time_out=3)
        self.click_box(travel, relative_x=1.5)
        self.wait_in_team_and_world(time_out=20)
        self.sleep(2)

    def raise_not_in_combat(self, message, exception_type=None):
        logger.error(message)
        if self.reset_to_false(reason=message):
            logger.error(f'reset to false failed: {message}')
        if exception_type is None:
            exception_type = NotInCombatException
        raise exception_type(message)

    def available(self, name):
        current = self.calculate_color_percentage(text_white_color,
                                                  self.get_box_by_name(f'box_{name}'))
        if current > 0 and not self.has_cd(name):
            return True

    def combat_once(self, wait_combat_time=200, wait_before=1.5):
        self.wait_until(self.in_combat, time_out=wait_combat_time, raise_if_not_found=True,
                        wait_until_before_delay=wait_before)
        self.load_chars()
        self.info['Combat Count'] = self.info.get('Combat Count', 0) + 1
        while self.in_combat():
            try:
                logger.debug(f'combat_once loop {self.chars}')
                self.get_current_char().perform()
            except CharDeadException as e:
                raise e
            except NotInCombatException as e:
                logger.info(f'combat_once out of combat break {e}')
                # self.screenshot(f'combat_once_ooc {self.out_of_combat_reason}')
                break
        self.wait_in_team_and_world(time_out=10)
        self.sleep(1)
        self.middle_click()
        self.sleep(0.2)

    def run_in_circle_to_find_echo(self, circle_count=3):
        directions = ['w', 'a', 's', 'd']
        step = 1.2
        duration = 0.8
        total_index = 0
        for count in range(circle_count):
            logger.debug(f'running first circle_count{circle_count} circle {total_index} duration:{duration}')
            for direction in directions:
                if total_index > 2 and (total_index + 1) % 2 == 0:
                    duration += step
                picked = self.send_key_and_wait_f(direction, False, time_out=duration, running=True,
                                                  target_text=self.absorb_echo_text())
                if picked:
                    self.mouse_up(key="right")
                    return True
                total_index += 1

    def switch_next_char(self, current_char, post_action=None, free_intro=False, target_low_con=False):
        max_priority = Priority.MIN
        switch_to = current_char
        has_intro = free_intro
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
                logger.info(
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
            # logger.warning(f"can't find next char to switch to, maybe switching too fast click and wait")
            # if time.time() - current_char.last_perform < 0.1:
            current_char.continues_normal_attack(0.2)
            logger.warning(f"can't find next char to switch to, performing too fast add a normal attack")
            return current_char.switch_next_char()
        switch_to.has_intro = has_intro
        logger.info(f'switch_next_char {current_char} -> {switch_to} has_intro {has_intro}')
        last_click = 0
        start = time.time()
        while True:
            now = time.time()
            if now - last_click > 0.1:
                self.send_key(switch_to.index + 1)
                last_click = now
            in_team, current_index, size = self.in_team()
            if not in_team:
                logger.info(f'not in team while switching chars_{current_char}_to_{switch_to} {now - start}')
                if self.debug:
                    self.screenshot(f'not in team while switching chars_{current_char}_to_{switch_to} {now - start}')
                confirm = self.wait_feature('revive_confirm_hcenter_vcenter', threshold=0.8, time_out=2)
                if confirm:
                    self.log_info(f'char dead')
                    self.raise_not_in_combat(f'char dead', exception_type=CharDeadException)
                if now - start > 5:
                    self.raise_not_in_combat(
                        f'switch too long failed chars_{current_char}_to_{switch_to}, {now - start}')
                continue
            if current_index != switch_to.index:
                has_intro = free_intro if free_intro else current_char.is_con_full()
                switch_to.has_intro = has_intro
                if now - start > 10:
                    if self.debug:
                        self.screenshot(f'switch_not_detected_{current_char}_to_{switch_to}')
                    self.raise_not_in_combat('failed switch chars')
                else:
                    self.next_frame()
            else:
                self.in_liberation = False
                current_char.switch_out()
                switch_to.is_current_char = True
                break

        if post_action:
            post_action()
        logger.info(f'switch_next_char end {(current_char.last_switch_time - start):.3f}s')

    def get_liberation_key(self):
        return self.key_config['Liberation Key']

    def get_echo_key(self):
        return self.key_config['Echo Key']

    def get_resonance_key(self):
        return self.key_config['Resonance Key']

    def has_resonance_cd(self):
        return self.has_cd('resonance')

    def has_cd(self, box_name):
        box = self.get_box_by_name(f'box_{box_name}')
        cropped = box.crop_frame(self.frame)
        num_labels, stats, labels = get_connected_area_by_color(cropped, dot_color, connectivity=8, gray_range=22)
        big_area_count = 0
        has_dot = False
        number_count = 0
        invalid_count = 0
        # dot = None
        # output_image = cropped.copy()
        for i in range(1, num_labels):
            # Check if the connected co  mponent touches the border
            left, top, width, height, area = stats[i]
            if area / self.frame.shape[0] / self.frame.shape[
                1] > 20 / 3840 / 2160:
                big_area_count += 1
            if left > 0 and top > 0 and left + width < box.width and top + height < box.height:
                # self.logger.debug(f"{box_name} Area of connected component {i}: {area} pixels {width}x{height} ")
                if 16 / 3840 / 2160 <= area / self.frame.shape[0] / self.frame.shape[
                    1] <= 90 / 3840 / 2160 and abs(width - height) / (
                        width + height) < 0.3 and top / cropped.shape[0] > 0.6:
                    # if  top < (
                    #     box.height / 2) and left > box.width * 0.2 and left + width < box.width * 0.8:
                    has_dot = True
                    #     self.logger.debug(f"{box_name} multiple dots return False")
                    #     return False
                    # dot = stats[i]
                elif 25 / 2160 <= height / self.screen_height <= 45 / 2160 and 5 / 2160 <= width / self.screen_height <= 35 / 2160:
                    number_count += 1
            else:
                # self.logger.debug(f"{box_name} has invalid return False")
                invalid_count += 1
                return False

            # Draw the connected component with a random color
            # mask = labels == i
            # import numpy as np
            # output_image[mask] = np.random.randint(0, 255, size=3)
        # if self.debug:
        #     self.screenshot(f'{self}_{box_name}_has_cd', output_image)
        has_cd = (has_dot and 2 <= number_count <= 3)
        self.logger.debug(f'{box_name} has_cd {has_cd} {invalid_count} {number_count} {has_dot}')
        return has_cd

    def get_current_char(self) -> BaseChar:
        for char in self.chars:
            if char.is_current_char:
                return char
        if not self.in_team()[0]:
            self.raise_not_in_combat('can find current char!!')
        self.load_chars()
        return self.get_current_char()

    def sleep_check_combat(self, timeout, check_combat=True):
        start = time.time()
        if not self.in_combat() and check_combat:
            self.raise_not_in_combat('sleep check not in combat')
        self.sleep(timeout - (time.time() - start))

    def check_combat(self):
        if not self.in_combat():
            if self.debug:
                self.screenshot('not_in_combat_calling_check_combat')
            self.raise_not_in_combat('combat check not in combat')

    def load_hotkey(self, force=False):
        if not self.key_config['HotKey Verify'] or force:

            resonance_key = self.ocr(0.82, 0.92, 0.85, 0.96, match=re.compile(r'^[a-zA-Z]$'), threshold=0.8,
                                     name='resonance_key', use_grayscale=True)
            echo_key = self.ocr(0.88, 0.92, 0.90, 0.96, match=re.compile(r'^[a-zA-Z]$'), threshold=0.8,
                                name='echo_key')
            liberation_key = self.ocr(0.93, 0.92, 0.96, 0.96, match=re.compile(r'^[a-zA-Z]$'), threshold=0.8,
                                      name='liberation_key')
            keys_str = str(resonance_key) + str(echo_key) + str(liberation_key)

            if echo_key:
                self.key_config['Echo Key'] = echo_key[0].name.lower()
            if liberation_key:
                self.key_config['Liberation Key'] = liberation_key[0].name.lower()
            if resonance_key:
                self.key_config['Resonance Key'] = resonance_key[0].name.lower()
            self.key_config['HotKey Verify'] = True
            self.log_info(f'set hotkey success {self.key_config.values()}', notify=True, tray=True)
            self.info['Skill HotKeys'] = keys_str

    def load_chars(self):
        self.load_hotkey()
        in_team, current_index, count = self.in_team()
        if not in_team:
            return
        self.log_info('load chars')
        char = get_char_by_pos(self, self.get_box_by_name('box_char_1'), 0)
        old_char = safe_get(self.chars, 0)
        if self.should_update(char, old_char):
            self.chars[0] = char
            logger.info(f'update char1 to {char.name} {type(char)} {type(char) is not BaseChar}')

        char = get_char_by_pos(self, self.get_box_by_name('box_char_2'), 1)
        old_char = safe_get(self.chars, 1)
        if self.should_update(char, old_char):
            self.chars[1] = char
            logger.info(f'update char2 to {char.name}')
        if count == 3:
            char = get_char_by_pos(self, self.get_box_by_name('box_char_3'), 2)
            old_char = safe_get(self.chars, 2)
            if self.should_update(char, old_char):
                if len(self.chars) == 3:
                    self.chars[2] = char
                else:
                    self.chars.append(char)
                logger.info(f'update char3 to {char.name}')
        else:
            if len(self.chars) == 3:
                self.chars = self.chars[:2]
            logger.info(f'team size changed to 2')

        for char in self.chars:
            if char is not None:
                char.reset_state()
                if char.index == current_index:
                    char.is_current_char = True
                else:
                    char.is_current_char = False
        self.combat_start = time.time()

        self.log_info(f'load chars success {self.chars}')

    @staticmethod
    def should_update(char, old_char):
        return (type(char) is BaseChar and old_char is None) or (type(char) is not BaseChar and old_char != char)

    def box_resonance(self):
        return self.get_box_by_name('box_resonance_cd')

    def get_resonance_cd_percentage(self):
        return self.calculate_color_percentage(white_color, self.get_box_by_name('box_resonance_cd'))

    def get_resonance_percentage(self):
        return self.calculate_color_percentage(white_color, self.get_box_by_name('box_resonance'))

    def is_con_full(self, char_config=None):
        return self.get_current_con(char_config) == 1

    def get_current_con(self, char_config=None):
        box = self.box_of_screen_scaled(3840, 2160, 1422, 1939, to_x=1566, to_y=2076, name='con_full',
                                        hcenter=True)
        box.confidence = 0

        max_area = 0
        percent = 0
        max_is_full = False
        color_index = -1
        target_index = -1
        if char_config:
            target_index = char_config.get('_ring_color_index', target_index)
        cropped = box.crop_frame(self.frame)
        for i in range(len(con_colors)):
            if target_index != -1 and i != target_index:
                continue
            color_range = con_colors[i]
            area, is_full = self.count_rings(cropped, color_range,
                                             1500 / 3840 / 2160 * self.screen_width * self.screen_height)
            # self.logger.debug(f'is_con_full test color_range {color_range} {area, is_full}')
            if is_full:
                max_is_full = is_full
                color_index = i
            if area > max_area:
                max_area = int(area)
        if max_is_full:
            percent = 1
        if max_is_full and char_config:
            self.logger.info(
                f'is_con_full found a full ring {char_config.get("_full_ring_area", 0)} -> {max_area}  {color_index}')
            char_config['_full_ring_area'] = max_area
            char_config['_ring_color_index'] = color_index
            self.logger.info(
                f'is_con_full2 found a full ring {char_config.get("_full_ring_area", 0)} -> {max_area}  {color_index}')
        if percent != 1 and char_config and char_config.get('_full_ring_area', 0) > 0:
            percent = max_area / char_config['_full_ring_area']
        if not max_is_full and percent >= 1:
            self.logger.warning(
                f'is_con_full not full but percent greater than 1, set to 0.99, {percent} {max_is_full}')
            percent = 0.99
        if percent > 1:
            self.logger.error(f'is_con_full percent greater than 1, set to 1, {percent} {max_is_full}')
            percent = 1
        # self.logger.info(
        #     f'is_con_full {self} {percent} {max_area}/{self.config.get("_full_ring_area", 0)} {color_index} ')
        # if self.task.debug:
        #     self.task.screenshot(
        #         f'is_con_full {self} {percent} {max_area}/{self.config.get("_full_ring_area", 0)} {color_index} ',
        #         cropped)
        box.confidence = percent
        self.draw_boxes(f'is_con_full_{self}', box)
        if percent > 1:
            percent = 1
        return percent

    def count_rings(self, image, color_range, min_area):
        # Define the color range
        lower_bound, upper_bound = color_range_to_bound(color_range)

        image_with_contours = image.copy()

        # Create a binary mask
        mask = cv2.inRange(image, lower_bound, upper_bound)

        # Find connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

        colors = [
            (0, 255, 0),  # Green
            (0, 0, 255),  # Red
            (255, 0, 0),  # Blue
            (0, 255, 255),  # Yellow
            (255, 0, 255),  # Magenta
            (255, 255, 0)  # Cyan
        ]

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

        # Iterate over each component
        ring_count = 0
        is_full = False
        the_area = 0
        for label in range(1, num_labels):
            x, y, width, height, area = stats[label, :5]
            bounding_box_area = width * height
            component_mask = (labels == label).astype(np.uint8) * 255
            contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            color = colors[label % len(colors)]
            cv2.drawContours(image_with_contours, contours, -1, color, 2)
            if bounding_box_area >= min_area:
                # Select a color from the list based on the label index
                if is_full_ring(component_mask):
                    is_full = True
                the_area = area
                ring_count += 1

        # Save or display the image with contours
        # cv2.imwrite(f'test\\test_{self}_{is_full}_{the_area}_{lower_bound}.jpg', image_with_contours)
        if ring_count > 1:
            is_full = False
            the_area = 0
            self.logger.warning(f'is_con_full found multiple rings {ring_count}')

        return the_area, is_full


white_color = {
    'r': (253, 255),  # Red range
    'g': (253, 255),  # Green range
    'b': (253, 255)  # Blue range
}

con_colors = [
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
