import re
import cv2
from qfluentwidgets import FluentIcon
from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


 


class NightmareNestTask(WWOneTimeTask, BaseCombatTask):
    _purification = 'Nightmare Purification'
    _nest = 'Tacet Discord Nest'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.target_enemy_time_out = 10
        self.name = "Nightmare Nest Task"
        self.description = "Auto Farm all Nightmare Nest"
        self.support_schedule_task = True
        self.group_name = "Daily"
        self.group_icon = FluentIcon.HOME
        self.icon = FluentIcon.CALORIES
        self.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")
        self.queues = []
        self._capture_success = False
        self._capture_mode = False
        self.default_config.update({
            self._purification: [str(i) for i in range(1, 6)],
            self._nest: [str(i) for i in range(1, 4)],
        })
        self.config_type[self._purification] = {
            'type': "multi_selection",
            'options': [str(i) for i in range(1, 6)]
        }
        self.config_type[self._nest] = {
            'type': "multi_selection",
            'options': [str(i) for i in range(1, 4)]
        }

    def run(self):
        self._capture_mode = False
        self._capture_success = False
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=30)
        nests = getattr(self, 'selected_nests', None)
        self._init_queue(nests)
        self.selected_nests = None
        self.log_info('opened gray_book_boss')
        while nest := self.get_nest_to_go():
            self.combat_nest(nest)
        self.ensure_main(time_out=30)

    def run_capture_mode(self, selected_nests=None):
        self._capture_mode = True
        self._capture_success = False
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=30)
        self._init_queue(selected_nests)
        self.log_info('opened gray_book_boss')
        while nest := self.get_nest_to_go():
            self.combat_nest(nest)
            if self._capture_success:
                break
        self.ensure_main(time_out=30)

    def on_combat_check(self):
        if self._capture_mode:
            self.pick_f(handle_claim=False)
            if self.has_echo_notification():
                raise NotInCombatException
        return True

    def has_echo_notification(self):
        if self.find_best_match_in_box(self.box_of_screen(0.078, 0.488, 0.094, 0.514),
                                       ['char_1_text', 'char_3_text'], 0.7,
                                       frame_processor=convert_image_to_negative):
            self._capture_success = True
        return self._capture_success

    def combat_nest(self, nest):
        self.click(nest, after_sleep=2)
        self.wait_click_travel()
        self.wait_in_team_and_world(time_out=30, raise_if_not_found=False)
        self.sleep(1)
        while self.find_f_with_text():
            self.send_key('f', after_sleep=1)
            self.wait_in_team_and_world(time_out=40, raise_if_not_found=False)
        self.sleep(2)
        self.run_until(self.in_combat, 'w', time_out=10, running=False, target=True)
        self.combat_once(wait_combat_time=0)
        if self._capture_mode:
            if self._capture_success or self.wait_until(self.has_echo_notification, time_out=3):
                self.log_info("Captured echo during combat, skipping search.")
                return
        else:
            self.sleep(3)
        if not self.walk_find_echo(time_out=5, backward_time=2.5):
            dropped = self.yolo_find_echo(turn=True, use_color=False, time_out=30)[0]
            logger.info(f'farm echo yolo find {dropped}')
        else:
            dropped = True
            self.log_info(f'farm echo walk find true')
        self._capture_success = dropped
        self.sleep(1)

    def get_nest_to_go(self):
        gray_book_boss = self.openF2Book("gray_book_boss")
        self.click_box(gray_book_boss, after_sleep=1)

        last_scanned_category = None
        last_scanned_scroll = None
        all_boxes_cache = None

        while self.queues:
            category, index = self.queues[0]
            need_scroll = category == self._purification and index > 4

            if category != last_scanned_category or need_scroll != last_scanned_scroll:
                if category != last_scanned_category:
                    self._go_to_category(category)
                if need_scroll:
                    self.click(self.tacet_scroll_x, 0.54, after_sleep=1)
                    self.log_info(f'scroll {category} to index {index}')
                text_boxes = self.ocr(0.43, 0.13, 0.58, 0.91, frame_processor=self.ocr_preprocess)
                all_boxes_cache = self._process_ocr_results(text_boxes)
                last_scanned_category = category
                last_scanned_scroll = need_scroll

            if nest := self._evaluate_nest_from_cache(index, need_scroll, all_boxes_cache):
                return nest
                
            self.queues.pop(0)

    def _process_ocr_results(self, text_boxes):
        tx = self.width_of_screen(0.43)
        ty = self.height_of_screen(0.13)
        for b in text_boxes:
            b.x = tx + (b.x - tx) / 2
            b.y = ty + (b.y - ty) / 2
            b.width /= 2
            b.height /= 2
        return text_boxes

    def ocr_preprocess(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
        h, w = binary.shape[:2]
        upscaled = cv2.resize(binary, (w * 2, h * 2), interpolation=cv2.INTER_LINEAR)
        return cv2.cvtColor(upscaled, cv2.COLOR_GRAY2BGR)

    def _init_queue(self, selected_nests=None):
        actions = []
        if selected_nests is not None:
            for category, index in selected_nests:
                actions.append((category, index))
        else:
            purification_list = self.config.get(self._purification) or []
            for i in sorted(purification_list, key=lambda x: int(x)):
                actions.append((self._purification, int(i)))
            nest_list = self.config.get(self._nest) or []
            for i in sorted(nest_list, key=lambda x: int(x)):
                actions.append((self._nest, int(i)))
        self.queues = actions

    def _go_to_category(self, category):
        if category == self._purification:
            self.click(0.17, 0.68, after_sleep=1)
            self.log_info('go nightmare purification')
        elif category == self._nest:
            self.click(0.17, 0.77, after_sleep=1)
            self.log_info('go tacet discord nest')

    def _evaluate_nest_from_cache(self, index, need_scroll, all_boxes):
        progress_boxes = [b for b in all_boxes if re.search(r'\d{1,2}/\d{1,2}', b.name)]
        progress_boxes.sort(key=lambda box: box.y)
        target_progress_box = None

        if not need_scroll:
            if index - 1 < len(progress_boxes):
                target_progress_box = progress_boxes[index - 1]
        else:
            target_progress_box = self._find_scrolled_nest(index, progress_boxes)

        if not target_progress_box:
            self.log_info(f'nest #{index} progress not found')
            return None

        return self._check_completion(index, target_progress_box)

    def _find_scrolled_nest(self, index, progress_boxes):
        if progress_boxes:
            idx_from_end = -1 if index == 5 else -2
            if len(progress_boxes) >= abs(idx_from_end):
                return progress_boxes[idx_from_end]
        return None

    def _check_completion(self, index, target_progress_box):
        match = re.search(r'(\d{1,2})\D*(\d{1,2})', target_progress_box.name)
        if match:
            num, den = match.group(1), match.group(2)
            if num != den:
                self.log_info(f'nest #{index} {num}/{den} is not complete')
                target_progress_box.x = self.width_of_screen(0.9)
                target_progress_box.y -= target_progress_box.height
                return target_progress_box
            self.log_info(f'nest #{index} {num}/{den} is complete')
        else:
            self.log_info(f'nest #{index} {target_progress_box.name} no numbers found')
        return None

 

    def find_nest(self):
        counts = self.ocr(0.36, 0.13, 0.98, 0.91, match=self.count_re)
        for count_box in counts:
            for match in re.finditer(self.count_re, count_box.name):
                numerator = match.group(1)
                denominator = match.group(2)
                if numerator != denominator and denominator in ['24', '36', '48']:
                    self.log_info(f'{count_box} is not complete')
                    count_box.x = self.width_of_screen(0.9)
                    count_box.y -= count_box.height
                    return count_box


def convert_image_to_negative(img):
    to_gray = False
    _mat = cv2.resize(img, None, fx=0.8, fy=0.8, interpolation=cv2.INTER_LINEAR)
    if len(_mat.shape) == 3:
        to_gray = True
        _mat = cv2.cvtColor(_mat, cv2.COLOR_BGR2GRAY)
    _, _mat = cv2.threshold(_mat, 80, 255, cv2.THRESH_BINARY)
    _mat = cv2.bitwise_not(_mat)
    if to_gray:
        _mat = cv2.cvtColor(_mat, cv2.COLOR_GRAY2BGR)
    return _mat
