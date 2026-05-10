import unittest
from config import config
from ok.test.TaskTestCase import TaskTestCase
from src.task.AutoCombatTask import AutoCombatTask

config['debug'] = True


class TestKey(TaskTestCase):
    task_class = AutoCombatTask
    config = config

    def test_key1(self):
        self.task.do_reset_to_false()
        self.task.key_config['Resonance Key'] = 'a'
        self.task.key_config['Echo Key'] = 'a'
        self.task.key_config['Liberation Key'] = 'a'
        self.task.key_config['Tool Key'] = 'a'

        self.set_image('tests/images/in_combat.png')
        self.task.load_hotkey(force=True)
        self.assertEqual(self.task.key_config['Resonance Key'], 'a')
        self.assertEqual(self.task.key_config['Liberation Key'], 'q')
        self.assertEqual(self.task.key_config['Echo Key'], 'r')
        self.assertEqual(self.task.key_config['Tool Key'], 'a')


if __name__ == '__main__':
    unittest.main()
