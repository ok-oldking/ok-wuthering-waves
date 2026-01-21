import re
import cv2
from qfluentwidgets import FluentIcon
from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class NightmareNestTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.target_enemy_time_out = 10
        self.name = "Nightmare Nest Task"
        self.description = "Auto Farm all Nightmare Nest"
        self.group_name = "Daily"
        self.group_icon = FluentIcon.HOME
        self.icon = FluentIcon.CALORIES
        self.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")
        self.step = 0
        self._capture_success = False
        self._capture_mode = False

    def run(self):
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=30)
        self.step = 0
        self.log_info('opened gray_book_boss')
        while nest := self.get_nest_to_go():
            self.combat_nest(nest)
        self.ensure_main(time_out=30)

    def run_capture_mode(self):
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=30)
        self.step = 0
        self.log_info('opened gray_book_boss')
        while nest := self.get_nest_to_go():
            self.combat_nest(nest, capture_mode=True)
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

    def combat_nest(self, nest, capture_mode=False):
        self._capture_mode = capture_mode
        self._capture_success = False
        self.click(nest, after_sleep=2)
        self.wait_click_travel()
        self.wait_in_team_and_world(time_out=30, raise_if_not_found=False)
        self.sleep(1)
        while self.find_f_with_text():
            self.send_key('f', after_sleep=1)
            self.wait_in_team_and_world(time_out=40, raise_if_not_found=False)
        self.run_until(self.in_combat, 'w', time_out=10, running=False)
        self.combat_once()
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
        while self.step <= 2:
            self.go_step()
            if nest := self.find_nest():
                return nest
            else:
                self.step += 1

    def go_step(self):
        if self.step <= 1:
            self.click(0.17, 0.68, after_sleep=1)
            self.log_info('go step 1')
            if self.step == 1:
                self.click(0.98, 0.54, after_sleep=1)
                self.log_info('go step 2 scroll')
        else:
            self.click(0.17, 0.77, after_sleep=1)
            self.log_info('go step 3')

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


