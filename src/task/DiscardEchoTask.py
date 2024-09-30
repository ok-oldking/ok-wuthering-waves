import re
from ok.feature.Box import get_bounding_box
from ok.feature.Feature import Feature
from ok.feature.FeatureSet import mask_white
from ok.util.list import find_index_in_list
from src.task.BaseCombatTask import BaseCombatTask


class DiscardEchoTask(BaseCombatTask):

    def __init__(self):
        super().__init__()
        self.description = "Check configs to keep, click start in game world, must be in a 16:9 screen ratio"
        self.name = "Discard Echo"
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

        self.first_echo_x = 0.15
        self.first_echo_y = 0.19
        self.col_count = 6
        self.row_count = 4
        self.echo_x_distance = (0.58 - 0.15) / (self.col_count - 1)
        self.echo_y_distance = (0.76 - 0.19) / (self.row_count - 1)
        self.set_names = []
        for i in range(len(self.sets)):
            self.set_names.append(f'set_name_{i}')

    def run(self):
        self.check_main()
        row = 0
        col = 0
        self.send_key('b')
        self.sleep(2)
        self.click_relative(0.04, 0.25, after_sleep=1)
        self.click_relative(0.12, 0.91, after_sleep=2)
        self.click_relative(0.61, 0.83, after_sleep=1)
        self.click_relative(0.21, 0.29, after_sleep=1)
        self.click_relative(0.80, 0.83, after_sleep=1)
        self.check_level_sort()
        while True:
            if col >= self.col_count:
                col = 0
                row += 1
            if row >= self.row_count:
                self.scroll_down_a_page()
                row = 0
                col = 0
            x, y = self.get_pos(row, col)
            self.click_relative(x, y)
            self.sleep(0.5)
            col = col + 1
            if not self.is_gold():
                self.log_info('not gold discard')
                self.discard()
                continue

            level, cost = self.get_echo_level_and_cost()
            if level > 0:
                self.log_info(f'Discard echo completed!')
                return True
            if cost <= 0:
                raise Exception("Can't find echo cost")

            main_stat = self.find_main_stat()
            set_name = self.find_set_by_template()

            config_name = f'Keep {cost}C {main_stat}'
            self.log_info(f'found {config_name} {self.config.get(config_name)}')
            if set_name not in self.config.get(config_name):
                self.log_info(f'discard {config_name}')
                self.info_incr('Discarded')
                self.discard()

    def find_main_stat(self):
        box = self.get_box_by_name('box_echo_stat')
        stat = self.find_best_match_in_box(box, self.main_stats_feature_name, 0.6)
        if not stat:
            raise Exception("Can't find main stat!")
        for main_stat in self.main_stats:
            if stat.name == get_stat_feature_name(main_stat):
                return main_stat

    def scroll_down_a_page(self):
        set_icon = self.find_best_match_in_box(self.box_of_screen(0.36, 0.67, 0.39, 0.86), self.set_names, 0.3)

        # last_box.x -= self.height_of_screen(0.04)
        # last_box.width += self.width_of_screen(0.03)
        # last_box.y -= self.height_of_screen(0.05)
        # last_box.height += self.width_of_screen(0.04)
        source_template = Feature(set_icon.crop_frame(self.frame), set_icon.x, set_icon.y)
        steps = 0.08
        target_box = set_icon.copy(y_offset=-self.height_of_screen(steps), height_offset=self.height_of_screen(steps))
        while True:
            self.click_relative(0.7, 0.5)
            self.sleep(0.05)
            self.scroll_relative(0.7, 0.5, -2)
            self.sleep(0.2)
            target = self.find_one('target_box', box=target_box, template=source_template, threshold=0.9)
            if not target:
                self.sleep(1)
                return
            self.log_info(f'found target box {target}, continue scrolling')
            target_box = target.copy(y_offset=-self.height_of_screen(steps),
                                     height_offset=self.height_of_screen(steps))
            if target_box.y < 0:
                target_box.y = 0

    def find_set_by_template(self):
        box = self.get_box_by_name('box_set_name')

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

    def check_level_sort(self):
        box = self.get_box_by_name('echo_sort_asc').scale(1.5, 1.5)

        sort = self.find_best_match_in_box(box, ['echo_sort_asc', 'echo_sort_desc'], 0.6)
        if not sort:
            raise Exception("Can't open echo bag!")
        if sort.name == 'echo_sort_desc':
            self.log_info('change sort to asc')
            self.click_box(sort, after_sleep=1)

    def is_gold(self):
        box = get_bounding_box([self.get_box_by_name('echo_rarity_gold'), self.get_box_by_name('echo_rarity_blue'),
                                self.get_box_by_name('echo_rarity_green'),
                                self.get_box_by_name('echo_rarity_purple')]).scale(1.03, 1.03)
        sort = self.find_best_match_in_box(box, ['echo_rarity_gold', 'echo_rarity_blue', 'echo_rarity_green',
                                                 'echo_rarity_purple'], 0.6)
        if not sort:
            raise Exception("Can't find rarity!")
        if sort.name == 'echo_rarity_gold':
            return True

    def get_echo_level_and_cost(self):
        texts = self.ocr(0.87, 0.17, 0.96, 0.26, name='echo_stats', target_height=1080, log=True)
        cost = 1
        level = -1
        level_pattern = r'^\+\d+$'
        cost_pattern = r'^(?:COST\s*)?(\d+)$'
        for text in texts:
            if re.match(level_pattern, text.name):
                level = int(text.name[1:])
            elif match := re.match(cost_pattern, text.name):
                cost = int(match.group(1))

        return level, cost

    def get_pos(self, row, col):
        return self.first_echo_x + col * self.echo_x_distance, self.first_echo_y + row * self.echo_y_distance


def get_stat_feature_name(main_stat):
    return f"echo_stats_{main_stat.lower().replace(' ', '_')}"


def mask_main_stats_white(image):
    return mask_white(image, 230)
