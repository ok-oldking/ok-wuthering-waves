import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.TacetTask import TacetTask

config['debug'] = True


class TestTacet(TaskTestCase):
    task_class = TacetTask
    config = config

    def test_find_treasure_icon(self):
        self.set_image('tests/images/treasure.png')
        treasure = self.task.find_treasure_icon()
        self.logger.info(f'find_treasure_icon {treasure}')
        self.assertIsNotNone(treasure)

if __name__ == '__main__':
    unittest.main()
