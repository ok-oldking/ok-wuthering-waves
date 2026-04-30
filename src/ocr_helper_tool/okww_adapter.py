from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, List, Optional, Pattern, Union

from ok import Box as OKBox

from .adapters import create_ocr_adapter
from .artifacts import make_timestamp_image_path, write_annotated_frame, write_results_json
from .interfaces import Box, OCRText

MatchType = Union[str, Pattern[str], Iterable[Union[str, Pattern[str]]]]


@dataclass
class OCRHelperConfig:
    engine: str = "auto"  # auto/RapidOCR/PaddleOCR/Tesseract
    min_confidence: float = 0.0
    reliability_mode: bool = False
    whitelist_terms: Optional[List[str]] = None
    whitelist_similarity: float = 0.62
    whitelist_confidence_floor: float = 0.85
    exact_match_confidence_boost: float = 0.08
    fuzzy_match_confidence_boost: float = 0.03
    dedupe_iou_threshold: float = 0.55
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
        self._fallback_adapters = self._build_fallback_adapters()

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

        helper_region: Optional[Box] = None
        if region is not None:
            helper_region = Box(int(region.x), int(region.y), int(region.x + region.width), int(region.y + region.height))

        # In-memory OCR by default; avoid disk IO in high-frequency loops.
        results: List[OCRText] = self.adapter.recognize(frame_bgr, helper_region)
        if self.config.reliability_mode and self._fallback_adapters:
            for adapter in self._fallback_adapters:
                try:
                    fallback_results = adapter.recognize(frame_bgr, helper_region)
                    results = _merge_results(results, fallback_results)
                except Exception:
                    continue
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
        fixed_results = _dedupe_results(fixed_results, self.config.dedupe_iou_threshold)
        image_path = ""
        should_save_artifacts = self.config.save_artifacts_on_verbose if save_artifacts is None else save_artifacts
        if should_save_artifacts:
            base_path = make_timestamp_image_path(screenshot_dir, ".png", stem_suffix="ocr_helper")
            annotated = write_annotated_frame(frame_bgr, base_path, fixed_results)
            write_results_json(base_path, fixed_results, frame_bgr.shape[1], frame_bgr.shape[0], self.engine_name)
            return fixed_results, annotated
        return fixed_results, image_path

    def _build_fallback_adapters(self):
        if self.config.engine != "auto":
            return []
        fallbacks = []
        for engine in ("RapidOCR", "PaddleOCR"):
            if engine == self.engine_name:
                continue
            try:
                adapter, resolved_name, _ = create_ocr_adapter(engine)
                if resolved_name == "Dummy":
                    continue
                fallbacks.append(adapter)
            except Exception:
                continue
        return fallbacks

    def _normalize_and_whitelist(self, text: str, confidence: float) -> tuple[str, float]:
        repaired = _repair_text((text or "").strip())
        whitelist = self.config.whitelist_terms or DEFAULT_OCR_WHITELIST
        conf = max(0.0, min(1.0, float(confidence)))
        matched, score, is_exact = _match_whitelist_detail(repaired, whitelist, self.config.whitelist_similarity)
        if matched is not None:
            conf = max(conf, float(self.config.whitelist_confidence_floor))
            boost = self.config.exact_match_confidence_boost if is_exact else self.config.fuzzy_match_confidence_boost
            conf = max(0.0, min(1.0, conf + float(boost)))
            return matched, conf
        return repaired, conf


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


def _match_whitelist_detail(text: str, whitelist: List[str], threshold: float) -> tuple[Optional[str], float, bool]:
    src = _normalize_for_compare(text)
    if not src:
        return None, 0.0, False

    best_term: Optional[str] = None
    best_score = 0.0
    best_exact = False
    for term in whitelist:
        target = _normalize_for_compare(term)
        if not target:
            continue

        if src == target or (len(target) >= 2 and target in src) or (len(src) >= 2 and src in target):
            return term, 1.0, True

        score = SequenceMatcher(None, src, target).ratio()
        if score > best_score:
            best_score = score
            best_term = term
            best_exact = False
    if best_term is not None and best_score >= threshold:
        return best_term, best_score, best_exact
    return None, 0.0, False


def _dedupe_results(results: List[OCRText], iou_threshold: float) -> List[OCRText]:
    if not results:
        return results
    thr = max(0.0, min(1.0, float(iou_threshold)))
    ordered = sorted(results, key=lambda x: float(x.confidence), reverse=True)
    kept: List[OCRText] = []
    for cand in ordered:
        c_text = _normalize_for_compare(cand.text)
        c_box = cand.box.normalized()
        drop = False
        for exist in kept:
            if _normalize_for_compare(exist.text) != c_text:
                continue
            e_box = exist.box.normalized()
            if _box_iou(c_box, e_box) >= thr or _box_contains(e_box, c_box):
                drop = True
                break
        if not drop:
            kept.append(cand)
    return kept


def _merge_results(primary: List[OCRText], secondary: List[OCRText]) -> List[OCRText]:
    if not secondary:
        return primary
    merged = list(primary)
    for cand in secondary:
        cand_text = _normalize_for_compare(cand.text)
        cand_box = cand.box.normalized()
        replaced = False
        for idx, exist in enumerate(merged):
            if _normalize_for_compare(exist.text) != cand_text:
                continue
            overlap = _box_iou(exist.box.normalized(), cand_box)
            if overlap >= 0.4 and cand.confidence > exist.confidence:
                merged[idx] = cand
                replaced = True
                break
        if not replaced:
            merged.append(cand)
    return merged


def _box_iou(a: Box, b: Box) -> float:
    ax1, ay1, ax2, ay2 = a.x1, a.y1, a.x2, a.y2
    bx1, by1, bx2, by2 = b.x1, b.y1, b.x2, b.y2
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    union = area_a + area_b - inter
    return float(inter) / float(max(1, union))


def _box_contains(outer: Box, inner: Box) -> bool:
    return outer.x1 <= inner.x1 and outer.y1 <= inner.y1 and outer.x2 >= inner.x2 and outer.y2 >= inner.y2



