import json
import sys
import threading
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import src.openvino_guard as guard


class TestOpenVinoGuard(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.state_file = str(Path(tmp.name) / "configs" / "openvino_state.json")

    def read_state(self):
        return json.loads(Path(self.state_file).read_text())

    def write_state(self, **kwargs):
        path = Path(self.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(kwargs))

    def resolve(self, version="1.0"):
        with patch.object(guard, "_start_probe") as start_probe:
            result = guard.resolve_openvino_params(self.state_file, version)
        return result, start_probe

    def test_first_launch_enables_openvino_and_writes_sentinel(self):
        result, start_probe = self.resolve()
        self.assertEqual(guard.ENABLED, result)
        self.assertEqual(guard.STATUS_INITIALIZING, self.read_state()["status"])
        start_probe.assert_called_once()

    def test_leftover_sentinel_disables_openvino(self):
        self.write_state(status=guard.STATUS_INITIALIZING, version="1.0")
        result, start_probe = self.resolve()
        self.assertEqual(guard.DISABLED, result)
        self.assertEqual(guard.STATUS_DISABLED, self.read_state()["status"])
        start_probe.assert_not_called()

    def test_leftover_sentinel_from_old_version_retries(self):
        self.write_state(status=guard.STATUS_INITIALIZING, version="1.0")
        result, start_probe = self.resolve(version="2.0")
        self.assertEqual(guard.ENABLED, result)
        self.assertEqual(guard.STATUS_INITIALIZING, self.read_state()["status"])
        start_probe.assert_called_once()

    def test_disabled_state_stays_disabled_for_same_version(self):
        self.write_state(status=guard.STATUS_DISABLED, version="1.0")
        result, start_probe = self.resolve(version="1.0")
        self.assertEqual(guard.DISABLED, result)
        start_probe.assert_not_called()

    def test_disabled_state_retries_after_app_update(self):
        self.write_state(status=guard.STATUS_DISABLED, version="1.0")
        result, start_probe = self.resolve(version="2.0")
        self.assertEqual(guard.ENABLED, result)
        self.assertEqual(guard.STATUS_INITIALIZING, self.read_state()["status"])
        start_probe.assert_called_once()

    def test_ok_state_probes_again(self):
        self.write_state(status=guard.STATUS_OK, version="1.0")
        result, start_probe = self.resolve()
        self.assertEqual(guard.ENABLED, result)
        self.assertEqual(guard.STATUS_INITIALIZING, self.read_state()["status"])
        start_probe.assert_called_once()

    def test_corrupt_state_treated_as_first_launch(self):
        path = Path(self.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json {")
        result, start_probe = self.resolve()
        self.assertEqual(guard.ENABLED, result)
        self.assertEqual(guard.STATUS_INITIALIZING, self.read_state()["status"])
        start_probe.assert_called_once()

    def test_probe_success_writes_ok_and_concludes(self):
        concluded = threading.Event()
        fake = types.ModuleType("openvino")
        fake.Core = lambda: SimpleNamespace(available_devices=["CPU"])
        with patch.dict(sys.modules, {"openvino": fake}):
            guard._probe(self.state_file, "1.0", concluded)
        state = self.read_state()
        self.assertEqual(guard.STATUS_OK, state["status"])
        self.assertEqual("1.0", state["version"])
        self.assertTrue(concluded.is_set())

    def test_probe_import_failure_writes_disabled(self):
        concluded = threading.Event()
        with patch.dict(sys.modules, {"openvino": None}):
            guard._probe(self.state_file, "1.0", concluded)
        self.assertEqual(guard.STATUS_DISABLED, self.read_state()["status"])
        self.assertTrue(concluded.is_set())

    def test_probe_does_not_conclude_when_verdict_write_fails(self):
        concluded = threading.Event()
        fake = types.ModuleType("openvino")
        fake.Core = lambda: SimpleNamespace(available_devices=["CPU"])
        with (
            patch.dict(sys.modules, {"openvino": fake}),
            patch.object(guard, "_write_state", return_value=False),
        ):
            guard._probe(self.state_file, "1.0", concluded)
        self.assertFalse(concluded.is_set())

    def test_clean_exit_before_probe_verdict_discards_sentinel(self):
        self.write_state(status=guard.STATUS_INITIALIZING, version="1.0")
        guard._discard_unfinished_probe(self.state_file, threading.Event())
        self.assertFalse(Path(self.state_file).exists())

    def test_clean_exit_keeps_concluded_probe_result(self):
        self.write_state(status=guard.STATUS_OK, version="1.0")
        concluded = threading.Event()
        concluded.set()
        guard._discard_unfinished_probe(self.state_file, concluded)
        self.assertTrue(Path(self.state_file).exists())

    def test_discard_tolerates_missing_file(self):
        guard._discard_unfinished_probe(self.state_file, threading.Event())


if __name__ == "__main__":
    unittest.main()
