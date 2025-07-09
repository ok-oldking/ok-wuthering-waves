import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class TacetTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.description = "Farm selected Tacet Suppression until out of stamina, will use the backup stamina, you need to be able to teleport from the menu(F2)"
        self.name = "Tacet Suppression (Must explore first to be able to teleport)"
        default_config = {
            # 'Teleport Timeout': 10,
            'Which Tacet Suppression to Farm': 1,  # starts with 1
            'Tacet Suppression Count': 10,
        }
        self.row_per_page = 5
        self.total_number = 12
        self.target_enemy_time_out = 8
        default_config.update(self.default_config)
        self.config_description = {
            # 'Teleport Timeout': 'the timeout of second for teleport',
            'Which Tacet Suppression to Farm': 'the Nth number in the Tacet Suppression list (F2)',
            'Tacet Suppression Count': 'farm Tacet Suppression N time(s), 60 stamina per time, set a large number to use all stamina',
        }
        self.default_config = default_config
        self.door_walk_method = {  # starts with 0
            0: [],
            1: [],
            2: [["a", 0.3]],
            3: [["d", 0.6]],
            4: [["a", 1.5], ["w", 3], ["a", 2.5]],
        }
        self.stamina_once = 60
        self.double_bonus = False

    def run(self):
        super().run()
        # timeout_second = self.config.get('Teleport Timeout', 10)
        timeout_second = 60
        self.wait_in_team_and_world(esc=True, time_out=timeout_second)
        self.farm_tacet()

    def farm_tacet(self):
        # timeout_second = self.config.get('Teleport Timeout', 10)
        timeout_second = 60
        serial_number = self.config.get('Which Tacet Suppression to Farm', 0)
        total_counter = self.config.get('Tacet Suppression Count', 0)
        # total counter
        if total_counter <= 0:
            self.log_info('0 time(s) farmed, 0 stamina used')
            return
        # stamina
        current, back_up = self.open_F2_book_and_get_stamina()
        if current + back_up < self.stamina_once:
            self.log_info('not enough stamina, 0 stamina used')
            self.back()
            return
        #
        counter = total_counter
        total_used = 0
        while counter > 0:
            gray_book_boss = self.openF2Book("gray_book_boss")
            self.click_box(gray_book_boss, after_sleep=1)
            self.click_relative(0.18, 0.48, after_sleep=1)
            index = serial_number - 1
            self.teleport_to_tacet(index)
            self.wait_click_travel()
            self.wait_in_team_and_world(time_out=timeout_second)
            self.sleep(max(2, timeout_second / 10)) # wait for treasure/door/enemy appear
            if self.door_walk_method.get(index) is not None:
                for method in self.door_walk_method.get(index):
                    self.send_key_down(method[0])
                    self.sleep(method[1])
                    self.send_key_up(method[0])
                    self.sleep(0.05)
                self.run_until(self.in_combat, 'w', time_out=10, running=True)
            else:
                self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
            self.combat_once()
            self.sleep(3)
            self.walk_to_treasure()
            if counter <= 1 or self.double_bonus:
                used, remaining_total, _, _ = self.ensure_stamina(self.stamina_once, self.stamina_once)
                counter -= 1
            else:
                used, remaining_total, _, _ = self.ensure_stamina(self.stamina_once, 2 * self.stamina_once)
                counter -= int(used / self.stamina_once)
            total_used += used
            self.wait_click_ocr(0.2, 0.56, 0.75, 0.69, match=[str(used), '确认', 'Confirm'], raise_if_not_found=True,
                                log=True)
            self.sleep(4)
            self.click(0.51, 0.84, after_sleep=2)
            if counter <= 0:
                self.log_info(f'{total_counter} time(s) farmed, {total_used} stamina used')
                break
            if remaining_total < self.stamina_once:
                self.log_info(f'not enough stamina, {total_used} stamina used')
                break

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        if index >= self.row_per_page:
            if index >= self.row_per_page * 2:  # page 3
                self.click_relative(0.98, 0.86)
                index -= self.row_per_page + 2  # only 1 in last page
            else:
                index -= self.row_per_page
                self.click_relative(0.98, 0.74)
            self.log_info(f'teleport_to_tacet scroll down a page new index: {index}')
        x = 0.88
        height = (0.85 - 0.28) / 4
        if self.ocr(0.3, 0.4, 0.36, 0.47, match=[re.compile("UP", re.IGNORECASE)]):
            logger.info("tacet double up")
            self.double_bonus = True
            y = 0.28
        else:
            y = 0.275
        y += height * index
        self.click_relative(x, y, after_sleep=2)


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
