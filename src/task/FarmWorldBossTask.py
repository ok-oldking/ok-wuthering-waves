import time

from ok.feature.Feature import Feature
from ok.logging.Logger import get_logger
from src.task.BaseCombatTask import BaseCombatTask

logger = get_logger(__name__)


class FarmWorldBossTask(BaseCombatTask):

    def __init__(self):
        super().__init__()
        self.description = "Click Start in Game World"
        self.name = "Farm World Boss(Must Drop a WayPoint on the Boss First)"
        self.boss_names = ['N/A', 'Crownless', 'Tempest Mephis', 'Thundering Mephis', 'Inferno Rider',
                           'Feilian Beringal',
                           'Mourning Aix', 'Impermanence Heron', 'Lampylumen Myriad', 'Mech Abomination',
                           'Bell-Borne Geochelone']
        self.weekly_boss_index = {'Bell-Borne Geochelone': 3}
        self.weekly_boss_count = 1  # Bell-Borne Geochelone
        default_config = {
            'Boss1': 'N/A',
            'Boss2': 'N/A',
            'Boss3': 'N/A',
            'Repeat Farm Count': 1000
        }
        default_config.update(self.default_config)
        self.default_config = default_config
        self.config_type["Boss1"] = {'type': "drop_down", 'options': self.boss_names}
        self.config_type["Boss2"] = {'type': "drop_down", 'options': self.boss_names}
        self.config_type["Boss3"] = {'type': "drop_down", 'options': self.boss_names}
        self.config_description = {
            'Level': '(1-6) Important, Choose which level to farm, lower levels might not produce a echo',
            'Entrance Direction': 'Choose Forward for Dreamless, Backward for Jue'
        }
        self.config_type["Entrance Direction"] = {'type': "drop_down", 'options': ['Forward', 'Backward']}
        self.crownless_pos = (0.9, 0.4)
        self.last_drop = False

    def teleport(self, boss_name):
        index = self.boss_names.index(boss_name)
        index -= 1
        self.log_info(f'teleport to {boss_name} index {index}')
        self.sleep(1)
        self.log_info('click f2 to open the book')
        self.send_key('f2')
        gray_book_boss = self.wait_until(
            lambda: self.find_one('gray_book_boss', vertical_variance=1, horizontal_variance=0.05,
                                  threshold=0.8, canny_lower=50,
                                  canny_higher=150) or self.find_one(
                'gray_book_boss_highlight',
                vertical_variance=1, horizontal_variance=0.05,
                threshold=0.8,
                canny_lower=50,
                canny_higher=150),
            time_out=3)
        if not gray_book_boss:
            self.log_error("can't find the gray_book_boss", notify=True)
            raise Exception("can't find gray_book_boss")
        if gray_book_boss.name == 'gray_book_boss':
            self.log_info(f'click {gray_book_boss}')
            self.click_box(gray_book_boss)
        self.sleep(1.5)
        self.click_relative(0.04, 0.29)
        self.sleep(1)
        if index >= (len(self.boss_names) - self.weekly_boss_count - 1):  # weekly turtle
            logger.info('click weekly boss')
            index = self.weekly_boss_index[boss_name]
            self.click_relative(0.21, 0.59)
        else:
            logger.info('click normal boss')
            self.click_relative(0.21, 0.36)
        # self.wait_click_feature('gray_book_forgery', raise_if_not_found=True, use_gray_scale=True, threshold=0.7)
        # self.wait_click_feature('gray_book_boss', raise_if_not_found=True, use_gray_scale=True, threshold=0.7)
        self.sleep(1)
        while index > 4:  # first page
            self.log_info(f'index {index} greater than 4, swipe')
            self.scroll_down_a_page()
            index -= 4
        # y = y + (index - 1) * distance
        self.log_info(f'index after scrolling down {index}')
        proceeds = self.find_feature('boss_proceed', vertical_variance=1, use_gray_scale=True, threshold=0.8)
        if self.debug:
            self.screenshot('proceeds')
        if not proceeds:
            raise Exception("can't find the boss proceeds")

        # self.click_relative(self.crownless_pos[0], self.crownless_pos[1])
        # self.wait_click_feature('gray_teleport', raise_if_not_found=True, use_gray_scale=True)
        self.wait_feature('gray_teleport', raise_if_not_found=True, use_gray_scale=True, time_out=120,
                          pre_action=lambda: self.click_box(proceeds[index], relative_x=-1))
        self.sleep(1)
        self.click_relative(0.5, 0.5)
        self.wait_click_feature('gray_custom_way_point', box=self.box_of_screen(0.62, 0.48, 0.70, 0.66),
                                raise_if_not_found=True,
                                use_gray_scale=True, threshold=0.75, time_out=2)
        travel = self.wait_feature('fast_travel_custom', raise_if_not_found=True, use_gray_scale=True, threshold=0.8)
        self.click_box(travel, relative_x=1.5)

    def check_main(self):
        if not self.in_team()[0]:
            self.send_key('esc')
            self.sleep(1)
            return self.in_team()[0]
        return True

    def scroll_down_a_page(self):
        source_box = self.box_of_screen(0.38, 0.78, 0.42, 0.80)
        source_template = Feature(source_box.crop_frame(self.frame), source_box.x, source_box.y)
        target_box = self.box_of_screen(0.38, 0.16, 0.42, 0.33)
        start = time.time()

        self.click_relative(0.5, 0.5)
        self.sleep(0.1)
        # count = 0
        while True:
            if time.time() - start > 20:
                raise Exception("scroll to long")
                # if count % 10 == 0:
            # count += 1
            self.scroll_relative(0.5, 0.5, -2)
            self.sleep(0.1)
            targets = self.find_feature('target_box', box=target_box, template=source_template)
            if targets:
                self.log_info(f'scroll to targets {targets} successfully')
                break

    def run(self):
        if not self.check_main():
            self.log_error('must be in game world and in teams', notify=True)
        self.handler.post(self.mouse_reset, 0.01)
        count = 0
        while True:
            for i in range(1, 4):
                key = 'Boss' + str(i)
                if boss_name := self.config.get(key):
                    if boss_name != 'N/A':
                        count += 1
                        self.teleport(boss_name)
                        logger.info(f'farm echo combat once start')
                        self.combat_once()
                        logger.info(f'farm echo combat end')
                        if boss_name == 'Bell-Borne Geochelone':
                            logger.info(f'sleep for the Boss model to disappear')
                            self.sleep(5)
                        self.wait_in_team_and_world(time_out=20)
                        logger.info(f'farm echo move forward walk_until_f to find echo')
                        if self.walk_until_f(time_out=6, backward_time=1,
                                             raise_if_not_found=False):  # find and pick echo
                            logger.debug(f'farm echo found echo move forward walk_until_f to find echo')
                            self.incr_drop(True)

            if count == 0:
                self.log_error('must choose at least 1 Boss to Farm', notify=True)
                return

    def incr_drop(self, dropped):
        if dropped:
            self.info['Echo Count'] = self.info.get('Echo Count', 0) + 1
        self.last_drop = dropped
