"""Print Stage C window metadata without starting capture or input."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import config
from ok.device.services import create_permission_service
from ok.device.window_target import (
    WindowMatchHints,
    candidate_diagnostics,
    create_macos_window_discovery,
)


def diagnose(manual_window_id: int | None = None) -> tuple[dict[str, object], int]:
    screen_recording, accessibility = create_permission_service().snapshot()
    report: dict[str, object] = {
        'screen_recording_permission': {
            'state': screen_recording.state.value,
            'settings_path': screen_recording.settings_path,
            'detail': screen_recording.detail,
        },
        'accessibility_permission': {
            'state': accessibility.state.value,
            'settings_path': accessibility.settings_path,
            'detail': accessibility.detail,
        },
    }
    if not screen_recording.granted:
        report['note'] = (
            '未请求系统权限；请由用户在系统设置中授权后重新运行。')
        return report, 2

    discovery = create_macos_window_discovery()
    selection = discovery.select(
        WindowMatchHints.from_mapping(config['macos']),
        manual_window_id=manual_window_id,
    )
    report.update({
        'selection_status': selection.status.value,
        'selected': (
            candidate_diagnostics(selection.selected)
            if selection.selected is not None else None
        ),
        'candidates': [
            candidate_diagnostics(candidate)
            for candidate in selection.candidates
        ],
        'persistable_hint': selection.stable_hint.to_mapping(),
        'note': (
            'content/capture geometry 与 display scale 在 Stage D 的真实 '
            'SCStream 帧到达前保持 unknown。'),
    })
    return report, 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description='枚举 OK-WW macOS Stage C 窗口候选，不启动截图或输入。')
    parser.add_argument(
        '--window-id', type=int,
        help='本次诊断显式选择的 runtime window ID；该 ID 不会被持久化。')
    args = parser.parse_args()
    report, exit_code = diagnose(args.window_id)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
