from types import SimpleNamespace

import numpy as np

from ok.device.services import PermissionKind
from scripts import smoke_macos_foreground_input as smoke


cleanup_order = []


class FakeStatus:
    state = SimpleNamespace(value="granted")
    granted = True
    settings_path = "settings"
    detail = ""


class FakePermissionService:
    def status(self, kind):
        assert kind in (
            PermissionKind.SCREEN_RECORDING,
            PermissionKind.ACCESSIBILITY,
        )
        return FakeStatus()


class FakeRect:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def to_dict(self):
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


class FakeGeometry:
    capture_generation = 7
    display_scale = 2.0

    def __init__(self, target_generation=3, x=0):
        self.target_generation = target_generation
        self.outer_geometry = FakeRect(x, 213, 960, 568)
        self.global_content_geometry = FakeRect(x, 241, 960, 540)


class FakeCapture:
    instances = []
    simulate_move = False

    def __init__(self, _exit_event, target, _permissions, **kwargs):
        self.closed = False
        self.target = target
        self.calls = 0
        self.moved = False
        self.invalidated = kwargs["on_input_invalidated"]
        self.instances.append(self)

    def get_frame_packet(self):
        self.calls += 1
        if self.simulate_move and self.calls >= 2:
            self.moved = True
            moved_outer = FakeRect(40, 213, 960, 568)
            self.target.snapshot = SimpleNamespace(
                candidate=SimpleNamespace(
                    process_id=10,
                    window_id=20,
                    outer_geometry=moved_outer,
                ),
            )
            geometry = FakeGeometry(target_generation=4, x=40)
        else:
            geometry = FakeGeometry()
        return SimpleNamespace(
            frame=np.zeros((1080, 1920, 3), dtype=np.uint8),
            geometry=geometry,
        )

    def diagnostics(self):
        return SimpleNamespace(rebuilds=1 if self.moved else 0)

    def close(self):
        cleanup_order.append("capture_close")
        self.closed = True


class FakeTarget:
    def __init__(self):
        self.snapshot = SimpleNamespace(
            candidate=SimpleNamespace(
                process_id=10,
                window_id=20,
                outer_geometry=FakeRect(0, 213, 960, 568),
            ),
        )

    def is_foreground(self):
        return False


class FakeSelection:
    status = SimpleNamespace(value="selected")
    selected = SimpleNamespace(window_id=20)


class FakeDiscovery:
    def select(self, _hints, manual_window_id=None):
        assert manual_window_id is None
        return FakeSelection()

    def bind(self, _selected, _hints):
        return FakeTarget()


class FakeInteraction:
    instances = []
    fail_destroy = False

    def __init__(self, *_args, **_kwargs):
        self.calls = []
        self.held = True
        self.instances.append(self)

    def on_run(self):
        self.calls.append(("on_run",))

    def send_key(self, key, down_time):
        self.calls.append(("send_key", key, down_time))

    def on_destroy(self):
        self.calls.append(("on_destroy",))
        cleanup_order.append("interaction_destroy")
        if self.fail_destroy:
            raise RuntimeError("release failed")
        self.held = False

    def stop(self):
        self.calls.append(("stop",))
        cleanup_order.append("interaction_stop")

    def release_all(self):
        self.calls.append(("release_all",))
        cleanup_order.append("interaction_release_all")
        self.held = False
        return True


def install_fakes(monkeypatch):
    cleanup_order.clear()
    FakeCapture.instances.clear()
    FakeCapture.simulate_move = False
    FakeInteraction.instances.clear()
    FakeInteraction.fail_destroy = False
    monkeypatch.setattr(smoke, "require_macos_foreground_host", lambda _feature: None)
    monkeypatch.setattr(
        smoke, "create_permission_service", lambda: FakePermissionService())
    monkeypatch.setattr(
        smoke, "create_macos_window_discovery", lambda: FakeDiscovery())
    monkeypatch.setattr(
        smoke, "candidate_diagnostics", lambda _candidate: {"window_id": 20})
    monkeypatch.setattr(
        smoke, "_load_runtime_types", lambda: (FakeCapture, FakeInteraction))


def test_execute_mode_requires_exact_confirmation_before_runtime(monkeypatch):
    called = []
    monkeypatch.setattr(
        smoke, "require_macos_foreground_host", lambda _feature: called.append(True))

    report, exit_code = smoke.run_smoke(execute=True, confirmation="wrong")

    assert exit_code == 2
    assert report["event_post_attempted"] is False
    assert report["action_completed"] is False
    assert "disarmed" in report["error"]
    assert called == []


def test_default_mode_is_read_only_but_checks_real_frame_contract(monkeypatch):
    install_fakes(monkeypatch)

    report, exit_code = smoke.run_smoke()

    assert exit_code == 0
    assert report["ready_for_one_f2_tap"] is True
    assert report["event_post_attempted"] is False
    assert report["action_completed"] is False
    assert report["capture"]["frame_width"] == 1920
    assert FakeInteraction.instances == []
    assert FakeCapture.instances[0].closed


def test_native_target_is_explicit_and_must_match_actual_frame(monkeypatch):
    install_fakes(monkeypatch)
    report, code = smoke.run_smoke(expected_frame=(1280, 800))
    assert code == 5
    assert not report['event_post_attempted'] and not FakeInteraction.instances
    original = FakeCapture.get_frame_packet

    def native(self):
        packet = original(self)
        packet.frame = np.zeros((800, 1280, 3), dtype=np.uint8)
        return packet

    monkeypatch.setattr(FakeCapture, 'get_frame_packet', native)
    report, code = smoke.run_smoke(expected_frame=(1280, 800))
    assert code == 0 and report['expected_frame'] == [1280, 800]
    assert not report['event_post_attempted'] and not FakeInteraction.instances


def test_unknown_frame_target_is_rejected_before_capture(monkeypatch):
    install_fakes(monkeypatch)
    report, code = smoke.run_smoke(expected_frame=(1512, 982))
    assert code == 2 and not FakeCapture.instances


def test_confirmed_mode_posts_only_one_f2_tap_and_cleans_up(monkeypatch):
    install_fakes(monkeypatch)

    report, exit_code = smoke.run_smoke(
        execute=True,
        confirmation=smoke.CONFIRMATION,
    )

    assert exit_code == 0
    assert report["event_post_attempted"] is True
    assert report["action_completed"] is True
    assert FakeInteraction.instances[0].calls == [
        ("on_run",),
        ("send_key", "f2", 0.05),
        ("on_destroy",),
    ]
    assert FakeCapture.instances[0].closed


def test_move_observation_is_read_only_and_requires_one_aligned_rebind(monkeypatch):
    install_fakes(monkeypatch)
    FakeCapture.simulate_move = True
    monkeypatch.setattr(smoke.time, "sleep", lambda _seconds: None)

    report, exit_code = smoke.run_smoke(observe_move=True, move_delay=0)

    assert exit_code == 0
    assert report["move_observed"] is True
    assert report["move_observation"]["stream_rebuilds"] == 1
    assert report["move_observation"]["maximum_geometry_difference"] == 0
    assert report["event_post_attempted"] is False
    assert FakeInteraction.instances == []
    assert FakeCapture.instances[0].closed


def test_interaction_cleanup_failure_is_nonzero_and_capture_still_closes(monkeypatch):
    install_fakes(monkeypatch)
    FakeInteraction.fail_destroy = True

    report, exit_code = smoke.run_smoke(
        execute=True,
        confirmation=smoke.CONFIRMATION,
    )

    assert exit_code == 7
    assert report["interaction_cleanup_error"] == "release failed"
    assert cleanup_order == [
        "interaction_destroy",
        "interaction_stop",
        "interaction_release_all",
        "capture_close",
    ]
    assert FakeInteraction.instances[0].held is False
    assert FakeCapture.instances[0].closed
