import math
import re
import time

import cv2
import numpy as np
from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class Farm13CTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.description = "Farm selected Tacet Suppression until out of stamina, will use the backup stamina, you need to be able to teleport from the menu(F2)"
        self.name = "Tacet Suppression (Must explore first to be able to teleport)"
        default_config = {
            'Which Tacet Suppression to Farm': 1  # starts with 1
        }
        self.row_per_page = 5
        self.total_number = 11
        default_config.update(self.default_config)
        self.config_description = {
            'Which Tacet Suppression to Farm': 'the Nth number in the Tacet Suppression list (F2)',
        }
        self.default_config = default_config
        self.max_star_distance = 1000
        self.last_star = None
        self.last_angle = None
        self.stuck_keys = [['space', 0.2], ['a',2], ['d',2]]
        self.stuck_index = 0
        self.last_cords = None
        self.cords_re = re.compile('^\d+,\d+,\d+$')

    @property
    def star_move_distance_threshold(self):
        return self.height_of_screen(0.005)

    def run(self):
        self.last_star = None
        self.last_angle = None
        while True:
            echos = self.yolo_find_all()
            self.draw_boxes("yolo", echos)
            self.sleep(0.1)

    def get_cords(self):
        cords = self.ocr(0.01, 0.95, 0.21, 1, match=self.cords_re, log=True)
        if cords:
            return cords[0].name

    def get_angle(self):
        arrow_template = self.get_feature_by_name('arrow')
        original_mat = arrow_template.mat
        max_conf = 0
        max_angle = 0
        max_target = None
        max_mat = None
        (h, w) = arrow_template.mat.shape[:2]
        # self.log_debug(f'turn_east h:{h} w:{w}')
        center = (w // 2, h // 2)
        target_box = self.get_box_by_name('box_arrow')
        # if self.debug:
        #     self.screenshot('arrow_original', original_ mat)
        for angle in range(0, 360):
            # Rotate the template image
            rotation_matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
            arrow_template.mat = cv2.warpAffine(original_mat, rotation_matrix, (w, h))
            arrow_template.mask = np.where(np.all(arrow_template.mat == [0, 0, 0], axis=2), 0, 255).astype(np.uint8)

            target = self.find_one(f'arrow_{angle}', box=target_box,
                                   template=arrow_template, threshold=0.01)
            # if self.debug and angle % 90 == 0:
            #     self.screenshot(f'arrow_rotated_{angle}', arrow_template.mat)
            if target and target.confidence > max_conf:
                max_conf = target.confidence
                max_angle = angle
                max_target = target
                max_mat = arrow_template.mat
        arrow_template.mat = original_mat
        # arrow_template.mask = None
        # if self.debug and max_mat is not None:
        #     self.screenshot('max_mat',frame=max_mat)
        # self.log_debug(f'turn_east max_conf: {max_conf} {max_angle}')
        return max_angle , max_target

    def find_next_star(self):
        stars = self.find_stars()
        min_distance = self.max_star_distance
        nearest_star = None
        x2, y2 = self.get_box_by_name('box_minimap').center()
        for star in stars:
            if not self.last_star:
                x1, y1 = star.center()
                angle = calculate_angle_clockwise(x1, y1, x2, y2)
                if self.last_angle is not None and abs(angle - self.last_angle) < 90:
                    self.log_debug(f'old path continue {abs(angle - self.last_angle)} {star}')
                    continue
                self.last_star = star
                self.log_debug(f'no last star return nearest {self.last_star} {self.last_angle}')
                return -1, star
            distance = star.center_distance(self.last_star)
            if distance < min_distance:
                min_distance = distance
                nearest_star = star
        if nearest_star:
            self.last_star = nearest_star
        self.log_debug(f'nearest_star: {min_distance} {nearest_star}')
        return min_distance, nearest_star

    def go_to_star(self):
        current_direction = None
        self.center_camera()
        while True:
            self.sleep(0.01)
            if self.in_combat():
                if current_direction is not None:
                    self.mouse_up(key='right')
                    self.send_key_up(current_direction)
                    current_direction = None
                self.combat_once()
                while self.yolo_find_echo(use_color=False, walk=False)[1]:
                    self.sleep(0.5)
            cords = self.get_cords()
            if cords and cords == self.last_cords:
                logger.info(f'might be stuck, try jump')
                self.send_key(self.stuck_keys[self.stuck_index % 3][0], down_time=self.stuck_keys[self.stuck_index % 3][1], after_sleep=0.5)
                self.stuck_index += 1
                continue
            self.last_cords = cords
            stars = self.find_stars()
            if not stars:
                self.log_info('cannot find any stars, stop farming', notify=True)
                break
            star = stars[0]
            angle = self.get_angle_to_star(star)
            if current_direction == 'w':
                if 4 <= angle <= 90:
                    minor_adjust = 'd'
                elif -90 <= angle <= -4:
                    minor_adjust = 'a'
                else:
                    minor_adjust = None
                if minor_adjust:
                    # if self.debug:
                    #     self.screenshot(f'minor_adjust_{minor_adjust}_{angle}')
                    self.log_info(f'minor_adjust to {minor_adjust}_{angle}')
                    self.send_key_down(minor_adjust)
                    # self.center_camera()
                    self.sleep(0.3)
                    self.send_key_up(minor_adjust)
                    continue
            if -45 <= angle <= 45:
                new_direction = 'w'
            elif 45 < angle <= 135:
                new_direction = 'd'
            elif -135 < angle <= -45:
                new_direction = 'a'
            else:
                new_direction = 's'
            if current_direction != new_direction:
                self.log_info(f'changed direction {angle} {current_direction} -> {new_direction}')
                if self.debug:
                    self.screenshot(f'{current_direction}_{new_direction}_{angle}')
                if current_direction:
                    self.send_key_up(current_direction)
                    self.sleep(0.2)
                self.turn_direction(new_direction)
                self.send_key_down('w')
                self.sleep(0.2)
                self.mouse_down(key='right')
                current_direction = 'w'
                self.sleep(1)

        if current_direction is not None:
            self.mouse_up(key='right')
            self.send_key_up(current_direction)

    def get_angle_to_star(self, star):
        x1, y1 = self.get_box_by_name('box_minimap').center()
        x2, y2 = star.center()
        target_angle = calculate_angle_clockwise(x1, y1, x2, y2)
        my_angle = self.get_angle()[0]
        if my_angle >= target_angle:
            turn_angle = -(my_angle - target_angle)
        else:
            turn_angle = target_angle - my_angle
        if turn_angle > 180:
            turn_angle = 360 - turn_angle
        if turn_angle < -180:
            turn_angle = 360 + turn_angle
        logger.debug(f'go to turn_angle {my_angle} {target_angle} {turn_angle}')
        return turn_angle

    def find_stars(self):
        box_minimap = self.get_box_by_name('box_minimap')
        stars = self.find_feature('star', threshold=0.5, box=box_minimap)
        sorted_stars = sorted(stars, key=lambda star: - box_minimap.center_distance(star))
        # if self.debug:
        #     self.screenshot('starts', show_box=True)
        #     self.screenshot('stars_mask', frame=mask_star(self.frame), show_box=True)
        return sorted_stars


def calculate_angle_clockwise(x1, y1, x2, y2):
  """
  Calculates angle (radians) from horizontal right to line (x1,y1)->(x2,y2).
  Positive clockwise, negative counter-clockwise.
  """
  dx = x2 - x1
  dy = y2 - y1
  # math.atan2(dy, dx) gives angle from positive x-axis, positive CCW.
  # Negate for positive CW convention.
  return math.degrees(math.atan2(dy, dx))

star_color = {
    'r': (190, 220),  # Red range
    'g': (190, 220),  # Green range
    'b': (190, 220)  # Blue range
}

def mask_star(image):
    # return image
    return create_color_mask(image, star_color)

def create_color_mask(image, color_ranges):
  mask = cv2.inRange(image, (color_ranges['b'][0], color_ranges['g'][0], color_ranges['r'][0]), (color_ranges['b'][1], color_ranges['g'][1], color_ranges['r'][1]))
  return mask
