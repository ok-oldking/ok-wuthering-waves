import json
import plistlib

import pytest

from scripts import verify_macos_internal as verifier


@pytest.mark.parametrize('plist_min, native_min, provenance, succeeds', [
    ('15.0', '15.0', True, True),
    (None, '15.0', True, False),
    ('13.0', '15.0', True, False),
    ('15.0', '15.1', True, False),
    ('15.0', '15.0', False, False),
])
def test_minimum_and_provenance_are_hard_gates(tmp_path, monkeypatch, plist_min, native_min, provenance, succeeds):
    contents = tmp_path / 'App.app' / 'Contents'
    binary_dir = contents / 'MacOS'
    binary_dir.mkdir(parents=True)
    (binary_dir / 'main').write_bytes(b'\xcf\xfa\xed\xfe' + b'fixture')
    for name in ('assets', 'icons', 'i18n'):
        (binary_dir / name).mkdir()
    info = dict(CFBundleIdentifier='org.okww.foreground.internal', CFBundleExecutable='main')
    if plist_min is not None:
        info['LSMinimumSystemVersion'] = plist_min
    (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
    if provenance:
        (contents / 'Resources').mkdir()
        (contents / 'Resources' / 'build-provenance.json').write_text(json.dumps(
            dict(bundle_id=info['CFBundleIdentifier'], minimum_macos='15.0', schema_version=1,
                 probe_sha256='a' * 64, native_dependency_receipt_sha256='b' * 64,
                 sources={name: dict(commit='a' * 40, dirty=True, diff_sha256='b' * 64,
                                     worktree_sha256='c' * 64) for name in ('ok_script', 'okww')},
                 versions=dict(python='3.12', pyside='6.11.2', qt='6.11.2', openvino='2025.4.1'))))
    monkeypatch.setattr(verifier.subprocess, 'check_output', lambda *a, **k: 'arm64')
    monkeypatch.setattr(verifier.subprocess, 'run', lambda *a, **k: None)
    monkeypatch.setattr(verifier, 'native_minimum', lambda path: native_min)
    if succeeds:
        relative_binary = str((binary_dir / 'main').relative_to(contents.parent))
        assert verifier.verify(contents.parent)['native_minimums'][relative_binary] == native_min
    else:
        with pytest.raises(SystemExit):
            verifier.verify(contents.parent)


def test_verifier_rejects_untrusted_bundle_and_executable_paths(tmp_path):
    not_app = tmp_path / 'not-an-app'
    not_app.mkdir()
    with pytest.raises(ValueError, match=r'existing \.app directory'):
        verifier._validated_bundle_path(not_app)

    bundle = tmp_path / 'Bad.app'
    (bundle / 'Contents' / 'MacOS').mkdir(parents=True)
    with pytest.raises(ValueError, match='plain non-option file name'):
        verifier._validated_executable(bundle, {'CFBundleExecutable': '../escape'})
    with pytest.raises(ValueError, match='plain non-option file name'):
        verifier._validated_executable(bundle, {'CFBundleExecutable': '-option'})
