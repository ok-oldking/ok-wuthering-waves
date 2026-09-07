"""Build a standalone arm64 internal app with the PySide/Nuitka deployment path.

Run with the project's Python 3.12 venv. No dependency installation or signing
credential discovery is performed. Artifacts are local and must not be committed.
"""
import argparse
import importlib.metadata
import importlib.util
import os
import platform
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
import plistlib

if __package__:
    from .macos_build_metadata import (BUNDLE_ID, INTERNAL_MINIMUM_MACOS, PRODUCT_TARGET_MACOS,
                                      repository_provenance, sha256, bundle_cdhash, write_json)
    from .verify_macos_internal import verify
else:
    from macos_build_metadata import (BUNDLE_ID, INTERNAL_MINIMUM_MACOS, PRODUCT_TARGET_MACOS,
                                     repository_provenance, sha256, bundle_cdhash, write_json)
    from verify_macos_internal import verify


def preflight_openvino(package):
    """Reject non-relocatable wheels before expensive compilation; never patch them."""
    libraries = sorted([*(package / 'libs').glob('*.dylib'),
                        *(package / 'libs').glob('*.so')])
    if not libraries:
        raise SystemExit('OpenVINO native libraries are missing.')
    with tempfile.TemporaryDirectory(prefix='okww-dylib-preflight-') as temporary:
        for library in libraries:
            copied = Path(temporary) / library.name
            shutil.copy2(library, copied)
            subprocess.run(['install_name_tool', '-id', library.name, str(copied)], check=True)
            subprocess.run(['codesign', '--force', '--sign', '-', str(copied)], check=True)
            subprocess.run(['codesign', '--verify', '--strict', str(copied)], check=True)


def build_command(root, python):
    return [python, '-m', 'nuitka', '--standalone', '--macos-create-app-bundle',
            '--macos-target-arch=arm64', '--macos-app-name=OK-WW',
            '--macos-app-icon=' + str(root / 'build' / 'macos-internal' / 'OK-WW.icns'),
            '--macos-signed-app-name=org.okww.foreground.internal',
            '--macos-app-version=0.1.0', '--macos-app-mode=gui',
            '--macos-prohibit-multiple-instances', '--enable-plugin=pyside6',
            '--include-qt-plugins=platforms,imageformats,styles',
            '--follow-imports', '--include-package=ok', '--include-package=src',
            '--include-package=onnxocr', '--include-package-data=onnxocr',
            '--include-package=openvino', '--include-package-data=openvino',
            '--include-package=AppKit', '--include-package=Foundation',
            '--include-package=Quartz', '--include-package=ApplicationServices',
            '--include-package=ScreenCaptureKit',
            '--nofollow-import-to=onnxruntime,torch,tensorflow,ok.test,ok.ui.web',
            '--include-data-dir=assets=assets', '--include-data-dir=icons=icons',
            '--include-data-dir=i18n=i18n', '--include-package-data=ok',
            '--assume-yes-for-downloads', '--jobs=4',
            '--output-dir=' + str(root / 'build' / 'macos-internal'),
            '--report=' + str(root / 'build' / 'macos-internal' / 'compilation-report.xml'),
            str(root / 'macos_main.py')]


def prepare_app_icon(root):
    output = root / 'build' / 'macos-internal'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='okww-icon-') as temporary:
        iconset = Path(temporary) / 'OK-WW.iconset'
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                pixels = str(size * scale)
                suffix = '@2x' if scale == 2 else ''
                subprocess.run(['sips', '-z', pixels, pixels, str(root / 'icons' / 'icon.png'),
                                '--out', str(iconset / f'icon_{size}x{size}{suffix}.png')],
                               check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['iconutil', '-c', 'icns', str(iconset),
                        '-o', str(output / 'OK-WW.icns')], check=True)


def _build():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--dependency-root', type=Path,
                        help='Explicit isolated build dependencies; never changes the dev venv')
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'darwin' or platform.machine() != 'arm64' or sys.version_info[:2] != (3, 12):
        raise SystemExit('Requires the project Apple Silicon Python 3.12 venv.')
    if importlib.metadata.version('Nuitka') != '4.1.1':
        raise SystemExit('Requires Nuitka==4.1.1 (PySide6 6.11.2 deploy pin); install explicitly first.')
    root = Path(__file__).resolve().parents[1]
    command = build_command(root, sys.executable)
    if args.dry_run:
        print('\n'.join(command))
        return
    environment = os.environ.copy()
    if args.dependency_root:
        dependency_root = args.dependency_root.resolve()
        if (dependency_root / '.okww-native-deps-incomplete').exists():
            raise SystemExit('Native dependency preparation is incomplete; refusing to package it.')
        package = dependency_root / 'openvino'
        if not (package / 'okww_native_build.json').is_file():
            raise SystemExit('Run prepare_macos_native_deps.py first; provenance receipt is missing.')
        environment['PYTHONPATH'] = str(dependency_root) + os.pathsep + environment.get('PYTHONPATH', '')
    else:
        package = Path(importlib.util.find_spec('openvino').origin).parent
    preflight_openvino(package)
    if args.preflight_only:
        return
    prepare_app_icon(root)
    licenses = list(package.parent.glob('openvino-*.dist-info/licenses'))
    if len(licenses) != 1:
        raise SystemExit('Exactly one OpenVINO distribution license directory is required.')
    command.insert(-1, '--include-data-dir=' + str(licenses[0]) + '=licenses/openvino')
    (root / 'build' / 'macos-internal').mkdir(parents=True, exist_ok=True)
    import ok
    framework_root = Path(ok.__file__).resolve().parents[1]
    sources = {'ok_script': repository_provenance(framework_root),
               'okww': repository_provenance(root)}
    versions = subprocess.check_output([sys.executable, '-c',
        'import json,sys,importlib.metadata as m; from PySide6.QtCore import qVersion; '
        'print(json.dumps(dict(python=sys.version.split()[0],pyside=m.version("PySide6"),'
        'qt=qVersion(),openvino=m.version("openvino"))))'], env=environment, text=True)
    import json
    provenance = {'schema_version': 1, 'sources': sources, 'versions': json.loads(versions),
                  'bundle_id': BUNDLE_ID, 'minimum_macos': INTERNAL_MINIMUM_MACOS,
                  'product_target_macos': PRODUCT_TARGET_MACOS,
                  'probe_sha256': sha256(root / 'scripts' / 'macos_internal_probe.py'),
                  'probe_scope': 'build-source only; external runtime probe hash must be recorded per run',
                  'native_dependency_receipt_sha256': sha256(package / 'okww_native_build.json')}
    subprocess.run(command, cwd=root, env=environment, check=True)
    if sources != {'ok_script': repository_provenance(framework_root), 'okww': repository_provenance(root)}:
        raise SystemExit('Source changed during compilation; refusing to attest this build. Rebuild from a stable worktree.')
    bundle = root / 'build' / 'macos-internal' / 'macos_main.app'
    info_path = bundle / 'Contents' / 'Info.plist'
    with info_path.open('rb') as stream:
        info = plistlib.load(stream)
    icon_name = info.get('CFBundleIconFile', '')
    if not icon_name or not (bundle / 'Contents' / 'Resources' / icon_name).is_file():
        raise SystemExit('macOS bundle icon is missing; refusing to sign incomplete UI packaging.')
    # Declare actual internal compatibility, never rewrite Mach-O load commands.
    info['LSMinimumSystemVersion'] = INTERNAL_MINIMUM_MACOS
    with info_path.open('wb') as stream:
        plistlib.dump(info, stream)
    resources = bundle / 'Contents' / 'Resources'
    resources.mkdir(exist_ok=True)
    write_json(resources / 'build-provenance.json', provenance)
    subprocess.run(['codesign', '--force', '--sign', '-', str(bundle)], check=True)
    verification = verify(bundle)
    manifest = dict(provenance, cdhash=bundle_cdhash(bundle), native_minimums=verification['native_minimums'])
    write_json(bundle.parent / 'build-manifest.json', manifest)


def main():
    if sys.platform != 'darwin':
        raise SystemExit('Internal app builds require macOS.')
    import fcntl
    output = Path(__file__).resolve().parents[1] / 'build' / 'macos-internal'
    output.mkdir(parents=True, exist_ok=True)
    with (output / '.build.lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another internal build is using this output directory.')
        _build()


if __name__ == '__main__':
    main()
