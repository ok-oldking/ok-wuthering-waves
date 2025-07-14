from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class DomainTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teleport_timeout = 100
        self.stamina_once = 0

    def make_sure_in_world(self):
        if (self.in_realm()):
            self.send_key('esc', after_sleep=1)
            self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=False,
                                    time_out=3, click_after_delay=0.5, threshold=0.7)
            self.wait_in_team_and_world(time_out=self.teleport_timeout)
        else:
            self.ensure_main()

    def open_F2_book_and_get_stamina(self):
        gray_book_boss = self.openF2Book('gray_book_boss')
        self.click_box(gray_book_boss, after_sleep=1)
        return self.get_stamina()

    def farm_in_domain(self, total_counter=0, current=0, back_up=0):
        if (self.stamina_once <= 0):
            raise RuntimeError('"self.stamina_once" must be override')
        # total counter
        if total_counter <= 0:
            self.log_info('0 time(s) farmed, 0 stamina used')
            self.make_sure_in_world()
            return
        # stamina
        if current + back_up < self.stamina_once:
            self.log_info('not enough stamina, 0 stamina used')
            self.make_sure_in_world()
            return
        # farm
        counter = total_counter
        remaining_total = 0
        total_used = 0
        while True:
            self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
            self.combat_once()
            self.sleep(3)
            self.walk_to_treasure()
            used, remaining_total, _, _ = self.ensure_stamina(self.stamina_once, 2 * self.stamina_once)
            # self.click(0.75, 0.32, after_sleep=2) # click fork of dialog (for debug)
            ocr_result = self.wait_click_ocr(0.2, 0.56, 0.75, 0.69, match=[str(used), '确认', 'Confirm'],
                                             raise_if_not_found=True,
                                             log=True)
            if ocr_result[0].name != str(used) and used != self.stamina_once:
                used = self.stamina_once
                remaining_total += self.stamina_once
            total_used += used
            counter -= int(used / self.stamina_once)
            self.sleep(4)
            if counter <= 0:
                self.log_info(f'{total_counter} time(s) farmed, {total_used} stamina used')
                break
            if remaining_total < self.stamina_once:
                self.log_info(f'not enough stamina, {total_used} stamina used')
                break
            self.click(0.68, 0.84, after_sleep=2)  # farm again
            self.wait_in_team_and_world(time_out=self.teleport_timeout)
            self.sleep(1)
        #
        self.click(0.42, 0.84, after_sleep=2)  # back to world
        self.make_sure_in_world()
