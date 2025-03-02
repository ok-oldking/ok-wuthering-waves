from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask

logger = Logger.get_logger(__name__)


class TacetTask(BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "Farm selected Tacet Suppression until out of stamina, will use the backup stamina, you need to be able to teleport from the menu(F2)"
        self.name = "Tacet Suppression (Must explore first to be able to teleport)"
        default_config = {
            'Which Tacet Suppression to Farm': 1  # starts with 1
        }
        self.row_per_page = 5
        self.total_number = 10
        default_config.update(self.default_config)
        self.config_description = {
            'Which Tacet Suppression to Farm': 'the Nth number in the Tacet Suppression list (F2)',
        }
        self.default_config = default_config
        self.door_walk_method = {  # starts with 0
            0: [["a", 0.3]],
            1: [["d", 0.6]],
            2: [["a", 1.6], ["w", 3], ["a", 2.5]],
        }

    def run(self):
        self.wait_in_team_and_world(esc=True)
        self.farm_tacet()

    def farm_tacet(self):
        total_used = 0
        while True:
            self.openF2Book()
            self.click_relative(0.04, 0.27, after_sleep=1)
            current, back_up = self.get_stamina()
            if current + back_up < 60:
                return self.not_enough_stamina()
            self.click_relative(0.18, 0.48, after_sleep=1)
            index = self.config.get('Which Tacet Suppression to Farm', 1) - 1
            self.teleport_to_tacet(index)
            self.wait_click_travel()
            self.wait_in_team_and_world()
            self.sleep(1)
            if methods := self.door_walk_method.get(index):
                for method in methods:
                    self.send_key_down(method[0])
                    self.sleep(method[1])
                    self.send_key_up(method[0])
                    self.sleep(0.05)
                self.run_until(self.in_combat, 'w', time_out=10, running=True)
            else:
                self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
            self.combat_once()
            self.walk_to_box(self.find_treasure_icon)
            self.walk_until_f(time_out=2, backward_time=0, raise_if_not_found=True, cancel=False)
            self.sleep(1)
            used, remaining_total, remaining_current, used_back_up = self.ensure_stamina(60, 120)
            total_used += used
            self.info_set('used stamina', total_used)
            if not used:
                return self.not_enough_stamina()
            self.wait_click_ocr(0.02, 0.56, 0.67, 0.67, match=str(used), raise_if_not_found=True)
            self.sleep(4)
            self.click(0.51, 0.84, after_sleep=1)
            if remaining_total < 60:
                return self.not_enough_stamina(back=False)
            if total_used >= 180 and remaining_current == 0:
                return self.not_enough_stamina(back=True)

    def not_enough_stamina(self, back=True):
        self.log_info(f"used all stamina", notify=True)
        if back:
            self.back(after_sleep=1)

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        if index >= self.row_per_page:
            index -= self.row_per_page
            self.click_relative(0.98, 0.86)
            self.log_info(f'teleport_to_tacet scroll down a page new index: {index}')
        x = 0.88
        height = (0.85 - 0.28) / 4
        y = 0.25
        y += height * index
        self.click_relative(x, y)


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
