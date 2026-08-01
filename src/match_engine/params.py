"""Param_Set 与 Param_Set_Name 的定义、命名、序列化与校验。

仅描述特征提取参数（SURF / SIFT）与匹配参数，不含任何连续定位后处理参数。
纯逻辑模块（无 I/O）。

命名约定：

- SURF::

    surf_h{hessian}_o{octaves}_l{layers}_g{grid}_mpc{max_per_cell}
        _r{round(ratio*100)}_md{round(max_dist*100)}

- SIFT::

    sift_ct{round(contrast_threshold*1000)}_et{edge_threshold}
        _ol{n_octave_layers}_s{round(sigma*10)}_g{grid}_mpc{max_per_cell}
        _r{round(ratio*100)}

Param_Set_Name 仅由小写字母、数字与下划线组成（匹配 ``^[a-z0-9_]+$``），
可直接用作目录名与数据库键。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, fields
from typing import Union

from .errors import MatchEngineError

NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")

SURF = "surf"
SIFT = "sift"
SIFTGZ = "siftgz"


@dataclass(frozen=True)
class SurfParams:
    hessian: int
    octaves: int
    layers: int
    extended: bool
    upright: bool
    grid: int
    max_per_cell: int
    ratio: float
    max_dist: float


@dataclass(frozen=True)
class SiftParams:
    contrast_threshold: float
    edge_threshold: int
    n_octave_layers: int
    sigma: float
    grid: int
    max_per_cell: int
    ratio: float


@dataclass(frozen=True)
class SiftGzParams:
    contrast_threshold: float
    edge_threshold: int
    n_octave_layers: int
    sigma: float
    grid: int
    max_per_cell: int
    ratio: float
    downscale: int
    tile_size: int
    tile_overlap: int
    black_thresh: int
    edge_margin: int
    min_dist: float


_PARAM_TYPES = {SURF: SurfParams, SIFT: SiftParams, SIFTGZ: SiftGzParams}


@dataclass(frozen=True)
class ParamSet:
    algo: str
    params: Union[SurfParams, SiftParams, SiftGzParams]

    @property
    def name(self) -> str:
        p = self.params
        if self.algo == SURF and isinstance(p, SurfParams):
            return (
                f"surf_h{p.hessian}_o{p.octaves}_l{p.layers}"
                f"_g{p.grid}_mpc{p.max_per_cell}"
                f"_r{round(p.ratio * 100)}_md{round(p.max_dist * 100)}"
            )
        if self.algo == SIFT and isinstance(p, SiftParams):
            return (
                f"sift_ct{round(p.contrast_threshold * 1000)}"
                f"_et{p.edge_threshold}_ol{p.n_octave_layers}"
                f"_s{round(p.sigma * 10)}"
                f"_g{p.grid}_mpc{p.max_per_cell}"
                f"_r{round(p.ratio * 100)}"
            )
        if self.algo == SIFTGZ and isinstance(p, SiftGzParams):
            return (
                f"siftgz_ct{round(p.contrast_threshold * 1000)}"
                f"_et{p.edge_threshold}_ol{p.n_octave_layers}"
                f"_s{round(p.sigma * 10)}"
                f"_g{p.grid}_mpc{p.max_per_cell}"
                f"_r{round(p.ratio * 100)}"
                f"_ds{p.downscale}_ts{p.tile_size}_to{p.tile_overlap}"
                f"_bt{p.black_thresh}_em{p.edge_margin}"
                f"_md{round(p.min_dist * 10)}"
            )
        raise MatchEngineError(
            f"算法标识与参数类型不匹配：algo={self.algo!r}, "
            f"params={type(p).__name__}",
            name=str(self.algo),
        )

    def to_dict(self) -> dict:
        return {"algo": self.algo, "params": asdict(self.params)}

    @staticmethod
    def from_dict(d: dict) -> "ParamSet":
        if not isinstance(d, dict):
            raise MatchEngineError(f"Param_Set 定义必须为字典，得到 {type(d).__name__}")
        if "algo" not in d:
            raise MatchEngineError("Param_Set 定义缺少必需字段：algo")
        algo = d["algo"]
        param_type = _PARAM_TYPES.get(algo)
        if param_type is None:
            raise MatchEngineError(
                f"未知算法标识：{algo!r}（应为 'surf'、'sift' 或 'siftgz'）",
                name=str(algo),
            )
        raw = d.get("params")
        if not isinstance(raw, dict):
            raise MatchEngineError(
                "Param_Set 定义缺少必需字段：params（应为字典）",
                name=str(algo),
            )
        expected = {f.name for f in fields(param_type)}
        missing = expected - raw.keys()
        if missing:
            raise MatchEngineError(
                f"Param_Set 缺少必需字段：{sorted(missing)}",
                name=str(algo),
            )
        extra = raw.keys() - expected
        if extra:
            raise MatchEngineError(
                f"Param_Set 含未知字段：{sorted(extra)}",
                name=str(algo),
            )
        params = param_type(**{k: raw[k] for k in expected})
        param_set = ParamSet(algo=algo, params=params)
        param_set.validate()
        return param_set

    @classmethod
    def from_name(cls, name: str) -> "ParamSet":
        m = _SURF_NAME_RE.match(name)
        if m:
            h, o, l, g, mpc, r, md = m.groups()
            ps = cls(algo=SURF, params=SurfParams(
                hessian=int(h), octaves=int(o), layers=int(l),
                extended=True, upright=True,
                grid=int(g), max_per_cell=int(mpc),
                ratio=int(r) / 100.0, max_dist=int(md) / 100.0,
            ))
            ps.validate()
            return ps

        m = _SIFT_NAME_RE.match(name)
        if m:
            ct, et, ol, s, g, mpc, r = m.groups()
            ps = cls(algo=SIFT, params=SiftParams(
                contrast_threshold=int(ct) / 1000.0,
                edge_threshold=int(et), n_octave_layers=int(ol),
                sigma=int(s) / 10.0,
                grid=int(g), max_per_cell=int(mpc),
                ratio=int(r) / 100.0,
            ))
            ps.validate()
            return ps

        m = _SIFTGZ_NAME_RE.match(name)
        if m:
            ct, et, ol, s, g, mpc, r, ds, ts, to, bt, em, md = m.groups()
            ps = cls(algo=SIFTGZ, params=SiftGzParams(
                contrast_threshold=int(ct) / 1000.0,
                edge_threshold=int(et), n_octave_layers=int(ol),
                sigma=int(s) / 10.0,
                grid=int(g), max_per_cell=int(mpc),
                ratio=int(r) / 100.0,
                downscale=int(ds), tile_size=int(ts), tile_overlap=int(to),
                black_thresh=int(bt), edge_margin=int(em),
                min_dist=int(md) / 10.0,
            ))
            ps.validate()
            return ps

        raise MatchEngineError(f"无法解析参数集名称：{name!r}", name=name)

    def validate(self) -> None:
        p = self.params
        if self.algo not in _PARAM_TYPES:
            raise MatchEngineError(
                f"未知算法标识：{self.algo!r}（应为 'surf'、'sift' 或 'siftgz'）",
                name=str(self.algo),
            )
        if not isinstance(p, _PARAM_TYPES[self.algo]):
            raise MatchEngineError(
                f"算法标识与参数类型不匹配：algo={self.algo!r}, "
                f"params={type(p).__name__}",
                name=str(self.algo),
            )

        name = self._safe_name()

        if self.algo == SURF:
            self._require_positive_int(p.hessian, "hessian", name)
            self._require_positive_int(p.octaves, "octaves", name)
            self._require_positive_int(p.layers, "layers", name)
            self._require_bool(p.extended, "extended", name)
            self._require_bool(p.upright, "upright", name)
            self._require_positive_int(p.grid, "grid", name)
            self._require_positive_int(p.max_per_cell, "max_per_cell", name)
            self._require_ratio(p.ratio, "ratio", name)
            self._require_positive_float(p.max_dist, "max_dist", name)
        elif self.algo == SIFT:
            self._require_positive_float(
                p.contrast_threshold, "contrast_threshold", name
            )
            self._require_positive_int(p.edge_threshold, "edge_threshold", name)
            self._require_positive_int(p.n_octave_layers, "n_octave_layers", name)
            self._require_positive_float(p.sigma, "sigma", name)
            self._require_positive_int(p.grid, "grid", name)
            self._require_positive_int(p.max_per_cell, "max_per_cell", name)
            self._require_ratio(p.ratio, "ratio", name)
        elif self.algo == SIFTGZ:
            self._require_positive_float(
                p.contrast_threshold, "contrast_threshold", name
            )
            self._require_positive_int(p.edge_threshold, "edge_threshold", name)
            self._require_positive_int(p.n_octave_layers, "n_octave_layers", name)
            self._require_positive_float(p.sigma, "sigma", name)
            self._require_positive_int(p.grid, "grid", name)
            self._require_positive_int(p.max_per_cell, "max_per_cell", name)
            self._require_ratio(p.ratio, "ratio", name)
            self._require_positive_int(p.downscale, "downscale", name)
            if p.tile_size < 0:
                raise MatchEngineError("tile_size 必须为非负整数。", name=name)
            self._require_positive_int(p.tile_overlap, "tile_overlap", name)
            if p.black_thresh < -1:
                raise MatchEngineError("black_thresh 必须 >= -1。", name=name)
            if p.edge_margin < 0:
                raise MatchEngineError("edge_margin 必须为非负整数。", name=name)
            self._require_positive_float(p.min_dist, "min_dist", name)

    def _safe_name(self) -> str:
        try:
            return self.name
        except (MatchEngineError, TypeError, ValueError):
            return str(self.algo)

    @staticmethod
    def _require_positive_int(value: object, field: str, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise MatchEngineError(
                f"字段 {field} 必须为整数，得到 {value!r}", name=name
            )
        if value <= 0:
            raise MatchEngineError(
                f"字段 {field} 必须为正整数，得到 {value!r}", name=name
            )

    @staticmethod
    def _require_positive_float(value: object, field: str, name: str) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise MatchEngineError(
                f"字段 {field} 必须为数值，得到 {value!r}", name=name
            )
        if value <= 0:
            raise MatchEngineError(
                f"字段 {field} 必须为正数，得到 {value!r}", name=name
            )

    @staticmethod
    def _require_ratio(value: object, field: str, name: str) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise MatchEngineError(
                f"字段 {field} 必须为数值，得到 {value!r}", name=name
            )
        if not (0 < value <= 1):
            raise MatchEngineError(
                f"字段 {field} 必须在 (0, 1] 范围内，得到 {value!r}", name=name
            )

    @staticmethod
    def _require_bool(value: object, field: str, name: str) -> None:
        if not isinstance(value, bool):
            raise MatchEngineError(
                f"字段 {field} 必须为布尔值，得到 {value!r}", name=name
            )


_SURF_NAME_RE = re.compile(
    r"^surf_h(\d+)_o(\d+)_l(\d+)_g(\d+)_mpc(\d+)_r(\d+)_md(\d+)$"
)
_SIFT_NAME_RE = re.compile(
    r"^sift_ct(\d+)_et(\d+)_ol(\d+)_s(\d+)_g(\d+)_mpc(\d+)_r(\d+)$"
)
_SIFTGZ_NAME_RE = re.compile(
    r"^siftgz_ct(\d+)_et(\d+)_ol(\d+)_s(\d+)_g(\d+)_mpc(\d+)_r(\d+)"
    r"_ds(\d+)_ts(\d+)_to(\d+)_bt(\d+)_em(\d+)_md(\d+)$"
)


def params_to_engine_kwargs(ps: "ParamSet") -> dict:
    p = ps.params
    if ps.algo == SURF:
        return dict(
            hessian=p.hessian, octaves=p.octaves, layers=p.layers,
            extended=p.extended, upright=p.upright,
            grid=p.grid, max_per_cell=p.max_per_cell,
            ratio=p.ratio, max_dist=p.max_dist,
        )
    if ps.algo == SIFT:
        return dict(
            nfeatures=0, nOctaveLayers=p.n_octave_layers,
            contrastThreshold=p.contrast_threshold,
            edgeThreshold=p.edge_threshold, sigma=p.sigma,
            grid=p.grid, max_per_cell=p.max_per_cell, ratio=p.ratio,
        )
    if ps.algo == SIFTGZ:
        return dict(
            nfeatures=0, nOctaveLayers=p.n_octave_layers,
            contrastThreshold=p.contrast_threshold,
            edgeThreshold=p.edge_threshold, sigma=p.sigma,
            grid=p.grid, max_per_cell=p.max_per_cell, ratio=p.ratio,
            downscale=p.downscale, tile_size=p.tile_size,
            tile_overlap=p.tile_overlap, black_thresh=p.black_thresh,
            edge_margin=p.edge_margin, min_dist=p.min_dist,
        )
    raise MatchEngineError(f"未知算法：{ps.algo!r}", name=str(ps.algo))


__all__ = [
    "SURF", "SIFT", "SIFTGZ",
    "SurfParams", "SiftParams", "SiftGzParams",
    "ParamSet",
    "params_to_engine_kwargs",
]
