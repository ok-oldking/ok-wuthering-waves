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


def _build_npy_bytes(shape, dtype, data):
    shape_str = "("
    for i, s in enumerate(shape):
        if i > 0:
            shape_str += ", "
        shape_str += str(s)
    if len(shape) == 1:
        shape_str += ","
    shape_str += ")"
    hdr = f"{{'descr': '{dtype}', 'fortran_order': False, 'shape': {shape_str}}}"
    prefix = bytes([0x93, ord('N'), ord('U'), ord('M'), ord('P'), ord('Y'), 1, 0])
    payload = hdr
    while (len(prefix) + 2 + len(payload) + 1) % 16 != 0:
        payload += " "
    payload += "\n"
    return prefix + struct.pack('<H', len(payload)) + payload.encode() + data


def save_npz(path, kps, descs, map_h, map_w):
    num_kp = len(kps)
    desc_cols = len(descs[0]) if descs else 0

    kp_data = []
    for kp in kps:
        kp_data.extend([kp.x, kp.y, kp.size, kp.angle, kp.response,
                        float(kp.octave), float(kp.class_id)])

    desc_data = []
    for row in descs:
        desc_data.extend(row)

    num_arr = _build_npy_bytes([], '<i4', struct.pack('<i', num_kp))
    kp_arr = _build_npy_bytes([num_kp, 7], '<f4', struct.pack(f'<{len(kp_data)}f', *kp_data))
    desc_arr = _build_npy_bytes([num_kp, desc_cols], '<f4', struct.pack(f'<{len(desc_data)}f', *desc_data))
    size_arr = _build_npy_bytes([2], '<i4', struct.pack('<ii', map_h, map_w))

    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('num_keypoints.npy', num_arr)
        zf.writestr('keypoints.npy', kp_arr)
        zf.writestr('descriptors.npy', desc_arr)
        zf.writestr('map_size.npy', size_arr)


def _skip_npy_header(data):
    if len(data) < 10 or data[0] != 0x93 or data[1:6] != b'NUMPY':
        raise ValueError("invalid npy header")
    hdr_len = struct.unpack('<H', data[8:10])[0]
    return data[10 + hdr_len:]


def load_npz(path):
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
