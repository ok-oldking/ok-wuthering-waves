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
        self.stamina_once = 60

    def run(self):
        super(BaseCombatTask,self).run()
        super(WWOneTimeTask,self).run()
        timeout_second = self.config.get('Teleport Timeout', 10)
        self.tacet_serial_number = self.config.get('Tacet Suppression Serial Number', 1)
        self.wait_in_team_and_world(esc=True, time_out=timeout_second)
        self.farm_tacet()

    def farm_tacet(self):
        # ⭐ {
        timeout_second = self.config.get('Teleport Timeout', 10)
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
        
        counter = total_counter
        total_used = 0
        while counter > 0:
            gray_book_boss = self.openF2Book("gray_book_boss")
            self.click_box(gray_book_boss, after_sleep=1)
            self.click_relative(0.18, 0.48, after_sleep=1)
            index = self.tacet_serial_number - 1
            self.teleport_to_tacet(index)
            self.wait_click_travel()
            self.wait_in_team_and_world(time_out=timeout_second)
            self.sleep(max(2, timeout_second / 10)) # wait for treasure/door/enemy appear
            # } ⭐
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
            # ⭐ {
            double_drop = self.ocr(0.2, 0.56, 0.75, 0.69, match=['双倍', 'Double'])
            if counter <= 1 or (double_drop and len(double_drop) >= 1):
                used, remaining_total, _, _ = self.ensure_stamina(self.stamina_once, self.stamina_once)
                counter -= 1
            else:
                used, remaining_total, _, _ = self.ensure_stamina(self.stamina_once, 2 * self.stamina_once)
                counter -= int(used / self.stamina_once)
            total_used += used
            # } ⭐
            self.wait_click_ocr(0.2, 0.56, 0.75, 0.69, match=[str(used), '确认', 'Confirm'], raise_if_not_found=True,
                                log=True)
            self.sleep(4)
            self.click(0.51, 0.84, after_sleep=2)
            # ⭐ {
            if counter <= 0:
                self.log_info(f'{total_counter} time(s) farmed, {total_used} stamina used')
                break
            if remaining_total < self.stamina_once:
                self.log_info(f'not enough stamina, {total_used} stamina used')
                break
            # } ⭐


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
