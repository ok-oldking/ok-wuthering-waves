"""Run one unittest module without racing OCR warmup against Python shutdown."""

import faulthandler
import os
import unittest
from unittest.mock import patch


def main():
    # Windows CI hosts can advertise AMX instructions that the VM cannot execute.
    # Keep real OCR inference on a portable oneDNN path, before OpenVINO loads.
    os.environ.setdefault('ONEDNN_MAX_CPU_ISA', 'AVX2')
    faulthandler.enable()
    faulthandler.dump_traceback_later(120, repeat=True)
    # TaskExecutor.ocr_lib still loads real models synchronously when a test
    # needs OCR. Template-only tests never start the native model loader.
    with patch('ok.task.TaskExecutor.TaskExecutor.init_default_ocr', lambda self: None):
        unittest.main(module=None, verbosity=2)


if __name__ == '__main__':
    main()
