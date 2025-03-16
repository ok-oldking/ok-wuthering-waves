from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask, CharDeadException

logger = Logger.get_logger(__name__)


class FarmWorldBossTask(BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = "Click Start in Game World"
        self.name = "Farm World Boss(May need to drop waypoint on Boss)"
        self.boss_names = ['N/A', 'Lorelei', 'Sentry Construct', 'Dragon of Dirge', 'Nightmare: Feilian Beringal',
                           'Nightmare: Impermanence Heron', 'Nightmare: Thundering Mephis',
                           'Nightmare: Tempest Mephis', 'Nightmare: Crownless',
                           'Nightmare: Inferno Rider', 'Nightmare: Mourning Aix', 'Bell-Borne Geochelone', 'Crownless',
                           'Thundering Mephis', 'Tempest Mephis',
                           'Inferno Rider',
                           'Feilian Beringal',
                           'Mourning Aix', 'Impermanence Heron', 'Lampylumen Myriad', 'Mech Abomination',
                           'Fallacy of No Return'
                           ]

        self.find_echo_method = ['Walk', 'Run in Circle', 'Turn Around and Search']

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
        self.icon = FluentIcon.GLOBE
        self.add_exit_after_config()

    # not current in use because not stable, right now using one click to scroll down

    def run(self):

        self.set_check_monthly_card()
        self.check_main()
        count = 0
        while True:
            for i in range(1, 4):
                key = 'Boss' + str(i)
                if boss_name := self.config.get(key):
                    if boss_name != 'N/A':
                        count += 1
                        self.teleport_to_boss(boss_name, use_custom=True)
                        logger.info(f'farm echo combat once start')
                        if boss_name == 'Crownless':
                            self.wait_in_team_and_world(time_out=20)
                            self.sleep(2)
                            logger.info('Crownless walk to f')
                            self.walk_until_f(raise_if_not_found=True, time_out=4, backward_time=1)
                            in_combat = self.wait_until(self.in_combat, raise_if_not_found=False, time_out=10)
                            if not in_combat:  # try click again
                                self.walk_until_f(raise_if_not_found=True, time_out=4)
                        elif boss_name == 'Lorelei':
                            if count % 6 < 3:
                                self.change_time_to_night()
                        self.middle_click_relative(0.5, 0.5)
                        self.sleep(0.4)
                        self.run_until(self.in_combat, 'w', time_out=5, running=True)
                        self.wait_until(self.in_combat, raise_if_not_found=True, time_out=120)
                        if boss_name == 'Sentry Construct':
                            logger.debug('Sentry Construct sleep')
                            self.sleep(5)
                        try:
                            self.combat_once()
                        except CharDeadException as e:
                            # 打开书，选择一个没有传送点的Boss（老朔雷），传送到附近坐标复活角色，再从下一个boss继续
                            self.sleep(1)
                            self.send_key('esc')
                            self.teleport_to_boss('Tempest Mephis', use_custom=True, dead=True)
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

            if count < 2:
                self.log_error('Must choose at least 2 Boss to Farm', notify=True)
                return

    def change_time_to_night(self):
        logger.info('change time to night')
        self.send_key("esc")
        self.sleep(1)
        self.click_relative(0.71, 0.96)
        self.sleep(2)
        self.click_relative(0.19, 0.14)
        self.sleep(1)
        self.click_relative(0.52, 0.90)
        self.sleep(6)
        self.send_key("esc")
        self.sleep(1)
        self.send_key("esc")
        self.sleep(1)
