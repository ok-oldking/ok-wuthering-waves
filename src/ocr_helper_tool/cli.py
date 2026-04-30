from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import cv2

from .artifacts import make_timestamp_image_path, write_annotated_frame, write_results_json
from .interfaces import Box, OCRText
from .okww_adapter import OKWWOCRHelper, OCRHelperConfig
from .text_utils import normalize_text_for_compare


def _engine_snapshot(items: list[OCRText]) -> dict:
    confs = [float(x.confidence) for x in items]
    texts = [normalize_text_for_compare(x.text) for x in items if normalize_text_for_compare(x.text)]
    return {
        "count": len(items),
        "avg_confidence": round(sum(confs) / len(confs), 6) if confs else 0.0,
        "unique_text_count": len(set(texts)),
        "texts": sorted(set(texts)),
    }


def _write_compare_report(image_path: str, report: dict) -> str:
    p = Path(image_path)
    out = p.with_name(f"{p.stem}_compare_report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)


def _run_toolbox_ocr(frame, args, screenshot_dir: str, wl) -> tuple[list[OCRText], str, str]:
    reliability_mode = not args.no_reliability_mode
    helper = OKWWOCRHelper(
        OCRHelperConfig(
            engine=args.engine,
            min_confidence=args.min_confidence,
            reliability_mode=reliability_mode,
            whitelist_terms=wl,
            whitelist_confidence_floor=args.whitelist_floor,
            whitelist_similarity=args.whitelist_similarity,
            exact_match_confidence_boost=args.exact_boost,
            fuzzy_match_confidence_boost=args.fuzzy_boost,
            dedupe_iou_threshold=args.dedupe_iou,
        )
    )
    results, _ = helper.recognize_verbose(
        frame_bgr=frame,
        screenshot_dir=screenshot_dir,
        tag="toolbox",
        save_artifacts=False,
    )
    base_path = make_timestamp_image_path(screenshot_dir, ".png", stem_suffix="ocr_helper")
    return results, base_path, helper.engine_name


def _to_native_items(native_result) -> list[OCRText]:
    out: list[OCRText] = []
    for line in (native_result[0] if native_result else []):
        if len(line) < 2:
            continue
        pts = line[0]
        txt = str(line[1][0]).strip()
        conf = float(line[1][1])
        if not txt:
            continue
        xs = [int(p[0]) for p in pts]
        ys = [int(p[1]) for p in pts]
        out.append(
            OCRText(
                text=txt,
                box=Box(min(xs), min(ys), max(xs), max(ys)),
                confidence=max(0.0, min(1.0, conf)),
                font_size=max(8, max(ys) - min(ys)),
            )
        )
    return out


def _run_native_ocr(frame, args, screenshot_dir: str) -> tuple[list[OCRText], str, str]:
    from onnxocr.onnx_paddleocr import ONNXPaddleOcr

    ocr = ONNXPaddleOcr(
        use_angle_cls=False,
        use_openvino=True,
        use_npu=True,
    )
    native_result = ocr.ocr(frame)
    results = _to_native_items(native_result)
    base_path = make_timestamp_image_path(screenshot_dir, ".png", stem_suffix="ocr_native")
    return results, base_path, "ONNXPaddleOcr(native)"


def main() -> int:
    ap = argparse.ArgumentParser(description="OKWW OCR helper offline debug")
    ap.add_argument("--image", required=True, help="Path to input image (.png/.jpg/...)")
    ap.add_argument(
        "--frontend-mode",
        default="toolbox",
        choices=["toolbox", "native", "both"],
        help="Choose frontend OCR entry: B(toolbox), C(native), or both",
    )
    ap.add_argument("--engine", default="auto", help="auto/RapidOCR/PaddleOCR/Tesseract")
    ap.add_argument("--min-confidence", type=float, default=0.0)
    ap.add_argument("--reliability-mode", action="store_true", help="Enable multi-engine verification when engine=auto")
    ap.add_argument("--no-reliability-mode", action="store_true", help="Disable reliability mode")
    ap.add_argument("--dev-compare", action="store_true", help="Run Rapid/Paddle/Tesseract side-by-side and save compare report")
    ap.add_argument("--whitelist", default="", help="Comma-separated whitelist terms")
    ap.add_argument("--whitelist-floor", type=float, default=0.85)
    ap.add_argument("--whitelist-similarity", type=float, default=0.62)
    ap.add_argument("--exact-boost", type=float, default=0.08, help="Confidence boost for exact whitelist matches")
    ap.add_argument("--fuzzy-boost", type=float, default=0.03, help="Confidence boost for fuzzy whitelist matches")
    ap.add_argument("--dedupe-iou", type=float, default=0.55, help="IOU threshold for same-text dedupe")
    ap.add_argument("--output-dir", default="screenshots", help="Directory to save OCR artifacts")
    args = ap.parse_args()

    frame = cv2.imread(args.image)
    if frame is None:
        raise SystemExit(f"Failed to read image: {args.image}")
    h, w = frame.shape[:2]
    screenshot_dir = args.output_dir or "screenshots"
    wl = [s.strip() for s in args.whitelist.split(",") if s.strip()] or None
    reliability_mode = not args.no_reliability_mode

    outputs: dict[str, dict] = {}
    if args.frontend_mode in ("toolbox", "both"):
        res_b, base_b, engine_b = _run_toolbox_ocr(frame, args, screenshot_dir, wl)
        outputs["toolbox"] = {
            "annotated": write_annotated_frame(frame, base_b, res_b),
            "json": write_results_json(base_b, res_b, w, h, engine_b),
            "count": len(res_b),
            "engine": engine_b,
        }
    if args.frontend_mode in ("native", "both"):
        res_c, base_c, engine_c = _run_native_ocr(frame, args, screenshot_dir)
        outputs["native"] = {
            "annotated": write_annotated_frame(frame, base_c, res_c),
            "json": write_results_json(base_c, res_c, w, h, engine_c),
            "count": len(res_c),
            "engine": engine_c,
        }
    if not outputs:
        raise SystemExit("No OCR output generated. Check frontend mode and input image.")

    for mode, info in outputs.items():
        print(f"[{mode}] annotated={info['annotated']}")
        print(f"[{mode}] json={info['json']}")
        print(f"[{mode}] count={info['count']} engine={info['engine']}")

    if args.dev_compare:
        if args.frontend_mode == "native":
            print("dev_compare is only for toolbox engines; skip in native-only mode.")
            return 0
        engines = ["RapidOCR", "PaddleOCR", "Tesseract"]
        snapshots = {}
        for eng in engines:
            h2 = OKWWOCRHelper(
                OCRHelperConfig(
                    engine=eng,
                    min_confidence=args.min_confidence,
                    reliability_mode=False,
                    whitelist_terms=wl,
                    whitelist_confidence_floor=args.whitelist_floor,
                    whitelist_similarity=args.whitelist_similarity,
                    exact_match_confidence_boost=args.exact_boost,
                    fuzzy_match_confidence_boost=args.fuzzy_boost,
                    dedupe_iou_threshold=args.dedupe_iou,
                )
            )
            if h2.engine_name == "Dummy":
                snapshots[eng] = {"available": False, "count": 0, "avg_confidence": 0.0, "unique_text_count": 0, "texts": []}
                continue
            r2, _ = h2.recognize_verbose(
                frame_bgr=frame,
                screenshot_dir=screenshot_dir,
                tag=f"compare_{eng}",
                save_artifacts=False,
            )
            snap = _engine_snapshot(r2)
            snap["available"] = True
            snapshots[eng] = snap
        available_sets = [set(v["texts"]) for v in snapshots.values() if v.get("available")]
        common_all = sorted(list(set.intersection(*available_sets))) if len(available_sets) >= 2 else []
        selected = outputs.get("toolbox") or next(iter(outputs.values()))
        report = {
            "image": args.image,
            "frontend_mode": args.frontend_mode,
            "selected_engine": selected["engine"],
            "selected_engine_count": selected["count"],
            "reliability_mode": reliability_mode,
            "engines": snapshots,
            "common_texts_all_engines": common_all,
            "common_texts_count": len(common_all),
            "available_engines_count": sum(1 for v in snapshots.values() if v.get("available")),
        }
        # Anchor compare report to the annotated image path (always persisted).
        report_path = _write_compare_report(selected["annotated"], report)
        print(f"compare_report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

