from pathlib import Path
import runpy

import pytest


@pytest.mark.parametrize('platform', ['win32', 'darwin'])
def test_native_ratio_is_opt_in_only_on_mac(monkeypatch, platform):
    monkeypatch.setattr('sys.platform', platform)
    config = runpy.run_path(str(Path(__file__).parents[1] / 'config.py'))['config']
    resolution = config['supported_resolution']
    assert resolution['ratio'] == '16:9'  # Keep the task/template reference.
    assert resolution['min_size'] == (1280, 720)
    if platform == 'darwin':
        assert resolution['allowed_ratios'] == ['16:9', '16:10']
        assert resolution['coordinate_mode'] == 'anchored'
        assert resolution['force_ratio'] is True
        assert resolution['resize_to'] == []
    else:
        assert resolution == {
            'ratio': '16:9', 'min_size': (1280, 720),
            'resize_to': [(2560, 1440), (1920, 1080), (1600, 900), (1280, 720)]}
