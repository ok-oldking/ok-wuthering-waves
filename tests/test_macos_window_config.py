from config import config
from dataclasses import replace
from ok.device.window_target import (
    WindowCandidate,
    WindowGeometry,
    WindowMatchHints,
    WindowSelectionStatus,
    select_window_candidate,
)


def test_macos_window_config_uses_hardware_observed_official_app_identity():
    assert config['macos'] is not config['windows']
    assert config['macos']['bundle_identifiers'] == ['com.kurogame.mingchao']
    assert config['macos']['application_names'] == ['鸣潮']
    assert config['windows']['exe'] == 'Client-Win64-Shipping.exe'
    assert WindowMatchHints.from_mapping(config['macos']).allowed_layers == (0,)


def test_title_hint_with_wrong_app_identity_requires_explicit_manual_selection():
    hints = WindowMatchHints.from_mapping(config['macos'])
    candidate = WindowCandidate(
        process_id=42,
        window_id=7,
        bundle_identifier='com.example.not-observed',
        application_name='Unverified Application',
        title='Wuthering Waves',
        layer=0,
        outer_geometry=WindowGeometry(0, 0, 1280, 720),
    )

    result = select_window_candidate([candidate], hints)

    assert result.status is WindowSelectionStatus.MANUAL_SELECTION_REQUIRED
    assert result.selected is None


def test_hardware_observed_bundle_identity_selects_the_official_client():
    hints = WindowMatchHints.from_mapping(config['macos'])
    candidate = WindowCandidate(
        process_id=42,
        window_id=7,
        bundle_identifier='com.kurogame.mingchao',
        application_name='鸣潮',
        title='鸣潮',
        layer=0,
        outer_geometry=WindowGeometry(0, 0, 960, 568),
    )

    result = select_window_candidate([candidate], hints)

    assert result.status is WindowSelectionStatus.SELECTED
    assert result.selected is candidate

    helper = replace(candidate, window_id=8, outer_geometry=WindowGeometry(0, 0, 52, 20))
    # Enumeration order must not bind a small floating helper before the game.
    assert select_window_candidate([helper, candidate], hints).selected is candidate
    assert select_window_candidate([candidate, helper], hints).selected is candidate
    assert select_window_candidate([helper], hints).selected is None
    other_main = replace(candidate, window_id=9)
    assert select_window_candidate([candidate, other_main], hints).selected is None


def test_manual_window_choice_produces_only_stable_persistable_fields():
    hints = WindowMatchHints.from_mapping(config['macos'])
    candidate = WindowCandidate(
        process_id=42,
        window_id=7,
        bundle_identifier='com.example.observed',
        application_name='Observed Application',
        title='Wuthering Waves',
        layer=0,
        outer_geometry=WindowGeometry(0, 0, 1280, 720),
    )

    result = select_window_candidate([candidate], hints, manual_window_id=7)

    assert result.status is WindowSelectionStatus.SELECTED
    assert result.stable_hint.to_mapping() == {
        'bundle_identifier': 'com.example.observed',
        'application_name': 'Observed Application',
        'title': 'Wuthering Waves',
    }
    assert 'process_id' not in result.stable_hint.to_mapping()
    assert 'window_id' not in result.stable_hint.to_mapping()
