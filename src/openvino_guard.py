import atexit
import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

STATUS_INITIALIZING = 'initializing'
STATUS_OK = 'ok'
STATUS_DISABLED = 'disabled'

NOTE = 'Delete this file to retry OpenVINO acceleration.'

_probe_done = False


def resolve_openvino_params(state_file, version):
    """Decide OCR acceleration params, remembering native OpenVINO crashes across runs.

    openvino.Core() can die with a native access violation (0xc0000005) that
    Python cannot catch, killing the whole app on startup (issue #1504). A
    sentinel state file written before OpenVINO is first touched turns
    "crashes on every launch" into "crashes at most once": if a launch dies
    while the sentinel is still in place, the next launch falls back to ONNX
    Runtime CPU and persists that decision. OpenVINO is retried once after
    each app update, or when the user deletes the state file.
    """
    state = _read_state(state_file)
    status = state.get('status')
    if status == STATUS_DISABLED and state.get('version') == version:
        logger.warning('OpenVINO disabled by previous failure: %s', state.get('reason'))
        return {'use_openvino': False, 'use_npu': False}
    if status == STATUS_INITIALIZING:
        _write_state(state_file, STATUS_DISABLED, version,
                     reason='app crashed during OpenVINO init on a previous launch')
        logger.warning('previous launch crashed during OpenVINO init, falling back to ONNX Runtime CPU')
        return {'use_openvino': False, 'use_npu': False}
    _write_state(state_file, STATUS_INITIALIZING, version)
    _start_probe(state_file, version)
    return {'use_openvino': True, 'use_npu': True}


def _start_probe(state_file, version):
    atexit.register(_discard_unfinished_probe, state_file)
    threading.Thread(target=_probe, args=(state_file, version),
                     name='OpenVinoProbe', daemon=True).start()


def _probe(state_file, version):
    global _probe_done
    try:
        import openvino
        # dies with 0xc0000005 here on broken drivers, leaving the sentinel behind
        devices = openvino.Core().available_devices
        logger.info('OpenVINO probe ok, devices: %s', devices)
    except Exception as e:
        _write_state(state_file, STATUS_DISABLED, version, reason=f'OpenVINO unusable: {e}')
        logger.warning('OpenVINO probe failed, falling back to ONNX Runtime CPU on next launch: %s', e)
        _probe_done = True
        return
    _write_state(state_file, STATUS_OK, version)
    _probe_done = True


def _discard_unfinished_probe(state_file):
    # Clean exit before the probe concluded: no verdict, retry next launch.
    # Racing a just-finished probe only deletes a fresh result, causing a
    # harmless re-probe, so no lock is needed.
    if not _probe_done:
        try:
            os.remove(state_file)
        except OSError:
            pass


def _read_state(state_file):
    try:
        with open(state_file, encoding='utf-8') as f:
            state = json.load(f)
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(state_file, status, version, reason=None):
    try:
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        state = {'status': status, 'version': version, 'note': NOTE}
        if reason:
            state['reason'] = reason
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except OSError as e:
        logger.warning('could not write OpenVINO state file %s: %s', state_file, e)
