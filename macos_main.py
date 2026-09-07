"""Internal standalone macOS entry; uses the normal OK GUI and safety lifecycle."""
import os
import platform
from pathlib import Path
import sys


BUNDLE_IDENTIFIER = 'org.okww.foreground.internal'


def self_check(resource_root):
    """No capture, permission request, task startup or input in this diagnostic."""
    import gettext
    import ctypes
    import json
    import numpy as np
    import cv2
    import openvino
    import AppKit
    import Quartz
    import ApplicationServices
    import ScreenCaptureKit
    from Foundation import NSBundle
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    from onnxocr.onnx_paddleocr import ONNXPaddleOcr
    from src.OpenVinoYolo8Detect import OpenVinoYolo8Detect

    qt = QApplication([sys.argv[0]])
    assert qt.platformName() == 'cocoa', 'Qt cocoa platform plugin missing'
    assert not QImage(str(resource_root / 'icons' / 'icon.png')).isNull()
    gettext.translation('ok', str(resource_root / 'i18n'), languages=['zh_CN'])
    with (resource_root / 'assets' / 'coco_annotations.json').open(encoding='utf-8') as stream:
        assert json.load(stream)['images']
    assert hasattr(AppKit, 'NSWorkspace') and hasattr(Quartz, 'CGEventCreateKeyboardEvent')
    assert hasattr(ApplicationServices, 'AXIsProcessTrusted')
    assert hasattr(ScreenCaptureKit, 'SCStream')
    libs = Path(openvino.__file__).parent / 'libs'
    tbb = ctypes.CDLL(str(libs / 'libtbb.12.dylib'))
    assert tbb.TBB_runtime_interface_version() == 12130
    ctypes.CDLL(str(libs / 'libtbbbind_2_5.3.dylib'))
    ctypes.CDLL(str(libs / 'libtbbmalloc_proxy.2.dylib'))
    ocr = ONNXPaddleOcr(use_openvino=True, use_npu=False)
    result = ocr.ocr(np.zeros((80, 200, 3), dtype=np.uint8))
    assert not any(result), 'Blank OCR self-check returned unexpected text'
    model = OpenVinoYolo8Detect(str(resource_root / 'assets' / 'echo_model' / 'echo.onnx'))
    print(json.dumps({'self_check': 'passed', 'bundle_identifier': NSBundle.mainBundle().bundleIdentifier(),
                      'arch': platform.machine(), 'qt_platform': qt.platformName(),
                      'opencv': cv2.__version__, 'openvino': openvino.__version__,
                      'cpu': 'CPU' in openvino.Core().available_devices,
                      'blank_ocr_empty': not any(result),
                      'echo_model_size': [model.input_width, model.input_height],
                      'input_posts': 0}), flush=True)
    qt.quit()


def configure_paths(config, resource_root, data_root):
    """Keep installed resources read-only and user-generated files outside the app."""
    config['config_folder'] = str(data_root / 'configs')
    config['screenshots_folder'] = str(data_root / 'screenshots')
    for key, name in (('log_file', 'ok-ww.log'), ('error_log_file', 'ok-ww_error.log'),
                      ('launcher_log_file', 'launcher.log'),
                      ('launcher_error_log_file', 'launcher_error.log')):
        config[key] = str(data_root / 'logs' / name)
    config['gui_icon'] = str(resource_root / 'icons' / 'icon.png')
    config['template_matching']['coco_feature_json'] = str(resource_root / 'assets' / 'coco_annotations.json')
    config['ocr']['params'].update(use_openvino=True, use_npu=False)
    config.pop('update_pyappify', None)
    config['gui_title'] = 'OK-WW'
    config['version'] = '0.1.0 内部版'
    return config


def main():
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise RuntimeError('This internal app requires Apple Silicon macOS.')
    resource_root = Path(__file__).resolve().parent
    # Framework resource helpers also consult argv[0]; preserve it before chdir.
    sys.argv[0] = str(Path(sys.argv[0]).resolve())
    data_root = Path.home() / 'Library' / 'Application Support' / 'OK-WW Foreground'
    data_root.mkdir(parents=True, exist_ok=True)
    os.chdir(data_root)
    if '--self-check' in sys.argv:
        self_check(resource_root)
        return
    from config import config
    from ok import OK
    configure_paths(config, resource_root, data_root)
    app = OK(config)
    try:
        app.start()
    finally:
        app.quit()


if __name__ == '__main__':
    main()
