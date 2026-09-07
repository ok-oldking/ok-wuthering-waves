import io
import json
from pathlib import Path
import subprocess
import tarfile

import pytest

from scripts import prepare_macos_native_deps as native


def test_rejects_archive_hash_before_any_subprocess_or_output(tmp_path, monkeypatch):
    archive = tmp_path / 'wrong.whl'
    archive.write_bytes(b'untrusted')
    output = tmp_path / 'build' / 'deps'
    monkeypatch.setattr(native.subprocess, 'run', lambda *a, **kw: pytest.fail('must not execute'))
    with pytest.raises(ValueError, match='SHA256 mismatch'):
        native.prepare(dict.fromkeys(native.ARCHIVE_HASHES, archive), output, Path('/cmake'))
    assert not output.exists()


def test_accepts_only_pinned_archive_hashes(tmp_path, monkeypatch):
    archive = tmp_path / 'archive'
    archive.write_bytes(b'pinned')
    monkeypatch.setattr(native, 'ARCHIVE_HASHES', {'openvino': native.sha256(archive)})
    native.verify_archives({'openvino': archive})


@pytest.mark.parametrize('relative', ['.', 'build', '.venv/deps', '../elsewhere'])
def test_output_must_be_new_build_subdirectory(tmp_path, relative):
    with pytest.raises(ValueError, match='below'):
        native.validate_output(tmp_path / relative, root=tmp_path)


def test_output_preserves_existing_directory_and_symlink(tmp_path):
    existing = tmp_path / 'build' / 'existing'
    existing.mkdir(parents=True)
    sentinel = existing / 'keep'
    sentinel.write_text('user data')
    with pytest.raises(ValueError, match='already exists'):
        native.validate_output(existing, root=tmp_path)
    link = tmp_path / 'build' / 'linked'
    link.symlink_to(existing, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        native.validate_output(link / 'new', root=tmp_path)
    assert sentinel.read_text() == 'user data'
    assert native.validate_output(tmp_path / 'build' / 'fresh', root=tmp_path).name == 'fresh'


def test_receipt_is_allowlisted_and_contains_no_local_paths(tmp_path):
    for name in native.LIBRARIES:
        (tmp_path / name).write_bytes(name.encode())
    receipt = native.build_receipt(tmp_path)
    encoded = json.dumps(receipt)
    assert str(tmp_path) not in encoded
    assert '/' not in encoded and '\\' not in encoded
    assert receipt['archive_sha256'] == native.ARCHIVE_HASHES
    assert set(receipt['rebuilt_library_sha256']) == set(native.LIBRARIES)
    assert receipt['target'] == {'architecture': 'arm64', 'macos_deployment_target': '13.0'}


def test_tar_data_filter_rejects_path_traversal(tmp_path):
    archive = tmp_path / 'source.tar.gz'
    with tarfile.open(archive, 'w:gz') as stream:
        member = tarfile.TarInfo('../escaped')
        member.size = 4
        stream.addfile(member, io.BytesIO(b'evil'))
    with pytest.raises(tarfile.FilterError):
        native.extract_source(archive, tmp_path / 'extract')
    assert not (tmp_path / 'escaped').exists()


def test_removes_only_generated_openvino_direct_url(tmp_path):
    metadata = tmp_path / f'openvino-{native.OPENVINO_VERSION}.dist-info'
    metadata.mkdir()
    direct_url = metadata / 'direct_url.json'
    direct_url.write_text(json.dumps({'url': 'file:///private/local/wheel.whl'}))
    retained = metadata / 'METADATA'
    retained.write_text('Version: pinned')
    unrelated = tmp_path / 'direct_url.json'
    unrelated.write_text('keep unrelated')
    native.remove_local_wheel_url(tmp_path)
    assert not direct_url.exists()
    assert retained.read_text() == 'Version: pinned'
    assert unrelated.read_text() == 'keep unrelated'
    native.remove_local_wheel_url(tmp_path)


def test_rejects_direct_url_symlink_without_removing_target(tmp_path):
    metadata = tmp_path / f'openvino-{native.OPENVINO_VERSION}.dist-info'
    metadata.mkdir()
    original = tmp_path / 'original.json'
    original.write_text('preserve')
    (metadata / 'direct_url.json').symlink_to(original)
    with pytest.raises(ValueError, match='symlink'):
        native.remove_local_wheel_url(tmp_path)
    assert original.read_text() == 'preserve'


def test_failed_install_keeps_incomplete_marker(tmp_path, monkeypatch):
    output = tmp_path / 'build' / 'deps'
    monkeypatch.setattr(native, 'verify_archives', lambda archives: None)
    monkeypatch.setattr(native, 'validate_output', lambda path: path)
    def run(command, **kwargs):
        if command[-1] == '--version':
            return subprocess.CompletedProcess(command, 0, f'cmake version {native.CMAKE_VERSION}\n')
        assert '--no-index' in command and '--no-deps' in command and '--no-compile' in command
        assert '--isolated' in command and '--target' in command
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(native.subprocess, 'run', run)
    with pytest.raises(subprocess.CalledProcessError):
        native.prepare({'openvino': Path('pinned.whl')}, output, Path('/cmake'))
    assert (output / native.INCOMPLETE).is_file()
    assert not (output / 'openvino' / 'okww_native_build.json').exists()


def test_rebuild_disables_absolute_build_rpath_and_relocates_owned_libraries(tmp_path, monkeypatch):
    tbb = tmp_path / 'onetbb' / 'source'
    hwloc = tmp_path / 'hwloc' / 'source'
    build = tmp_path / 'tbb-build'
    libraries = tmp_path / 'output' / 'openvino' / 'libs'
    for directory in (tbb, hwloc, build, libraries):
        directory.mkdir(parents=True)
    for name in native.LIBRARIES:
        (libraries / name).write_bytes(b'wheel original')
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        if '--build' in command:
            for name in native.LIBRARIES:
                (build / name).write_bytes(b'rebuilt')
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(native.subprocess, 'run', run)
    native.rebuild_tbb(Path('/cmake'), tbb, hwloc, build, libraries, {})
    configure = next(command for command in commands if '-S' in command)
    assert '-DCMAKE_SKIP_RPATH=ON' in configure
    assert '-DCMAKE_OSX_ARCHITECTURES=arm64' in configure
    assert '-DCMAKE_OSX_DEPLOYMENT_TARGET=13.0' in configure
    assert f'-DCMAKE_CXX_FLAGS=-ffile-prefix-map={tmp_path}=.' in configure
    assert commands[0][0] == str(hwloc / 'configure')
    assert all(command[0] != 'make' for command in commands)
    relocations = [command for command in commands if command[0] == 'install_name_tool']
    assert [command[3] for command in relocations] == [
        '@loader_path/libhwloc.dylib', '@loader_path/libtbbmalloc.2.dylib']
    assert all((libraries / name).read_bytes() == b'rebuilt' for name in native.LIBRARIES)
