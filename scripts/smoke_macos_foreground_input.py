"""Preflight and explicitly arm one foreground-only macOS input smoke action."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import config
from ok.device.services import (
    PermissionKind,
    create_permission_service,
)
from ok.device.window_target import (
    WindowMatchHints,
    candidate_diagnostics,
    create_macos_window_discovery,
)
from ok.platform import require_macos_foreground_host
from ok.util.handler import ExitEvent


CONFIRMATION = "I_CONFIRM_ONE_F2_TAP"
EXPECTED_FRAME = (1920, 1080)
FRAME_TARGETS = ('1920x1080', '1280x800', '1352x845', '1512x945',
                 '2560x1600', '2704x1690', '3024x1890')


class _SmokeFinished(Exception):
    def __init__(self, exit_code: int):
        super().__init__(exit_code)
        self.exit_code = exit_code


def _load_runtime_types():
    # Keep Windows and non-Darwin imports isolated from PyObjC-backed modules.
    from ok.device.capture_methods import ScreenCaptureKitCaptureMethod
    from ok.device.interaction_methods import QuartzForegroundInteraction
    return ScreenCaptureKitCaptureMethod, QuartzForegroundInteraction


def _permission_report(status) -> dict[str, object]:
    return {
        "state": status.state.value,
        "granted": status.granted,
        "settings_path": status.settings_path,
        "detail": status.detail,
    }


def _wait_for_frame(capture, timeout: float, *, after_target_generation=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        packet = capture.get_frame_packet()
        if (
                packet is not None
                and (
                    after_target_generation is None
                    or packet.geometry.target_generation
                    != after_target_generation)):
            return packet
        time.sleep(0.02)
    raise RuntimeError(f"no complete ScreenCaptureKit frame within {timeout:.1f}s")


def _capture_report(packet) -> dict[str, object]:
    frame_height, frame_width = packet.frame.shape[:2]
    return {
        "frame_width": frame_width,
        "frame_height": frame_height,
        "target_generation": packet.geometry.target_generation,
        "capture_generation": packet.geometry.capture_generation,
        "display_scale": packet.geometry.display_scale,
        "outer_geometry": packet.geometry.outer_geometry.to_dict(),
        "global_content_geometry": (
            packet.geometry.global_content_geometry.to_dict()),
    }


def _geometry_difference(left, right) -> float:
    return max(abs(a - b) for a, b in (
        (left.x, right.x),
        (left.y, right.y),
        (left.width, right.width),
        (left.height, right.height),
    ))


def run_smoke(
        *, execute: bool = False, confirmation: str = "",
        observe_move: bool = False, move_delay: float = 8.0,
        window_id: int | None = None, timeout: float = 10.0,
        expected_frame: tuple[int, int] = EXPECTED_FRAME
        ) -> tuple[dict[str, object], int]:
    """Run a read-only preflight, or one explicitly confirmed F2 tap."""
    report: dict[str, object] = {
        "mode": (
            "execute-one-f2-tap" if execute else (
                "observe-window-move" if observe_move else "read-only-preflight")),
        "event_post_attempted": False,
        "action_completed": False,
        "expected_frame": list(expected_frame),
    }
    if 'x'.join(str(v) for v in expected_frame) not in FRAME_TARGETS:
        report['error'] = 'unsupported explicit frame target'
        return report, 2
    if timeout <= 0 or move_delay < 0:
        report["error"] = "timeout must be positive and move delay non-negative"
        return report, 2
    if execute and observe_move:
        report["error"] = "move observation and real input execution are separate modes"
        return report, 2
    if execute and confirmation != CONFIRMATION:
        report["error"] = (
            "real input remains disarmed; pass the exact confirmation token "
            f"{CONFIRMATION!r}")
        return report, 2

    capture = None
    interaction = None
    exit_event = ExitEvent()
    try:
        require_macos_foreground_host("OK-WW foreground input smoke")
        permission_service = create_permission_service()
        permissions = {
            kind.value: _permission_report(permission_service.status(kind))
            for kind in (
                PermissionKind.SCREEN_RECORDING,
                PermissionKind.ACCESSIBILITY,
            )
        }
        report["permissions"] = permissions
        if not all(value["granted"] for value in permissions.values()):
            report["error"] = "required macOS permissions are not granted"
            raise _SmokeFinished(3)

        hints = WindowMatchHints.from_mapping(config["macos"])
        discovery = create_macos_window_discovery()
        selection = discovery.select(hints, manual_window_id=window_id)
        report["selection_status"] = selection.status.value
        if selection.selected is None:
            report["error"] = "official Wuthering Waves window was not selected"
            raise _SmokeFinished(4)
        target = discovery.bind(selection.selected, hints)
        report["target"] = candidate_diagnostics(target.snapshot.candidate)
        report["frontmost_before_run"] = target.is_foreground()

        capture_type, interaction_type = _load_runtime_types()

        def invalidate_input(_capture, reason: str) -> None:
            if interaction is not None:
                interaction.invalidate(reason)

        capture = capture_type(
            exit_event,
            target,
            permission_service,
            lifecycle_timeout=timeout,
            on_input_invalidated=invalidate_input,
        )
        packet = _wait_for_frame(capture, timeout)
        report["capture"] = _capture_report(packet)
        frame_width = report["capture"]["frame_width"]
        frame_height = report["capture"]["frame_height"]
        if (frame_width, frame_height) != expected_frame:
            report["error"] = (
                f"hardware smoke requires an actual {expected_frame[0]}x{expected_frame[1]} content frame")
            raise _SmokeFinished(5)

        report["ready_for_one_f2_tap"] = True
        if observe_move:
            initial_generation = packet.geometry.target_generation
            initial_rebuilds = capture.diagnostics().rebuilds
            print(
                f"MOVE_WINDOW_NOW: move the game window once within {move_delay:.1f}s",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(move_delay)
            moved_packet = _wait_for_frame(
                capture,
                timeout,
                after_target_generation=initial_generation,
            )
            moved_snapshot = target.snapshot
            if moved_snapshot.candidate is None:
                raise RuntimeError("game window disappeared during move observation")
            rebuilds = capture.diagnostics().rebuilds - initial_rebuilds
            geometry_difference = _geometry_difference(
                moved_snapshot.candidate.outer_geometry,
                moved_packet.geometry.outer_geometry,
            )
            report["move_observation"] = {
                "initial_target_generation": initial_generation,
                "final_target_generation": moved_packet.geometry.target_generation,
                "stream_rebuilds": rebuilds,
                "target_outer_geometry": (
                    moved_snapshot.candidate.outer_geometry.to_dict()),
                "capture_outer_geometry": (
                    moved_packet.geometry.outer_geometry.to_dict()),
                "maximum_geometry_difference": geometry_difference,
                "capture_after_move": _capture_report(moved_packet),
            }
            if rebuilds != 1 or geometry_difference > 0.5:
                report["error"] = (
                    "window move did not produce one aligned fail-closed rebind")
                raise _SmokeFinished(6)
            report["move_observed"] = True
            raise _SmokeFinished(0)
        if not execute:
            raise _SmokeFinished(0)

        interaction = interaction_type(
            capture,
            target,
            permission_service,
            exit_event=exit_event,
        )
        interaction.on_run()
        report["event_post_attempted"] = True
        interaction.send_key("f2", down_time=0.05)
        report["action_completed"] = True
        report["action"] = "one F2 key tap"
        raise _SmokeFinished(0)
    except _SmokeFinished as result:
        exit_code = result.exit_code
    except Exception as error:
        report["error"] = str(error)
        exit_code = 1
    finally:
        cleanup_failed = False
        if interaction is not None:
            try:
                interaction.on_destroy()
            except Exception as error:
                report["interaction_cleanup_error"] = str(error)
                cleanup_failed = True
                try:
                    interaction.stop()
                except Exception as fallback_error:
                    report["interaction_stop_fallback_error"] = str(fallback_error)
                try:
                    released = interaction.release_all()
                    if released is False:
                        report["interaction_release_fallback_error"] = (
                            "one or more held-input release events failed")
                except Exception as fallback_error:
                    report["interaction_release_fallback_error"] = str(fallback_error)
        if capture is not None:
            try:
                capture.close()
            except Exception as error:
                report["capture_cleanup_error"] = str(error)
                cleanup_failed = True
    return report, 7 if cleanup_failed else exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "默认只预检；显式确认后仅向前台官方客户端发送一次 F2 tap。"))
    parser.add_argument("--window-id", type=int)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument('--expected-frame-size', choices=FRAME_TARGETS, default='1920x1080',
                        help='显式验收内容帧尺寸；按新截图实测选择，不根据菜单或Retina倍数猜测。')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--execute-one-f2-tap",
        action="store_true",
        help="通过全部 gate 后发送一次 F2 tap。",
    )
    mode.add_argument(
        "--observe-window-move",
        action="store_true",
        help="只读观察一次手动窗口移动后的 generation 与 stream 重建。",
    )
    parser.add_argument(
        "--move-delay",
        type=float,
        default=8.0,
        help="窗口移动观察模式中留给人工移动的秒数。",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"真实输入确认短语：{CONFIRMATION}",
    )
    args = parser.parse_args()
    report, exit_code = run_smoke(
        execute=args.execute_one_f2_tap,
        confirmation=args.confirm,
        observe_move=args.observe_window_move,
        move_delay=args.move_delay,
        window_id=args.window_id,
        timeout=args.timeout,
        expected_frame=tuple(int(v) for v in args.expected_frame_size.split('x')),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
