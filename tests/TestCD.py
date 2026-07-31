import unittest
from types import SimpleNamespace

from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class TestCD(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def assert_cd_values(self, image, expected):
        self.task.do_reset_to_false()
        self.set_image(image)
        self.task.chars = [SimpleNamespace(index=0, is_current_char=True), None, None]
        self.task.refresh_cd()

        actual = {
            name: self.task.cds[0][name]
            for name in ('resonance', 'echo', 'liberation')
        }
        self.assertEqual(expected, actual)

    def test_cd_values_from_screenshots(self):
        cases = {
            'tests/images/in_combat.png': {
                'resonance': 0,
                'echo': 18.1,
                'liberation': 0,
            },
            'tests/images/in_combat3.png': {
                'resonance': 1.3,
                'echo': 14.1,
                'liberation': 18.0,
            },
            'tests/images/all_cd_1080p.png': {
                'resonance': 13.6,
                'echo': 18.4,
                'liberation': 22.6,
            },
            'tests/images/con_full2.png': {
                'resonance': 1.9,
                'echo': 21.3,
                'liberation': 0,
            },
        }

        for image, expected in cases.items():
            with self.subTest(image=image):
                self.assert_cd_values(image, expected)


if __name__ == '__main__':
    unittest.main()
