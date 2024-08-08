import time

from ok.feature.Feature import Feature
from ok.logging.Logger import get_logger
from src.task.BaseCombatTask import BaseCombatTask, CharDeadException

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
        self.find_echo_method = ['Walk', 'Run in Circle', 'Turn Around and Search']

        self.weekly_boss_index = {'Bell-Borne Geochelone': 3}
        self.weekly_boss_count = 1  # Bell-Borne Geochelone
        default_config = {
            'Boss1': 'N/A',
            'Boss1 Echo Pickup Method': 'Turn Around and Search',
            'Boss2': 'N/A',
            'Boss2 Echo Pickup Method': 'Turn Around and Search',
            'Boss3': 'N/A',
            'Boss3 Echo Pickup Method': 'Turn Around and Search',
            'Repeat Farm Count': 1000
        }
        self.config_type['Boss1 Echo Pickup Method'] = {'type': "drop_down", 'options': self.find_echo_method}
        self.config_type['Boss2 Echo Pickup Method'] = {'type': "drop_down", 'options': self.find_echo_method}
        self.config_type['Boss3 Echo Pickup Method'] = {'type': "drop_down", 'options': self.find_echo_method}
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

    def teleport_to_boss(self, boss_name):
        index = self.boss_names.index(boss_name)
        index -= 1
        self.log_info(f'teleport to {boss_name} index {index}')
        self.sleep(1)
        self.log_info('click f2 to open the book')
        self.send_key('f2')
        gray_book_boss = self.wait_book()
        if not gray_book_boss:
            self.log_error("can't find gray_book_boss, make sure f2 is the hotkey for book", notify=True)
            raise Exception("can't find gray_book_boss, make sure f2 is the hotkey for book")

        self.log_info(f'click {gray_book_boss}')
        self.click_box(gray_book_boss)
        self.sleep(1.5)

        if index >= (len(self.boss_names) - self.weekly_boss_count - 1):  # weekly turtle
            logger.info('click weekly boss')
            index = self.weekly_boss_index[boss_name]
            self.click_relative(0.21, 0.59)
        else:
            logger.info('click normal boss')
            self.click_relative(0.21, 0.36)

        self.sleep(1)

        if index > 4:
            self.log_info(f'click scroll bar')
            self.click_relative(3760 / 3840, 1852 / 2160)
            self.sleep(0.5)
            index -= 4

        self.log_info(f'index after scrolling down {index}')
        proceeds = self.find_feature('boss_proceed', vertical_variance=1, horizontal_variance=0.05, threshold=0.8)
        if self.debug:
            self.screenshot('proceeds')
        if not proceeds:
            raise Exception("can't find the boss proceeds")

        self.wait_feature('gray_teleport', raise_if_not_found=True, time_out=200,
                          pre_action=lambda: self.click_box(proceeds[index], relative_x=-1), wait_until_before_delay=5)
        self.sleep(1)
        teleport = self.wait_click_feature('custom_teleport_hcenter_vcenter',
                                           box=self.box_of_screen(0.48, 0.45, 0.54, 0.58),
                                           raise_if_not_found=False, threshold=0.8, time_out=2)
        if not teleport:
            self.click_relative(0.5, 0.5, hcenter=True)
        self.sleep(0.5)
        self.wait_click_feature('gray_custom_way_point', box=self.box_of_screen(0.62, 0.48, 0.70, 0.86),
                                raise_if_not_found=True, threshold=0.75, time_out=2)
        self.click_fast_travel()
        self.wait_in_team_and_world(time_out=120)

    def click_fast_travel(self):
        travel = self.wait_feature('fast_travel_custom', raise_if_not_found=True, threshold=0.75)
        self.click_box(travel, relative_x=1.5)

    def wait_book(self):
        gray_book_boss = self.wait_until(
            lambda: self.find_one('gray_book_boss', vertical_variance=0.8, horizontal_variance=0.05,
                                  threshold=0.7, canny_lower=50,
                                  canny_higher=150) or self.find_one(
                'gray_book_boss_highlight',
                vertical_variance=1, horizontal_variance=0.05,
                threshold=0.7,
                canny_lower=50,
                canny_higher=150),
            time_out=3)
        return gray_book_boss

    def check_main(self):
        if not self.in_team()[0]:
            self.send_key('esc')
            self.sleep(1)
            return self.in_team()[0]
        return True

    # not current in use because not stable, right now using one click to scroll down
    def scroll_down_a_page(self):
        source_box = self.box_of_screen(0.38, 0.80, 0.42, 0.83)
        source_template = Feature(source_box.crop_frame(self.frame), source_box.x, source_box.y)
        target_box = self.box_of_screen(0.38, 0.16, 0.42, 0.31)
        start = time.time()

        self.click_relative(0.5, 0.5)
        self.sleep(0.1)
        while True:
            if time.time() - start > 20:
                raise Exception("scroll to long")
            self.scroll_relative(0.5, 0.5, -1)
            self.sleep(0.1)
            targets = self.find_feature('target_box', box=target_box, template=source_template)
            if targets:
                self.log_info(f'scroll to targets {targets} successfully')
                break

    def teleport_to_heal(self):
        self.info['Death Count'] = self.info.get('Death Count', 0) + 1
        self.send_key('esc')
        self.sleep(1)
        self.log_info('click m to open the map')
        self.send_key('m')
        self.sleep(2)
        self.click_relative(0.68, 0.05)
        self.sleep(1)
        self.click_relative(0.37, 0.42)
        travel = self.wait_feature('gray_teleport', raise_if_not_found=True, time_out=3)
        self.click_box(travel, relative_x=1.5)
        self.wait_in_team_and_world(time_out=20)
        self.sleep(2)

    def run(self):
        self.set_check_monthly_card()
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
                        self.teleport_to_boss(boss_name)
                        logger.info(f'farm echo combat once start')
                        if boss_name == 'Crownless':
                            self.wait_in_team_and_world(time_out=20)
                            self.sleep(2)
                            logger.info('Crownless walk to f')
                            self.walk_until_f(raise_if_not_found=True, time_out=4, backward_time=1)
                            in_combat = self.wait_until(self.in_combat, raise_if_not_found=False, time_out=10)
                            if not in_combat:  # try click again
                                self.walk_until_f(raise_if_not_found=True, time_out=4)
                        elif boss_name == 'Bell-Borne Geochelone':
                            logger.info(f'sleep for the Bell-Borne model to appear')
                            self.sleep(15)
                        try:
                            self.combat_once()
                        except CharDeadException:
                            logger.info(f'char dead try teleport to heal')
                            self.teleport_to_heal()
                            continue
                        logger.info(f'farm echo combat end')
                        if boss_name == 'Bell-Borne Geochelone':
                            logger.info(f'sleep for the Boss model to disappear')
                            self.sleep(5)
                        logger.info(f'farm echo move forward walk_until_f to find echo')
                        method = self.config.get(f'Boss{i} Echo Pickup Method', 'Walk')

                        if method == 'Run in Circle':
                            dropped = self.run_in_circle_to_find_echo()
                        elif method == 'Turn Around and Search':
                            dropped = self.turn_and_find_echo()
                        else:
                            dropped = self.walk_find_echo()
                        self.incr_drop(dropped)

            if count == 0:
                self.log_error('must choose at least 1 Boss to Farm', notify=True)
                return
