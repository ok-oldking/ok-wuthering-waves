from ok import Logger
from ok.task.exceptions import WaitFailedException
from src.task.BaseCombatTask import BaseCombatTask, NotInCombatException, CharDeadException
from src.task.BaseWWTask import RECHALLENGE_TEXT
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class DomainTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teleport_timeout = 100
        self.stamina_once = 0

    def revive_action(self):
        """副本内死亡恢复：关闭弹窗 → 退出副本 → 传最近传送点回血。"""

        # ① 关闭复活弹窗 (点按钮优先, esc 兜底, 与 BaseCombatTask 共用)
        self.close_revive_popup()

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
        if self.realm_entry_at_heal_point:
            logger.info('revive_action: left realm at heal point, skip teleport')
            return True
        self.revive_at_tower_and_heal()
        return True

    def make_sure_in_world(self):
        if self.in_realm():
            self.send_key('esc', after_sleep=1)
            self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=False,
                                    time_out=3, click_after_delay=0.5, threshold=0.7, after_sleep=1)
            self.wait_in_team_and_world(time_out=self.teleport_timeout)
        else:
            self.ensure_main()

    def open_F2_book_and_get_stamina(self):
        self.openF2Book('gray_book_boss')
        return self.get_stamina()

    def farm_domain_with_recovery_loop(self, must_use, teleport_into_domain_once, max_recovery_retries=3):
        """刷本中断后从 F2 重新进入，并限制重试次数。"""
        recovery_retries = 0
        self.realm_entry_at_heal_point = False
        while True:
            current, _, total = self.open_F2_book_and_get_stamina()
            if total < self.stamina_once or total < must_use or (must_use == 0 and current < self.stamina_once):
                self.log_info(self.tr('not enough stamina'), notify=True)
                self.back()
                return
            teleport_into_domain_once()
            self.sleep(1)
            finished, must_use = self.farm_in_domain(must_use=must_use)
            if finished:
                return
            recovery_retries += 1
            if recovery_retries >= max_recovery_retries:
                self.log_info(self.tr('farm_domain: exceeded recovery retries ({max_recovery_retries}), stop farming').format(max_recovery_retries=max_recovery_retries),
                              notify=True)
                self.make_sure_in_world()
                return
            if self.realm_entry_at_heal_point:
                self.log_info(self.tr('farm_domain: death recovered, re-enter from F2 book'))
            self.sleep(1)

    def farm_in_domain(self, must_use=0):
        """刷本循环；返回 (是否整段正常结束, 剩余 must_use)。

        提前退出时保留剩余体力额度，供外层恢复循环继续刷取。
        """
        if self.stamina_once <= 0:
            raise RuntimeError(self.tr('"self.stamina_once" must be override'))
        self.info_incr('used stamina', 0)
        rechallenging = False
        while True:
            if not self.walk_until_f(time_out=4, raise_if_not_found=not rechallenging):
                return self.recover_domain_rechallenge(must_use)
            self.pick_f()
            try:
                self.combat_once()
                self.sleep(3)
                self.walk_to_treasure()
                self.pick_f(handle_claim=False)
            except (NotInCombatException, CharDeadException):
                self.log_info(self.tr('farm_in_domain: death recovered, exiting domain'))
                self.make_sure_in_world()
                self.realm_entry_at_heal_point = True
                return False, must_use
            can_continue, used = self.use_stamina(once=self.stamina_once, must_use=must_use)
            self.info_incr('used stamina', used)
            must_use -= used
            self.sleep(4)
            if not can_continue:
                self.log_info(self.tr('used all stamina'))
                break
            try:
                self.rechallenge_domain()
            except WaitFailedException:
                return self.recover_domain_rechallenge(must_use)
            rechallenging = True

        self.click(0.42, 0.84, after_sleep=2)  # back to world
        self.make_sure_in_world()
        return True, must_use

    def rechallenge_domain(self):
        buttons = self.wait_ocr(0.54, 0.79, 0.82, 0.92, match=RECHALLENGE_TEXT,
                                time_out=2, raise_if_not_found=False)
        if buttons:
            self.click(buttons[0], after_sleep=1)
        else:
            self.click(0.68, 0.84, after_sleep=1)
        confirm_features = ['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter']
        if confirm := self.wait_feature(confirm_features, threshold=0.6, time_out=2, raise_if_not_found=False):
            self.click(0.49, 0.55, after_sleep=0.5)  # 点击不再提醒
            self.click(confirm, after_sleep=0.5)
            self.wait_click_feature(confirm_features, relative_x=-1, raise_if_not_found=False,
                                    threshold=0.6, time_out=1)
        self.wait_in_team_and_world(time_out=self.teleport_timeout)
        self.sleep(1)

    def recover_domain_rechallenge(self, must_use):
        logger.warning('Domain rechallenge did not reach the next start prompt. Re-entering from the guidebook.')
        self.make_sure_in_world()
        self.realm_entry_at_heal_point = False
        return False, must_use
