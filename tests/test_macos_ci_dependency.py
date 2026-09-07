"""The two integration gates must validate the same immutable framework."""
from pathlib import Path
import re


def test_both_ci_gates_pin_the_same_complete_framework_sha():
    workflows = Path(__file__).resolve().parents[1] / '.github' / 'workflows'
    refs = []
    for name in ('test.yml', 'macos-foreground-guardrails.yml'):
        text = (workflows / name).read_text(encoding='utf-8')
        match = re.search(r'repository: Silhouette-my/ok-script\s+ref: ([0-9a-f]{40})\s', text)
        assert match, f'{name} must pin a complete ok-script commit'
        refs.append(match.group(1))
        assert 'PYTHONPATH:' in text
        assert 'ok-script' in text
    assert refs[0] == refs[1]


def test_windows_matrix_uses_locked_runtime_without_resolving_framework_extras():
    workflow = (Path(__file__).resolve().parents[1] / '.github' / 'workflows'
                / 'macos-foreground-guardrails.yml').read_text(encoding='utf-8')
    windows = workflow.split('- name: Install Windows locked runtime and exact sibling', 1)[1]
    windows = windows.split('- name:', 1)[0]
    assert "if: runner.os == 'Windows'" in windows
    assert 'python -m pip install -r requirements.txt' in windows
    assert 'python -m pip check' in windows
    assert 'python -m pip install --no-deps -e ../ok-script -e .' not in windows
    assert '[default' not in windows
    assert 'PYTHONPATH: ${{ github.workspace }}/ok-script' in workflow
    # Dependency alignment must not remove either test suite on Windows.
    for step_name in ('Run platform and task capability contracts',
                      'Run legacy task tests in isolated processes'):
        step = workflow.split(f'- name: {step_name}', 1)[1].split('- name:', 1)[0]
        assert 'if:' not in step


def test_legacy_qt_platform_matches_each_host_without_changing_contracts():
    workflow = (Path(__file__).resolve().parents[1] / '.github' / 'workflows'
                / 'macos-foreground-guardrails.yml').read_text(encoding='utf-8')
    assert 'QT_QPA_PLATFORM: offscreen' in workflow
    contracts = workflow.split('- name: Run platform and task capability contracts', 1)[1]
    contracts = contracts.split('- name:', 1)[0]
    assert 'QT_QPA_PLATFORM:' not in contracts
    legacy = workflow.split('- name: Run legacy task tests in isolated processes', 1)[1]
    assert "QT_QPA_PLATFORM: ${{ runner.os == 'Windows' && 'windows' || 'offscreen' }}" in legacy
    assert 'python -m unittest "$test_file"' in legacy
