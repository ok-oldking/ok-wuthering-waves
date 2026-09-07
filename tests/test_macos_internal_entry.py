from pathlib import PurePosixPath

from macos_main import BUNDLE_IDENTIFIER, configure_paths


def test_internal_paths_do_not_write_into_bundle():
    config = {'ocr': {'params': {'use_npu': True}}, 'template_matching': {},
              'update_pyappify': {'zip_url': 'windows-only'}}
    configure_paths(config, PurePosixPath('/Applications/Test.app/Contents/MacOS'), PurePosixPath('/data'))
    assert BUNDLE_IDENTIFIER == 'org.okww.foreground.internal'
    assert config['config_folder'] == '/data/configs'
    assert config['log_file'] == '/data/logs/ok-ww.log'
    assert config['screenshots_folder'] == '/data/screenshots'
    assert config['ocr']['params'] == {'use_openvino': True, 'use_npu': False}
    assert 'update_pyappify' not in config
    assert config['gui_title'] == 'OK-WW'
    assert config['version'] == '0.1.0 内部版'
    assert config['gui_icon'].startswith('/Applications/Test.app/')
