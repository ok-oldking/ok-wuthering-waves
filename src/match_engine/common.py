import cv2
import numpy as np
import zipfile
import os
import json
import struct
from typing import List, Tuple, Optional
from collections import namedtuple
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
    map_scale: float = 0.0
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
        if self.map_scale > 0:
            d["map_scale"] = round(self.map_scale, 4)
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
        with np.load(path, allow_pickle=False) as data:
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


def extract_scale_factor(H, cx, cy):
    pt = np.array([[[cx, cy]]], dtype=np.float64)
    mapped = cv2.perspectiveTransform(pt, H)
    xp, yp = float(mapped[0, 0, 0]), float(mapped[0, 0, 1])
    s = H[2, 0] * cx + H[2, 1] * cy + H[2, 2]
    J = np.array([
        [(H[0, 0] - H[2, 0] * xp) / s, (H[0, 1] - H[2, 1] * xp) / s],
        [(H[1, 0] - H[2, 0] * yp) / s, (H[1, 1] - H[2, 1] * yp) / s],
    ])
    return float(np.sqrt(np.linalg.det(J)))


#: 大地图坐标参考文件名（``{map_id: {offset, scale, min, max, ...}}``）。
COORDS_FILENAME = "map_coords.json"

#: 坐标条目中记录“特征提取时使用的放大系数”的键，用于幂等地换算 ``scale``。
COORDS_UPSCALE_KEY = "feature_upscale"


def upscaled_size(h, w, upscale):
    """返回放大后的 ``(h, w)``，与 :func:`resize_for_upscale` 保持一致的取整。"""
    us = float(upscale)
    if us == 1.0:
        return int(h), int(w)
    return max(1, int(round(h * us))), max(1, int(round(w * us)))


def resize_for_upscale(img, upscale):
    """按放大系数放大灰度图（``upscale == 1.0`` 时原样返回）。

    使用 ``INTER_CUBIC``：放大场景下比 ``INTER_LINEAR`` 保留更多高频细节，
    利于 SIFT/SURF 在大缩放比图上检出更多可用特征。
    """
    if img is None:
        return None
    us = float(upscale)
    if us == 1.0:
        return img
    h, w = img.shape[:2]
    new_h, new_w = upscaled_size(h, w, us)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def coords_base_scale(entry):
    """取出坐标条目里“未放大”的原始 scale（游戏单位/原图像素）。"""
    applied = float(entry.get(COORDS_UPSCALE_KEY) or 1.0)
    return (float(entry["scale"][0]) * applied,
            float(entry["scale"][1]) * applied)


def apply_feature_upscale(entry, upscale):
    """返回按放大系数调整 ``scale`` 后的坐标条目副本（幂等）。

    特征提取放大后，关键点坐标位于放大后的像素空间，故
    ``scale`` = 原始 scale / upscale；``offset`` 与 ``min`` / ``max``
    是游戏坐标，保持不变。重复调用不会累积除法，因为原始 scale
    通过 :data:`COORDS_UPSCALE_KEY` 可还原。
    """
    out = dict(entry)
    base_x, base_y = coords_base_scale(entry)
    us = float(upscale)
    out["scale"] = [base_x / us, base_y / us]
    if us == 1.0:
        out.pop(COORDS_UPSCALE_KEY, None)
    else:
        out[COORDS_UPSCALE_KEY] = us
    return out


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


#: OpenCV ``BFMatcher::knnMatchImpl`` 要求 ``trainDesc.rows < IMGIDX_ONE``
#: （``1 << 18`` = 262144），超过会抛 ``cv2.error``。放大提取后大地图（如 ``8``）
#: 的特征量很容易突破，这里分块匹配再合并，保留全局最近 k 个。
BF_IMGIDX_LIMIT = 1 << 18
BF_MAX_TRAIN_ROWS = 200000

_Match = namedtuple("_Match", "queryIdx trainIdx distance")


def knn_match_l2(query_desc, train_mat, k=2):
    """L2 暴力 knn 匹配，训练集过大时自动分块，结果与不分块等价。"""
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    rows = train_mat.shape[0] if getattr(train_mat, 'ndim', 0) == 2 else 0
    if rows <= BF_MAX_TRAIN_ROWS:
        return matcher.knnMatch(query_desc, train_mat, k)

    pooled = [[] for _ in range(len(query_desc))]
    for start in range(0, rows, BF_MAX_TRAIN_ROWS):
        chunk = train_mat[start:start + BF_MAX_TRAIN_ROWS]
        if not chunk.flags['C_CONTIGUOUS']:
            chunk = np.ascontiguousarray(chunk)
        for pairs in matcher.knnMatch(query_desc, chunk, k):
            for m in pairs:
                pooled[m.queryIdx].append((m.distance, m.trainIdx + start))

    out = []
    for qi, cands in enumerate(pooled):
        cands.sort(key=lambda t: t[0])
        out.append([_Match(qi, tidx, dist) for dist, tidx in cands[:k]])
    return out


def _failed_match(elapsed_ms):
    return MatchOutput(success=False, match_count=0, inlier_count=0,
                       confidence=0.0, elapsed_ms=elapsed_ms)


def _filter_knn_matches(knn, ratio_thresh):
    good = []
    for pair in knn:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < ratio_thresh * n.distance:
            good.append((m.queryIdx, m.trainIdx, m.distance))
    return good


def _estimate_homography(good, test_kps, match_cache, constrained):
    if not good:
        return None, 0
    min_matches = 2 if constrained else 4
    if len(good) < min_matches:
        return None, 0
    src_pts = np.array([[test_kps[q].x, test_kps[q].y] for q, _, _ in good],
                       dtype=np.float64).reshape(-1, 1, 2)
    dst_pts = np.array([[match_cache.kps[t].x, match_cache.kps[t].y] for _, t, _ in good],
                       dtype=np.float64).reshape(-1, 1, 2)
    if constrained:
        M, inliers = cv2.estimateAffinePartial2D(
            src_pts, dst_pts, method=cv2.RANSAC,
            ransacReprojThreshold=3.0, maxIters=2000, confidence=0.995)
        if M is None:
            return None, 0
        H = np.eye(3, dtype=np.float64)
        H[:2, :] = M
        return H, int(inliers.sum())
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0,
                                 maxIters=2000, confidence=0.995)
    inlier_count = int(mask.sum()) if mask is not None else 0
    return H, inlier_count


if __name__ == "__main__":
    import argparse
    import sys
    import glob as _glob
    from .params import ParamSet, SURF, SIFT, SIFTGZ, SurfParams, SiftParams, SiftGzParams

    def _load_json(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_json(path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _merge_setting_json(out_dir, algo, param_set_name):
        path = os.path.join(out_dir, "setting.json")
        data = _load_json(path) if os.path.exists(path) else {}
        if algo not in data:
            data[algo] = {}
        data[algo]["default"] = param_set_name
        _save_json(path, data)

    def _build_default_ps(algo, grid, mpc, upscale=1.0):
        if algo == SURF:
            return ParamSet(algo=SURF, params=SurfParams(
                hessian=40, octaves=8, layers=4,
                extended=True, upright=True,
                grid=grid, max_per_cell=mpc,
                ratio=0.62, max_dist=0.50,
                upscale=upscale,
            ))
        if algo == SIFT:
            return ParamSet(algo=SIFT, params=SiftParams(
                contrast_threshold=0.02, edge_threshold=7,
                n_octave_layers=5, sigma=1.6,
                grid=grid, max_per_cell=mpc, ratio=0.75,
                upscale=upscale,
            ))
        if algo == SIFTGZ:
            return ParamSet(algo=SIFTGZ, params=SiftGzParams(
                contrast_threshold=0.02, edge_threshold=7,
                n_octave_layers=2, sigma=1.6,
                grid=grid, max_per_cell=mpc, ratio=0.60,
                downscale=1, tile_size=14800, tile_overlap=512,
                black_thresh=5, edge_margin=8, min_dist=4.0,
                upscale=upscale,
            ))
        raise ValueError(f"unknown algo: {algo}")

    def _extract_one(png_path, out_path, ps):
        algo = ps.algo
        p = ps.params
        if algo == SIFTGZ:
            from .siftgz import _extract as siftgz_extract
            cfg = cv2.SIFT_create(
                0, p.n_octave_layers, p.contrast_threshold,
                p.edge_threshold, p.sigma,
            )
            kps, descs, h, w = siftgz_extract(
                cfg, png_path, out_path, p.grid, p.max_per_cell,
                downscale=p.downscale, tile_size=p.tile_size,
                tile_overlap=p.tile_overlap, black_thresh=p.black_thresh,
                edge_margin=p.edge_margin, min_dist=p.min_dist,
                upscale=p.upscale,
            )
            return len(kps), h, w
        if algo == SURF:
            cfg = cv2.xfeatures2d.SURF_create(
                p.hessian, p.octaves, p.layers, p.extended, p.upright,
            )
        else:
            cfg = cv2.SIFT_create(
                0, p.n_octave_layers, p.contrast_threshold,
                p.edge_threshold, p.sigma,
            )
        img = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"cannot read: {png_path}")
        img = resize_for_upscale(img, p.upscale)
        h, w = img.shape[:2]
        kps, desc = cfg.detectAndCompute(img, None)
        if not kps or desc is None:
            raise ValueError(f"no features: {png_path}")
        sel_kps, sel_descs = grid_sample(kps, desc, h, w, p.grid, p.grid, p.max_per_cell)
        save_npz(out_path, sel_kps, sel_descs, h, w)
        return len(sel_kps), h, w

    def _update_coords_json(src_dir, out_dir, upscale_by_map, explicit_path=None):
        """把各地图的放大系数写进 ``map_coords.json``（scale 同步除以放大系数）。

        源文件优先取 ``--coords``，否则依次在 ``--dir`` / ``--out`` 里找；
        结果始终写到 ``--out``，多次执行幂等（放大系数记录在
        ``feature_upscale``，可还原原始 scale）。
        """
        candidates = [explicit_path] if explicit_path else [
            os.path.join(src_dir, COORDS_FILENAME),
            os.path.join(out_dir, COORDS_FILENAME),
        ]
        base_path = next((p for p in candidates if p and os.path.exists(p)), None)
        if base_path is None:
            if any(float(u) != 1.0 for u in upscale_by_map.values()):
                print(f"  WARNING: {COORDS_FILENAME} not found, coords scale NOT updated "
                      f"(searched: {[p for p in candidates if p]})", file=sys.stderr)
            return None

        data = _load_json(base_path)
        updated = {}
        for map_id, upscale in upscale_by_map.items():
            entry = data.get(map_id)
            if entry is None or "scale" not in entry:
                if float(upscale) != 1.0:
                    print(f"  WARNING: no coords entry for map {map_id}, "
                          f"scale NOT updated", file=sys.stderr)
                continue
            data[map_id] = apply_feature_upscale(entry, upscale)
            updated[map_id] = data[map_id]["scale"][0]

        dst = os.path.join(out_dir, COORDS_FILENAME)
        _save_json(dst, data)
        for map_id, scale in updated.items():
            print(f"  coords {map_id}: upscale={upscale_by_map[map_id]} "
                  f"scale -> {scale}", file=sys.stderr)
        return dst

    def _cmd_extract(args):
        os.makedirs(args.out, exist_ok=True)
        setting_path = getattr(args, 'setting', None)
        param_set_name_arg = getattr(args, 'param_set', None)

        if setting_path and param_set_name_arg:
            print(json.dumps({"error": "--setting and --param-set cannot be used together"}), file=sys.stderr)
            sys.exit(1)

        png_files = _glob.glob(os.path.join(args.dir, "*.png"))
        if not png_files:
            print(json.dumps({"error": f"no png files in {args.dir}"}), file=sys.stderr)
            sys.exit(1)

        tasks = []
        if setting_path:
            if not os.path.exists(setting_path):
                print(json.dumps({"error": f"setting file not found: {setting_path}"}), file=sys.stderr)
                sys.exit(1)
            setting = _load_json(setting_path)
            for algo_key, algo_cfg in setting.items():
                default_name = algo_cfg.get("default")
                if not default_name:
                    continue
                maps_cfg = algo_cfg.get("maps", {})
                for png_path in sorted(png_files):
                    basename = os.path.splitext(os.path.basename(png_path))[0]
                    ps_name = maps_cfg.get(basename, default_name)
                    ps = ParamSet.from_name(ps_name)
                    out_path = os.path.join(args.out, f"{basename}_{algo_key}.npz")
                    tasks.append((png_path, out_path, ps, ps_name))
        elif param_set_name_arg:
            ps = ParamSet.from_name(param_set_name_arg)
            for png_path in sorted(png_files):
                basename = os.path.splitext(os.path.basename(png_path))[0]
                out_path = os.path.join(args.out, f"{basename}_{ps.algo}.npz")
                tasks.append((png_path, out_path, ps, param_set_name_arg))
        else:
            algo = args.algo.lower()
            ps = _build_default_ps(algo, args.grid, args.max_per_cell,
                                   upscale=args.upscale)
            for png_path in sorted(png_files):
                basename = os.path.splitext(os.path.basename(png_path))[0]
                out_path = os.path.join(args.out, f"{basename}_{algo}.npz")
                tasks.append((png_path, out_path, ps, ps.name))

        results = []
        seen_algos = set()
        upscale_by_map = {}
        for png_path, out_path, ps, ps_name in tasks:
            basename = os.path.splitext(os.path.basename(png_path))[0]
            try:
                total, h, w = _extract_one(png_path, out_path, ps)
                entry = {
                    "file": os.path.basename(png_path),
                    "out": out_path,
                    "algo": ps.algo,
                    "param_set": ps_name,
                    "size": [w, h],
                    "upscale": float(ps.params.upscale),
                    "saved_features": total,
                }
                results.append(entry)
                prev = upscale_by_map.get(basename)
                if prev is not None and float(prev) != float(ps.params.upscale):
                    print(f"  WARNING: map {basename} extracted with conflicting "
                          f"upscale ({prev} vs {ps.params.upscale}); coords scale "
                          f"keeps {prev}", file=sys.stderr)
                else:
                    upscale_by_map[basename] = float(ps.params.upscale)
                print(f"  {basename} [{ps.algo}]: {total} features -> {out_path}", file=sys.stderr)
                if not setting_path and ps.algo not in seen_algos:
                    _merge_setting_json(args.out, ps.algo, ps_name)
                    seen_algos.add(ps.algo)
            except Exception as e:
                entry = {
                    "file": os.path.basename(png_path),
                    "out": out_path,
                    "algo": ps.algo,
                    "param_set": ps_name,
                    "error": str(e),
                }
                results.append(entry)
                print(f"  {basename} [{ps.algo}]: ERROR: {e}", file=sys.stderr)

        if upscale_by_map:
            _update_coords_json(args.dir, args.out, upscale_by_map,
                                explicit_path=getattr(args, 'coords', None))

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

        if algo in ("sift", "siftgz"):
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
    ep.add_argument("--algo", choices=["surf", "sift", "siftgz"], default="surf",
                    help="algorithm (default: surf)")
    ep.add_argument("--param-set", default=None,
                    help="full param set name, algo auto-detected from name prefix")
    ep.add_argument("--setting", default=None,
                    help="path to setting.json describing algorithms and params")
    ep.add_argument("--grid", type=int, default=100)
    ep.add_argument("--max-per-cell", type=int, default=160)
    ep.add_argument("--upscale", type=float, default=1.0,
                    help="upscale factor applied before extraction "
                         "(1.0=off, non-integer allowed; ignored when "
                         "--param-set/--setting provides one)")
    ep.add_argument("--coords", default=None,
                    help=f"path to {COORDS_FILENAME} to read as base; the updated "
                         f"copy (scale / upscale) is always written to --out")

    mp = sub.add_parser("match", help="match a query image against a feature cache")
    mp.add_argument("--query", required=True, help="query image path")
    mp.add_argument("--features", required=True, help=".npz feature cache path")
    mp.add_argument("--coords", default=None, help="optional _coords.json for game_center output")
    mp.add_argument("--algo", choices=["surf", "sift", "siftgz"], default="surf")
    mp.add_argument("--crop", type=int, default=0, help="center crop size (0=no crop)")

    args = parser.parse_args()
    if args.command == "extract":
        _cmd_extract(args)
    elif args.command == "match":
        _cmd_match(args)
    else:
        parser.print_help()
