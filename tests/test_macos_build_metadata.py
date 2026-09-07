import subprocess

import pytest

from scripts.macos_build_metadata import parse_minos, repository_provenance, version_tuple


def test_product_and_internal_deployment_contract_agree():
    from scripts.macos_build_metadata import INTERNAL_MINIMUM_MACOS, PRODUCT_TARGET_MACOS
    assert INTERNAL_MINIMUM_MACOS == PRODUCT_TARGET_MACOS == '15.0'


@pytest.mark.parametrize('text, expected', [
    ('cmd LC_BUILD_VERSION\ncmdsize 32\nplatform 1\nminos 15.0\nsdk 26.2', '15.0'),
    ('cmd LC_VERSION_MIN_MACOSX\ncmdsize 16\nversion 13.0\nsdk 14.2', '13.0'),
])
def test_macho_deployment_target_parser(text, expected):
    assert parse_minos(text) == expected


def test_missing_minos_is_not_silently_accepted():
    with pytest.raises(ValueError):
        parse_minos('cmd LC_UUID\nversion 15.0')
    assert version_tuple('15') == version_tuple('15.0')
    assert version_tuple('15.1') > version_tuple('15.0')


def test_provenance_covers_untracked_and_tracked_changes_without_paths(tmp_path):
    def git(*args):
        subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)
    git('init')
    source = tmp_path / 'tracked.py'
    source.write_text('first')
    git('add', 'tracked.py')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
    clean = repository_provenance(tmp_path)
    assert clean['dirty'] is False
    extra = tmp_path / 'new.py'
    extra.write_text('untracked')
    dirty = repository_provenance(tmp_path)
    assert dirty['dirty'] is True
    assert dirty['diff_sha256'] == clean['diff_sha256']
    assert dirty['worktree_sha256'] != clean['worktree_sha256']
    source.write_text('changed')
    assert repository_provenance(tmp_path)['diff_sha256'] != clean['diff_sha256']
    assert str(tmp_path) not in str(dirty)
