"""Game-layer policy for the selected Mac provider; no native OS dependencies."""
from src.macos_capabilities import MacTaskSupportStatus, MacTaskUnsupportedError


def uses_macos_provider(task):
    manager = getattr(task.executor, 'device_manager', None)
    device = manager.get_preferred_device() if manager else None
    return bool(device and device.get('device') == 'macos')


def task_required_capabilities(task, fallback):
    return task.get_macos_compatibility().required if task._uses_macos_provider() else fallback()


def decorate_task_compatibility(task, state):
    if not task._uses_macos_provider():
        return state
    compatibility = task.get_macos_compatibility()
    state['level'] = compatibility.level.value if compatibility.level else None
    if compatibility.status is MacTaskSupportStatus.UNSUPPORTED:
        return dict(status='unsupported', level=state['level'], missing=(), reason=compatibility.note)
    state['reason'] = compatibility.note
    if state['status'] == 'compatible':
        state['status'] = compatibility.status.value
    return state


def ensure_task_supported(task):
    if task._uses_macos_provider():
        compatibility = task.get_macos_compatibility()
        if compatibility.status is MacTaskSupportStatus.UNSUPPORTED:
            raise MacTaskUnsupportedError(task.name, compatibility)


def map_book_category_point(task, name, x, y):
    manager = task.executor.device_manager
    if (uses_macos_provider(task) and name != 'mengyan'
            and getattr(manager, 'coordinate_mode', 'legacy') == 'anchored'
            and task.out_of_ratio() and task.width / task.height < manager.supported_ratio):
        # The unscrolled list is top-aligned, including its lower rows. Leave
        # the scrolled nightmare path and recognized frame coordinates alone.
        return round(x * task.width), round(y * task.width / manager.supported_ratio)
    return None


def book_destination_ready_feature(task):
    # Mac guide and team pages share the close icon; only a distinct positive
    # feature establishes the team page. Keep the Windows/default contract.
    return 'team_start_challenge' if task._uses_macos_provider() else 'team_close'
