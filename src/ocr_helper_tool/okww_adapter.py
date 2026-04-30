from __future__ import annotations

import os
import re
import time
import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, List, Optional, Pattern, Union

import cv2
from PIL import Image, ImageDraw, ImageFont

from ok import Box as OKBox

from .adapters import create_ocr_adapter
from .geometry import pixel_box_to_rel
from .interfaces import Box, OCRText

MatchType = Union[str, Pattern[str], Iterable[Union[str, Pattern[str]]]]


@dataclass
class OCRHelperConfig:
    engine: str = "auto"  # auto/RapidOCR/PaddleOCR/Tesseract
    min_confidence: float = 0.0
    whitelist_terms: Optional[List[str]] = None
    whitelist_similarity: float = 0.62
    whitelist_confidence_floor: float = 0.85
    save_artifacts_on_verbose: bool = True


DEFAULT_OCR_WHITELIST = [
    "领取",
    "登录游戏",
    "活跃度",
    "开始游戏",
    "进入游戏",
    "确认",
    "同意",
    "特征码",
]


class OKWWOCRHelper:
    """
    Bridge ocr_helper_tool engines into okww:
    - input: numpy BGR frame (task.frame), optional OKBox region (pixel)
    - output: List[ok.Box] where Box.name is recognized text
    """

    def __init__(self, config: OCRHelperConfig) -> None:
        self.config = config
        self.adapter, self.engine_name, self.engine_status = create_ocr_adapter(config.engine)

    def recognize(
        self,
        frame_bgr,
        region: Optional[OKBox] = None,
        match: Optional[MatchType] = None,
        screenshot_dir: str = "screenshots",
        tag: str = "ocr_helper",
    ) -> List[OKBox]:
        results, _image_path = self.recognize_verbose(
            frame_bgr=frame_bgr,
            region=region,
            screenshot_dir=screenshot_dir,
            tag=tag,
        )
        out: List[OKBox] = []
        for item in results:
            if item.confidence < self.config.min_confidence:
                continue
            text = (item.text or "").strip()
            if not text:
                continue
            if match is not None and not _match_text(text, match):
                continue
            b = item.box.normalized()
            out.append(OKBox(b.x1, b.y1, b.width, b.height, name=text))
        return out

    def recognize_verbose(
        self,
        frame_bgr,
        region: Optional[OKBox] = None,
        screenshot_dir: str = "screenshots",
        tag: str = "ocr_helper",
        save_artifacts: Optional[bool] = None,
    ) -> tuple[List[OCRText], str]:
        if frame_bgr is None:
            return [], ""

        # Persist the frame to disk (adapters use image_path).
        Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        # Keep filename minimal for quick sorting: timestamp only.
        image_path = os.path.join(screenshot_dir, f"{ts}.png")
        cv2.imwrite(image_path, frame_bgr)

        helper_region: Optional[Box] = None
        if region is not None:
            helper_region = Box(int(region.x), int(region.y), int(region.x + region.width), int(region.y + region.height))

        results: List[OCRText] = self.adapter.recognize(image_path, helper_region)
        fixed_results: List[OCRText] = []
        for item in results:
            fixed_text, fixed_confidence = self._normalize_and_whitelist(item.text, item.confidence)
            fixed_results.append(
                OCRText(
                    text=fixed_text,
                    box=item.box,
                    confidence=fixed_confidence,
                    font_size=item.font_size,
                )
            )
        should_save_artifacts = self.config.save_artifacts_on_verbose if save_artifacts is None else save_artifacts
        if should_save_artifacts:
            self._write_annotated_image(image_path, fixed_results)
            self._write_results_json(image_path, fixed_results, frame_bgr.shape[1], frame_bgr.shape[0])
        return fixed_results, image_path

    def _normalize_and_whitelist(self, text: str, confidence: float) -> tuple[str, float]:
        repaired = _repair_text((text or "").strip())
        whitelist = self.config.whitelist_terms or DEFAULT_OCR_WHITELIST
        matched = _match_whitelist(repaired, whitelist, self.config.whitelist_similarity)
        if matched is not None:
            boosted = max(float(confidence), float(self.config.whitelist_confidence_floor))
            return matched, boosted
        return repaired, float(confidence)

    def _write_annotated_image(self, raw_path: str, results: List[OCRText]) -> str:
        img = Image.open(raw_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        font = _pick_cjk_font(16)
        for item in results:
            b = item.box.normalized()
            draw.rectangle((b.x1, b.y1, b.x2, b.y2), outline=(0, 80, 255), width=2)
            label = f"{item.text} | {item.confidence:.2f}"
            tx, ty = b.x1 + 2, max(2, b.y1 - 20)
            draw.rectangle((tx - 1, ty - 1, tx + len(label) * 9, ty + 18), fill=(20, 20, 20))
            draw.text((tx, ty), label, fill=(255, 255, 0), font=font)
        out = raw_path.replace(".png", "_annotated.png")
        img.save(out)
        return out

    def _write_results_json(self, raw_path: str, results: List[OCRText], frame_w: int, frame_h: int) -> str:
        payload = {
            "engine": self.engine_name,
            "frame_size": {"width": frame_w, "height": frame_h},
            "count": len(results),
            "items": [],
        }
        for item in results:
            b = item.box.normalized()
            rel = pixel_box_to_rel(b, frame_w, frame_h).normalized()
            payload["items"].append(
                {
                    "text": item.text,
                    "confidence": round(float(item.confidence), 6),
                    "pixel_box": {"x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2},
                    "relative_box": {
                        "x1": round(rel.x1, 6),
                        "y1": round(rel.y1, 6),
                        "x2": round(rel.x2, 6),
                        "y2": round(rel.y2, 6),
                    },
                }
            )
        out = raw_path.replace(".png", "_results.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return out


def _match_text(text: str, match: MatchType) -> bool:
    if isinstance(match, str):
        return match in text
    if isinstance(match, re.Pattern):
        return bool(match.search(text))
    # Iterable[str|Pattern]
    for m in match:
        if isinstance(m, str) and m in text:
            return True
        if isinstance(m, re.Pattern) and m.search(text):
            return True
    return False


def _repair_text(text: str) -> str:
    """
    Attempt to repair common mojibake patterns seen in OCR pipelines.
    Keep the original text when repair does not improve quality.
    """
    if not text:
        return text
    candidates = [text]
    # common mojibake path: utf-8 bytes decoded as latin-1/cp1252
    for enc in ("latin1", "cp1252"):
        try:
            candidates.append(text.encode(enc).decode("utf-8"))
        except Exception:
            pass
    # common mojibake path: utf-8 bytes decoded as gbk
    try:
        candidates.append(text.encode("gbk", errors="ignore").decode("utf-8", errors="ignore"))
    except Exception:
        pass
    return max(candidates, key=_text_quality)


def _text_quality(text: str) -> int:
    # Higher score means "looks like meaningful OCR text".
    score = 0
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":  # CJK
            score += 3
        elif ch.isalnum():
            score += 2
        elif ch in " +-/:%().,，。！？!?:_#[]":
            score += 1
        elif ch == "�":  # replacement char
            score -= 4
        else:
            score -= 1
    return score


def _normalize_for_compare(text: str) -> str:
    if not text:
        return ""
    chars = []
    for ch in text:
        if ("\u4e00" <= ch <= "\u9fff") or ch.isalnum():
            chars.append(ch)
    return "".join(chars).lower()


def _match_whitelist(text: str, whitelist: List[str], threshold: float) -> Optional[str]:
    src = _normalize_for_compare(text)
    if not src:
        return None

    best_term: Optional[str] = None
    best_score = 0.0
    for term in whitelist:
        target = _normalize_for_compare(term)
        if not target:
            continue

        if src == target or (len(target) >= 2 and target in src) or (len(src) >= 2 and src in target):
            return term

        score = SequenceMatcher(None, src, target).ratio()
        if score > best_score:
            best_score = score
            best_term = term
    if best_term is not None and best_score >= threshold:
        return best_term
    return None


def _pick_cjk_font(size: int):
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()

