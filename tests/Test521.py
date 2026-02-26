import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.FiveToOneTask import FiveToOneTask

config['debug'] = True


class Test521(TaskTestCase):
    task_class = FiveToOneTask
    config = config

    def test_con_full(self):
        self.task.do_reset_to_false()
        self.set_image('tests/images/5_to_1.png')
        stats = self.task.ocr_main_stats()
        self.assertEqual(18, len(stats))


if __name__ == '__main__':
    unittest.main()
