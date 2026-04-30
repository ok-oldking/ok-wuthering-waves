from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from .interfaces import Box, OCRAdapter, OCRText

COMMON_RESOLUTIONS: Dict[str, Tuple[int, int]] = {
    "原始尺寸": (0, 0),
    "1920 x 1080 (FHD)": (1920, 1080),
    "2560 x 1440 (QHD)": (2560, 1440),
    "3840 x 2160 (4K)": (3840, 2160),
    "1280 x 720 (HD)": (1280, 720),
    "1080 x 1920 (手机竖屏)": (1080, 1920),
    "1440 x 2560 (手机高分辨率)": (1440, 2560),
}


@dataclass
class OCRSession:
    image_path: Optional[Path] = None
    display_resolution: str = "原始尺寸"
    selected_box: Optional[Box] = None
    ocr_adapter: Optional[OCRAdapter] = None
    _image_size: Tuple[int, int] = field(default_factory=lambda: (0, 0))
    ocr_results: List[OCRText] = field(default_factory=list)

    def load_image(self, image_path: str) -> None:
        path = Path(image_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Image does not exist: {path}")
        self.image_path = path
        with Image.open(path) as img:
            self._image_size = img.size
        self.selected_box = None
        self.ocr_results = []

    @property
    def image_size(self) -> Tuple[int, int]:
        return self._image_size

    def set_resolution(self, resolution_label: str) -> None:
        if resolution_label not in COMMON_RESOLUTIONS:
            raise ValueError(f"Unsupported resolution option: {resolution_label}")
        self.display_resolution = resolution_label

    def update_selection(self, box: Box) -> None:
        self.selected_box = box.normalized()

    def run_ocr(self, region: Optional[Box] = None) -> List[OCRText]:
        if self.image_path is None:
            raise RuntimeError("No image loaded.")
        if self.ocr_adapter is None:
            raise RuntimeError("No OCR adapter configured.")
        target_region = region
        if target_region is None and self.selected_box is not None:
            target_region = self.selected_box
        self.ocr_results = self.ocr_adapter.recognize(str(self.image_path), target_region)
        return self.ocr_results

    def run_full_ocr(self) -> List[OCRText]:
        return self.run_ocr(region=None)

    def target_canvas_size(self) -> Tuple[int, int]:
        if self.display_resolution == "原始尺寸":
            return self._image_size
        return COMMON_RESOLUTIONS[self.display_resolution]

