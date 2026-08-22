import re

import numpy as np
from PIL import Image

from ok import Logger

logger = Logger.get_logger(__name__)


class PositionDetector:
    CROP_BOX_1080P = (0, 1050, 240, 1080)

    def __init__(self):
        self.last_position = ''

    def _get_ocr_engine(self):
        from ok import og
        if og.executor is None:
            raise RuntimeError("TaskExecutor not initialized")
        return og.executor.ocr_lib()

    def preprocess(self, cropped):
        return cropped.resize((cropped.width * 2, cropped.height * 2), Image.LANCZOS)

    def do_ocr(self, arr):
        try:
            ocr_engine = self._get_ocr_engine()
        except RuntimeError:
            logger.warning("OCR engine not available")
            return []
        result = ocr_engine.ocr(arr, det=False, rec=True, cls=False)
        if result and result[0]:
            return [text for text, _ in result[0]]
        return []

    @staticmethod
    def try_parse_3nums(text):
        if not text:
            return None
        parts = text.split(",")
        if len(parts) == 3:
            for p in parts:
                if not p.lstrip("-").isdigit():
                    return None
            return text
        return None

    @staticmethod
    def _text_process(raw_text):
        text = ''.join(c if c.isalnum() or c == '-' else ',' for c in raw_text)
        comma_count = text.count(',')
        if comma_count >= 2:
            text = ''.join(c for c in text if c in set('0123456789,-'))
        else:
            text = ''.join(c if c.isdigit() or c == '-' else ',' for c in text)
        return text.strip(',')

    @staticmethod
    def _rule1_strip_space_20(text):
        idx = text.rfind(' ')
        if idx != -1:
            after = text[idx + 1:]
            if re.match(r'^20', after):
                text = text[:idx]
        return text

    @staticmethod
    def _rule2_strip_202_or_20(text):
        parts = [p for p in text.split(',') if p]
        if not parts:
            return text
        last = parts[-1]
        digits_only = ''.join(c for c in last if c.isdigit())
        if len(digits_only) <= 4:
            return text
        ridx = last.rfind('202')
        if ridx != -1:
            parts[-1] = last[:ridx]
            text = ','.join(parts)
            return text
        ridx = last.rfind('20')
        if ridx != -1:
            parts[-1] = last[:ridx]
            text = ','.join(parts)
            return text
        return text

    @staticmethod
    def _rule3_strip_before_first_minus(text):
        first_comma = text.find(',')
        if first_comma == -1:
            segment = text
            rest = ''
        else:
            segment = text[:first_comma]
            rest = text[first_comma:]
        minus_idx = segment.find('-')
        if minus_idx > 0:
            segment = segment[minus_idx:]
        return segment + rest

    @staticmethod
    def _enumerate_3nums(result):
        parts = [p for p in result.split(',') if p]
        if len(parts) == 3:
            candidate = ','.join(parts)
            if PositionDetector.try_parse_3nums(candidate):
                return candidate
        groups = re.findall(r'-?\d+', result)
        if len(groups) >= 3:
            for i in range(len(groups) - 2):
                for j in range(i + 1, len(groups) - 1):
                    for k in range(j + 1, len(groups)):
                        candidate = f'{groups[i]},{groups[j]},{groups[k]}'
                        if PositionDetector.try_parse_3nums(candidate):
                            return candidate
            candidate = ','.join(groups[:3])
            if PositionDetector.try_parse_3nums(candidate):
                return candidate
        return ''

    def postprocess(self, texts):
        if not texts:
            return ''
        joined = ''.join(texts)
        joined = self._rule1_strip_space_20(joined)
        joined = self._rule2_strip_202_or_20(joined)
        joined = self._rule3_strip_before_first_minus(joined)
        text = self._text_process(joined)
        if not text:
            return ''
        candidate = self._enumerate_3nums(text)
        if candidate:
            return candidate
        return ''

    def _calc_crop_box(self, frame_h, frame_w):
        scale = frame_h / 1080
        left = int(self.CROP_BOX_1080P[0] * scale)
        upper = int(self.CROP_BOX_1080P[1] * scale)
        right = int(self.CROP_BOX_1080P[2] * scale)
        lower = int(self.CROP_BOX_1080P[3] * scale)
        return (left, upper, right, lower)

    def detect_position(self, frame, crop_box=None):
        if frame is None:
            return ''
        if crop_box is None:
            h, w = frame.shape[:2]
            crop_box = self._calc_crop_box(h, w)

        if isinstance(frame, np.ndarray):
            img = Image.fromarray(frame[..., ::-1])
        else:
            img = frame

        cropped = img.crop(crop_box)
        processed = self.preprocess(cropped)
        arr = np.array(processed)
        if len(arr.shape) == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        texts = self.do_ocr(arr)
        position = self.postprocess(texts)
        self.last_position = position
        return position
