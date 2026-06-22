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

    def test_load_hotkey_skips_set_key_when_short_action_bar_visible(self):
        self.task.do_reset_to_false()
        self.task.key_config['Echo Key'] = 'a'
        self.task.key_config['Liberation Key'] = 'a'
        set_key_calls = []

        def set_key(key, box):
            set_key_calls.append(key)
            self.task.key_config[key] = 't'

        self.task.set_key = set_key
        self.set_image('ok_templates/25.png')
        self.task.load_hotkey(force=True)

        self.assertEqual(set_key_calls, [])
        self.assertEqual(self.task.key_config['Echo Key'], 'a')
        self.assertEqual(self.task.key_config['Liberation Key'], 'a')


if __name__ == '__main__':
    unittest.main()
