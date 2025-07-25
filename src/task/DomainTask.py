import re

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
            # in domain with exit icon on top-left, click exit icon and confirm to exit
            self.send_key('esc', after_sleep=1)
            self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=False,
                                    time_out=3, click_after_delay=0.5, threshold=0.7)
            self.wait_in_team_and_world(time_out=self.teleport_timeout)
            return
        while (not self.is_main(esc=False)):
            # no earth icon on top-left, back until it appear
            self.back()
            self.sleep(2)
        # final confirm
        self.ensure_main()

    def open_F2_book_and_get_stamina(self):
        gray_book_boss = self.openF2Book('gray_book_boss')
        self.click_box(gray_book_boss, after_sleep=1)
        return self.get_stamina()

    def farm_in_domain(self, must_use=0):
        if self.stamina_once <= 0:
            raise RuntimeError('"self.stamina_once" must be override')
        self.info_incr('used stamina', 0)
        while True:
            self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
            self.pick_f()
            self.combat_once()
            self.sleep(3)
            self.walk_to_treasure()
            self.pick_f(handle_claim=False)
            can_continue, used = self.use_stamina(once=self.stamina_once, must_use=must_use)
            self.info_incr('used stamina', used)
            must_use -= used
            if not can_continue:
                self.log_info(f'not enough stamina', notify=True)
                self.back()
                break
            must_use -= used
            self.sleep(4)
            self.click(0.68, 0.84, after_sleep=2)  # farm again
            self.wait_in_team_and_world(time_out=self.teleport_timeout)
            self.sleep(1)
        #
        self.click(0.42, 0.84, after_sleep=2)  # back to world
        self.make_sure_in_world()
