from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ok.task.exceptions import WaitFailedException
from src.task.NightmareNestTask import NightmareNestTask, NestTarget


def make_task():
    task = NightmareNestTask.__new__(NightmareNestTask)
    task._executor = SimpleNamespace(device_manager=SimpleNamespace(
        get_preferred_device=lambda: {'device': 'macos'}))
    task._unreachable_nests = set()
    travel = SimpleNamespace(name='gray_teleport')
    task.wait_until = Mock(return_value=travel)
    task.click = Mock()
    task.next_frame = Mock()
    task._find_first_feature = Mock(return_value=None)
    task._find_travel_button = Mock(return_value=travel)
    task.back = Mock()
    task.log_info = Mock()
    return task, NestTarget(object(), 'test-nest')


def test_delayed_loading_does_not_use_one_second_button_check():
    task, nest = make_task()
    def wait(**kwargs):
        assert kwargs == {'time_out': 120, 'raise_if_not_found': False}
        task.next_frame.assert_called_once()
        assert not task._unreachable_nests
        task.back.assert_not_called()
        # The map button can still be visible before the loading transition.
        return True
    task.wait_in_team_and_world = Mock(side_effect=wait)
    assert task._travel_to_nest_or_skip(nest)
    task._find_travel_button.assert_not_called()
    assert not task._unreachable_nests


@pytest.mark.parametrize('on_map', [True, False])
def test_only_confirmed_map_after_full_timeout_is_cached(on_map):
    task, nest = make_task()
    task.wait_in_team_and_world = Mock(return_value=False)
    task._find_travel_button.return_value = object() if on_map else None
    if on_map:
        assert not task._travel_to_nest_or_skip(nest)
        assert nest.cache_key in task._unreachable_nests
        task.back.assert_called_once()
    else:
        with pytest.raises(WaitFailedException, match='loading timed out'):
            task._travel_to_nest_or_skip(nest)
        assert not task._unreachable_nests
        task.back.assert_not_called()
    assert task.next_frame.call_count == 2


def test_capture_failure_does_not_cache_target_or_send_navigation():
    task, nest = make_task()
    task.next_frame.side_effect = RuntimeError('capture unavailable')
    task.wait_in_team_and_world = Mock()
    with pytest.raises(RuntimeError, match='capture unavailable'):
        task._travel_to_nest_or_skip(nest)
    assert not task._unreachable_nests
    task.back.assert_not_called()
    assert task.click.call_count == 1
