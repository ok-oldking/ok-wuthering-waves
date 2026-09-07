import importlib
from types import SimpleNamespace

import pytest
from unittest.mock import Mock

from config import config
from ok.device.capabilities import DeviceCapabilities, MissingDeviceCapabilitiesError
from src.macos_capabilities import (
    MAC_BASIC_CAPABILITIES,
    MAC_FULL_CAMERA_CAPABILITIES,
    MAC_LOCKED_GAMEPLAY_CAPABILITIES,
    TASK_MACOS_COMPATIBILITY,
    MacTaskCapabilityLevel,
    MacTaskSupportStatus,
    MacTaskUnsupportedError,
)
from src.task.AutoCombatTask import AutoCombatTask
from src.task.AutoPickTask import AutoPickTask
from src.task.MouseResetTask import MouseResetTask


@pytest.mark.parametrize('platform,enabled', [('darwin', False), ('win32', True)])
def test_mouse_reset_default_does_not_block_fresh_macos_start(monkeypatch, platform, enabled):
    module = importlib.import_module('src.task.MouseResetTask')
    monkeypatch.setattr(module.sys, 'platform', platform)
    task = MouseResetTask(Mock(), Mock())
    assert task.default_config['_enabled'] is enabled


def test_mouse_reset_saved_enabled_preference_is_not_run_on_macos(monkeypatch):
    module = importlib.import_module('src.task.MouseResetTask')
    monkeypatch.setattr(module.sys, 'platform', 'darwin')
    task = MouseResetTask(Mock(), Mock())
    task.config = {'_enabled': True}
    task.on_create()
    assert not task.enabled
    assert task.config['_enabled'] is True  # Do not erase the Windows preference.


def registered_task_ids():
    return {
        f"{module}.{class_name}"
        for group in ("onetime_tasks", "trigger_tasks")
        for module, class_name in config[group]
    }


def fake_task(task_class, capabilities):
    manager = SimpleNamespace(
        capabilities=capabilities,
        get_preferred_device=lambda: {"device": "macos"},
    )
    task = object.__new__(task_class)
    task._executor = SimpleNamespace(device_manager=manager)
    task.name = task_class.__name__
    return task


def test_every_registered_task_has_an_explicit_macos_declaration():
    assert set(TASK_MACOS_COMPATIBILITY) == registered_task_ids()


def test_every_registered_class_resolves_its_macos_compatibility_state():
    available = DeviceCapabilities.from_names(DeviceCapabilities.names())
    for task_id, declaration in TASK_MACOS_COMPATIBILITY.items():
        module_name, class_name = task_id.rsplit('.', 1)
        task_class = getattr(importlib.import_module(module_name), class_name)
        task = fake_task(task_class, available)

        state = task.get_device_compatibility_state()

        assert state['status'] == declaration.status.value, task_id
        assert state['level'] == (
            declaration.level.value if declaration.level else None
        ), task_id
        assert state['missing'] == (), task_id


def test_no_registered_task_currently_requires_free_camera_delta():
    declarations = TASK_MACOS_COMPATIBILITY.values()

    assert all(item.level is not MacTaskCapabilityLevel.MAC_FULL_CAMERA for item in declarations)
    assert all(not item.required.relative_mouse for item in declarations)


def test_task_statuses_do_not_claim_hardware_validation():
    statuses = {
        task_id: item.status
        for task_id, item in TASK_MACOS_COMPATIBILITY.items()
    }

    assert MacTaskSupportStatus.VALIDATED not in statuses.values()
    assert statuses["src.task.MouseResetTask.MouseResetTask"] is MacTaskSupportStatus.UNSUPPORTED
    assert all(
        status is MacTaskSupportStatus.EXPERIMENTAL
        for task_id, status in statuses.items()
        if task_id != "src.task.MouseResetTask.MouseResetTask"
    )


def test_relative_mouse_false_does_not_block_basic_or_locked_gameplay_levels():
    available = DeviceCapabilities(
        keyboard_tap=True,
        keyboard_hold=True,
        absolute_mouse=True,
        mouse_left=True,
        mouse_right=True,
        mouse_middle=True,
        mouse_button_hold=True,
        scroll=True,
        relative_mouse=False,
        foreground_only=True,
    )

    assert available.supports(MAC_BASIC_CAPABILITIES)
    assert available.supports(MAC_LOCKED_GAMEPLAY_CAPABILITIES)
    assert available.missing(MAC_FULL_CAMERA_CAPABILITIES) == ("relative_mouse",)


def test_basic_task_can_pass_without_relative_mouse():
    task = fake_task(
        AutoPickTask,
        DeviceCapabilities(keyboard_tap=True, scroll=True, foreground_only=True),
    )

    task.ensure_device_capabilities()
    assert task.get_required_capabilities().relative_mouse is False
    state = task.get_device_compatibility_state()
    assert state['status'] == 'experimental'
    assert state['level'] == MacTaskCapabilityLevel.MAC_BASIC.value


def test_locked_gameplay_task_can_pass_without_relative_mouse():
    task = fake_task(
        AutoCombatTask,
        DeviceCapabilities(
            keyboard_tap=True,
            keyboard_hold=True,
            absolute_mouse=True,
            mouse_left=True,
            mouse_middle=True,
            mouse_button_hold=True,
            foreground_only=True,
            relative_mouse=False,
        ),
    )

    task.ensure_device_capabilities()
    assert task.get_required_capabilities().relative_mouse is False
    state = task.get_device_compatibility_state()
    assert state['status'] == 'experimental'
    assert state['level'] == MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY.value


def test_missing_locked_gameplay_capability_is_rejected_before_run():
    task = fake_task(
        AutoCombatTask,
        DeviceCapabilities(
            keyboard_tap=True,
            absolute_mouse=True,
            mouse_left=True,
            mouse_middle=True,
            mouse_button_hold=True,
            foreground_only=True,
        ),
    )

    state = task.get_device_compatibility_state()
    assert state['status'] == 'missing-capabilities'
    assert state['level'] == MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY.value
    assert state['missing'] == ('keyboard_hold',)
    with pytest.raises(MissingDeviceCapabilitiesError) as exc_info:
        task.ensure_device_capabilities()

    assert exc_info.value.missing == ("keyboard_hold",)


def test_mouse_reset_remains_explicitly_unsupported_on_macos():
    task = fake_task(
        MouseResetTask,
        DeviceCapabilities.from_names(DeviceCapabilities.names()),
    )

    state = task.get_device_compatibility_state()
    assert state['status'] == 'unsupported'
    assert state['level'] is None
    assert state['missing'] == ()
    with pytest.raises(MacTaskUnsupportedError, match="not available on macOS"):
        task.ensure_device_capabilities()
