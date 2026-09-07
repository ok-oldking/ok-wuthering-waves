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
    assert refs[0] == refs[1]
    test_workflow = (workflows / 'test.yml').read_text(encoding='utf-8')
    assert 'PYTHONPATH: ${{ github.workspace }}/.ci/ok-script' in test_workflow


def test_branch_guardrail_is_dependency_free_and_source_only():
    workflow = (Path(__file__).resolve().parents[1] / '.github' / 'workflows'
                / 'macos-foreground-guardrails.yml').read_text(encoding='utf-8')
    assert 'python -m pip install' not in workflow
    assert 'python -m compileall -q src scripts config.py macos_main.py' in workflow
    assert 'Verify foreground-only integration boundaries' in workflow
    assert 'CGEvent.postToPid' in workflow
    assert 'PYTHONPATH: ${{ github.workspace }}/.ci/ok-script' in (
        Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'test.yml'
    ).read_text(encoding='utf-8')


def test_branch_guardrail_does_not_run_dependency_bound_qt_or_legacy_tests():
    workflow = (Path(__file__).resolve().parents[1] / '.github' / 'workflows'
                / 'macos-foreground-guardrails.yml').read_text(encoding='utf-8')
    assert 'QT_QPA_PLATFORM' not in workflow
    assert 'python -m unittest' not in workflow
    assert 'python -m pytest' not in workflow
    assert 'python -m pip install' not in workflow
