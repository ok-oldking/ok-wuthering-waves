import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask, CombatAbortedAfterRevive
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class DomainTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teleport_timeout = 100
        self.stamina_once = 0
        self.group_name = "Dungeon"
        self.group_icon = FluentIcon.HOME

    def make_sure_in_world(self):
        if self.in_realm():
            exited = self.exit_realm_to_world(time_out=self.teleport_timeout, retries=2)
            if not exited:
                self.log_error('make_sure_in_world: exit_realm_to_world failed, fallback ensure_main with esc')
                self.ensure_main(esc=True, time_out=self.teleport_timeout)
        else:
            try:
                self.ensure_main(esc=False)
            except Exception:
                # 兜底允许一次退层，避免卡在确认离开等弹窗导致主流程中断。
                self.ensure_main(esc=True)

    def open_F2_book_and_get_stamina(self):
        gray_book_boss = self.openF2Book('gray_book_boss')
        self.click_box(gray_book_boss, after_sleep=1)
        return self.get_stamina()

    def farm_in_domain(self, must_use=0):
        if self.stamina_once <= 0:
            raise RuntimeError('"self.stamina_once" must be override')
        self.info_incr('used stamina', 0)
        while True:
            try:
                self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
                self.pick_f()
                self.combat_once()
                self.sleep(3)
                self.walk_to_treasure()
                self.pick_f(handle_claim=False)
            except CombatAbortedAfterRevive:
                self.log_info('farm_in_domain: death recovery left instance, stopping domain farm loop')
                self.make_sure_in_world()
                return False, must_use
            can_continue, used = self.use_stamina(once=self.stamina_once, must_use=must_use)
            self.info_incr('used stamina', used)
            must_use -= used
            self.sleep(4)
            if not can_continue:
                self.log_info("used all stamina")
                break
            self.click(0.68, 0.84, after_sleep=1)  # farm again
            if confirm := self.wait_feature(
                    ['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                    raise_if_not_found=False,
                    threshold=0.6,
                    time_out=2):
                self.click(0.49, 0.55, after_sleep=0.5)  # 点击不再提醒
                self.click(confirm, after_sleep=0.5)
                self.wait_click_feature(
                    ['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter'],
                    relative_x=-1, raise_if_not_found=False,
                    threshold=0.6,
                    time_out=1)
            self.wait_in_team_and_world(time_out=self.teleport_timeout)
            self.sleep(1)
        #
        self.click(0.42, 0.84, after_sleep=2)  # back to world
        self.make_sure_in_world()
        return True, must_use
