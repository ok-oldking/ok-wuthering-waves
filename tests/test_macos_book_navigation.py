"""Synthetic fixtures only; never capture a window or post input."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.task.BaseWWTask import BaseWWTask
from ok import Box


def task_for(device='macos', mode='anchored', width=1280, height=800):
    task = object.__new__(BaseWWTask)
    task._executor = SimpleNamespace(
        device_manager=SimpleNamespace(
            coordinate_mode=mode, supported_ratio=16 / 9,
            get_preferred_device=lambda: {'device': device}),
        method=SimpleNamespace(width=width, height=height))
    task.sleep = Mock()
    task.log_info = Mock()
    task.click = Mock()
    task.click_relative = Mock()
    return task


@pytest.mark.parametrize('category,y', [('wuyin', 526), ('canxiang', 598), ('zhange', 439)])
def test_native_tall_guide_rows_stay_top_aligned(category, y):
    task = task_for()
    task.open_boss_book(category, after_sleep=1)
    task.click.assert_called_once_with(307, y, after_sleep=1, name=category)
    task.click_relative.assert_not_called()


def test_native_tall_mapping_scales_without_changing_frame_geometry():
    task = task_for(width=2560, height=1600)
    task.open_boss_book('wuyin', after_sleep=1)
    task.click.assert_called_once_with(614, 1051, after_sleep=1, name='wuyin')
    assert (task.width, task.height) == (2560, 1600)


@pytest.mark.parametrize('device,mode,width,height', [
    ('windows', 'legacy', 1280, 800),
    ('windows', 'anchored', 1280, 800),
    ('macos', 'anchored', 1280, 720),
    ('windows', 'legacy', 1920, 1080),
])
def test_legacy_and_matching_ratio_keep_existing_click_path(device, mode, width, height):
    task = task_for(device, mode, width, height)
    task.open_boss_book('wuyin', after_sleep=1)
    task.click_relative.assert_called_once_with(.24, .73, after_sleep=1, name='wuyin')
    task.click.assert_not_called()


def test_scrolled_nightmare_path_is_not_recalibrated_without_evidence():
    task = task_for()
    task.open_boss_book('mengyan', after_sleep=1)
    assert task.click_relative.call_count == 2
    task.click.assert_not_called()


def test_mac_guide_close_alone_does_not_establish_team_page():
    task = task_for()
    def wait(names, **kwargs):
        assert 'team_close' not in names
        assert 'team_start_challenge' in names
        assert kwargs == dict(time_out=10, settle_time=.5, raise_if_not_found=True)
        raise TimeoutError('Only the shared close icon is present')
    task.wait_feature = Mock(side_effect=wait)
    with pytest.raises(TimeoutError):
        task.wait_book_destination()
    task.click.assert_not_called()


@pytest.mark.parametrize('device,name,expected', [
    ('macos', 'team_start_challenge', True),
    ('macos', 'gray_teleport', False),
    ('windows', 'team_close', True),
    ('windows', 'fast_travel_custom', False),
])
def test_destination_classification_preserves_legacy_branch(device, name, expected):
    task = task_for(device)
    task.wait_feature = Mock(return_value=SimpleNamespace(name=name))
    assert task.wait_book_destination() is expected
    team = 'team_start_challenge' if device == 'macos' else 'team_close'
    task.wait_feature.assert_called_once_with(
        ['fast_travel_custom', 'gray_teleport', 'remove_custom', team],
        time_out=10, settle_time=.5, raise_if_not_found=True)


@pytest.mark.parametrize('via_book_target', [False, True])
def test_formal_task_box_click_retains_target_with_default_move_false(via_book_target):
    task = task_for(width=1920, height=1080)
    del task.click  # Exercise BaseWWTask -> BaseTask -> click_box -> BaseWWTask.
    task.logger = Mock()
    task._executor.interaction = SimpleNamespace(click=Mock())
    task._executor.reset_scene = Mock()
    target = Box(1800, 340, 48, 34, name='boss_proceed')
    target.relative_with_variance = Mock(return_value=(1824, 357))
    if via_book_target:
        task._find_book_scroll_top = Mock(return_value=.2)
        task.box_of_screen = Mock(return_value=Box(1700, 200, 180, 700))
        task.find_feature = Mock(return_value=[target])
        task.draw_boxes = Mock()
        task.wait_book_destination = Mock(return_value=False)
        assert task.click_on_book_target(1, 4) is False
        task.wait_book_destination.assert_called_once_with()
    else:
        task.click(target, after_sleep=1)
    task._executor.interaction.click.assert_called_once_with(
        1824, 357, move_back=False, name='boss_proceed', move=False, down_time=.2, key='left')
