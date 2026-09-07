from types import SimpleNamespace
from unittest.mock import Mock

from ok.device.services import PermissionState

from scripts import diagnose_macos_windows


def test_diagnostic_preflight_does_not_request_or_enumerate_without_permission(
        monkeypatch):
    permission_service = Mock()
    screen_recording = SimpleNamespace(
        state=PermissionState.REQUIRED,
        settings_path=(
            'System Settings > Privacy & Security > '
            'Screen & System Audio Recording'),
        detail='',
        granted=False,
    )
    accessibility = SimpleNamespace(
        state=PermissionState.REQUIRED,
        settings_path='System Settings > Privacy & Security > Accessibility',
        detail='',
        granted=False,
    )
    permission_service.snapshot.return_value = (
        screen_recording, accessibility)
    discovery_factory = Mock()
    monkeypatch.setattr(
        diagnose_macos_windows,
        'create_permission_service',
        Mock(return_value=permission_service),
    )
    monkeypatch.setattr(
        diagnose_macos_windows,
        'create_macos_window_discovery',
        discovery_factory,
    )

    report, exit_code = diagnose_macos_windows.diagnose()

    assert exit_code == 2
    assert report['screen_recording_permission']['state'] == 'permission-required'
    assert report['accessibility_permission']['state'] == 'permission-required'
    assert '未请求系统权限' in report['note']
    permission_service.request.assert_not_called()
    discovery_factory.assert_not_called()
