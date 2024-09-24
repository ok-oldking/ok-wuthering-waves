import time

import cv2
import numpy as np
from qfluentwidgets import FluentIcon

from ok.feature.FeatureSet import mask_white
from ok.logging.Logger import get_logger
from src.task.BaseCombatTask import BaseCombatTask

logger = get_logger(__name__)


class IllusiveRealmTask(BaseCombatTask):

    def __init__(self):
        super().__init__()
        self.description = "Auto Combat in Illusive Realm"
        self.name = "Illusive Realm"
        self.icon = FluentIcon.ALBUM
        self.last_is_click = False

    def in_realm(self):
        illusive_realm_menu = self.find_one('illusive_realm_menu',
                                            use_gray_scale=False, threshold=0.4,
                                            mask_function=mask_white)
        if illusive_realm_menu:
            illusive_realm_exit = self.find_one('illusive_realm_exit',
                                                use_gray_scale=False, threshold=0.4,
                                                mask_function=mask_white)
            return illusive_realm_exit is not None

    def perform(self):
        if not self.last_is_click:
            self.click()
        else:
            if self.available('liberation'):
                self.send_key_and_wait_animation(self.get_liberation_key())
            elif self.available('echo'):
                self.send_key(self.get_echo_key())
            elif self.available('resonance'):
                self.send_key(self.get_resonance_key())
        self.last_is_click = not self.last_is_click

    def send_key_and_wait_animation(self, key, total_wait=10, animation_wait=5):
        start = time.time()
        animation_start = 0
        while time.time() - start < total_wait and (
                animation_start == 0 or time.time() - animation_start < animation_wait):
            if self.in_realm() or self.in_team()[0]:
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

    def run(self):
        while True:
            start = time.time()
            if self.in_combat(check_team=False):
                self.perform()
                if time.time() - start < 0.1:
                    self.sleep(0.1)

            self.next_frame()


def mask_target(image_path):
    # Read the image
    image = cv2.imread(image_path)

    # Define the color ranges
    lower_white = np.array([255, 255, 255])
    upper_white = np.array([255, 255, 255])

    lower_range = np.array([130, 120, 225])
    upper_range = np.array([170, 160, 255])

    # Create masks for the color ranges
    mask_white = cv2.inRange(image, lower_white, upper_white)
    mask_range = cv2.inRange(image, lower_range, upper_range)

    # Combine the masks
    combined_mask = cv2.bitwise_or(mask_white, mask_range)

    # Apply the mask to the image
    masked_image = cv2.bitwise_and(image, image, mask=combined_mask)

    return masked_image
