from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)


class TacetTask(WWOneTimeTask, BaseCombatTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.description = "Farm selected Tacet Suppression until out of stamina, will use the backup stamina, you need to be able to teleport from the menu(F2)"
        self.name = "Tacet Suppression (Must explore first to be able to teleport)"
        default_config = {
            'What materials to brush': 1, #刷什么材料
            'Which Tacet Suppression to Farm': 1  # starts with 1
        }
        self.row_per_page = 5
        self.total_number = 11
        self.target_enemy_time_out = 6
        default_config.update(self.default_config)
        self.config_description = {
            'What materials to brush': 'Counting from top to bottom(Forgery Challenge ETC.)',
            'Which Tacet Suppression to Farm': 'the Nth number in the Tacet Suppression list (F2)',
        }
        self.default_config = default_config
        self.door_walk_method = {  # starts with 0
            0:[],
            1: [["a", 0.3]],
            2: [["d", 0.6]],
            3: [["a", 1.5], ["w", 3], ["a", 2.5]],
        }

    def run(self):
        super().run()
        self.wait_in_team_and_world(esc=True)
        self.farm_tacet()

    def farm_tacet(self):
        total_used = 0
        if self.config.get('What materials to brush', 1) == 4:#运行无音区模式
            work_health = 60#最少体力
        else:
            work_health = 40#最少体力
        while True:
            gray_book_boss = self.openF2Book("gray_book_boss")
            self.click_box(gray_book_boss, after_sleep=1)
            current, back_up = self.get_stamina()# 获取体力值
            if current == -1:#获取不到体力值
                self.click_relative(0.04, 0.4, after_sleep=1)
                current, back_up = self.get_stamina()
            if current + back_up < work_health:#体力不足以运行循环
                return self.not_enough_stamina()
            materials_index =  self.config.get('What materials to brush', 1) - 1
            self.teleport_to_type(materials_index)#导航到材料
            #self.click_relative(0.18, 0.19, after_sleep=1)
            index = self.config.get('Which Tacet Suppression to Farm', 1) - 1
            self.teleport_to_tacet(index)#导航到选项
            self.wait_click_travel()
            self.wait_in_team_and_world()
            self.sleep(1)
            if materials_index == 3:#如果是无音区模式
                if self.door_walk_method.get(index) is not None:
                    for method in self.door_walk_method.get(index):
                        self.send_key_down(method[0])
                        self.sleep(method[1])
                        self.send_key_up(method[0])
                        self.sleep(0.05)
                    self.run_until(self.in_combat, 'w', time_out=10, running=True)
                else:
                    self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
            elif materials_index == 0:#是燃素领域
                self.walk_until_f(time_out=8, backward_time=0, raise_if_not_found=True)
            elif materials_index == 1:#是模拟领域
                self.walk_until_f(time_out=8, backward_time=0, raise_if_not_found=True)
            elif materials_index == 2:#是讨伐强敌
                self.run_until(time_out=8, backward_time=0, raise_if_not_found=True)
            if materials_index != 3:#当前运行任务不是无音区
                self.sleep(5)
                self.wait_click_ocr(0.80, 0.87, 0.97, 0.95, match=['单人挑战', 'Confirm'], raise_if_not_found=True, log=True)
                self.sleep(1)
                self.wait_click_ocr(0.77, 0.87, 0.95, 0.94, match=['开启挑战', 'Confirm'], raise_if_not_found=True, log=True)
                self.sleep(5)
                self.walk_until_f(time_out=4, backward_time=0, raise_if_not_found=True)
            self.combat_once()
            self.walk_to_treasure()
            used, remaining_total, remaining_current, used_back_up = self.ensure_stamina(work_health, work_health * 2)#使用体力自动同步
            total_used += used
            self.info_set('used stamina', total_used)
            if not used:
                return self.not_enough_stamina()
            self.wait_click_ocr(0.2, 0.56, 0.75, 0.69, match=[str(used), '确认', 'Confirm'], raise_if_not_found=True, log=True)
            self.sleep(4)
            if materials_index == 0:#如果当前运行模式为非无音区
                self.click(0.37, 0.85, after_sleep=2)
            else:
                self.click(0.51, 0.84, after_sleep=2)
            if remaining_total < work_health:
                return self.not_enough_stamina(back=False)
            if total_used >= 180 and remaining_current == 0:
                return self.not_enough_stamina(back=True)
            if materials_index != 3:#如果运行模式为非无音区
                self.sleep(8)


    def walk_to_treasure(self, retry=0):
        if retry > 4:
            raise RuntimeError('walk_to_treasure too many retries!')
        if self.find_treasure_icon():
            self.walk_to_box(self.find_treasure_icon, end_condition=self.find_f_with_text)
        self.walk_until_f(time_out=2, backward_time=0, raise_if_not_found=True, cancel=False)
        self.sleep(1)
        if self.find_treasure_icon():
            self.log_info('retry walk_to_treasure')
            self.walk_to_treasure(retry=retry + 1)

    def not_enough_stamina(self, back=True):
        self.log_info(f"used all stamina", notify=True)
        if back:
            self.back(after_sleep=1)

    def teleport_to_type(self, index):#导航不同材料
        self.info_set('Choice material type', index)
        if index >= 4:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        x = 0.22
        height = 0.10
        y = 0.16
        y += height * index
        self.click_relative(x, y, after_sleep=2)

    def teleport_to_tacet(self, index):
        self.info_set('Teleport to Tacet Suppression', index)
        if index >= self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        if index >= self.row_per_page:
            if index >= self.row_per_page * 2: # page 3
                self.click_relative(0.98, 0.86)
                index -= self.row_per_page + 1 # only 1 in last page
            else:
                index -= self.row_per_page
                self.click_relative(0.98, 0.8)
            self.log_info(f'teleport_to_tacet scroll down a page new index: {index}')
        x = 0.88
        height = (0.85 - 0.28) / 4
        y = 0.275
        y += height * index
        self.click_relative(x, y, after_sleep=2)

echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
