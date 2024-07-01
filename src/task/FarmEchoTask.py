import re

from ok.logging.Logger import get_logger
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException

logger = get_logger(__name__)


class FarmEchoTask(BaseCombatTask):

    def __init__(self):
        super().__init__()
        self.default_config.update({
            'Repeat Farm Count': 100,
            'Teleport': True
        })
        self.crownless_pos = (0.9, 0.4)

    def run(self):
        if not self.in_team()[0]:
            self.log_error('must be in game world and in teams', notify=True)
            return
        if self.config.get('Teleport'):
            book = self.find_one('gray_book_button', use_gray_scale=True)
            if not book:
                self.log_error("can't find the book button")
                return
            self.sleep(2)
            self.log_info('click f2 to open the book')
            self.send_key('f2')
            self.wait_click_feature('gray_book_forgery', raise_if_not_found=True, use_gray_scale=True)
            self.wait_click_feature('gray_book_weekly_boss', raise_if_not_found=True, use_gray_scale=True)
            self.sleep(1)
            self.click_relative(self.crownless_pos[0], self.crownless_pos[1])
            self.wait_click_feature('gray_teleport', raise_if_not_found=True, use_gray_scale=True)

        # loop here
        count = 0
        i = -1
        while count < self.config.get("Repeat Farm Count", 0):
            count += 1
            self.wait_until(lambda: self.in_team()[0], time_out=40)
            self.walk_until_f()
            self.wait_ocr(0.75, 0.02, 0.85, 0.09, match=re.compile('240'), raise_if_not_found=True)
            i = self.choose_level(0)
            if i == -1:
                self.log_error('Can not find a level to enter', notify=True)
                return
            # self.wait_click_feature('gray_crownless_battle', raise_if_not_found=True, use_gray_scale=True,
            #                         box=self.box_of_screen(0.05, 0.12, 0.11, 0.22), threshold=0.7)
            # self.click_relative(0.15, 0.17)
            # self.sleep(1)
            #

            self.wait_until(lambda: self.in_combat(), time_out=40, raise_if_not_found=True)
            self.load_chars()
            while True:
                try:
                    logger.debug(f'autocombat loop {self.chars}')
                    self.get_current_char().perform()
                except NotInCombatException:
                    logger.info('out of combat break')
                    break
            self.wait_in_team(time_out=20)
            if self.walk_until_f(time_out=1.5, raise_if_not_found=False):  # find and pick echo
                self.info['Echo Count'] = self.info.get('Echo Count', 0) + 1
            self.send_key('esc')
            self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=True,
                                    use_gray_scale=True)
            self.wait_in_team(time_out=40)

    def choose_level(self, start):
        y = 0.17
        x = 0.15
        distance = 0.08
        for i in range(4):
            if i < start:
                continue
            self.click_relative(x, y + i * distance)
            self.sleep(1)
            self.wait_click_feature('gray_button_challenge', raise_if_not_found=True, use_gray_scale=True)
            self.sleep(1)
            cancel_button = self.find_one('cancel_button', use_gray_scale=True, threshold=0.7)
            self.screenshot(f'cancel_{cancel_button}')
            if not cancel_button:
                self.wait_click_feature('gray_start_battle', relative_x=-1, raise_if_not_found=True,
                                        use_gray_scale=True)
                return i
            else:
                self.click(cancel_button)
                self.sleep(1)
        return -1
