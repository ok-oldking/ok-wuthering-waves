from ok.feature.Feature import Feature
from ok.feature.FeatureSet import mask_white
from ok.util.list import find_index_in_list
from src.task.BaseCombatTask import BaseCombatTask


class DiscardEchoTask(BaseCombatTask):

    def __init__(self):
        super().__init__()
        self.description = "Check configs to keep, click start in game world, must be in a 16:9 screen ratio"
        self.name = "Auto Echo Data Merge"
        self.default_config = {
            'Keep 1C HP': ['Rejuvenating Glow'],
            'Keep 1C DEF': [],
            'Keep 1C ATK': [
                'Freezing Frost', 'Molten Rift', 'Void Thunder', 'Sierra Gale', 'Celestial Light',
                'Sun-sinking Eclipse',
                'Rejuvenating Glow',
                'Moonlit Clouds'],
            'Keep 3C HP': [],
            'Keep 3C DEF': [],
            'Keep 3C ATK': [],
            'Keep 3C Aero DMG': ['Sierra Gale', 'Moonlit Clouds'],
            'Keep 3C Fusion DMG': ['Molten Rift', 'Moonlit Clouds'],
            'Keep 3C Electro DMG': ['Void Thunder', 'Moonlit Clouds'],
            'Keep 3C Spectro DMG': ['Celestial Light', 'Moonlit Clouds'],
            'Keep 3C Havoc DMG': ['Sun-sinking Eclipse', 'Moonlit Clouds'],
            'Keep 3C Glacio DMG': ['Freezing Frost', 'Moonlit Clouds'],
            'Keep 3C Energy Regen': [
                'Freezing Frost', 'Molten Rift', 'Void Thunder', 'Sierra Gale', 'Celestial Light',
                'Sun-sinking Eclipse',
                'Rejuvenating Glow',
                'Moonlit Clouds'],
            'Keep 4C Crit': ['Freezing Frost', 'Molten Rift', 'Void Thunder', 'Sierra Gale', 'Celestial Light',
                             'Sun-sinking Eclipse',
                             'Rejuvenating Glow',
                             'Moonlit Clouds'],
            'Keep 4C Crit DMG': ['Freezing Frost', 'Molten Rift', 'Void Thunder', 'Sierra Gale', 'Celestial Light',
                                 'Sun-sinking Eclipse',
                                 'Rejuvenating Glow',
                                 'Moonlit Clouds'],
            'Keep 4C Healing': ['Moonlit Clouds'],
            'Keep 4C HP': [],
            'Keep 4C DEF': [],
            'Keep 4C ATK': [],
        }

        self.sets = [
            'Freezing Frost', 'Molten Rift', 'Void Thunder', 'Sierra Gale', 'Celestial Light', 'Sun-sinking Eclipse',
            'Rejuvenating Glow',
            'Moonlit Clouds',
            'Lingering Tunes']

        self.main_stats = ["攻击", "防御", "生命", "共鸣效率", "冷凝伤害加成", "热熔伤害加成", "导电伤害加成",
                           "气动伤害加成", "衍射伤害加成", "湮灭伤害加成", "治疗效果加成", "暴击伤害", "暴击"]
        self.main_stats = ["ATK", "DEF", "HP", "Energy Regen", "Crit", "Crit DMG", "Healing",
                           "Glacio DMG", "Aero DMG", "Electro DMG", "Fusion DMG", "Havoc DMG", "Spectro DMG"]
        self.main_stats_feature_name = []
        for main_stat in self.main_stats:
            self.main_stats_feature_name.append(get_stat_feature_name(main_stat))

        self.config_type = {}
        for key in self.default_config.keys():
            self.config_type[key] = {'type': "multi_selection", 'options': self.sets}

        self.set_names = []
        for i in range(len(self.sets)):
            self.set_names.append(f'set_name_{i}')
        self.echo_positions = [(0.79, 0.20), (0.87, 0.30), (0.84, 0.47), (0.73, 0.47), (0.7, 0.3)]
        self.confirmed = False
        self.current_cost = 0

    def run(self):
        self.current_cost = 0
        if self.find_one('button_echo_merge'):
            self.click_empty_area()
            if not self.find_one('data_merge_first_add_slot', threshold=0.6):
                self.log_info(f'remove added echos')
                self.add_5()
        else:
            self.check_main()
            self.send_key('esc')
            self.sleep(2)
            self.click_relative(0.75, 0.46, after_sleep=1)
            self.click_relative(0.04, 0.55, after_sleep=1)
            self.click_relative(0.53, 0.2, after_sleep=1)
        self.incr_cost_filter()
        starting_index = 0
        while True:
            starting_index = self.loop_merge(starting_index)
            if starting_index == -1:
                break
        self.log_info(f'Data Merge Completed!', notify=True)

    def add_5(self):
        self.log_info('try_add_five')
        self.click(self.get_box_by_name('box_data_merge_add_clear'), after_sleep=0.5)

    def loop_merge(self, start_index):
        self.add_5()
        if self.find_one('data_merge_first_add_slot', threshold=0.6):
            if self.incr_cost_filter():
                self.add_5()
            else:
                return -1
        for i in range(start_index, len(self.echo_positions)):
            x, y = self.echo_positions[i]
            self.click_relative(x, y, after_sleep=0.5)
            main_stat = self.find_main_stat()
            set_name = self.find_set_by_template()

            config_name = f'Keep {self.current_cost}C {main_stat}'
            self.log_info(f'found {config_name} {self.config.get(config_name)}')
            if set_name in self.config.get(config_name):
                self.click_box(self.get_box_by_name('box_echo_lock_merge'))
                self.click_empty_area()
                self.add_5()
                self.info_incr('Lock Count', 1)
                return i
            self.click_empty_area()
        self.wait_merge()
        return 0

    def wait_merge(self):
        self.wait_click_feature('button_echo_merge', raise_if_not_found=True)
        self.handle_confirm()
        self.wait_feature('data_merge_hcenter', pre_action=self.click_empty_area, wait_until_before_delay=1,
                          time_out=15, raise_if_not_found=True)
        self.click_relative(0.53, 0.19, after_sleep=1)
        self.info_incr('Merge Count', 1)

    def handle_confirm(self):
        if not self.confirmed:
            confirm = self.wait_feature('confirm_btn_hcenter_vcenter', time_out=3, raise_if_not_found=False,
                                        wait_until_before_delay=1.5)
            if confirm:
                self.click_relative(0.44, 0.55)
                self.sleep(0.5)
                self.click_box(confirm, relative_x=-1)
            self.confirmed = True

    def click_empty_area(self):
        self.click_relative(0.95, 0.51, after_sleep=0.5)

    def find_main_stat(self):
        box = self.get_box_by_name('box_echo_main_stat_merge').scale(1.2, 1.2)
        stat = self.find_best_match_in_box(box, self.main_stats_feature_name, 0.3)
        if not stat:
            raise Exception("Can't find main stat!")
        for main_stat in self.main_stats:
            if stat.name == get_stat_feature_name(main_stat):
                return main_stat

    def scroll_down_a_page(self):
        self.log_info(f'scroll down a page')
        set_icon = self.find_best_match_in_box(self.box_of_screen(0.36, 0.67, 0.39, 0.86), self.set_names, 0.3)

        source_template = Feature(set_icon.crop_frame(self.frame), set_icon.x, set_icon.y)
        steps = 0.03
        target_box = set_icon.copy(y_offset=-self.height_of_screen(steps),
                                   height_offset=self.height_of_screen(steps) + 2)
        x, y = self.width_of_screen(1596 / 2560), self.height_of_screen(0.6)
        self.mouse_down(x, y)
        # self.sleep(0.1)
        while True:
            self.scroll(x, y, -1)
            self.sleep(0.005)
            target = self.find_one('target_box', box=target_box, template=source_template, threshold=0.9)
            if not target:
                self.scroll(x, y, -1)
                self.mouse_up()
                self.sleep(0.01)
                return
            self.log_info(f'found target box {target}, continue scrolling')
            target_box = target.copy(y_offset=-self.height_of_screen(steps),
                                     height_offset=self.height_of_screen(steps) + 2)
            if target_box.y < 0:
                target_box.y = 0

    def find_set_by_template(self):
        box = self.get_box_by_name('box_set_merge')

        set_name = self.find_best_match_in_box(box, self.set_names, 0.3)
        if not set_name:
            raise Exception("Can't find set name")
        index = find_index_in_list(self.set_names, set_name.name)
        if index == -1:
            raise Exception("Can't find set name")
        max_name = self.sets[index]
        self.log_info(f'find_set_by_template: {set_name} {max_name}')
        return max_name

    def discard(self):
        discard = self.find_one('echo_discard', threshold=0.6)
        if not discard:
            raise Exception("Can't find discard button!")
        self.click_box(discard)
        self.wait_feature('echo_discarded', threshold=0.6, time_out=5, raise_if_not_found=True)

    def incr_cost_filter(self):
        if self.current_cost == 0:
            self.current_cost = 1
            x = 0.26
        elif self.current_cost == 1:
            self.current_cost = 3
            x = 0.5
        elif self.current_cost == 3:
            self.current_cost = 4
            x = 0.72
        else:
            return False

        self.click_relative(0.04, 0.91, after_sleep=1)
        self.click_relative(0.61, 0.83, after_sleep=0.5)
        self.click_relative(x, 0.63, after_sleep=0.5)
        self.click_relative(0.81, 0.84, after_sleep=1)
        self.log_info(f'incr_cost_filter: {self.current_cost}')
        return True


def get_stat_feature_name(main_stat):
    return f"echo_stats_{main_stat.lower().replace(' ', '_')}"


def mask_main_stats_white(image):
    return mask_white(image, 230)
