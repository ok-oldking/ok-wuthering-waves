import re

from ok.logging.Logger import get_logger
from src.task.BaseCombatTask import BaseCombatTask

logger = get_logger(__name__)


class FarmEchoTask(BaseCombatTask):

    def __init__(self):
        super().__init__()
        self.description = "Click Start at the Entrance(Dreamless, Jue)"
        self.name = "Farm Echo in Dungeon"
        self.default_config.update({
            'Level': 1,
            'Repeat Farm Count': 100,
            'Entrance Direction': 'Forward'
        })
        self.config_description = {
            'Level': '(1-6) Important, Choose which level to farm, lower levels might not produce a echo',
            'Entrance Direction': 'Choose Forward for Dreamless, Backward for Jue'
        }
        self.config_type["Entrance Direction"] = {'type': "drop_down", 'options': ['Forward', 'Backward']}
        self.crownless_pos = (0.9, 0.4)
        self.last_drop = False

    def run(self):
        # return self.run_in_circle_to_find_echo()
        self.handler.post(self.mouse_reset, 0.01)
        if not self.in_team()[0]:
            self.log_error('must be in game world and in teams', notify=True)
            return

        # loop here
        count = 0

        while count < self.config.get("Repeat Farm Count", 0):
            count += 1
            self.wait_in_team_and_world(time_out=20)
            self.sleep(1)
            self.walk_until_f(time_out=10,
                              direction='w' if self.config.get('Entrance Direction') == 'Forward' else 's',
                              raise_if_not_found=True)
            logger.info(f'enter success')
            stam = self.wait_ocr(0.75, 0.02, 0.85, 0.09, match=re.compile('240'), raise_if_not_found=True)
            logger.info(f'found stam {stam}')
            self.sleep(1)
            self.choose_level(self.config.get("Level"))

            self.combat_once()
            logger.info(f'farm echo combat end')
            self.wait_in_team_and_world(time_out=20)
            logger.info(f'farm echo move {self.config.get("Entrance Direction")} walk_until_f to find echo')
            if self.config.get('Entrance Direction') == 'Forward':
                dropped = self.walk_until_f(time_out=3,
                                            raise_if_not_found=False)  # find and pick echo
                logger.debug(f'farm echo found echo move forward walk_until_f to find echo')
            else:
                self.sleep(2)
                dropped = self.run_in_circle_to_find_echo(3)
            self.incr_drop(dropped)
            self.sleep(0.5)
            self.send_key('esc')
            self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=True,
                                    use_gray_scale=True)
            self.wait_in_team_and_world(time_out=40)
            self.sleep(4)
            if self.config.get('Entrance Direction') == 'Backward':
                self.send_key('a', down_time=0.2)  # Jue
                self.sleep(1)

    def incr_drop(self, dropped):
        if dropped:
            self.info['Echo Count'] = self.info.get('Echo Count', 0) + 1
        self.last_drop = dropped

    def choose_level(self, start):
        y = 0.17
        x = 0.15
        distance = 0.08
        
        logger.info(f'choose level {start}')
        self.click_relative(x, y + (start - 1) * distance)
        self.sleep(0.5)

        self.wait_click_feature('gray_button_challenge', raise_if_not_found=True, use_gray_scale=True,
                                click_after_delay=0.5)
        self.wait_click_feature('gray_confirm_exit_button', relative_x=-1, raise_if_not_found=False,
                                use_gray_scale=True, time_out=3, click_after_delay=0.5, threshold=0.8)
        self.wait_click_feature('gray_start_battle', relative_x=-1, raise_if_not_found=True,
                                use_gray_scale=True, click_after_delay=0.5, threshold=0.8)


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
