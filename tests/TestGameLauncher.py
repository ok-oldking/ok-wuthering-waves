import base64
import gettext
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import config
from src import game_launcher


class TestGameLauncher(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.launcher_folder = Path(temporary.name)
        self.game_folder = self.launcher_folder / 'Wuthering Waves Game'
        self.game_folder.mkdir()
        self.game_exe = self.game_folder / 'Wuthering Waves.exe'
        self.state_path = self.launcher_folder / 'kr_game_cache' / 'platform_ui_state.bin'
        self.state_path.parent.mkdir()

    def write_state(self, state):
        data = json.dumps(state).encode('utf-8')
        self.state_path.write_bytes(base64.b64encode(bytes(value ^ 0x63 for value in data)))

    def test_windows_config_registers_launch_arguments_callback(self):
        self.assertIs(
            config.config['windows']['launch_arguments'],
            game_launcher.get_game_launch_arguments,
        )

    def test_game_package_option_is_removed(self):
        self.assertNotIn('Game Package', config.basic_config_option.default_config)
        self.assertNotIn('Game Package', config.basic_config_option.config_type)

    def test_launch_arguments_default_to_hd(self):
        global_config = Mock()
        global_config.get_config.return_value = {}
        with patch.object(game_launcher, 'og', SimpleNamespace(global_config=global_config)), \
                patch.object(game_launcher, 'alert_error') as alert:
            self.assertEqual('-krqlv=hd', game_launcher.get_game_launch_arguments())
        alert.assert_called_once_with(game_launcher.GAME_ASSETS_QUALITY_ERROR, tray=True)
        global_config.get_config.assert_not_called()

    def test_detect_selected_bundle(self):
        for package in ('SD', 'HD', 'UHD'):
            with self.subTest(package=package):
                self.write_state({'activeGameScope': {'gameIdentity': 'Aki', 'bundleName': package}})
                self.assertEqual(package.lower(), game_launcher.detect_game_package(self.game_exe))

    def test_active_bundle_takes_priority_over_recent_bundle_and_downloads(self):
        self.write_state({
            'activeGameScope': {'gameIdentity': 'Aki', 'bundleName': 'HD'},
            'recentGames': {'Aki': {'bundleName': 'UHD'}},
        })
        (self.game_folder / 'launcherDownloadConfig.json').write_text(
            json.dumps({'bundles': {'HD': {}, 'UHD': {}}}), encoding='utf-8',
        )
        self.assertEqual('hd', game_launcher.detect_game_package(self.game_exe))

    def test_recent_bundle_used_when_another_game_is_active(self):
        self.write_state({
            'activeGameScope': {'gameIdentity': 'OtherGame', 'bundleName': 'HD'},
            'recentGames': {'Aki': {'gameId': 'G153', 'bundleName': 'UHD'}},
        })
        self.assertEqual('uhd', game_launcher.detect_game_package(self.game_exe))

    def test_missing_or_invalid_state_returns_none(self):
        self.assertIsNone(game_launcher.detect_game_package(self.game_exe))
        for raw in (b'not base64', base64.b64encode(b'invalid json'), b'////'):
            with self.subTest(raw=raw):
                self.state_path.write_bytes(raw)
                self.assertIsNone(game_launcher.detect_game_package(self.game_exe))
        for state in ([], {'activeGameScope': []}, {'recentGames': []},
                      {'activeGameScope': {'gameIdentity': 'Aki', 'bundleName': 'invalid'}},
                      {'activeGameScope': {'gameIdentity': 'Aki', 'bundleName': 1}}):
            with self.subTest(state=state):
                self.write_state(state)
                self.assertIsNone(game_launcher.detect_game_package(self.game_exe))

    def test_manifest_only_used_for_one_known_bundle(self):
        manifest_path = self.game_folder / 'launcherDownloadConfig.json'
        for bundles, expected in (({'HD': {}}, 'hd'), ({'UHD': {}}, 'uhd'),
                                  ({'HD': {}, 'UHD': {}}, None), ({'unknown': {}}, None)):
            with self.subTest(bundles=bundles):
                manifest_path.write_text(json.dumps({'bundles': bundles}), encoding='utf-8-sig')
                self.assertEqual(expected, game_launcher.detect_game_package(self.game_exe))

    def test_unreadable_state_falls_back_to_manifest(self):
        (self.game_folder / 'launcherDownloadConfig.json').write_text(
            '{"bundles": {"HD": {}}}', encoding='utf-8',
        )
        original_read = Path.read_bytes

        def read_bytes(path):
            if path == self.state_path:
                raise PermissionError('locked')
            return original_read(path)

        with patch.object(Path, 'read_bytes', read_bytes):
            self.assertEqual('hd', game_launcher.detect_game_package(self.game_exe))

    def test_launch_arguments_detect_current_selection_each_time(self):
        device_manager = Mock()
        device_manager.get_preferred_device.return_value = {'device': 'windows'}
        device_manager.get_exe_path.return_value = str(self.game_exe)
        global_config = Mock()
        global_config.get_config.return_value = {'Game Package': 'sd'}
        globals = SimpleNamespace(device_manager=device_manager, global_config=global_config)
        with patch.object(game_launcher, 'og', globals), \
                patch.object(game_launcher, 'alert_error') as alert:
            for package in ('UHD', 'HD'):
                self.write_state({'activeGameScope': {'gameIdentity': 'Aki', 'bundleName': package}})
                self.assertEqual(f'-krqlv={package.lower()}', game_launcher.get_game_launch_arguments())
        global_config.get_config.assert_not_called()
        alert.assert_not_called()

    def test_launch_arguments_fall_back_when_detection_is_unavailable(self):
        device_manager = Mock()
        device_manager.get_preferred_device.return_value = {'device': 'windows'}
        global_config = Mock()
        globals = SimpleNamespace(device_manager=device_manager, global_config=global_config)
        with patch.object(game_launcher, 'og', globals), \
                patch.object(game_launcher, 'alert_error') as alert:
            for path in (None, str(self.game_exe)):
                device_manager.get_exe_path.return_value = path
                for package in ('uhd', 'invalid'):
                    global_config.get_config.return_value = {'Game Package': package}
                    alert.reset_mock()
                    self.assertEqual('-krqlv=hd', game_launcher.get_game_launch_arguments())
                    alert.assert_called_once_with(game_launcher.GAME_ASSETS_QUALITY_ERROR, tray=True)
        global_config.get_config.assert_not_called()

    def test_fallback_alert_is_translated_in_all_catalogs(self):
        i18n_folder = Path(__file__).resolve().parents[1] / 'i18n'
        catalogs = list(i18n_folder.glob('*/LC_MESSAGES/ok.po'))
        self.assertTrue(catalogs)
        for catalog in catalogs:
            locale = catalog.parents[1].name
            with self.subTest(locale=locale):
                translation = gettext.translation('ok', localedir=str(i18n_folder), languages=[locale])
                message = translation.gettext(game_launcher.GAME_ASSETS_QUALITY_ERROR)
                if not locale.startswith('en'):
                    self.assertNotEqual(game_launcher.GAME_ASSETS_QUALITY_ERROR, message)
                app = SimpleNamespace(tr=translation.gettext)
                with patch.object(game_launcher, 'og', SimpleNamespace(app=app)), \
                        patch.object(game_launcher, 'alert_error') as alert:
                    self.assertEqual('-krqlv=hd', game_launcher.get_game_launch_arguments())
                alert.assert_called_once_with(message, tray=True)


if __name__ == '__main__':
    unittest.main()
