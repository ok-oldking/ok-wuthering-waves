import math
import re
import time
from typing import List

import cv2
import numpy as np
from qfluentwidgets import FluentIcon

from ok import Logger, Box, get_bounding_box
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)

class BigMap(WWOneTimeTask, BaseCombatTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.big_map_frame = None
        self.stars = None
        self.bounding_box = None
        self.sorted = False


    def reset(self):
        self.big_map_frame = None
        self.stars = None
        self.bounding_box = None
        self.sorted = False

    def load_stars(self):
        self.reset()
        self.click_relative(0.94, 556 / 1080, after_sleep=1)
        self.big_map_frame = self.frame
        self.stars = self.find_feature('big_map_star', threshold=0.7, frame=self.big_map_frame, box=Box(0,0,self.big_map_frame.shape[1],self.big_map_frame.shape[0]))
        all_star_len = len(self.stars)
        self.stars = group_boxes_by_center_distance(self.stars, self.height_of_screen(0.2))
        if len(self.stars) <= 2:
            raise Exception('Need be in the map screen and have a path of at least 3 stars!')
        self.log_info(f'Loaded {len(self.stars)} from {all_star_len} Stars', notify=True)
        self.bounding_box = get_bounding_box(self.stars)
        mini_map_box = self.get_box_by_name('box_minimap')
        self.bounding_box.width += mini_map_box.width * 2
        self.bounding_box.height += mini_map_box.height * 2
        self.bounding_box.x -= mini_map_box.width
        self.bounding_box.y -= mini_map_box.height
        self.info_set('Stars', len(self.stars))
        self.send_key('esc', after_sleep=1)

    def get_angle_between(self, my_angle, angle):
        if my_angle > angle:
            to_turn = angle - my_angle
        else:
            to_turn = -(my_angle - angle)
        if to_turn > 180:
            to_turn -= 360
        elif to_turn < -180:
            to_turn += 360
        return to_turn

    def get_my_angle(self):
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
            template = cv2.warpAffine(original_mat, rotation_matrix, (w, h))
            # mask = np.where(np.all(template == [0, 0, 0], axis=2), 0, 255).astype(np.uint8)

            target = self.find_one(box=target_box,
                                   template=template, threshold=0.01)
            # if self.debug and angle % 90 == 0:
            #     self.screenshot(f'arrow_rotated_{angle}', arrow_template.mat)
            if target and target.confidence > max_conf:
                max_conf = target.confidence
                max_angle = angle
                # max_target = target
                # max_mat = template
        # arrow_template.mat = original_mat
        # arrow_template.mask = None
        # if self.debug and max_mat is not None:
        #     self.screenshot('max_mat',frame=max_mat)
        # self.log_debug(f'turn_east max_conf: {max_conf} {max_angle}')
        return max_angle

    def find_closest(self, my_box):
        min_distance = 100000
        min_star = None
        if len(self.stars) == 0:
            return None, 0, 0
        for star in self.stars:
            distance = star.center_distance(my_box)
            if distance < min_distance:
                min_distance = distance
                min_star = star
        return min_star

    def sort_stars(self, my_box):
        if self.sorted:
            return
        remaining_boxes = self.stars[:]  # Make a copy
        sorted_boxes = []
        # Start with the first box in the original list
        current_box = self.find_closest(my_box)
        remaining_boxes.remove(current_box)
        sorted_boxes.append(current_box)
        while remaining_boxes:
            min_dist = float('inf')
            best_idx = -1
            # Find the box in remaining_boxes closest to the current_box
            for i, box in enumerate(remaining_boxes):
                dist = current_box.center_distance(box)
                if dist < min_dist:
                    min_dist = dist
                    best_idx = i
            # Add the closest box to the sorted list and remove from remaining
            next_box = remaining_boxes.pop(best_idx)
            sorted_boxes.append(next_box)
            current_box = next_box  # Update the reference point
        self.stars = sorted_boxes
        self.sorted = True

    def find_direction_angle(self):
        if len(self.stars) == 0:
            return None, 0, 0
        my_box = self.find_my_location()
        self.sort_stars(my_box)
        min_star = self.stars[0]
        min_distance = my_box.center_distance(min_star)
        self.draw_boxes('star', min_star, color='green')
        direction_angle = calculate_angle_clockwise(my_box, min_star)
        my_angle = self.get_my_angle()
        to_turn = self.get_angle_between(my_angle, direction_angle)
        # self.log_debug(f'direction_angle {to_turn} {my_angle} {direction_angle}  min_distance {min_distance} min_star {min_star} ')
        return min_star, min_distance, to_turn

    def remove_star(self, star):
        before = len(self.stars)
        self.stars.remove(star)
        self.info_set('Stars', len(self.stars))
        self.log_debug(f'removed star {before} -> {len(self.stars)}')


    def find_my_location(self):
        frame = self.big_map_frame
        mat = self.get_box_by_name('box_minimap').crop_frame(self.frame)
        mat = keep_circle(mat)
        in_big_map = self.find_one(frame=frame, template=mat, threshold=0.01, box=self.bounding_box, mask_function=create_circle_mask_with_hole)
        # in_big_maps = self.find_feature(frame=frame, template=mat, threshold=0.01, box=self.bounding_box)
        if not in_big_map:
            raise RuntimeError('can not find my cords on big map!')
        self.log_debug(f'found big map: {in_big_map}')
        if self.debug and in_big_map:
            self.draw_boxes('stars', self.stars)
            self.draw_boxes('search_map', self.bounding_box)
            self.draw_boxes('in_big_map', in_big_map.scale(0.1), color='blue')
            # self.screenshot('box_minimap', frame=mat, show_box=True)
        return in_big_map

def keep_circle(img):
    height, width = img.shape[:2]
    # Create a black mask with the same dimensions
    mask = np.zeros((height, width), dtype=np.uint8)
    # Define circle parameters (center and radius)
    center_x, center_y = width // 2, height // 2
    radius = min(center_x, center_y)  # Fit circle within image bounds
    # Draw a filled white circle on the mask
    cv2.circle(mask, (center_x, center_y), radius, (255), thickness=-1)
    # Apply the mask to the original image using bitwise AND
    result = cv2.bitwise_and(img, img, mask=mask)
    return result

def create_circle_mask_with_hole(image):
    """
    Creates a binary circular mask with a rectangular hole in the center.
    The circle fills the mask dimensions, and the hole is 1/4 width and height.
    Args:
        shape (tuple): The (height, width) of the desired mask.
    Returns:
        numpy.ndarray: A uint8 NumPy array representing the mask
                       (255 in the circle ring, 0 elsewhere and in the hole).
    """
    h, w = image.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    center_x, center_y = w // 2, h // 2
    radius = min(w, h) // 2
    # 1. Draw the outer filled white circle
    cv2.circle(mask, (center_x, center_y), radius, 255, -1)
    # 2. Calculate rectangle dimensions and corners for the hole
    rect_w = round(w / 4.4)
    rect_h = round(h / 4.4)
    # Calculate top-left corner centered
    rect_x1 = center_x - rect_w // 2
    rect_y1 = center_y - rect_h // 2
    # Calculate bottom-right corner
    rect_x2 = rect_x1 + rect_w
    rect_y2 = rect_y1 + rect_h
    # 3. Draw the inner filled black rectangle (the hole)
    # Use color=0 and thickness=-1 to fill with black
    cv2.rectangle(mask, (rect_x1, rect_y1), (rect_x2, rect_y2), 0, -1)
    return mask

class FarmMapTask(BigMap):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.GLOBE
        self.description = "Farm world map with a marked path of stars, start in the map screen"
        self.name = "Farm Map with Star Path"
        self.max_star_distance = 1000
        self.stuck_keys = [['space', 0.2], ['a',2], ['d',2]]
        self.stuck_index = 0
        self.last_distance = 0
        self.check_pick_echo = True

    @property
    def star_move_distance_threshold(self):
        return self.height_of_screen(0.025)

    def run(self):
        self.stuck_index = 0
        self.last_distance = 0
        self.load_stars()
        self.go_to_star()

    def go_to_star(self):
        current_direction = None
        self.center_camera()
        current_adjust = None
        too_far_count = 0
        while True:
            self.sleep(0.01)
            self.middle_click(interval=1, after_sleep=0.2)
            if self.in_combat():
                if current_direction is not None:
                    self.mouse_up(key='right')
                    self.send_key_up(current_direction)
                    current_direction = None
                self.combat_once()
                while True:
                    dropped, has_more = self.yolo_find_echo(use_color=False, walk=False)[1]
                    self.incr_drop(dropped)
                    self.sleep(0.5)
                    if not dropped or not has_more:
                        break
            star, distance, angle = self.find_direction_angle()
            # self.draw_boxes('next_star', star, color='green')
            if not star:
                self.log_info('cannot find any stars, stop farming', notify=True)
                break
            if distance <= self.star_move_distance_threshold:
                self.log_info(f'reached star {star} {distance} {self.star_move_distance_threshold}')
                self.remove_star(star)
                continue
            elif distance >= self.height_of_screen(0.4):
                too_far_count += 1
                if self.debug:
                    self.screenshot('too_far',frame=self.big_map_frame,show_box=True)
                    self.screenshot('far',frame=self.get_box_by_name('box_minimap').crop_frame(self.frame))
                if too_far_count >= 3:
                    self.log_error('too far from next star, stop farming', notify=True)
                    break
                else:
                    continue
            elif distance == self.last_distance:
                logger.info(f'might be stuck, try {[self.stuck_index % 3]}')
                self.send_key(self.stuck_keys[self.stuck_index % 3][0], down_time=self.stuck_keys[self.stuck_index % 3][1], after_sleep=0.5)
                self.stuck_index += 1
                continue

            self.last_distance = distance

            if current_direction == 'w':
                if 15 <= angle <= 75:
                    minor_adjust = 'd'
                elif -75 <= angle <= -15:
                    minor_adjust = 'a'
                else:
                    minor_adjust = None

                if minor_adjust:
                    self.send_key_down(minor_adjust)
                    # self.center_camera()
                    self.sleep(0.1)
                    self.middle_click(down_time=0.1)
                    self.send_key_up(minor_adjust)
                    self.sleep(0.2)
                    continue
            if current_adjust:
                self.send_key_up(current_adjust)
                current_adjust = None
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

def calculate_angle_clockwise(box1, box2):
  """
  Calculates angle (radians) from horizontal right to line (x1,y1)->(x2,y2).
  Positive clockwise, negative counter-clockwise.
  """
  x1, y1 = box1.center()
  x2, y2 = box2.center()
  dx = x2 - x1
  dy = y2 - y1
  # math.atan2(dy, dx) gives angle from positive x-axis, positive CCW.
  # Negate for positive CW convention.

  degree = math.degrees(math.atan2(dy, dx))
  if degree < 0:
      degree += 360
  return degree

star_color = {
    'r': (190, 220),  # Red range
    'g': (190, 220),  # Green range
    'b': (190, 220)  # Blue range
}

def group_boxes_by_center_distance(boxes: List[Box], distance_threshold: float) -> List[Box]:
    """
    Groups boxes where any box is close (center_distance < threshold)
    to any other box in the group (connected components).
    Returns the largest group.
    """
    if not boxes:
        return []
    n = len(boxes)
    visited = [False] * n
    all_groups = []
    # Find connected components using DFS
    for i in range(n):
        if not visited[i]:
            current_group = []
            stack = [i]
            visited[i] = True
            while stack:
                current_idx = stack.pop()
                current_group.append(boxes[current_idx])
                for j in range(n):
                    if not visited[j]:
                        # Use center_distance as requested
                        dist = boxes[current_idx].center_distance(boxes[j])
                        if dist < distance_threshold:
                            visited[j] = True
                            stack.append(j)
            all_groups.append(current_group)
    # Return the largest group found
    if not all_groups:
         return [] # Should not happen if boxes is not empty, but safe check
    return max(all_groups, key=len)

def mask_star(image):
    # return image
    return create_color_mask(image, star_color)

def create_color_mask(image, color_ranges):
  mask = cv2.inRange(image, (color_ranges['b'][0], color_ranges['g'][0], color_ranges['r'][0]), (color_ranges['b'][1], color_ranges['g'][1], color_ranges['r'][1]))
  return mask
