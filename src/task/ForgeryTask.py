import re

from qfluentwidgets import FluentIcon

from ok import Logger
from src.task.DomainTask import DomainTask

logger = Logger.get_logger(__name__)


class ForgeryTask(DomainTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.FLAG
        self.name = '⭐ Forgery Challenge'
        self.description = 'Farm selected Forgery Challenge, you need to be able to teleport'
        self.default_config = {
            'Teleport Timeout': 10,
            'Forgery Suppression Serial Number': 1,  # starts with 1
            'Forgery Challenge Count': 10,  # starts with 0
        }
        material_option_list = ['Resonator EXP', 'Weapon EXP', 'Shell Credit']
        self.config_type['Material Selection'] = {'type': 'drop_down', 'options': material_option_list}
        self.config_description = {
            'Teleport Timeout': 'the timeout of second for teleport',
            'Forgery Suppression Serial Number': 'the Nth number in the list of Forgery Suppression list (in F2 menu)',
            'Forgery Challenge Count': 'farm Forgery Challenge N time(s), 40 stamina per time, set a large number to use all stamina',
        }
        self.teleport_timeout = 60
        self.stamina_once = 40
        self.total_number = 10

    def run(self):
        super().run()
        self.teleport_timeout = self.config.get('Teleport Timeout', 10)
        self.make_sure_in_world()
        self.farm_forgery()

    def farm_forgery(self):
        total_counter = self.config.get('Forgery Challenge Count', 0)
        if total_counter <= 0:
            self.log_info('0 time(s) farmed, 0 stamina used')
            return
        current, back_up = self.open_F2_book_and_get_stamina()
        if current + back_up < self.stamina_once:
            self.back()
            return
        self.teleport_into_domain(self.config.get('Forgery Suppression Serial Number', 0))
        self.farm_in_domain(total_counter=total_counter, current=current, back_up=back_up)

    def teleport_into_domain(self, serial_number):
        self.click_relative(0.18, 0.16, after_sleep=1)
        self.info_set('Teleport to Forgery Suppression', serial_number - 1)
        if serial_number > self.total_number:
            raise IndexError(f'Index out of range, max is {self.total_number}')
        self.click_on_book_target(serial_number, self.total_number)
        #
        self.wait_click_travel()
        self.wait_in_team_and_world(time_out=self.teleport_timeout)
        self.sleep(max(5, self.teleport_timeout / 10))
        self.walk_until_f(time_out=1)
        self.sleep(10)
        self.click_relative(0.93, 0.90, after_sleep=1)
        self.click_relative(0.93, 0.90, after_sleep=1)
        self.wait_in_team_and_world(time_out=self.teleport_timeout)


echo_color = {
    'r': (200, 255),  # Red range
    'g': (150, 220),  # Green range
    'b': (130, 170)  # Blue range
}
