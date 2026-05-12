import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException, CharDeadException
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class DomainTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teleport_timeout = 100
        self.stamina_once = 0
        self.group_name = "Dungeon"
        self.group_icon = FluentIcon.HOME

    def revive_action(self):
        """副本内死亡恢复：关闭弹窗 → 退出副本 → 传周本入口 → 传最近传送点。"""

        # ① 关闭复活弹窗：优先点击弹窗按钮（避免 ESC 注入不生效），失败再回退 ESC
        closed_by_click = False
        if self.wait_click_feature('cancel_button_hcenter_vcenter',
                                   raise_if_not_found=False,
                                   time_out=1.2,
                                   click_after_delay=0.2,
                                   threshold=0.7):
            closed_by_click = True
        else:
            btn_dialog_close = self.find_one('btn_dialog_close', threshold=0.8)
            if btn_dialog_close:
                self.click(btn_dialog_close, move_back=True)
                closed_by_click = True
        if not closed_by_click:
            self.send_key('esc', after_sleep=2)
            self.sleep(1)

        # ② 打开退出菜单
        self.send_key('esc')
        self.sleep(1)

        # ③ 确认离开
        self.wait_click_feature('gray_confirm_exit_button',
                                relative_x=-1, raise_if_not_found=False,
                                time_out=3, click_after_delay=0.5, threshold=0.7)

        # ④ 必须确认已回到大世界队伍态后，再继续走 F2/传送流程
        if not self.wait_in_team_and_world(time_out=max(self.teleport_timeout, 120), raise_if_not_found=False):
            return False
        self.sleep(0.5)
        self.revive_at_tower_and_heal()
        return True

    def make_sure_in_world(self):
        if self.in_realm():
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

    def farm_domain_with_recovery_loop(self, must_use, teleport_into_domain_once, max_recovery_retries=3):
        """包装副本刷取循环：死亡恢复后自动从 F2 重新进入，并限制重试次数。"""
        recovery_retries = 0
        while True:
            current, _, total = self.open_F2_book_and_get_stamina()
            if total < self.stamina_once or total < must_use or (must_use == 0 and current < self.stamina_once):
                self.log_info('not enough stamina', notify=True)
                self.back()
                return
            teleport_into_domain_once()
            self.sleep(1)
            finished = self.farm_in_domain(must_use=must_use)
            if finished:
                return
            recovery_retries += 1
            if recovery_retries >= max_recovery_retries:
                self.log_info(f'farm_domain: exceeded recovery retries ({max_recovery_retries}), stop farming',
                              notify=True)
                self.make_sure_in_world()
                return
            self.log_info('farm_domain: death recovered, re-enter from F2 book')
            self.sleep(1)

    def farm_in_domain(self, must_use=0):
        if self.stamina_once <= 0:
            raise RuntimeError('"self.stamina_once" must be override')
        self.info_incr('used stamina', 0)
        while True:
            self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
            self.pick_f()
            try:
                self.combat_once()
                self.sleep(3)
                self.walk_to_treasure()
                self.pick_f(handle_claim=False)
            except (NotInCombatException, CharDeadException):
                self.log_info('farm_in_domain: death recovered, exiting domain')
                self.make_sure_in_world()
                return False
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
        return True
