from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask, CharRevivedException
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class TacetTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.group_name = "Dungeon"
        self.group_icon = FluentIcon.HOME
        self.description = "Farms the selected Tacet Suppression, until no stamina. Must be able to teleport (F2)."
        self.name = "Tacet Suppression"
        self.support_schedule_task = True
        default_config = {
            'Which Tacet Suppression to Farm': 1,  # starts with 1
        }
        self.total_number = 17
        self.target_enemy_time_out = 10
        default_config.update(self.default_config)
        self.config_description = {
            'Which Tacet Suppression to Farm': 'The Tacet Suppression number in the F2 list.',
        }
        self.default_config = default_config
        self.door_walk_method = {  # starts with 0
            0: [],
            1: [],
            2: [],
            3: [],
            4: [],
            5: [],
            6: [],
            7: [["a", 0.3]],
            8: [["d", 0.6]],
            9: [["a", 1.5], ["w", 3], ["a", 2.5]],
        }
        self.stamina_once = 60

    def run(self):
        super().run()
        self.ensure_main(time_out=180)
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
            self.openF2Book("gray_book_boss")
            current, back_up, total = self.get_stamina()
            if current == -1:
                self.click_relative(0.04, 0.4, after_sleep=1)
                current, back_up, total = self.get_stamina()
            if total < self.stamina_once:
                return self.not_enough_stamina()

            self.open_boss_book('wuyin')
            index = config.get('Which Tacet Suppression to Farm', 1) - 1
            self.teleport_to_tacet(index)
            self.click_team_challenge()
            while True:
                self.wait_in_team_and_world(time_out=120)
                self.combat_once(target=True)
                self.walk_to_treasure()
                self.pick_f(handle_claim=False)
                if not self.has_claim_stamina():
                    self.click(0.352, 0.624, after_sleep=1)
                    self.log_info('is not claim treasure, restart challenge')
                    continue
                can_continue, used = self.use_stamina(once=self.stamina_once, must_use=must_use)
                self.info_incr('used stamina', used)
                self.sleep(4)
                if not can_continue:
                    self.click(0.365, 0.853)
                    self.wait_in_team_and_world(time_out=120)
                    return None
                else:
                    self.click(0.640, 0.851, after_sleep=3)
                must_use -= used

    def not_enough_stamina(self, back=True):
        self.log_info(f"used all stamina")
        if back:
            self.back(after_sleep=1)

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        return self.click_on_book_target(index + 1, self.total_number)
