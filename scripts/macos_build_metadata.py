"""Sanitized internal-build provenance and Mach-O deployment-target inspection."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

BUNDLE_ID = 'org.okww.foreground.internal'
INTERNAL_MINIMUM_MACOS = '15.0'
PRODUCT_TARGET_MACOS = '15.0'  # ADR 0003; framework API baseline remains 13+.


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repository_provenance(root):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root)
    # git diff alone omits untracked source; include every non-ignored source
    # file in a second fingerprint. Only digests/commit IDs leave this function.
    digest = hashlib.sha256()
    for raw in sorted(set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0'))):
        if not raw:
            continue
        path = root / raw.decode('utf-8')
        if path.is_symlink():
            digest.update(raw + b'\0link\0' + os.fsencode(os.readlink(path)))
        elif path.is_file():
            digest.update(raw + b'\0' + bytes.fromhex(sha256(path)))
        else:
            digest.update(raw + b'\0deleted')
    return {
        'commit': git('rev-parse', 'HEAD').decode().strip(),
        'dirty': bool(git('status', '--porcelain')),
        'diff_sha256': hashlib.sha256(git('diff', '--binary', 'HEAD')).hexdigest(),
        'worktree_sha256': digest.hexdigest(),
    }


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+){0,2}', value):
        raise ValueError('invalid macOS deployment target')
    return tuple(int(part) for part in value.split('.')) + (0,) * (3 - len(value.split('.')))


def parse_minos(text):
    versions = re.findall(r'cmd LC_BUILD_VERSION\b(?:(?!Load command).)*?\bminos (\d+(?:\.\d+){0,2})', text, re.S)
    versions += re.findall(r'cmd LC_VERSION_MIN_MACOSX\b(?:(?!Load command).)*?\bversion (\d+(?:\.\d+){0,2})', text, re.S)
    if not versions:
        raise ValueError('missing macOS deployment load command')
    return max(versions, key=version_tuple)


def native_minimum(path):
    return parse_minos(subprocess.check_output(
        ['otool', '-arch', 'arm64', '-l', str(path)], text=True))


def bundle_cdhash(bundle):
    result = subprocess.run(['codesign', '-d', '--verbose=4', str(bundle)],
                            capture_output=True, text=True, check=True)
    match = re.search(r'^CDHash=([0-9a-f]+)$', result.stderr, re.M)
    if not match:
        raise ValueError('missing bundle CDHash')
    return match.group(1)


def write_json(path, value):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.metadata-', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate_provenance(value):
    if not isinstance(value, dict) or value.get('schema_version') != 1:
        raise ValueError('invalid provenance schema')
    for key in ('probe_sha256', 'native_dependency_receipt_sha256'):
        if not re.fullmatch('[0-9a-f]{64}', str(value.get(key, ''))):
            raise ValueError('invalid provenance ' + key)
    for name in ('ok_script', 'okww'):
        source = value.get('sources', {}).get(name, {})
        if (not re.fullmatch('[0-9a-f]{40}', str(source.get('commit', '')))
                or not isinstance(source.get('dirty'), bool)):
            raise ValueError('invalid source identity ' + name)
        for key in ('diff_sha256', 'worktree_sha256'):
            if not re.fullmatch('[0-9a-f]{64}', str(source.get(key, ''))):
                raise ValueError('invalid source fingerprint ' + name)
    for name in ('python', 'pyside', 'qt', 'openvino'):
        if not isinstance(value.get('versions', {}).get(name), str) or not value['versions'][name]:
            raise ValueError('missing dependency version ' + name)
