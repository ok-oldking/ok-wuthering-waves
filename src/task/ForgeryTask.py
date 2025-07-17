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
            'Forgery Challenge Count': 20,  # starts with 20
        }
        self.config_description = {
            'Which Forgery Challenge to Farm': 'The Forgery Challenge number in the F2 list.',
            'Forgery Challenge Count': 'Number of times to farm the Forgery Challenge (40 stamina per run). Set a large number to use all stamina.',
        }
        self.stamina_once = 40
        self.total_number = 10
        self.material_mat = None

    def run(self):
        super().run()
        self.make_sure_in_world()
        self.farm_forgery()

    def farm_forgery(self):
        total_counter = self.config.get('Forgery Challenge Count', 20)
        if total_counter <= 0:
            self.log_info('0 time(s) farmed, 0 stamina used')
            return
        current, back_up = self.open_F2_book_and_get_stamina()
        if current + back_up < self.stamina_once:
            self.back()
            return
        self.teleport_into_domain(self.config.get('Which Forgery Challenge to Farm', 1))
        self.sleep(1)
        self.farm_in_domain(total_counter=total_counter, current=current, back_up=back_up)

    def purification_material(self):
        if self.material_mat is None:
            raise RuntimeError('material_mat is not set')
        self.send_key("esc")
        self.sleep(1)
        self.click_relative(0.62, 0.7)
        self.sleep(2)
        box = self.box_of_screen(243 / 2560, 162 / 1440, 928 / 2560, 559 / 1440, name='ascension_materials')
        self.draw_boxes(box.name, box)
        target = self.wait_until(lambda: self.find_one(template=self.material_mat, box=box, threshold=0.7),
                                 raise_if_not_found=True, time_out=4)
        self.click_box(target, after_sleep=1)
        self.click_relative(0.75, 0.90, after_sleep=1)
        self.ensure_main()

    def teleport_into_domain(self, serial_number):
        self.click_relative(0.18, 0.16, after_sleep=1)
        self.info_set('Teleport to Forgery Challenge', serial_number - 1)
        if serial_number > self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        self.click_on_book_target(serial_number, self.total_number)
        if self._daily_task:
            self.get_material_mat()
        self.wait_click_travel()
        self.wait_in_team_and_world(time_out=self.teleport_timeout)
        self.sleep(1)
        self.walk_until_f(time_out=1)
        self.pick_f()
        self.sleep(1)
        self.wait_click_feature('gray_button_challenge', relative_x=4, raise_if_not_found=True,
                                click_after_delay=1, threshold=0.6, after_sleep=1, time_out=10)
        self.click_relative(0.93, 0.90, after_sleep=1)
        self.wait_in_team_and_world(time_out=self.teleport_timeout)

    def get_material_mat(self):
        min_width = self.width_of_screen(80 / 2560)
        min_height = self.height_of_screen(80 / 1440)
        box = self.box_of_screen(2205 / 2560, 566 / 1440, 2357 / 2560, 984 / 1440)
        self.draw_boxes(box.name, box)
        material_boxes = find_color_rectangles(self.frame, material_box_color, min_width, min_height,
                                               box=box, threshold=0.6)
        if material_boxes:
            target = min(material_boxes, key=lambda box: box.y)
            logger.info(f"Found {len(material_boxes)} material boxes, selected target at y={target.y}")
            mat_box = target.copy(20, 20, 90-target.width, 90-target.height, 'material_mat')
            self.draw_boxes(mat_box.name, mat_box)
            self.material_mat = cv2.resize(mat_box.crop_frame(self.frame),None,
                                           fx=1.1, fy=1.1, interpolation=cv2.INTER_LINEAR)
        else:
            raise RuntimeError('can not find material_box')

material_box_color = {
    'r': (45, 75),  # Red range
    'g': (45, 75),  # Green range
    'b': (45, 75)  # Blue range
}
