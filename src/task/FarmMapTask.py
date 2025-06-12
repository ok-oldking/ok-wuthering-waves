import math
import re
import time
from typing import List

import cv2
import numpy as np
from qfluentwidgets import FluentIcon

from ok import Logger, Box, get_bounding_box
from src.task.BaseCombatTask import BaseCombatTask
from src.task.BaseWWTask import calculate_angle_clockwise
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class BigMap(WWOneTimeTask, BaseCombatTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.big_map_frame = None
        self.stars = None
        self.my_box = None
        self.diamond = None

    def reset(self):
        self.big_map_frame = None
        self.stars = None
        self.my_box = None
        self.diamond = None

    def load_stars(self, wait_world=True):
        self.reset()
        self.click_relative(0.94, 556 / 1080, after_sleep=1)
        self.big_map_frame = self.frame
        self.diamond = self.find_one('big_map_diamond', threshold=0.7, frame=self.big_map_frame,
                                     box=Box(0, 0, self.big_map_frame.shape[1], self.big_map_frame.shape[0]))
        if not self.diamond:
            raise Exception('Need be in the map screen and have a diamond as the starting point!')
        self.stars = self.find_feature('big_map_star', threshold=0.7, frame=self.big_map_frame,
                                       box=Box(0, 0, self.big_map_frame.shape[1], self.big_map_frame.shape[0]))
        all_star_len = len(self.stars)
        self.stars = sort_stars(self.stars, self.diamond, self.height_of_screen(0.2))
        self.stars.insert(0, self.diamond)
        mini_map_box = self.get_box_by_name('box_minimap')
        self.my_box = self.diamond.scale(mini_map_box.width / self.diamond.width * 2)
        # if self.debug:
        #     init_my_box = self.my_box.crop_frame(self.frame)
        #     self.screenshot('init_my_box', frame=init_my_box)
        if len(self.stars) <= 2:
            raise Exception('Need be in the map screen and have a path of at least 3 stars!')

        self.log_info(f'Loaded {len(self.stars)} from {all_star_len + 1} Stars', notify=True)

        # self.click(self.diamond, after_sleep=1)
        # self.wait_click_travel()
        self.send_key('esc')
        self.info_set('Stars', len(self.stars))
        if wait_world:
            self.wait_in_team_and_world()

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

    def find_direction_angle(self, screenshot=False):
        if len(self.stars) == 0:
            return None, 0, 0
        my_box = self.find_my_location(screenshot=screenshot)
        sort_stars(self.stars, my_box, 0)
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

    def find_my_location(self, screenshot=False):
        frame = self.big_map_frame
        mat = self.get_box_by_name('box_minimap').crop_frame(self.frame)
        # mask = create_circle_mask_with_hole(mat)
        # mat = cv2.bitwise_and(mat, mat, mask=mask)

        in_big_map = self.find_one(frame=frame, template=mat, threshold=0.05,
                                   box=self.my_box, mask_function=create_circle_mask_with_hole,
                                   screenshot=screenshot)
        # in_big_maps = self.find_feature(frame=frame, template=mat, threshold=0.01, box=self.bounding_box)
        if not in_big_map:
            raise RuntimeError('can not find my cords on big map!')
        self.log_debug(f'found in_big_map: {in_big_map}')
        if self.debug and in_big_map:
            self.draw_boxes('stars', self.stars)
            self.draw_boxes('my_box', self.my_box, color='green')
            self.draw_boxes('in_big_map', in_big_map, color='yellow')
            self.draw_boxes('me', in_big_map.scale(0.1), color='blue')
            # self.screenshot('box_minimap', frame=frame, show_box=True)
            # self.screenshot('template_minimap', frame=mat)
        self.my_box = in_big_map.scale(1.3)
        return in_big_map


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
        self.description = "Farm world map with a marked path of stars (diamond as the starting point), start in the map screen"
        self.name = "Farm Map with Star Path"
        self.max_star_distance = 1000
        self.stuck_keys = [['space', 0.02], ['a', 2], ['d', 2], ['t', 0.02]]
        self.stuck_index = 0
        self.last_distance = 0
        self._has_health_bar = False

    @property
    def star_move_distance_threshold(self):
        return self.height_of_screen(0.03)

    def run(self):
        self.stuck_index = 0
        self.last_distance = 0
        self.load_stars()
        self.go_to_star()

    def on_combat_check(self):
        self.incr_drop(self.pick_f())
        self.find_my_location()
        if not self._has_health_bar:
            self._has_health_bar = self.has_health_bar()
        return True

    def go_to_star(self):
        current_direction = None
        current_adjust = None
        self.center_camera()
        too_far_count = 0

        try:
            while True:
                self.sleep(0.01)
                self.middle_click(interval=1, after_sleep=0.2)
                self._has_health_bar = False
                if self.in_combat():
                    self.sleep(2)
                    self._stop_movement(current_direction)
                    current_direction = None
                    start = time.time()
                    self.combat_once()
                    duration = time.time() - start

                    while True:
                        dropped, has_more = self.yolo_find_echo(use_color=False,
                                                                turn=duration > 15 or self._has_health_bar)
                        self.incr_drop(dropped)
                        self.sleep(0.5)
                        if not dropped or not has_more:
                            break

                star, distance, angle = self.find_direction_angle()
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
                        self.screenshot('too_far', frame=self.big_map_frame, show_box=True)
                        self.screenshot('far', frame=self.get_box_by_name('box_minimap').crop_frame(self.frame))
                    if too_far_count >= 3:
                        self.log_error('too far from next star, stop farming', notify=True)
                        break
                    else:
                        continue
                elif distance == self.last_distance:
                    logger.info(f'might be stuck, try {[self.stuck_index % 4]}')
                    self.send_key(self.stuck_keys[self.stuck_index % 4][0],
                                  down_time=self.stuck_keys[self.stuck_index % 4][1], after_sleep=0.5)
                    self.stuck_index += 1
                    continue

                self.last_distance = distance

                # --- REFACTORED BLOCK ---
                current_direction, current_adjust, should_continue = self._navigate_based_on_angle(
                    angle, current_direction, current_adjust
                )
                if should_continue:
                    continue
                # --- END REFACTORED BLOCK ---

        finally:
            self._stop_movement(current_direction)


star_color = {
    'r': (190, 220),  # Red range
    'g': (190, 220),  # Green range
    'b': (190, 220)  # Blue range
}


def sort_stars(points, start_point, max_distance=0):
    """
    BUILDS A PATH using Nearest Neighbor heuristic starting from 'start_point'.
    Filters steps where distance < 'min_distance'. Prepends start_point.
    NOTE: This is a HEURISTIC, likely NOT the absolute shortest total path.
    """
    unvisited = points[:]  # Copy the list of points to visit
    if not unvisited:  # Handle empty input list
        return []

    path_result = []  # Initialize empty list for the results (excluding start)
    current_point = start_point  # Start the calculation from start_point
    while unvisited:
        # Find points reachable according to min_distance
        # If min_distance is 0, distance(..) >= 0 is always true for distinct points.
        reachable_points = [p for p in unvisited if
                            max_distance == 0 or current_point.center_distance(p) <= max_distance]
        if not reachable_points:
            # Stop if no remaining points meet the criteria (or if unvisited is empty)
            # print(f"Stopping: No remaining points meet criteria from {current_point}.") # Optional debug
            break
            # Find the closest point among the reachable ones
        next_point = min(reachable_points, key=lambda p: current_point.center_distance(p))

        path_result.append(next_point)  # Add the chosen point to the result list
        unvisited.remove(next_point)  # Mark as visited
        current_point = next_point  # Update the current point for the next iteration
    return path_result


def mask_star(image):
    # return image
    return create_color_mask(image, star_color)


def create_color_mask(image, color_ranges):
    mask = cv2.inRange(image, (color_ranges['b'][0], color_ranges['g'][0], color_ranges['r'][0]),
                       (color_ranges['b'][1], color_ranges['g'][1], color_ranges['r'][1]))
    return mask
