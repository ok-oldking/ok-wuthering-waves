"""Frame-independent controls. No personal paths or gameplay/resource changes."""
import time


def wait_seconds(task, seconds, clock=time.monotonic):
    from ok import TaskDisabledException
    remaining = float(seconds)
    previous = clock()
    was_paused = bool(task.paused or task.executor.paused)
    while True:
        if task.executor.exit_event.is_set() or not task.enabled:
            raise TaskDisabledException()
        paused = bool(task.paused or task.executor.paused)
        now = clock()
        if not paused and not was_paused:
            remaining -= max(0, now - previous)
        previous, was_paused = now, paused
        if remaining <= 0 and not paused:
            return
        task.executor.exit_event.wait(min(0.1, max(0.01, remaining)))


def close_selected_game(manager, timeout=15):
    """Terminate only the selected game identity, not launcher/accelerator/app."""
    import os
    import psutil
    import win32process
    def confirm_no_game():
        for process in psutil.process_iter(['name']):
            if (process.info.get('name') or '').lower() == 'client-win64-shipping.exe':
                raise RuntimeError('Game process is still running without a verified target window')
    window = manager.hwnd_window
    if window is None or not getattr(window, 'hwnd', None):
        confirm_no_game()
        return  # No selected game: an idempotent no-op, not a name-wide kill.
    expected = getattr(window, 'exe_full_path', '')
    normalize = lambda path: os.path.normcase(os.path.realpath(path))
    if os.path.basename(expected).lower() != 'client-win64-shipping.exe':
        raise RuntimeError('Selected window is not the game; refusing to close it')
    try:
        _, pid = win32process.GetWindowThreadProcessId(window.hwnd)
    except Exception as exc:
        # Refresh a vanished HWND, but never invent a PID from a process name.
        manager.do_refresh(True)
        if manager.hwnd_window is None or not getattr(manager.hwnd_window, 'hwnd', None):
            confirm_no_game()
            return
        raise RuntimeError('Could not verify game process identity') from exc
    try:
        process = psutil.Process(pid)
        created = process.create_time()
        if normalize(process.exe()) != normalize(expected):
            raise RuntimeError('Game process path changed; refusing to close it')
        if process.create_time() != created or not process.is_running():
            raise RuntimeError('Game process identity changed; refusing to close it')
        process.terminate()
        process.wait(timeout=timeout)
    except psutil.NoSuchProcess:
        return
    except psutil.TimeoutExpired as exc:
        raise RuntimeError('Game exit timed out; no other process was killed') from exc
    manager.do_refresh(True)
