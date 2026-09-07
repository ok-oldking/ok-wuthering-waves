"""离线准备内部包的隔离 OpenVINO / oneTBB 依赖，不修改开发 venv。

先显式下载并核验所列归档，再使用项目 Python 3.12 运行本脚本。
只重建 oneTBB；hwloc configure 仅生成头文件，运行库沿用已锁定 wheel。
失败的输出保留 incomplete 标记；重试必须选择新的 build/ 子目录。
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

try:
    from scripts.build_macos_internal import preflight_openvino
except ModuleNotFoundError:
    from build_macos_internal import preflight_openvino


ROOT = Path(__file__).resolve().parents[1]
OPENVINO_VERSION = '2025.4.1'
TBB_COMMIT = '1c4c93fc5398c4a1acb3492c02db4699f3048dea'
HWLOC_VERSION = '2.9.3'
CMAKE_VERSION = '3.31.6'
ARCHIVE_HASHES = {
    'openvino': '8d082e73af653a40b97efaa8219adf62c60f32060b9929ebcb60d7f14e79e4f1',
    'onetbb': 'fb9a554eb1ab728a4c9669e079152dcbad7fe258ee0f03e85bed0ba967efa71a',
    'hwloc': '5985db3a30bbe51234c2cd26ebe4ae9b4c3352ab788b1a464c40c0483bf4de59',
}
LIBRARIES = ('libtbb.12.dylib', 'libtbbmalloc.2.dylib',
             'libtbbmalloc_proxy.2.dylib', 'libtbbbind_2_5.3.dylib')
INCOMPLETE = '.okww-native-deps-incomplete'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_archives(archives):
    for name, expected in ARCHIVE_HASHES.items():
        path = archives[name]
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f'{name}: archive SHA256 mismatch or file missing; no build started.')


def validate_output(output, root=ROOT):
    """Reject existing outputs, symlink traversal and writes outside build/."""
    output = Path(os.path.abspath(output))
    build_root = root.resolve() / 'build'
    if output == build_root or not output.is_relative_to(build_root):
        raise ValueError('Output must be a new directory below this repository build/.')
    for component in (output, *output.parents):
        if component.is_symlink():
            raise ValueError('Output path must not traverse a symlink.')
        if component == root.resolve():
            break
    if output.exists():
        raise ValueError('Output already exists; preserve it and choose a new directory.')
    return output


def extract_source(archive, destination):
    destination.mkdir()
    with tarfile.open(archive, 'r:*') as source:
        source.extractall(destination, filter='data')
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir() or roots[0].is_symlink():
        raise ValueError('Source archive must contain exactly one real root directory.')
    return roots[0]


def build_receipt(libraries):
    """An allowlist only: never serialize local archive or build paths."""
    return {
        'schema_version': 1,
        'target': {'architecture': 'arm64', 'macos_deployment_target': '13.0'},
        'versions': {'openvino': OPENVINO_VERSION, 'onetbb_commit': TBB_COMMIT,
                     'hwloc': HWLOC_VERSION, 'cmake': CMAKE_VERSION},
        'archive_sha256': dict(ARCHIVE_HASHES),
        'rebuilt_library_sha256': {name: sha256(libraries / name) for name in LIBRARIES},
    }


def remove_local_wheel_url(output):
    """Remove only pip's newly generated local URL; hashes retain provenance."""
    metadata = output / f'openvino-{OPENVINO_VERSION}.dist-info'
    direct_url = metadata / 'direct_url.json'
    if metadata.is_symlink() or direct_url.is_symlink():
        raise ValueError('Unexpected symlink in generated OpenVINO metadata.')
    if direct_url.exists():
        direct_url.unlink()


def rebuild_tbb(cmake, tbb, hwloc, build, libraries, environment):
    subprocess.run([
        str(hwloc / 'configure'), '--disable-shared', '--disable-static',
        '--disable-libxml2', '--disable-io', '--disable-cairo', '--disable-netloc',
        '--disable-plugins',
    ], cwd=hwloc, env=environment, check=True)
    subprocess.run([
        str(cmake), '-S', str(tbb), '-B', str(build), '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=13.0',
        '-DCMAKE_SKIP_RPATH=ON',
        '-DTBB_TEST=OFF', '-DTBB_STRICT=OFF', '-DTBB_DISABLE_HWLOC_AUTOMATIC_SEARCH=ON',
        f'-DCMAKE_HWLOC_2_5_LIBRARY_PATH={libraries / "libhwloc.dylib"}',
        f'-DCMAKE_HWLOC_2_5_INCLUDE_PATH={hwloc / "include"}',
        f'-DCMAKE_CXX_FLAGS=-ffile-prefix-map={tbb.parent.parent}=.',
    ], env=environment, check=True)
    subprocess.run([str(cmake), '--build', str(build), '--parallel', '4'],
                   env=environment, check=True)
    for name in LIBRARIES:
        matches = {path.resolve() for path in build.rglob(name) if path.is_file()}
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one rebuilt {name}.')
        destination = libraries / name
        if destination.is_symlink() or not destination.is_file():
            raise ValueError(f'Unexpected wheel library layout: {name}.')
        shutil.copy2(matches.pop(), destination)
    relocations = (
        ('libtbbbind_2_5.3.dylib', '/usr/local/lib/libhwloc.15.dylib',
         '@loader_path/libhwloc.dylib'),
        ('libtbbmalloc_proxy.2.dylib', '@rpath/libtbbmalloc.2.dylib',
         '@loader_path/libtbbmalloc.2.dylib'),
    )
    for name, previous, replacement in relocations:
        library = str(libraries / name)
        subprocess.run(['install_name_tool', '-change', previous, replacement, library], check=True)
        subprocess.run(['codesign', '--force', '--sign', '-', library], check=True)


def prepare(archives, output, cmake):
    verify_archives(archives)
    output = validate_output(output)
    version = subprocess.run([str(cmake), '--version'], text=True, capture_output=True,
                             check=True).stdout.splitlines()[0]
    if version != f'cmake version {CMAKE_VERSION}':
        raise ValueError(f'Requires CMake=={CMAKE_VERSION}; install tooling explicitly first.')
    output.mkdir(parents=True, exist_ok=False)
    marker = output / INCOMPLETE
    marker.write_text('INCOMPLETE: do not package. On failure preserve this output and retry '
                      'with a new directory.\n', encoding='utf-8')
    environment = os.environ.copy()
    environment['MACOSX_DEPLOYMENT_TARGET'] = '13.0'
    subprocess.run([
        str(ROOT / '.venv' / 'bin' / 'python'), '-m', 'pip', '--isolated',
        '--disable-pip-version-check', 'install',
        '--no-index', '--no-deps', '--no-compile', '--target', str(output),
        str(archives['openvino']),
    ], env=environment, check=True)
    remove_local_wheel_url(output)
    libraries = output / 'openvino' / 'libs'
    if not (libraries / 'libhwloc.dylib').is_file():
        raise ValueError('Pinned wheel is missing libhwloc.dylib; output remains incomplete.')
    with tempfile.TemporaryDirectory(prefix='okww-native-deps-') as temporary:
        source_root = Path(temporary)
        tbb = extract_source(archives['onetbb'], source_root / 'onetbb')
        hwloc = extract_source(archives['hwloc'], source_root / 'hwloc')
        rebuild_tbb(cmake, tbb, hwloc, source_root / 'tbb-build', libraries, environment)
    preflight_openvino(output / 'openvino')
    receipt = output / 'openvino' / 'okww_native_build.json'
    receipt.write_text(json.dumps(build_receipt(libraries), indent=2, sort_keys=True) + '\n',
                       encoding='utf-8')
    marker.unlink()
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--openvino-wheel', type=Path, default=ROOT / 'build' / 'macos-internal' /
                        'openvino-2025.4.1-20426-cp312-cp312-macosx_11_0_arm64.whl')
    parser.add_argument('--onetbb-archive', type=Path, default=ROOT / 'build' / 'oneTBB-2021.13.0.tar.gz')
    parser.add_argument('--hwloc-archive', type=Path, default=ROOT / 'build' / 'hwloc-2.9.3.tar.gz')
    parser.add_argument('--cmake', type=Path, default=ROOT / 'build' / 'macos-tooling' /
                        'cmake' / 'data' / 'bin' / 'cmake')
    parser.add_argument('--output', type=Path, default=ROOT / 'build' / 'macos-native-deps')
    args = parser.parse_args()
    if (sys.platform != 'darwin' or platform.machine() != 'arm64'
            or sys.version_info[:2] != (3, 12)
            or Path(sys.prefix).resolve() != (ROOT / '.venv').resolve()):
        parser.error('Use this repository .venv/bin/python (Apple Silicon Python 3.12).')
    archives = {'openvino': args.openvino_wheel.resolve(),
                'onetbb': args.onetbb_archive.resolve(), 'hwloc': args.hwloc_archive.resolve()}
    try:
        result = prepare(archives, args.output, args.cmake.resolve())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        reason = str(error) if isinstance(error, ValueError) else type(error).__name__
        parser.exit(1, f'Native dependency preparation failed: {reason} '
                    'Do not package incomplete output; inspect the command diagnostics and '
                    'retry with a new --output directory.\n')
    print(f'Native dependencies prepared and Apple relocation preflight passed: {result}')


if __name__ == '__main__':
    main()
