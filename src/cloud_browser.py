"""Per-account browser profiles for 云鸣潮 (cloud Wuthering Waves).

ok-script launches the browser with one fixed persistent profile
(``cache/playwright``), so every account shares the same cookie jar and two
accounts cannot stay logged in at the same time.

This module keeps one complete Chromium profile per account under
``data/cloud_profiles/<account>/`` and swaps the whole directory in and out of
``cache/playwright`` while the browser is closed.  Nothing in ok-script has to
change: the framework keeps using ``cache/playwright`` and simply finds the
other account's cookies there.

The module only uses the standard library plus the framework's capture classes,
so it can also be imported from ``config.py`` before the GUI is up.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

CONFIG_FOLDER = Path('configs')
DATA_FOLDER = Path('data')
STATE_FILE = CONFIG_FOLDER / 'cloud_browser.json'
# The directory ok-script hardcodes for the browser's persistent profile.
LIVE_PROFILE = Path('cache') / 'playwright'
# Marker inside the live profile telling which account it currently belongs to.
MARKER_NAME = '.okww_account'
DEFAULT_ACCOUNT = 'default'

_SAFE_RE = re.compile(r'[^A-Za-z0-9._-]+')


def safe_account_name(account_key: str) -> str:
    """Turn an account id into a portable, collision-free folder name."""
    key = str(account_key).strip()
    base = _SAFE_RE.sub('_', key).strip('._')[:60] or 'account'
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()[:8]
    return f'{base}-{digest}'


def profiles_root() -> Path:
    return DATA_FOLDER / 'cloud_profiles'


def profile_dir(account_key: str | None) -> Path:
    return profiles_root() / (safe_account_name(account_key) if account_key else DEFAULT_ACCOUNT)


def storage_state_path(account_key: str | None) -> Path:
    return profile_dir(account_key) / 'storage_state.json'


def _read_state() -> dict:
    try:
        with STATE_FILE.open(encoding='utf-8') as stream:
            state = json.load(stream)
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def get_active_account() -> str | None:
    account = _read_state().get('active_account')
    return str(account) if account else None


def set_active_account(account_key: str | None) -> Path:
    """Remember which account's profile the cloud device should start with."""
    target = profile_dir(account_key)
    target.mkdir(parents=True, exist_ok=True)
    state = _read_state()
    state['active_account'] = account_key or None
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=STATE_FILE.parent,
                                         prefix='.cloud_browser-', suffix='.tmp',
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, STATE_FILE)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return target


def list_profiles() -> list[str]:
    root = profiles_root()
    if not root.exists():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


# --- profile directory swapping ------------------------------------------------

def _read_marker(profile: Path) -> str | None:
    try:
        with (profile / MARKER_NAME).open(encoding='utf-8') as stream:
            account = json.load(stream).get('account')
        return str(account) if account else None
    except (OSError, ValueError, AttributeError):
        return None


def _write_marker(profile: Path, account_key: str | None) -> None:
    try:
        profile.mkdir(parents=True, exist_ok=True)
        with (profile / MARKER_NAME).open('w', encoding='utf-8') as stream:
            json.dump({'account': account_key or DEFAULT_ACCOUNT}, stream)
    except OSError as error:  # pragma: no cover - filesystem only
        print(f'cloud_browser: failed to write profile marker: {error}', file=sys.stderr)


_REPLACE_RETRIES = 8
_REPLACE_DELAY = 0.4


def _cleanup_retired(retired: Path) -> None:
    """Remove the parked old profile once the swap has safely completed."""
    if retired.exists():
        shutil.rmtree(retired, ignore_errors=True)


def _restore_retired(retired: Path, target: Path) -> None:
    """Put a half-swapped old profile back so nothing is left under .retired."""
    if retired.exists() and not target.exists():
        try:
            os.replace(retired, target)
        except OSError:  # pragma: no cover - still locked
            pass


def _try_swap(source: Path, target: Path, retired: Path):
    """Perform one rename attempt.

    Returns ``'done'`` on success, ``'retry'`` after a recoverable failure
    (the old profile is restored first), or ``('exdev', error)`` when the
    paths are on different volumes and a copy fallback is required.
    """
    try:
        if retired.exists():
            shutil.rmtree(retired)
        if target.exists():
            os.replace(target, retired)
        os.replace(source, target)
    except OSError as error:
        if error.errno == errno.EXDEV:
            # 跨盘时目标已经被挪到 retired 了, 交给 _copy_across_volumes 直接复制;
            # 先还原再挪一次只会让 copytree 撞上已存在的目录。
            return 'exdev', error
        _restore_retired(retired, target)
        return 'retry', error
    return 'done', None


def _copy_across_volumes(source: Path, target: Path, retired: Path) -> None:
    """Cross-volume fallback for different filesystems.

    ``target`` may still exist here (``_restore_retired`` runs only for
    non-EXDEV failures, but callers can reach this path with the old profile
    still in place) and ``shutil.copytree`` refuses to write into an existing
    directory — that made every cross-volume swap fail with FileExistsError.
    Move it aside first (same volume, so a plain rename), then copy; on failure
    restore the old profile instead of leaving a half-written directory behind.
    """
    if target.exists():
        if retired.exists():
            shutil.rmtree(retired, ignore_errors=True)
        try:
            os.replace(target, retired)
        except OSError as error:
            raise RuntimeError(
                f'cloud_browser: cannot move {target} aside for the cross-volume copy: {error}'
            ) from error
    try:
        shutil.copytree(source, target)
    except OSError:
        shutil.rmtree(target, ignore_errors=True)
        _restore_retired(retired, target)
        raise
    _cleanup_retired(retired)
    shutil.rmtree(source, ignore_errors=True)


def _replace_dir(source: Path, target: Path) -> None:
    """Move ``source`` onto ``target``, replacing it.

    Chromium keeps profile files locked for a while after ``close()`` returns.
    Never delete a locked target to work around that: the old behaviour wiped
    whatever it could and left a half-written profile behind, which is another
    way a browser restart appeared to "lose" the account.  Retry the rename,
    roll back if the old profile was already moved aside, and fail loudly if
    the profile cannot be swapped safely.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    retired = target.with_name(target.name + '.retired')
    last_error: OSError | None = None
    for attempt in range(_REPLACE_RETRIES):
        result, error = _try_swap(source, target, retired)
        if result == 'done':
            _cleanup_retired(retired)
            return
        last_error = error
        if result == 'exdev':
            break
        if attempt + 1 < _REPLACE_RETRIES:
            time.sleep(_REPLACE_DELAY)

    if last_error is not None and last_error.errno == errno.EXDEV:
        _copy_across_volumes(source, target, retired)
        return

    raise RuntimeError(
        f'cloud_browser: cannot swap browser profile {source} -> {target}: {last_error}'
    ) from last_error


def live_profile_account() -> str | None:
    """Which account the browser profile at ``cache/playwright`` belongs to."""
    return _read_marker(LIVE_PROFILE)


def profile_matches(account_key: str | None) -> bool:
    """True when ``cache/playwright`` already holds ``account_key``'s login state."""
    return bool(account_key) and LIVE_PROFILE.is_dir() and live_profile_account() == account_key


def resolve_account(account_key: str | None = None) -> str | None:
    """Which account owns the login state we are about to use.

    Error recovery/restart paths call ``restart_browser`` without an explicit
    account.  Guessing ``default`` there swaps in an unrelated (often empty)
    profile and logs the user out.  The marker inside the live profile is the
    authority on which cookies are actually loaded; ``cloud_browser.json`` is
    the fallback when the marker has not been written yet.
    """
    if account_key:
        return str(account_key)
    return live_profile_account() or get_active_account()


def prepare_live_profile(account_key: str | None) -> bool:
    """Make the live profile directory belong to ``account_key``.

    Must only be called while the browser is closed: Windows locks the files of
    a running Chromium profile.  Returns True when the directory already held
    that account (nothing was swapped).
    """
    account_key = account_key or DEFAULT_ACCOUNT
    if profile_matches(account_key):
        set_active_account(account_key)
        return True

    if LIVE_PROFILE.exists():
        # Whoever is logged in right now keeps the session they just used.
        _replace_dir(LIVE_PROFILE, profile_dir(live_profile_account() or DEFAULT_ACCOUNT))

    saved = profile_dir(account_key)
    if saved.exists():
        _replace_dir(saved, LIVE_PROFILE)
    else:
        LIVE_PROFILE.mkdir(parents=True, exist_ok=True)
    _write_marker(LIVE_PROFILE, account_key)
    set_active_account(account_key)
    return False


def adopt_live_profile(account_key: str | None) -> bool:
    """Claim the profile already open in the browser for ``account_key``.

    Used on the first run after upgrading: the browser is logged in but no
    per-account profile exists yet, so the live directory becomes that account's
    profile instead of being replaced by an empty one (which would log the user
    out for no reason).
    """
    if not account_key or not LIVE_PROFILE.is_dir() or live_profile_account():
        return False
    _write_marker(LIVE_PROFILE, account_key)
    set_active_account(account_key)
    return True


def migrate_legacy_profile(account_key: str | None = None) -> Path:
    """Move an existing ``cache/playwright`` profile into an account folder.

    Used once when upgrading an installation that was already logged in but has
    no per-account profiles yet.
    """
    target = profile_dir(account_key)
    if LIVE_PROFILE.exists() and not profile_matches(account_key):
        _replace_dir(LIVE_PROFILE, target)
        _write_marker(target, account_key)
    else:
        target.mkdir(parents=True, exist_ok=True)
        _write_marker(target, account_key)
    return target


# --- live browser helpers ------------------------------------------------------

def get_browser_capture(task=None):
    """Return the running BrowserCaptureMethod, or None in PC-client mode."""
    executor = getattr(task, 'executor', None)
    manager = getattr(executor, 'device_manager', None)
    capture = getattr(manager, 'capture_method', None)
    if capture is None:
        return None
    if capture.__class__.__name__ != 'BrowserCaptureMethod':
        return None
    return capture


def _run(capture, coroutine):
    """Run a coroutine on Playwright's private event loop and return its result."""
    runner = getattr(capture, 'run_in_loop', None)
    if runner is None:
        return None
    return runner(coroutine)


async def _save_async(capture, path: Path) -> bool:
    context = getattr(capture, 'browser', None)
    if context is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await context.storage_state(path=str(path))
        return path.exists()
    except Exception as error:  # pragma: no cover - depends on live browser
        print(f'cloud_browser: failed to save storage state: {error}', file=sys.stderr)
        return False


async def _reload_async(capture) -> bool:
    page = getattr(capture, 'page', None)
    if page is None:
        return False
    await page.reload()
    return True


async def _restart_async(capture) -> bool:
    """Navigate back to the cloud game entry URL (harder than a plain reload)."""
    page = getattr(capture, 'page', None)
    if page is None:
        return False
    capture_config = getattr(capture, 'config', None)
    url = capture_config.get('url') if isinstance(capture_config, dict) else None
    if url:
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            return True
        except Exception:
            pass
    await page.reload()
    return True


def reload_page(task=None) -> bool:
    """Reload the cloud game page."""
    capture = get_browser_capture(task)
    if capture is None:
        return False
    return bool(_run(capture, _reload_async(capture)))


def restart_page(task=None) -> bool:
    """Restart the cloud game page by navigating to the configured entry URL."""
    capture = get_browser_capture(task)
    if capture is None:
        return False
    return bool(_run(capture, _restart_async(capture)))


def save_current(task=None, account_key: str | None = None) -> bool:
    """Write a cookies/localStorage snapshot of the live browser for an account.

    The snapshot is a portable backup: the full Chromium profile directory is
    what actually gets restored, but the JSON survives even if the profile is
    rebuilt by a browser update.
    """
    capture = get_browser_capture(task)
    if capture is None:
        return False
    # Prefer the profile that is actually open: cloud_browser.json can be
    # updated ahead of the live profile (cloud_launch --account X), and saving
    # X's cookies under that stale id would give the wrong account a snapshot.
    account = resolve_account(account_key)
    result = _run(capture, _save_async(capture, storage_state_path(account)))
    if not result:
        return False
    # The live profile now belongs to this account even if it was never marked.
    if account and LIVE_PROFILE.exists():
        _write_marker(LIVE_PROFILE, account)
        set_active_account(account)
    return True


def _close_capture(manager) -> None:
    capture = getattr(manager, 'capture_method', None)
    if capture is None:
        return
    try:
        capture.close()
    except Exception as error:  # pragma: no cover - depends on live browser
        print(f'cloud_browser: failed to close previous browser: {error}', file=sys.stderr)
    manager.capture_method = None


def restart_browser(task=None, account_key=None, save_previous=True) -> bool:
    """Save the current account, then launch a fresh browser for ``account_key``.

    Injecting cookies into a running page is not enough for 云鸣潮: the page
    keeps the previous account's session in memory/WebSocket, so the next
    account can silently stay logged out.  Closing the browser and starting a
    new one on that account's own profile directory is the reliable path.

    ``save_previous=False`` is used by the error-recovery path, where the old
    browser may be frozen and saving its storage state would only stall the
    restart (no account switch is happening there anyway).
    """
    executor = getattr(task, 'executor', None)
    manager = getattr(executor, 'device_manager', None)
    if manager is None:
        print('cloud_browser: no device manager available, cannot restart browser', file=sys.stderr)
        return False

    # Resolve before closing the browser: error recovery calls us without an
    # account, and loading `default` there would silently log the active
    # account out.  save_current() still snapshots whichever account is live
    # right now, not the one we are switching to.
    account = resolve_account(account_key)

    if save_previous:
        save_current(task)

    _close_capture(manager)
    prepare_live_profile(account)

    try:
        from ok.device.capture import BrowserCaptureMethod
        from ok.device.interaction import BrowserInteraction
    except Exception as error:
        print(f'cloud_browser: cannot import browser classes: {error}', file=sys.stderr)
        return False

    browser_config = getattr(manager, 'browser_config', None) or {}
    capture = BrowserCaptureMethod(
        browser_config, getattr(manager, 'exit_event', None),
        global_config=getattr(manager, 'global_config', None))
    manager.capture_method = capture
    manager.interaction = BrowserInteraction(capture)
    try:
        capture.start_browser()
    except Exception as error:  # pragma: no cover - depends on live browser
        print(f'cloud_browser: failed to start browser: {error}', file=sys.stderr)
        return False
    return bool(capture.connected())


def switch_account(task, account_key: str) -> bool:
    """Switch the cloud device to ``account_key`` and restart the browser."""
    if not account_key:
        return False
    return restart_browser(task, account_key=account_key)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='云鸣潮 account browser profiles')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list', help='List saved browser profiles')
    sub.add_parser('active', help='Show the active account')
    activate_parser = sub.add_parser('activate', help='Switch to an account')
    activate_parser.add_argument('account')
    sub.add_parser('migrate', help='Import the legacy cache/playwright profile')
    args = parser.parse_args(argv)

    if args.command == 'list':
        print('\n'.join(list_profiles()) or '(no profiles yet)')
        print(f'active: {get_active_account() or "(none)"}')
    elif args.command == 'active':
        print(get_active_account() or '(none)')
    elif args.command == 'activate':
        print(f'profile: {prepare_live_profile(args.account)}')
    elif args.command == 'migrate':
        print(f'profile: {migrate_legacy_profile()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
