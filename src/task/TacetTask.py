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
            'Which Tacet Suppression to Farm': 1  # starts with 1
        }
        self.row_per_page = 5
        self.total_number = 11
        self.target_enemy_time_out = 6
        default_config.update(self.default_config)
        self.config_description = {
            'Which Tacet Suppression to Farm': 'the Nth number in the Tacet Suppression list (F2)',
        }
        self.default_config = default_config
        self.door_walk_method = {  # starts with 0
            0:[],
            1: [["a", 0.3]],
            2: [["d", 0.6]],
            3: [["a", 1.5], ["w", 3], ["a", 2.5]],
        }

    def run(self):
        super().run()
        self.wait_in_team_and_world(esc=True)
        self.farm_tacet()

    def farm_tacet(self):
        total_used = 0
        while True:
            gray_book_boss = self.openF2Book("gray_book_boss")
            self.click_box(gray_book_boss, after_sleep=1)
            current, back_up = self.get_stamina()
            if current == -1:
                self.click_relative(0.04, 0.4, after_sleep=1)
                current, back_up = self.get_stamina()
            if current + back_up < 60:
                return self.not_enough_stamina()
            self.click_relative(0.18, 0.48, after_sleep=1)
            index = self.config.get('Which Tacet Suppression to Farm', 1) - 1
            self.teleport_to_tacet(index)
            self.wait_click_travel()
            self.wait_in_team_and_world()
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
            self.combat_once()
            self.walk_to_treasure()
            used, remaining_total, remaining_current, used_back_up = self.ensure_stamina(60, 120)
            total_used += used
            self.info_set('used stamina', total_used)
            if not used:
                return self.not_enough_stamina()
            self.wait_click_ocr(0.2, 0.56, 0.75, 0.69, match=[str(used), '确认', 'Confirm'], raise_if_not_found=True, log=True)
            self.sleep(4)
            self.click(0.51, 0.84, after_sleep=2)
            if remaining_total < 60:
                return self.not_enough_stamina(back=False)
            if total_used >= 180 and remaining_current == 0:
                return self.not_enough_stamina(back=True)


    def walk_to_treasure(self, retry=0):
        if retry > 4:
            raise RuntimeError('walk_to_treasure too many retries!')
        if self.find_treasure_icon():
            self.walk_to_box(self.find_treasure_icon, end_condition=self.find_f_with_text)
        self.walk_until_f(time_out=2, backward_time=0, raise_if_not_found=True, cancel=False)
        self.sleep(1)
        if self.find_treasure_icon():
            self.log_info('retry walk_to_treasure')
            self.walk_to_treasure(retry=retry + 1)

    def not_enough_stamina(self, back=True):
        self.log_info(f"used all stamina", notify=True)
        if back:
            self.back(after_sleep=1)

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        if index >= self.row_per_page:
            if index >= self.row_per_page * 2: # page 3
                self.click_relative(0.98, 0.86)
                index -= self.row_per_page + 1 # only 1 in last page
            else:
                index -= self.row_per_page
                self.click_relative(0.98, 0.8)
            self.log_info(f'teleport_to_tacet scroll down a page new index: {index}')
        x = 0.88
        height = (0.85 - 0.28) / 4
        y = 0.275
        y += height * index
        self.click_relative(x, y, after_sleep=2)

echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
