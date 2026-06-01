import cv2
import numpy as np
import zipfile
import os
import json
import struct
from typing import List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class KeyPoint:
    x: float
    y: float
    size: float
    angle: float
    response: float
    octave: int
    class_id: int


@dataclass
class MatchResult:
    query_idx: int
    train_idx: int
    distance: float


@dataclass
class MapCache:
    kps: List[KeyPoint]
    descs: List[List[float]]
    desc_mat: np.ndarray
    h: int
    w: int


@dataclass
class CoordsRef:
    offset: Tuple[float, float]
    scale: Tuple[float, float]
    min_xy: Tuple[float, float] = (0.0, 0.0)
    max_xy: Tuple[float, float] = (0.0, 0.0)

    def pixel_to_game(self, px, py):
        gx = px * self.scale[0] + self.offset[0]
        gy = py * self.scale[1] + self.offset[1]
        return gx, gy

    def game_to_pixel(self, gx, gy):
        px = (gx - self.offset[0]) / self.scale[0]
        py = (gy - self.offset[1]) / self.scale[1]
        return px, py

    def contains(self, gx, gy):
        return (self.min_xy[0] <= gx <= self.max_xy[0] and
                self.min_xy[1] <= gy <= self.max_xy[1])

    @property
    def area(self):
        return (self.max_xy[0] - self.min_xy[0]) * (self.max_xy[1] - self.min_xy[1])

    @staticmethod
    def load(json_path):
        with open(json_path, 'r') as f:
            d = json.load(f)
        return CoordsRef(
            offset=(float(d["offset"][0]), float(d["offset"][1])),
            scale=(float(d["scale"][0]), float(d["scale"][1])),
            min_xy=(float(d.get("min", [0.0, 0.0])[0]), float(d.get("min", [0.0, 0.0])[1])),
            max_xy=(float(d.get("max", [0.0, 0.0])[0]), float(d.get("max", [0.0, 0.0])[1])),
        )


@dataclass
class MatchOutput:
    success: bool
    match_count: int
    inlier_count: int
    confidence: float
    center: Optional[Tuple[float, float]] = None
    corners: Optional[List[Tuple[float, float]]] = None
    game_center: Optional[Tuple[float, float]] = None
    elapsed_ms: float = 0.0
    H: Optional[np.ndarray] = field(default=None, repr=False)

    def with_coords(self, coords: CoordsRef):
        if self.center is not None and coords is not None:
            self.game_center = coords.pixel_to_game(self.center[0], self.center[1])
        return self

    def to_dict(self):
        d = {
            "success": self.success,
            "match_count": self.match_count,
            "inlier_count": self.inlier_count,
            "confidence": round(self.confidence, 4),
            "elapsed_ms": round(self.elapsed_ms, 1),
        }
        if self.center is not None:
            d["center"] = [round(self.center[0], 2), round(self.center[1], 2)]
        if self.corners is not None:
            d["corners"] = [[round(c[0], 2), round(c[1], 2)] for c in self.corners]
        if self.game_center is not None:
            d["game_center"] = [round(self.game_center[0], 1), round(self.game_center[1], 1)]
        return d


def grid_sample(kps, desc, rows, cols, grid_rows, grid_cols, max_per_cell):
    cell_h = rows / grid_rows
    cell_w = cols / grid_cols

    sorted_kps = sorted(enumerate(kps), key=lambda x: -x[1].response)

    buckets = [[[] for _ in range(grid_cols)] for _ in range(grid_rows)]
    for idx, kp in sorted_kps:
        c = int(kp.pt[0] / cell_w)
        r = int(kp.pt[1] / cell_h)
        if 0 <= c < grid_cols and 0 <= r < grid_rows:
            buckets[r][c].append((idx, kp))

    selected = []
    for r in range(grid_rows):
        for c in range(grid_cols):
            bucket = buckets[r][c]
            n = min(max_per_cell, len(bucket))
            selected.extend(bucket[:n])

    out_kps = []
    out_descs = []
    for idx, kp in selected:
        out_kps.append(KeyPoint(
            x=kp.pt[0], y=kp.pt[1], size=kp.size,
            angle=kp.angle, response=kp.response,
            octave=kp.octave, class_id=kp.class_id
        ))
        out_descs.append(desc[idx].tolist())

    return out_kps, out_descs


def desc_mat_from_slice_fast(descs):
    if not descs:
        return np.array([], dtype=np.float32)
    rows = len(descs)
    cols = len(descs[0])
    mat = np.zeros((rows, cols), dtype=np.float32)
    for i, row in enumerate(descs):
        mat[i] = row
    return mat


def save_npz(path, kps, descs, map_h, map_w):
    num_kp = len(kps)
    desc_cols = len(descs[0]) if descs else 0

    kp_arr = np.array([[kp.x, kp.y, kp.size, kp.angle, kp.response,
                        float(kp.octave), float(kp.class_id)] for kp in kps],
                      dtype=np.float32)
    desc_arr = np.array(descs, dtype=np.float32) if descs else np.array([], dtype=np.float32)
    size_arr = np.array([map_h, map_w], dtype=np.int32)

    np.savez_compressed(path,
                        keypoints=kp_arr,
                        descriptors=desc_arr,
                        map_size=size_arr,
                        num_keypoints=np.array(num_kp, dtype=np.int32))


def _skip_npy_header(data):
    if len(data) < 10 or data[0] != 0x93 or data[1:6] != b'NUMPY':
        raise ValueError("invalid npy header")
    hdr_len = struct.unpack('<H', data[8:10])[0]
    return data[10 + hdr_len:]


def load_npz(path):
    try:
        data = np.load(path, allow_pickle=False)
        kp_arr = data['keypoints']
        desc_arr = data['descriptors']
        map_h, map_w = int(data['map_size'][0]), int(data['map_size'][1])

        kps = []
        for row in kp_arr:
            kps.append(KeyPoint(
                x=float(row[0]), y=float(row[1]), size=float(row[2]),
                angle=float(row[3]), response=float(row[4]),
                octave=int(row[5]), class_id=int(row[6])
            ))
        descs = desc_arr.tolist()
        return kps, descs, map_h, map_w
    except (KeyError, ValueError):
        pass

    with zipfile.ZipFile(path, 'r') as zf:
        size_data = zf.read('map_size.npy')
        size_body = _skip_npy_header(size_data)
        map_h, map_w = struct.unpack('<ii', size_body[:8])

        kp_data = zf.read('keypoints.npy')
        kp_body = _skip_npy_header(kp_data)
        num_kp = len(kp_body) // (7 * 4)

        kps = []
        for i in range(num_kp):
            off = i * 7
            x, y, size, angle, response = struct.unpack('<5f', kp_body[off*4:(off+5)*4])
            octave, class_id = struct.unpack('<ii', kp_body[(off+5)*4:(off+7)*4])
            kps.append(KeyPoint(x, y, size, angle, response, octave, class_id))

        desc_data = zf.read('descriptors.npy')
        desc_body = _skip_npy_header(desc_data)
        desc_cols = len(desc_body) // (num_kp * 4)

        descs = []
        for i in range(num_kp):
            row = struct.unpack(f'<{desc_cols}f', desc_body[i*desc_cols*4:(i+1)*desc_cols*4])
            descs.append(list(row))

        return kps, descs, map_h, map_w


def project_corners(H, w, h):
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    projected = cv2.perspectiveTransform(corners, H)
    return [(float(p[0][0]), float(p[0][1])) for p in projected]


def compute_center(corners):
    cx = float((corners[0][0] + corners[2][0]) / 2)
    cy = float((corners[0][1] + corners[2][1]) / 2)
    return cx, cy


def _prepare_test_image(src, crop_size):
    if isinstance(src, np.ndarray):
        img = src
    else:
        img = cv2.imread(src, cv2.IMREAD_GRAYSCALE)

    if img is None:
        return None

    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if crop_size > 0:
        h, w = img.shape[:2]
        if w > crop_size or h > crop_size:
            cx, cy = w // 2, h // 2
            half = crop_size // 2
            img = img[cy - half:cy + half, cx - half:cx + half].copy()

    return img


if __name__ == "__main__":
    import argparse
    import sys
    import glob as _glob

    def _cmd_extract(args):
        algo = args.algo.lower()
        os.makedirs(args.out, exist_ok=True)

        if algo == "sift":
            detector = cv2.SIFT_create()
        else:
            detector = cv2.xfeatures2d.SURF_create()

        png_files = _glob.glob(os.path.join(args.dir, "*.png"))
        if not png_files:
            print(json.dumps({"error": f"no png files in {args.dir}"}))
            sys.exit(1)

        results = []
        for png_path in sorted(png_files):
            basename = os.path.splitext(os.path.basename(png_path))[0]
            out_path = os.path.join(args.out, f"{basename}_{algo}.npz")

            img = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(json.dumps({"error": f"cannot read {png_path}"}), file=sys.stderr)
                continue

            h, w = img.shape[:2]
            kps, desc = detector.detectAndCompute(img, None)
            if not kps or desc is None:
                print(json.dumps({"error": f"no features in {png_path}"}), file=sys.stderr)
                continue

            sel_kps, sel_descs = grid_sample(kps, desc, h, w, args.grid, args.grid, args.max_per_cell)
            save_npz(out_path, sel_kps, sel_descs, h, w)

            entry = {
                "file": os.path.basename(png_path),
                "out": out_path,
                "size": [w, h],
                "total_features": len(kps),
                "saved_features": len(sel_kps),
            }
            results.append(entry)
            print(f"  {basename}: {len(kps)} -> {len(sel_kps)} -> {out_path}")

        print(json.dumps(results, indent=2))

    def _cmd_match(args):
        algo = args.algo.lower()

        from .surf import SurfEngine, _load_cache, _match_flann
        from .sift import SiftEngine, _match_bf

        kps, descs, map_h, map_w = load_npz(args.features)
        desc_mat = desc_mat_from_slice_fast(descs)
        if algo == "surf" and not desc_mat.flags['C_CONTIGUOUS']:
            desc_mat = np.ascontiguousarray(desc_mat)
        cache = MapCache(kps, descs, desc_mat, map_h, map_w)

        if algo == "sift":
            cfg = cv2.SIFT_create()
            ratio = 0.75
            result = _match_bf(cfg, args.query, cache, ratio,
                               crop_size=args.crop, region=None)
        else:
            cfg = cv2.xfeatures2d.SURF_create()
            ratio = 0.62
            max_dist = 0.50
            result = _match_flann(cfg, args.query, cache, ratio, max_dist,
                                  crop_size=args.crop, region=None)

        if args.coords and os.path.exists(args.coords):
            coords = CoordsRef.load(args.coords)
            result.with_coords(coords)

        print(json.dumps(result.to_dict(), indent=2))

    parser = argparse.ArgumentParser(prog="python -m src.match_engine.common")
    sub = parser.add_subparsers(dest="command")

    ep = sub.add_parser("extract", help="extract features from PNGs in a folder")
    ep.add_argument("--dir", required=True, help="folder containing map PNG files")
    ep.add_argument("--out", required=True, help="output folder for .npz cache files")
    ep.add_argument("--algo", choices=["surf", "sift"], default="surf")
    ep.add_argument("--grid", type=int, default=100)
    ep.add_argument("--max-per-cell", type=int, default=160)

    mp = sub.add_parser("match", help="match a query image against a feature cache")
    mp.add_argument("--query", required=True, help="query image path")
    mp.add_argument("--features", required=True, help=".npz feature cache path")
    mp.add_argument("--coords", default=None, help="optional _coords.json for game_center output")
    mp.add_argument("--algo", choices=["surf", "sift"], default="surf")
    mp.add_argument("--crop", type=int, default=0, help="center crop size (0=no crop)")

    args = parser.parse_args()
    if args.command == "extract":
        _cmd_extract(args)
    elif args.command == "match":
        _cmd_match(args)
    else:
        parser.print_help()
