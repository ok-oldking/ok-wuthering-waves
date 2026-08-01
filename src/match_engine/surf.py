import cv2
import numpy as np
import time
import os
from typing import Tuple, Optional

from .common import (
    KeyPoint, MapCache, MatchOutput, CoordsRef, grid_sample,
    save_npz, load_npz, desc_mat_from_slice_fast,
    project_corners, compute_center, extract_scale_factor, _prepare_test_image
)


def _extract(cfg, map_path, out_path, grid, mpc):
    img = cv2.imread(map_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"cannot read: {map_path}")
    h, w = img.shape[:2]

    kps, desc = cfg.detectAndCompute(img, None)
    if not kps or desc is None:
        raise ValueError(f"no features: {map_path}")

    sel_kps, sel_descs = grid_sample(kps, desc, h, w, grid, grid, mpc)
    save_npz(out_path, sel_kps, sel_descs, h, w)
    return sel_kps, sel_descs, h, w


def _load_cache(npz_path):
    kps, descs, h, w = load_npz(npz_path)
    desc_mat = desc_mat_from_slice_fast(descs)
    if not desc_mat.flags['C_CONTIGUOUS']:
        desc_mat = np.ascontiguousarray(desc_mat)
    return MapCache(kps, descs, desc_mat, h, w)


def _build_region_cache(cache, region):
    x, y, rw, rh = region
    mask = []
    for i, kp in enumerate(cache.kps):
        if x <= kp.x <= x + rw and y <= kp.y <= y + rh:
            mask.append(i)

    if len(mask) < 4:
        return None

    sub_kps = [cache.kps[i] for i in mask]
    sub_descs = [cache.descs[i] for i in mask]
    sub_mat = np.array(sub_descs, dtype=np.float32)
    return MapCache(sub_kps, sub_descs, sub_mat, cache.h, cache.w)


def _match_flann(cfg, test_src, cache, ratio_thresh, max_dist, crop_size, region,
                 constrained=False):
    start = time.time()
    img = _prepare_test_image(test_src, crop_size)
    if img is None:
        return MatchOutput(success=False, match_count=0, inlier_count=0,
                           confidence=0.0, elapsed_ms=(time.time() - start) * 1000)

    crop_w = img.shape[1]
    crop_h = img.shape[0]

    kps, desc = cfg.detectAndCompute(img, None)
    if not kps or desc is None:
        return MatchOutput(success=False, match_count=0, inlier_count=0,
                           confidence=0.0, elapsed_ms=(time.time() - start) * 1000)

    test_kps = [KeyPoint(
        kp.pt[0], kp.pt[1], kp.size, kp.angle,
        kp.response, kp.octave, kp.class_id
    ) for kp in kps]

    match_cache = cache
    if region is not None:
        match_cache = _build_region_cache(cache, region)
        if match_cache is None:
            return MatchOutput(success=False, match_count=0, inlier_count=0,
                               confidence=0.0, elapsed_ms=(time.time() - start) * 1000)

    matcher = cv2.FlannBasedMatcher_create()
    knn = matcher.knnMatch(desc, match_cache.desc_mat, 2)

    good = []
    for pair in knn:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < ratio_thresh * n.distance and m.distance < max_dist:
            good.append((m.queryIdx, m.trainIdx, m.distance))

    H = None
    inlier_count = 0
    min_matches = 2 if constrained else 4
    if len(good) >= min_matches:
        src_pts = np.array([[test_kps[q].x, test_kps[q].y] for q, _, _ in good],
                           dtype=np.float64).reshape(-1, 1, 2)
        dst_pts = np.array([[match_cache.kps[t].x, match_cache.kps[t].y] for _, t, _ in good],
                           dtype=np.float64).reshape(-1, 1, 2)
        if constrained:
            M, inliers = cv2.estimateAffinePartial2D(
                src_pts, dst_pts, method=cv2.RANSAC,
                ransacReprojThreshold=3.0, maxIters=2000, confidence=0.995)
            if M is not None:
                H = np.eye(3, dtype=np.float64)
                H[:2, :] = M
                inlier_count = int(inliers.sum())
        else:
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0,
                                         maxIters=2000, confidence=0.995)
            if mask is not None:
                inlier_count = int(mask.sum())

    elapsed = time.time() - start
    output = MatchOutput(
        success=H is not None and inlier_count > 0,
        match_count=len(good),
        inlier_count=inlier_count,
        confidence=inlier_count / max(len(good), 1),
        H=H,
        elapsed_ms=elapsed * 1000,
    )

    if output.success:
        corners = project_corners(H, crop_w, crop_h)
        output.center = compute_center(corners)
        output.corners = corners
        output.map_scale = extract_scale_factor(H, crop_w / 2, crop_h / 2)

    return output


class SurfEngine:
    def __init__(self, map_id, map_path, assets_dir,
                 hessian=40, octaves=8, layers=4,
                 extended=True, upright=True,
                 grid=150, max_per_cell=200,
                 ratio=0.62, max_dist=0.50,
                 coords_path=None):
        self.map_id = map_id
        self.ratio = ratio
        self.max_dist = max_dist
        self.grid = grid
        self.mpc = max_per_cell
        self.crop_size = 350

        npz_path = os.path.join(assets_dir, f"{map_id}_surf.npz")
        self.cfg = cv2.xfeatures2d.SURF_create(
            hessian, octaves, layers, extended, upright)

        if os.path.exists(npz_path):
            self.cache = _load_cache(npz_path)
        else:
            os.makedirs(assets_dir, exist_ok=True)
            kps, descs, h, w = _extract(self.cfg, map_path, npz_path, grid, max_per_cell)
            desc_mat = desc_mat_from_slice_fast(descs)
            self.cache = MapCache(kps, descs, desc_mat, h, w)

        self.coords = None
        if coords_path and os.path.exists(coords_path):
            self.coords = CoordsRef.load(coords_path)
        elif coords_path is None:
            alt = os.path.join(os.path.dirname(os.path.abspath(map_path)), f"{map_id}_coords.json")
            if os.path.exists(alt):
                self.coords = CoordsRef.load(alt)

    @property
    def feature_count(self):
        return len(self.cache.kps)

    @property
    def map_size(self):
        return self.cache.w, self.cache.h

    def match(self, test_path, region=None, crop_size=None, constrained=False):
        cs = crop_size if crop_size is not None else self.crop_size
        result = _match_flann(self.cfg, test_path, self.cache,
                              self.ratio, self.max_dist, cs, region,
                              constrained=constrained)
        if self.coords is not None:
            result.with_coords(self.coords)
        return result

    def match_array(self, test_img, region=None, crop_size=0, constrained=False):
        result = _match_flann(self.cfg, test_img, self.cache,
                              self.ratio, self.max_dist, crop_size, region,
                              constrained=constrained)
        if self.coords is not None:
            result.with_coords(self.coords)
        return result
