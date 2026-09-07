"""Read-only checks for an internal bundle; not a substitute for TCC/game tests."""
import argparse
import mmap
from pathlib import Path
import plistlib
import subprocess
import json

if __package__:
    from .macos_build_metadata import INTERNAL_MINIMUM_MACOS, native_minimum, version_tuple, validate_provenance
else:
    from macos_build_metadata import INTERNAL_MINIMUM_MACOS, native_minimum, version_tuple, validate_provenance


def _validated_bundle_path(bundle):
    bundle = Path(bundle).expanduser().resolve(strict=True)
    if not bundle.is_dir() or bundle.suffix != '.app':
        raise ValueError('bundle must be an existing .app directory')
    return bundle


def _validated_executable(bundle, info):
    name = info.get('CFBundleExecutable')
    if (not isinstance(name, str) or not name or name.startswith('-')
            or Path(name).name != name):
        raise ValueError('CFBundleExecutable must be a plain non-option file name')
    executable_dir = (bundle / 'Contents' / 'MacOS').resolve(strict=True)
    binary = (executable_dir / name).resolve(strict=True)
    if binary.parent != executable_dir or not binary.is_file():
        raise ValueError('CFBundleExecutable escapes Contents/MacOS or is not a file')
    return binary


def verify(bundle, minimum_macos=INTERNAL_MINIMUM_MACOS):
    bundle = _validated_bundle_path(bundle)
    with (bundle / 'Contents' / 'Info.plist').open('rb') as stream:
        info = plistlib.load(stream)
    errors = []
    if info.get('LSMinimumSystemVersion') != minimum_macos:
        errors.append('LSMinimumSystemVersion does not match declared internal minimum ' + minimum_macos)
    provenance_path = bundle / 'Contents' / 'Resources' / 'build-provenance.json'
    if not provenance_path.is_file():
        errors.append('missing signed build provenance')
    else:
        try:
            provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
            validate_provenance(provenance)
            if provenance.get('minimum_macos') != minimum_macos or provenance.get('bundle_id') != info.get('CFBundleIdentifier'):
                errors.append('build provenance identity/minimum mismatch')
        except (ValueError, TypeError, AttributeError) as error:
            errors.append('invalid signed build provenance: ' + str(error))
    if info.get('CFBundleIdentifier') != 'org.okww.foreground.internal':
        errors.append('unexpected CFBundleIdentifier')
    binary = _validated_executable(bundle, info)
    arch = subprocess.check_output(['lipo', '-archs', str(binary)], text=True).strip()
    if arch != 'arm64':
        errors.append('main executable is not arm64-only')
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(bundle)], check=True)
    forbidden = {'.venv', '__pycache__', '.git', 'configs', 'screenshots', 'logs'}
    personal_prefix = str(Path.home()).encode()
    macho_magic = {b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe'}
    native_count = 0
    native_minimums = {}
    for path in bundle.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(bundle)
        if forbidden.intersection(relative.parts) or path.suffix in {'.log', '.ips', '.crash', '.pyc'}:
            errors.append(f'private/generated file: {relative}')
        if not path.stat().st_size:
            continue
        with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            if data.find(personal_prefix) != -1:
                errors.append(f'build user path embedded: {relative}')
            if data[:4] in macho_magic:
                native_count += 1
                native_arch = subprocess.check_output(['lipo', '-archs', str(path)], text=True).split()
                if 'arm64' not in native_arch:
                    errors.append(f'no arm64 slice: {relative}')
                try:
                    minos = native_minimum(path)
                    native_minimums[str(relative)] = minos
                    if version_tuple(minos) > version_tuple(minimum_macos):
                        errors.append(f'native minimum {minos} exceeds {minimum_macos}: {relative}')
                except (ValueError, subprocess.CalledProcessError) as error:
                    errors.append(f'{relative}: {error}')
    for folder in ('assets', 'icons', 'i18n'):
        if not (binary.parent / folder).exists() and not (bundle / 'Contents' / 'Resources' / folder).exists():
            errors.append(f'missing resource directory: {folder}')
    print(f'identity={info.get("CFBundleIdentifier")} executable_arch={arch} native_files={native_count}')
    for error in errors:
        print('FAIL: ' + error)
    if errors:
        raise SystemExit(1)
    print('Static checks passed; runtime, TCC, game and exit acceptance remain separate.')
    print('OK-WW packaged MVP requires macOS 15+; macOS 13/14 are outside this product baseline.')
    return {'native_minimums': native_minimums}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--minimum-macos', default=INTERNAL_MINIMUM_MACOS)
    args = parser.parse_args()
    verify(args.bundle, args.minimum_macos)
