import cv2

from qfluentwidgets import FluentIcon

from ok import Logger, find_color_rectangles
from src.task.DomainTask import DomainTask

logger = Logger.get_logger(__name__)


class ForgeryTask(DomainTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.name = 'Forgery Challenge'
        self.description = 'Farms the selected Forgery Challenge. Must be able to teleport (F2).'
        self.default_config = {
            'Which Forgery Challenge to Farm': 1,  # starts with 1
        }
        self.config_description = {
            'Which Forgery Challenge to Farm': 'The Forgery Challenge number in the F2 list.',
        }
        self.stamina_once = 40
        self.total_number = 10
        self.material_mat = None

    def run(self):
        super().run()
        self.make_sure_in_world()
        self.farm_forgery()

    def farm_forgery(self, daily=False, used_stamina=0, config=None):
        if daily:
            must_use = 180 - used_stamina
        else:
            must_use = 0
        if config is None:
            config = self.config
        current, back_up, total = self.open_F2_book_and_get_stamina()
        if total < self.stamina_once or total < must_use or (must_use == 0 and current < self.stamina_once):
            self.log_info(f'not enough stamina', notify=True)
            self.back()
            return
        self.teleport_into_domain(config.get('Which Forgery Challenge to Farm', 1), daily)
        self.sleep(1)
        self.farm_in_domain(must_use=must_use)

    def purification_material(self):
        self.send_key("esc")
        self.sleep(1)
        self.click_relative(0.62, 0.7)
        self.sleep(1)
        box = self.box_of_screen(243 / 2560, 162 / 1440, 928 / 2560, 559 / 1440, name='ascension_materials')
        self.draw_boxes(box.name, box)
        self.wait_book()
        if self.material_mat is not None and \
            (target := self.wait_until(lambda: self.find_one(template=self.material_mat, box=box, threshold=0.7), time_out=1)):
            self.click_box(target, after_sleep=1)
        self.click_relative(0.75, 0.90, after_sleep=1)
        self.ensure_main()

    def teleport_into_domain(self, serial_number, daily=False):
        self.click_relative(0.18, 0.16, after_sleep=1)
        self.info_set('Teleport to Forgery Challenge', serial_number - 1)
        if serial_number > self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        self.click_on_book_target(serial_number, self.total_number)
        if daily:
            self.get_material_mat()
        self.wait_click_travel()
        self.wait_in_team_and_world(time_out=self.teleport_timeout)
        self.sleep(max(5, self.teleport_timeout / 10))
        self.walk_until_f(time_out=2)
        self.pick_f()
        self.wait_click_feature('gray_button_challenge', relative_x=4, raise_if_not_found=True, click_after_delay=1, threshold=0.6, after_sleep=1, time_out=20) # solo challenge
        self.click_relative(0.62, 0.62, after_sleep=1) # click confirm of not enough stamina dialog (may appear)
        self.click_relative(0.93, 0.90, after_sleep=1) # start challenge
        self.wait_in_team_and_world(time_out=self.teleport_timeout)

    def get_material_mat(self):
        min_width = self.width_of_screen(80 / 2560)
        min_height = self.height_of_screen(80 / 1440)
        box = self.box_of_screen(2205 / 2560, 566 / 1440, 2357 / 2560, 984 / 1440)
        self.draw_boxes(box.name, box)
        material_boxes = find_color_rectangles(self.frame, material_box_color, min_width, min_height,
                                               box=box, threshold=0.6)
        if material_boxes:
            box_start = self.width_of_screen(20 / 2560)
            box_len = self.width_of_screen(90 / 2560)
            target = min(material_boxes, key=lambda box: box.y)
            logger.info(f"Found {len(material_boxes)} material boxes, selected target at y={target.y}")
            mat_box = target.copy(box_start, box_start, box_len - target.width, box_len - target.height, 'material_mat')
            self.draw_boxes(mat_box.name, mat_box)
            self.material_mat = cv2.resize(mat_box.crop_frame(self.frame), None,
                                           fx=1.1, fy=1.1, interpolation=cv2.INTER_LINEAR)


material_box_color = {
    'r': (45, 75),  # Red range
    'g': (45, 75),  # Green range
    'b': (45, 75)  # Blue range
}
