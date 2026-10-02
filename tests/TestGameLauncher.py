import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import config
from src import game_launcher


class TestGameLauncher(unittest.TestCase):
    def test_windows_config_registers_launch_arguments_callback(self):
        self.assertIs(
            config.config['windows']['launch_arguments'],
            game_launcher.get_game_launch_arguments,
        )

    def test_launch_arguments_read_current_game_package(self):
        basic_options = {'Game Package': 'hd'}
        global_config = Mock()
        global_config.get_config.return_value = basic_options
        with patch.object(game_launcher, 'og', SimpleNamespace(global_config=global_config)):
            for package in ('sd', 'hd', 'uhd'):
                basic_options['Game Package'] = package
                self.assertEqual(f'-krqlv={package}', game_launcher.get_game_launch_arguments())

        self.assertEqual(3, global_config.get_config.call_count)
        global_config.get_config.assert_called_with('Basic Options')

    def test_launch_arguments_default_to_hd(self):
        global_config = Mock()
        global_config.get_config.return_value = {}
        with patch.object(game_launcher, 'og', SimpleNamespace(global_config=global_config)):
            self.assertEqual('-krqlv=hd', game_launcher.get_game_launch_arguments())


if __name__ == '__main__':
    unittest.main()
