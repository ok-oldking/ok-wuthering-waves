from ok import Logger
from src.task.TacetTask import TacetTask
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class TacetTask2(TacetTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = '⭐ Tacet Suppression'
        self.description = 'Farm selected Tacet Suppression, you need to be able to teleport'
        self.default_config = {
            'Teleport Timeout': 10,
            'Tacet Suppression Serial Number': 1, # starts with 1
            'Tacet Suppression Count': 0, # starts with 0
        }
        self.config_description = {
            'Teleport Timeout': 'the timeout of second for teleport',
            'Tacet Suppression Serial Number': 'the Nth number in the list of Tacet Suppression list (in F2 menu)',
            'Tacet Suppression Count': 'farm Tacet Suppression N time(s), 60 stamina per time, set a large number to use all stamina',
        }

    def run(self):
        super(BaseCombatTask,self).run()
        super(WWOneTimeTask,self).run()
        timeout_second = self.config.get('Teleport Timeout', 10) # ⭐
        self.wait_in_team_and_world(esc=True, time_out=timeout_second)
        self.farm_tacet()

    def farm_tacet(self):
        timeout_second = self.config.get('Teleport Timeout', 10) # ⭐
        serial_number = self.config.get('Tacet Suppression Serial Number', 0) # ⭐
        counter = self.config.get('Tacet Suppression Count', 0) # ⭐
        remaining_total = 0 # ⭐
        total_used = 0
        while counter > 0: # ⭐
            self.sleep(1)
            gray_book_boss = self.openF2Book("gray_book_boss")
            self.click_box(gray_book_boss, after_sleep=1)
            current, back_up = self.get_stamina()
            if current == -1:
                self.click_relative(0.04, 0.4, after_sleep=1)
                current, back_up = self.get_stamina()
            if current + back_up < 60:
                return self.not_enough_stamina()
            self.click_relative(0.18, 0.48, after_sleep=1)
            index = serial_number - 1 # ⭐
            self.teleport_to_tacet(index)
            self.wait_click_travel()
            self.wait_in_team_and_world(time_out=timeout_second) # ⭐
            self.sleep(max(2, timeout_second / 10)) # wait for treasure/door/enemy appear ⭐
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
            used, remaining_total, remaining_current, used_back_up = self.ensure_stamina(60, 60) # ⭐
            total_used += used
            self.info_set('used stamina', total_used)
            if not used:
                return self.not_enough_stamina()
            # self.click(0.75, 0.32, after_sleep=2) # uncomment current line and comment next 2 lines for debug (not use stamina) ⭐
            self.wait_click_ocr(0.2, 0.56, 0.75, 0.69, match=[str(used), '确认', 'Confirm'], raise_if_not_found=True,
                                log=True)
            self.sleep(4)
            self.click(0.51, 0.84, after_sleep=2)
            if remaining_total < 60:
                return self.not_enough_stamina(back=False)
            if total_used >= 180 and remaining_current == 0:
                return self.not_enough_stamina(back=True)
            counter -= 1 # ⭐


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
