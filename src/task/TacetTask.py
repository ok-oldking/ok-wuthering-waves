from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask, CombatAbortedAfterRevive
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
        self.total_number = 16
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
            6: [["a", 0.3]],
            7: [["d", 0.6]],
            8: [["a", 1.5], ["w", 3], ["a", 2.5]],
        }
        self.stamina_once = 60

    def run(self):
        super().run()
        self.ensure_main(time_out=180)
        self.wait_in_team_and_world(esc=True)
        self.farm_tacet()

    def revive_action(self):
        """Tacet flow: same structured recovery, skipping exit-confirm steps."""
        self.log_info('tacet revive_action: recovering after character death (Tacet flow)')
        max_retries = 2
        last_error = None
        prev_skip_combat_check = self.skip_combat_check
        self.skip_combat_check = True
        try:
            for attempt in range(max_retries):
                try:
                    # Step1: close revive popup.
                    if not self._step_close_revive_popup_once():
                        raise RuntimeError('step1 close revive popup failed')
                    # Skip Forgery/Simulation step2+step3 (ESC -> confirm exit).
                    # Step4: reuse weekly entrance route.
                    if not self.go_to_weekly_entrance_for_recovery():
                        raise RuntimeError('step4 go weekly entrance failed')
                    # Step5: open map.
                    if not self._step_open_map_once():
                        raise RuntimeError('step5 open map failed')
                    # Step6: fast travel left waypoint.
                    if not self._step_fast_travel_left_waypoint_once():
                        raise RuntimeError('step6 fast travel left waypoint failed')
                    raise CombatAbortedAfterRevive('tacet recovered after character death')
                except CombatAbortedAfterRevive:
                    raise
                except Exception as e:
                    last_error = e
                    self.log_error(f'tacet revive_action: recovery failed attempt {attempt + 1}/{max_retries}', e)
                    self._force_reset_to_main_after_recovery_failure()
        finally:
            self.skip_combat_check = prev_skip_combat_check
        if last_error:
            self.log_error('tacet revive_action: all retries failed', last_error)
        raise CombatAbortedAfterRevive('tacet recovery attempted with partial failure')

    def _force_reset_to_main_after_recovery_failure(self):
        self.log_info('tacet revive_action: force reset to main')
        # If we failed while map is open, close it first to avoid ESC opening/closing other modals.
        if self._is_map_open_for_recovery():
            self.send_key('m')
            self._recovery_pause(1.5)
        for _ in range(3):
            self.send_key('esc')
            self._recovery_pause(1.5)
            self._dismiss_exit_confirm_popup(prefer_confirm=False)
            if self.in_team_and_world():
                return
        self.ensure_main(esc=True, time_out=60)

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
            gray_book_boss = self.openF2Book("gray_book_boss")
            self.click_box(gray_book_boss, after_sleep=1)
            current, back_up, total = self.get_stamina()
            if current == -1:
                self.click_relative(0.04, 0.4, after_sleep=1)
                current, back_up, total = self.get_stamina()
            if total < self.stamina_once:
                return self.not_enough_stamina()

            self.click_relative(0.18, 0.48, after_sleep=1)
            index = config.get('Which Tacet Suppression to Farm', 1) - 1
            self.teleport_to_tacet(index)
            self.wait_click_travel()
            self.wait_in_team_and_world(time_out=120)
            self.sleep(2)
            if self.door_walk_method.get(index) is not None:
                for method in self.door_walk_method.get(index):
                    self.send_key_down(method[0])
                    self.sleep(method[1])
                    self.send_key_up(method[0])
                    self.sleep(0.05)
                in_combat = self.run_until(self.in_combat, 'w', time_out=10, running=True,
                                           target=False, post_walk=1)
                if not in_combat:
                    raise Exception('Tacet can not walk to combat')
            else:
                self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
                self.pick_f(handle_claim=False)
            try:
                self.combat_once()
                self.sleep(3)
                self.walk_to_treasure()
                self.pick_f(handle_claim=False)
            except CombatAbortedAfterRevive:
                self.log_info('farm_tacet: death recovery, retry from F2 book')
                try:
                    self.ensure_main(esc=False, time_out=180)
                except Exception as e:
                    self.log_error('farm_tacet: ensure_main after death recovery failed, continue', e)
                continue
            can_continue, used = self.use_stamina(once=self.stamina_once, must_use=must_use)
            self.info_incr('used stamina', used)
            self.sleep(4)
            self.click(0.51, 0.84, after_sleep=3)
            if not can_continue:
                return self.not_enough_stamina()
            must_use -= used

    def not_enough_stamina(self, back=True):
        self.log_info(f"used all stamina")
        if back:
            self.back(after_sleep=1)

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        self.click_on_book_target(index + 1, self.total_number)
