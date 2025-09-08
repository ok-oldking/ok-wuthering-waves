from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class TacetTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.description = "Farms the selected Tacet Suppression, until no stamina. Must be able to teleport (F2)."
        self.name = "Tacet Suppression"
        default_config = {
            'Which Tacet Suppression to Farm': 1,  # starts with 1
        }
        self.total_number = 12
        self.target_enemy_time_out = 10
        default_config.update(self.default_config)
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
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

    def run(self):
        super().run()
        self.wait_in_team_and_world(esc=True)
        self.farm_tacet()

    def farm_tacet(self, daily=False, used_stamina=0, config=None):
        if config is None:
            config = self.config
        if daily:
            must_use = 180 - used_stamina
        else:
            must_use = 0
        self.info_incr('used stamina', 0)
        while True:
            self.sleep(1)
            gray_book_boss = self.openF2Book("gray_book_boss")
            self.click_box(gray_book_boss, after_sleep=1)
            current, back_up, total = self.get_stamina()
            if current == -1:
                self.click_relative(0.04, 0.4, after_sleep=1)
                current, back_up, total = self.get_stamina()
            if total < self.stamina_once:
                return self.not_enough_stamina()

            self.click_relative(0.18, 0.48, after_sleep=1)
            index = config.get('Which Tacet Suppression to Farm', 1) - 1
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
            can_continue, used = self.use_stamina(once=self.stamina_once, must_use=must_use)
            self.info_incr('used stamina', used)
            self.sleep(4)
            self.click(0.51, 0.84, after_sleep=2)
            if not can_continue:
                return self.not_enough_stamina()
            must_use -= used

    def not_enough_stamina(self, back=True):
        self.log_info(f"used all stamina")
        if back:
            self.back(after_sleep=1)

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        self.click_on_book_target(index + 1, self.total_number)
