import time

from ok import Logger
from src.char.BaseChar import BaseChar
from src.char.YangYangSpPolicy import YangYangSpPolicy
from src.char.YangYangSpVision import YangYangSpVision


class YangYangSp(BaseChar):
    POLL_INTERVAL = 0.05
    NORMAL_ATTACK_INTERVAL = 0.1
    LONG_PRESS_RELEASE_DELAY = 0.1
    DISPLAY_NAME = 'Yangyang: Xuanling'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = Logger.get_logger(self.DISPLAY_NAME)
        self.vision = YangYangSpVision()
        self.left_held = False

    @property
    def display_name(self):
        return self.DISPLAY_NAME

    def __repr__(self):
        return self.DISPLAY_NAME

    def do_perform(self):
        self.perform_rotation()
        self.switch_next_char()

    def observe_state(self):
        # Every decision uses one captured frame for all icons and ready rings.
        return self.vision.observe(self.task.frame, self.task.find_one)

    def perform_rotation(self):
        policy = YangYangSpPolicy()
        start = time.time()
        previous_action = None
        try:
            while True:
                self.check_combat()
                state = self.observe_state()
                elapsed = self.time_elapsed_accounting_for_freeze(start)
                # Do not run expensive general skill checks during a protected hold.
                idle = policy.hold_started is None and not (state.heavy_ready or state.followup)
                can_r = idle and state.liberation_ready and not policy.r_used and self.task.use_liberation
                can_q = (idle and state.normal and not policy.q_used and not state.enhanced_e
                         and not can_r and self.echo_available())
                con_full = idle and policy.heavy_ends > 0 and self.is_con_full()
                action = policy.choose(state, elapsed, can_r=can_r, can_q=can_q, con_full=con_full)
                if policy.feedback:
                    self.logger.debug(policy.feedback)
                if (action, policy.reason) != previous_action:
                    self.logger.debug(f'action={action} reason={policy.reason} elapsed={elapsed:.3f}')
                    previous_action = (action, policy.reason)
                if action == 'switch':
                    break
                if action == 'hold':
                    self.start_long_press()
                elif action == 'release':
                    self.release_long_press()
                    if policy.reason == 'heavy_timeout_unconfirmed':
                        self.logger.warning('Yangyang heavy timed out without a stable normal icon; releasing input')
                elif action == 'E':
                    self.release_long_press()
                    self.send_resonance_key()
                    self.record_resonance_use()
                elif action == 'R':
                    self.release_long_press()
                    self.click_liberation(send_click=False, wait_if_cd_ready=0, click_f=False)
                elif action == 'Q':
                    self.release_long_press()
                    self.click_echo(time_out=0)
                elif action == 'normal':
                    self.release_long_press()
                    self.click(interval=self.NORMAL_ATTACK_INTERVAL)
                self.sleep(self.POLL_INTERVAL)
                self.task.next_frame()
        finally:
            # Always release on combat exit, exception, pause, or timeout.
            self.task.mouse_up()
            self.left_held = False
            self.sleep(self.LONG_PRESS_RELEASE_DELAY, check_combat=False)

    def start_long_press(self):
        if not self.left_held:
            self.task.mouse_down()
            self.left_held = True

    def release_long_press(self):
        if self.left_held:
            self.task.mouse_up()
            self.left_held = False
