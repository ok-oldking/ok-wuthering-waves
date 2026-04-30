from __future__ import annotations

import argparse
import os

import cv2

from .artifacts import make_timestamp_image_path, write_annotated_image, write_raw_frame, write_results_json
from .okww_adapter import OKWWOCRHelper, OCRHelperConfig

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

    results2, raw_path = helper.recognize_verbose(
        frame_bgr=frame,
        screenshot_dir=os.path.dirname(args.image) or ".",
        tag="offline",
        save_artifacts=False,
    )
    if not raw_path:
        raw_path = make_timestamp_image_path(os.path.dirname(args.image) or ".", ".png")
        write_raw_frame(frame, raw_path)

    annotated = write_annotated_image(raw_path, results2)
    js = write_results_json(raw_path, results2, w, h, helper.engine_name)
    print(f"raw={raw_path}")
    print(f"annotated={annotated}")
    print(f"json={js}")
    print(f"count={len(results2)} engine={helper.engine_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

