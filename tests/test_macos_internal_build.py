from pathlib import Path, PurePosixPath
import subprocess

import pytest

from scripts import build_macos_internal as build


def test_build_identity_and_resource_allowlist():
    command = build.build_command(PurePosixPath('/repo'), '/venv/bin/python')
    assert '--macos-signed-app-name=org.okww.foreground.internal' in command
    assert '--macos-target-arch=arm64' in command
    assert '--macos-app-name=OK-WW' in command
    assert '--macos-app-icon=/repo/build/macos-internal/OK-WW.icns' in command
    data = [arg for arg in command if arg.startswith('--include-data-dir=')]
    assert data == ['--include-data-dir=assets=assets', '--include-data-dir=icons=icons',
                    '--include-data-dir=i18n=i18n']


def test_preflight_failure_does_not_modify_dependency(tmp_path, monkeypatch):
    package = tmp_path / 'openvino'
    (package / 'libs').mkdir(parents=True)
    library = package / 'libs' / 'libtest.dylib'
    library.write_bytes(b'original dependency')
    def reject(command, **kwargs):
        assert Path(command[-1]) != library
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(build.subprocess, 'run', reject)
    with pytest.raises(subprocess.CalledProcessError):
        build.preflight_openvino(package)
    assert library.read_bytes() == b'original dependency'
