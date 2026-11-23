"""Per-account browser profiles for 云鸣潮 (cloud Wuthering Waves).

ok-script's ``BrowserCaptureMethod`` launches a Playwright persistent context in
one fixed directory (``cache/playwright``).  Consequently every account shares
the same cookie jar, and the multi-account task cannot keep several accounts
logged in at the same time.

This module gives each account its own Chromium profile under
``data/cloud_profiles/<account>/``.  A small, optional patch to ok-script (see
``tools/patch_ok_script_browser.py``) makes the launch read the active profile
directory and automatically restore/save ``storage_state.json`` (cookies plus
localStorage).  Without that patch the module still works for *live* switching:
``activate()`` writes cookies/localStorage into the already running context.

The module deliberately uses only the standard library so it can be imported
from ``config.py`` before the GUI framework is up.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

CONFIG_FOLDER = Path('configs')
DATA_FOLDER = Path('data')
STATE_FILE = CONFIG_FOLDER / 'cloud_browser.json'
LEGACY_PROFILE = Path('cache') / 'playwright'
ENV_PROFILE = 'OK_WW_CLOUD_PROFILE'

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
    return profiles_root() / (safe_account_name(account_key) if account_key else 'default')


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
    """Persist the active account and expose its profile to ok-script."""
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
    os.environ[ENV_PROFILE] = str(target.resolve())
    return target


def current_profile_dir() -> str:
    """Callable used as ``config['browser']['user_data_dir']``.

    It is evaluated by ok-script when the browser actually launches, so an
    account switch during a multi-account run is honoured by the next launch.
    """
    return str(profile_dir(get_active_account()).resolve())


def list_profiles() -> list[str]:
    root = profiles_root()
    if not root.exists():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def migrate_legacy_profile(account_key: str | None = None) -> Path:
    """Move an existing ``cache/playwright`` profile into the default account.

    Run once when upgrading an installation that already has a cloud login.
    """
    target = profile_dir(account_key)
    if target.exists() and any(target.iterdir()):
        return target
    if LEGACY_PROFILE.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(LEGACY_PROFILE), str(target))
    else:
        target.mkdir(parents=True, exist_ok=True)
    return target


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


async def _load_async(capture, path: Path) -> bool:
    context = getattr(capture, 'browser', None)
    if context is None or not path.exists():
        return False
    try:
        with path.open(encoding='utf-8') as stream:
            state = json.load(stream)
        cookies = state.get('cookies') or []
        if cookies:
            await context.clear_cookies()
            await context.add_cookies(cookies)
        page = getattr(capture, 'page', None)
        origins = state.get('origins') or []
        if page is not None and origins:
            url = getattr(page, 'url', '') or ''
            for origin in origins:
                origin_url = str(origin.get('origin', ''))
                if origin_url and not url.startswith(origin_url):
                    continue
                items = [(str(item.get('name', '')), str(item.get('value', '')))
                         for item in origin.get('localStorage', [])]
                if items:
                    await page.evaluate(
                        """items => { localStorage.clear();
                            for (const [name, value] of items) localStorage.setItem(name, value); }""",
                        items,
                    )
        return True
    except Exception as error:  # pragma: no cover - depends on live browser
        print(f'cloud_browser: failed to load storage state: {error}', file=sys.stderr)
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
    """Reload the cloud game page so newly loaded cookies take effect."""
    capture = get_browser_capture(task)
    if capture is None:
        return False
    return bool(_run(capture, _reload_async(capture)))


def restart_page(task=None) -> bool:
    """Restart the cloud game page by navigating to the configured entry URL.

    Falls back to a normal reload when no URL is configured or navigation
    fails.  Used by the auto-recovery path after a cloud task errors.
    """
    capture = get_browser_capture(task)
    if capture is None:
        return False
    return bool(_run(capture, _restart_async(capture)))


def save_current(task=None) -> bool:
    """Persist the live browser's cookies/localStorage for the active account."""
    capture = get_browser_capture(task)
    if capture is None:
        return False
    account = get_active_account()
    result = _run(capture, _save_async(capture, storage_state_path(account)))
    return bool(result)


def activate(account_key: str | None, task=None) -> Path:
    """Switch to ``account_key``, saving the previous account on the way out.

    Kept for callers that only need the profile pointer.  The cloud game keeps a
    live session in the page, so switching accounts reliably needs
    :func:`restart_browser` instead of just swapping cookies in a running page.
    """
    previous = get_active_account()
    if previous and previous != account_key:
        save_current(task)
    target = set_active_account(account_key)
    if previous != account_key:
        capture = get_browser_capture(task)
        if capture is not None:
            _run(capture, _load_async(capture, storage_state_path(account_key)))
    return target


def restart_browser(task=None, account_key=None, save_previous=True) -> bool:
    """Save the current account, then launch a fresh browser for ``account_key``.

    Injecting cookies into an already running page is not enough for 云鸣潮:
    the page keeps the previous account's session in memory/WebSocket, so the
    next account can silently stay logged out (or even revert to the old one).
    A dedicated browser per account is the reliable path: close the old
    Playwright context, point ok-script at the new per-account profile and open
    a brand new browser window.

    ``save_previous=False`` is used by the error-recovery path, where the old
    browser may be frozen and saving its storage state would only stall the
    restart (no account switch is happening there anyway).
    """
    executor = getattr(task, 'executor', None)
    manager = getattr(executor, 'device_manager', None)
    if manager is None:
        print('cloud_browser: no device manager available, cannot restart browser', file=sys.stderr)
        return False

    previous = get_active_account()
    if save_previous and previous and previous != account_key:
        save_current(task)
    if account_key is not None:
        set_active_account(account_key)

    old = getattr(manager, 'capture_method', None)
    if old is not None:
        try:
            old.close()
        except Exception as error:  # pragma: no cover - depends on live browser
            print(f'cloud_browser: failed to close previous browser: {error}', file=sys.stderr)
        manager.capture_method = None

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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='云鸣潮 account browser profiles')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list', help='List saved browser profiles')
    sub.add_parser('active', help='Show the active account')
    activate_parser = sub.add_parser('activate', help='Switch to an account')
    activate_parser.add_argument('account')
    save_parser = sub.add_parser('save', help='Save the current browser login state')
    save_parser.add_argument('account', nargs='?')
    sub.add_parser('migrate', help='Import the legacy cache/playwright profile')
    args = parser.parse_args(argv)

    if args.command == 'list':
        print('\n'.join(list_profiles()) or '(no profiles yet)')
        print(f'active: {get_active_account() or "(none)"}')
    elif args.command == 'active':
        print(get_active_account() or '(none)')
    elif args.command == 'activate':
        target = activate(args.account)
        print(f'active profile: {target}')
    elif args.command == 'save':
        if args.account:
            set_active_account(args.account)
        print('saved' if save_current() else 'no running cloud browser to save')
    elif args.command == 'migrate':
        print(f'profile: {migrate_legacy_profile(args.account if hasattr(args, "account") else None)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
