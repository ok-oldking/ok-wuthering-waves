from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List

import cv2
from PIL import Image, ImageDraw, ImageFont

from .geometry import pixel_box_to_rel
from .interfaces import OCRText


def make_timestamp_image_path(folder: str, ext: str = ".png") -> str:
    Path(folder).mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    return str(Path(folder) / f"{ts}{ext}")


def build_artifact_path(base_image_path: str, suffix: str) -> str:
    p = Path(base_image_path)
    ext = p.suffix if p.suffix else ".png"
    return str(p.with_name(f"{p.stem}{suffix}{ext}"))


def pick_cjk_font(size: int):
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


def write_raw_frame(frame_bgr, output_path: str) -> str:
    cv2.imwrite(output_path, frame_bgr)
    return output_path


def write_annotated_image(image_path: str, results: List[OCRText]) -> str:
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = pick_cjk_font(16)
    for item in results:
        b = item.box.normalized()
        draw.rectangle((b.x1, b.y1, b.x2, b.y2), outline=(0, 80, 255), width=2)
        label = f"{item.text} | {item.confidence:.2f}"
        tx, ty = b.x1 + 2, max(2, b.y1 - 20)
        draw.rectangle((tx - 1, ty - 1, tx + len(label) * 9, ty + 18), fill=(20, 20, 20))
        draw.text((tx, ty), label, fill=(255, 255, 0), font=font)
    out = build_artifact_path(image_path, "_annotated")
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
    out = str(Path(image_path).with_name(f"{Path(image_path).stem}_results.json"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out

