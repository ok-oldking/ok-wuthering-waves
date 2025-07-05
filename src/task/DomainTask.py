import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class DomainTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teleport_timeout = 60
        self.stamina_once = 0

    def make_sure_in_world(self):
        exit_icon = self.find_one('illusive_realm_exit', vertical_variance=0.8, horizontal_variance=0.05, threshold=0.88),
        if (exit_icon and exit_icon[0]):
            # exit icon at the top left, means currently in domain/mission, not in world
            self.send_key_down('alt')
            self.sleep(0.05)
            self.click_relative(0.01, 0.04)
            self.send_key_up('alt')
            self.sleep(0.05)
            self.wait_click_ocr(0.2, 0.56, 0.75, 0.69, match=['确认', 'Confirm'], raise_if_not_found=True, log=True)
        self.wait_in_team_and_world(time_out = self.teleport_timeout)
    
    def open_F2_book_and_get_stamina(self):
        gray_book_boss = self.openF2Book('gray_book_boss')
        self.click_box(gray_book_boss, after_sleep=1)
        return self.get_stamina()

    def farm_in_domain(self, total_counter = 0, current = 0, back_up = 0):
        if (self.stamina_once <= 0):
            raise Exception('"self.stamina_once" must be override')
        # total counter
        if total_counter <= 0:
            self.log_info(f'0 time(s) farmed, 0 stamina used')
            return
        # stamina
        if current + back_up < self.stamina_once:
            self.log_info(f'not enough stamina, 0 stamina used')
            return
        # farm
        counter = total_counter
        remaining_total = 0
        total_used = 0
        while True: 
            self.sleep(max(5, self.teleport_timeout / 5))
            self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
            self.combat_once()
            self.sleep(3)
            self.walk_to_treasure()
            used, remaining_total, remaining_current, used_back_up = self.ensure_stamina(self.stamina_once, self.stamina_once)
            total_used += used
            # self.click(0.75, 0.32, after_sleep=2) # click fork of dialog (for debug)
            self.wait_click_ocr(0.2, 0.56, 0.75, 0.69, match=[str(used), '确认', 'Confirm'], raise_if_not_found=True, log=True) # click use stamina of dialog
            self.sleep(4)
            counter -= 1
            if counter <= 0:
                self.log_info(f'{total_counter} time(s) farmed, {total_used} stamina used')
                break
            if remaining_total < self.stamina_once:
                self.log_info(f'not enough stamina, {total_used} stamina used')
                break
            self.click(0.68, 0.84, after_sleep=2) # farm again
        #
        self.click(0.42, 0.84, after_sleep=2) # back to world
        self.wait_in_team_and_world(time_out=self.teleport_timeout)

            
echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
