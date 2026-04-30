from __future__ import annotations

import importlib
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from .interfaces import Box, ImageInput, OCRAdapter, OCRText


def _to_text_items(
    raw_items: List[Tuple[List[List[float]], str, float]],
    offset_x: int,
    offset_y: int,
) -> List[OCRText]:
    texts: List[OCRText] = []
    for points, text_raw, score_raw in raw_items:
        text = str(text_raw).strip()
        if not text:
            continue
        score = float(score_raw)
        xs = [int(p[0]) for p in points]
        ys = [int(p[1]) for p in points]
        x1 = min(xs) + offset_x
        y1 = min(ys) + offset_y
        x2 = max(xs) + offset_x
        y2 = max(ys) + offset_y
        box = Box(x1, y1, x2, y2)
        texts.append(
            OCRText(
                text=text,
                box=box,
                confidence=max(0.0, min(1.0, score)),
                font_size=max(8, box.height),
            )
        )
    return texts


class DummyOCRAdapter(OCRAdapter):
    name = "Dummy"

    def recognize(self, image: ImageInput, region: Optional[Box] = None) -> List[OCRText]:
        if region is None:
            region = Box(20, 20, 380, 84)
        return [
            OCRText(
                text="[Dummy] OCR engine unavailable",
                box=region.normalized(),
                confidence=1.0,
                font_size=14,
            )
        ]


class TesseractOCRAdapter(OCRAdapter):
    name = "Tesseract"

    def __init__(self, tesseract_cmd: Optional[str] = None) -> None:
        self.module = importlib.import_module("pytesseract")
        if tesseract_cmd:
            self.module.pytesseract.tesseract_cmd = tesseract_cmd

    def recognize(self, image: ImageInput, region: Optional[Box] = None) -> List[OCRText]:
        image = _to_pil_rgb(image)
        ox, oy = 0, 0
        if region is not None:
            r = region.normalized()
            image = image.crop((r.x1, r.y1, r.x2, r.y2))
            ox, oy = r.x1, r.y1

        data = self.module.image_to_data(image, output_type=self.module.Output.DICT)
        out: List[OCRText] = []
        for i, raw in enumerate(data["text"]):
            txt = raw.strip()
            if not txt:
                continue
            try:
                conf = max(0.0, min(1.0, float(data["conf"][i]) / 100.0))
            except Exception:
                conf = 0.0
            x, y = int(data["left"][i]) + ox, int(data["top"][i]) + oy
            w, h = int(data["width"][i]), int(data["height"][i])
            if w <= 0 or h <= 0:
                continue
            out.append(
                OCRText(
                    text=txt,
                    box=Box(x, y, x + w, y + h),
                    confidence=conf,
                    font_size=max(8, h),
                )
            )
        return out


class RapidOCRAdapter(OCRAdapter):
    name = "RapidOCR"

    def __init__(self) -> None:
        module = importlib.import_module("rapidocr_onnxruntime")
        self.engine = getattr(module, "RapidOCR")()

    def recognize(self, image: ImageInput, region: Optional[Box] = None) -> List[OCRText]:
        ox, oy = 0, 0
        if region is None and isinstance(image, str):
            result, _elapsed = self.engine(image)
        else:
            image = _to_pil_rgb(image)
            if region is not None:
                r = region.normalized()
                image = image.crop((r.x1, r.y1, r.x2, r.y2))
                ox, oy = r.x1, r.y1
            result, _elapsed = self.engine(np.array(image))
        if not result:
            return []
        parsed = [(item[0], item[1], item[2]) for item in result if len(item) >= 3]
        return _to_text_items(parsed, ox, oy)


class PaddleOCRAdapter(OCRAdapter):
    name = "PaddleOCR"

    def __init__(self) -> None:
        module = importlib.import_module("paddleocr")
        PaddleOCR = getattr(module, "PaddleOCR")
        self.engine = PaddleOCR(use_angle_cls=True, lang="ch")

    def recognize(self, image: ImageInput, region: Optional[Box] = None) -> List[OCRText]:
        ox, oy = 0, 0
        if region is None and isinstance(image, str):
            result = self.engine.ocr(image, cls=True)
        else:
            image = _to_pil_rgb(image)
            if region is not None:
                r = region.normalized()
                image = image.crop((r.x1, r.y1, r.x2, r.y2))
                ox, oy = r.x1, r.y1
            result = self.engine.ocr(np.array(image), cls=True)
        raw_items: List[Tuple[List[List[float]], str, float]] = []
        if result and result[0]:
            for line in result[0]:
                pts = line[0]
                txt = line[1][0]
                score = line[1][1]
                raw_items.append((pts, txt, score))
        return _to_text_items(raw_items, ox, oy)


def _to_pil_rgb(image: ImageInput) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    if isinstance(image, str):
        return Image.open(image).convert("RGB")
    if isinstance(image, np.ndarray):
        if image.ndim == 2:
            return Image.fromarray(image).convert("RGB")
        if image.ndim == 3 and image.shape[2] >= 3:
            rgb = image[:, :, :3][:, :, ::-1]
            return Image.fromarray(rgb).convert("RGB")
    raise TypeError(f"Unsupported OCR image input type: {type(image)}")


def create_ocr_adapter(engine: str = "auto") -> Tuple[OCRAdapter, str, Dict[str, bool]]:
    status: Dict[str, bool] = {"Tesseract": False, "RapidOCR": False, "PaddleOCR": False}
    engines = [engine] if engine != "auto" else ["RapidOCR", "PaddleOCR", "Tesseract"]

    for name in engines:
        try:
            if name == "RapidOCR":
                adapter = RapidOCRAdapter()
            elif name == "PaddleOCR":
                adapter = PaddleOCRAdapter()
            elif name == "Tesseract":
                adapter = TesseractOCRAdapter()
            else:
                continue
            status[name] = True
            return adapter, name, status
        except Exception:
            status[name] = False
            continue
    return DummyOCRAdapter(), "Dummy", status

