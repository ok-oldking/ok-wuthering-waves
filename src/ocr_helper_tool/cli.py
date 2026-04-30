from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from typing import List

import cv2
from PIL import Image, ImageDraw, ImageFont

from .geometry import pixel_box_to_rel
from .interfaces import OCRText
from .okww_adapter import OKWWOCRHelper, OCRHelperConfig


def _pick_cjk_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
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


def write_annotated(image_path: str, results: List[OCRText]) -> str:
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = _pick_cjk_font(16)
    for item in results:
        b = item.box.normalized()
        draw.rectangle((b.x1, b.y1, b.x2, b.y2), outline=(0, 80, 255), width=2)
        label = f"{item.text} | {item.confidence:.2f}"
        tx, ty = b.x1 + 2, max(2, b.y1 - 20)
        draw.rectangle((tx - 1, ty - 1, tx + len(label) * 9, ty + 18), fill=(20, 20, 20))
        draw.text((tx, ty), label, fill=(255, 255, 0), font=font)
    out = image_path.replace(".png", "_annotated.png")
    img.save(out)
    return out


def write_results_json(image_path: str, results: List[OCRText], frame_w: int, frame_h: int, engine: str) -> str:
    payload = {
        "engine": engine,
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
    out = image_path.replace(".png", "_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="OKWW OCR helper offline debug")
    ap.add_argument("--image", required=True, help="Path to input image (.png/.jpg/...)")
    ap.add_argument("--engine", default="auto", help="auto/RapidOCR/PaddleOCR/Tesseract")
    ap.add_argument("--min-confidence", type=float, default=0.0)
    ap.add_argument("--whitelist", default="", help="Comma-separated whitelist terms")
    ap.add_argument("--whitelist-floor", type=float, default=0.85)
    ap.add_argument("--whitelist-similarity", type=float, default=0.62)
    args = ap.parse_args()

    frame = cv2.imread(args.image)
    if frame is None:
        raise SystemExit(f"Failed to read image: {args.image}")
    h, w = frame.shape[:2]
    wl = [s.strip() for s in args.whitelist.split(",") if s.strip()] or None
    helper = OKWWOCRHelper(
        OCRHelperConfig(
            engine=args.engine,
            min_confidence=args.min_confidence,
            whitelist_terms=wl,
            whitelist_confidence_floor=args.whitelist_floor,
            whitelist_similarity=args.whitelist_similarity,
        )
    )

    # Use recognize_verbose to apply repair + whitelist; it will also create a timestamp-only copy
    # if you pass screenshot_dir. Here we OCR the provided image directly to avoid extra copies.
    results, _raw = helper.adapter.recognize(args.image, None), args.image
    # normalize/whitelist path is in helper.recognize_verbose; reuse that by faking a frame write
    # Instead, run through helper.recognize_verbose by writing frame to same folder.
    results2, raw_path = helper.recognize_verbose(
        frame_bgr=frame,
        screenshot_dir=os.path.dirname(args.image) or ".",
        tag="offline",
        save_artifacts=False,
    )

    annotated = write_annotated(raw_path, results2)
    js = write_results_json(raw_path, results2, w, h, helper.engine_name)
    print(f"raw={raw_path}")
    print(f"annotated={annotated}")
    print(f"json={js}")
    print(f"count={len(results2)} engine={helper.engine_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

