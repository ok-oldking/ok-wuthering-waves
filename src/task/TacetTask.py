from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class TacetTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.description = "Farms the selected Tacet Suppression. Must be able to teleport (F2)."
        self.name = "Tacet Suppression"
        default_config = {
            'Which Tacet Suppression to Farm': 1,  # starts with 1
            'Tacet Suppression Count': 20,  # starts with 20
        }
        self.total_number = 12
        self.target_enemy_time_out = 8
        default_config.update(self.default_config)
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
            'Tacet Suppression Count': 'Number of times to farm the Tacet Suppression (60 stamina per run). Set a large number to use all stamina.',
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
        self._daily_task = False

    def run(self):
        super().run()
        self.wait_in_team_and_world(esc=True)
        self.farm_tacet()

    def farm_tacet(self):
        total_counter = counter = self.config.get('Tacet Suppression Count', 20)
        total_used = 0
        while True:
            self.sleep(1)
            gray_book_boss = self.openF2Book("gray_book_boss")
            self.click_box(gray_book_boss, after_sleep=1)
            current, back_up = self.get_stamina()
            if current == -1:
                self.click_relative(0.04, 0.4, after_sleep=1)
                current, back_up = self.get_stamina()
            if current + back_up < self.stamina_once:
                return self.not_enough_stamina()
            self.click_relative(0.18, 0.48, after_sleep=1)
            index = self.config.get('Which Tacet Suppression to Farm', 1) - 1
            self.teleport_to_tacet(index)
            self.wait_click_travel()
            self.wait_in_team_and_world(time_out=120)
            self.sleep(1)
            if self.door_walk_method.get(index) is not None:
                for method in self.door_walk_method.get(index):
                    self.send_key_down(method[0])
                    self.sleep(method[1])
                    self.send_key_up(method[0])
                    self.sleep(0.05)
                self.run_until(self.in_combat, 'w', time_out=10, running=True)
            else:
                self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
                self.pick_f(handle_claim=False)
            self.combat_once()
            self.sleep(3)
            self.walk_to_treasure()
            self.pick_f(handle_claim=False)
            used, remaining_total, remaining_current, _ = self.use_stamina(once=self.stamina_once, max_count=counter)
            if used == 0:
                return self.not_enough_stamina()
            total_used += used
            counter -= int(used / self.stamina_once)
            self.info_set('used stamina', total_used)
            self.sleep(4)
            self.click(0.51, 0.84, after_sleep=2)
            if counter <= 0:
                self.log_info(f'{total_counter} time(s) farmed')
                return
            if self._daily_task and total_used >= 180 and remaining_current < self.stamina_once:
                return self.not_enough_stamina(back=True)
            if remaining_total < self.stamina_once:
                return self.not_enough_stamina(back=False)

    def not_enough_stamina(self, back=True):
        self.log_info(f"used all stamina")
        if back:
            self.back(after_sleep=1)

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        self.click_on_book_target(index + 1, self.total_number)
