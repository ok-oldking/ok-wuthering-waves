"""库存或图像配置的独立逻辑，不启动游戏，不修改已有任务计划。"""

from __future__ import annotations

import configparser
import json
import re
import sqlite3
import subprocess
import os
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROFILES = Path(__file__).with_name("calibrated_profiles.json")


def write_staged(stream: Any, data: bytes) -> None:
    """完整写入并刷盘临时文件；失败时不触碰原配置。"""
    if stream.write(data) != len(data):
        raise OSError('INI 临时文件未完整写入')
    stream.flush()
    os.fsync(stream.fileno())


def atomic_ini(path: Path, data: bytes, expected: tuple[bytes, ...]) -> None:
    """同目录暂存，复核原文件所有权后原子替换。"""
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            name = stream.name
            write_staged(stream, data)
        if path.read_bytes() not in expected:
            raise RuntimeError('INI发生外部改动，保留原文件')
        os.replace(name, path)
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)
DB_KEYS = (
    "AntiAliasing",
    "AutoAdjustImageQuality",
    "BloomEnable",
    "NpcDensity",
    "VegetationDensity",
    "CustomFrameRate",
    "ImageDetail",
    "ImageQuality",
    "IsUsingQualityPreset",
    "MotionBlur",
    "NiagaraQuality",
    "NvidiaSuperSamplingEnable",
    "NvidiaSuperSamplingFrameGenerate",
    "NvidiaSuperSamplingQuality",
    "NvidiaSuperSamplingSharpness",
    "PcVsync",
    "RayTracedShadow",
    "RayTracing",
    "SceneAo",
    "ShadowQuality",
    "VolumeFog",
    "VolumeLight",
)
INI_KEYS = {
    "ScalabilityGroups": (
        "sg.ResolutionQuality",
        "sg.ViewDistanceQuality",
        "sg.AntiAliasingQuality",
        "sg.ShadowQuality",
        "sg.PostProcessQuality",
        "sg.TextureQuality",
        "sg.EffectsQuality",
        "sg.FoliageQuality",
        "sg.ShadingQuality",
        "sg.KuroRenderQuality",
        "sg.RayTracingQuality",
        "sg.KuroLocalRenderQuality",
    ),
    "/Script/Engine.GameUserSettings": (
        "bUseVSync",
        "bUseDynamicResolution",
        "GameQualitySettingLevel",
        "FrameRateLimit",
    ),
}


def ensure_idle() -> None:
    """确认游戏未运行；状态不明时拒绝修改。"""
    for name in ("Client-Win64-Shipping.exe", "launcher_main.exe", "launcher.exe"):
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            check=True,
            timeout=10,
        )
        if (
            not result.stdout.strip()
            or ('"' + name + '"').lower().encode() in result.stdout.lower()
        ):
            raise RuntimeError("游戏/启动器仍在运行或进程核实失败，不改图形配置")


def read_graphics(db_path: Any, ini_path: Any) -> Any:
    """只读图像白名单字段。"""
    with closing(
        sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=2)
    ) as db:
        rows = {
            key: row[0]
            for key in DB_KEYS
            if (
                row := db.execute(
                    "SELECT Value FROM LocalStorage WHERE Key=?", (key,)
                ).fetchone()
            )
        }
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(ini_path, encoding="utf-8-sig")
    ini = {
        section: {
            key: parser.get(section, key)
            for key in keys
            if parser.has_option(section, key)
        }
        for section, keys in INI_KEYS.items()
    }
    if "ImageQuality" not in rows or not ini["ScalabilityGroups"]:
        raise RuntimeError("图形配置结构已变更，暂停切换")
    return {"db": rows, "ini": ini}


def patch_ini(text: Any, changes: Any) -> Any:
    """只修改指定的已有 INI 字段。"""
    section = ""
    found = set()
    result = []
    for line in text.splitlines(keepends=True):
        header = re.fullmatch("\\[([^\\]]+)\\]", line.strip())
        if header:
            section = header[1]
        key = line.split("=", 1)[0].strip() if "=" in line else None
        if key in changes.get(section, {}):
            pair = (section, key)
            if pair in found:
                raise RuntimeError("INI图形字段重复，拒绝切换")
            found.add(pair)
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            line = key + "=" + changes[section][key] + newline
        result.append(line)
    required = {(s, k) for s, fields in changes.items() for k in fields}
    if found != required:
        raise RuntimeError("INI字段缺失，不盲目新增")
    return "".join(result)


def profile_mismatches(profile: Any, actual: Any) -> Any:
    """比较目标配置和实际读回的图像字段。"""
    return ["db:" + k for k, v in profile["db"].items() if actual["db"].get(k) != v] + [
        "ini:" + s + ":" + k
        for s, fields in profile["ini"].items()
        for k, v in fields.items()
        if actual["ini"].get(s, {}).get(k) != v
    ]


def restore_owned_graphics(
    before: Any,
    profile: Any,
    original: Any,
    changed: Any,
    db_path: Any,
    ini_path: Any,
    idle: Any = None,
) -> Any:
    """仅回滚本次拥有的图像改动，不覆盖外部保存。"""
    idle = idle or ensure_idle
    with closing(sqlite3.connect(db_path, timeout=2)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        for key, value in profile["db"].items():
            rows = db.execute(
                "SELECT Value FROM LocalStorage WHERE Key=?", (key,)
            ).fetchall()
            if len(rows) != 1 or rows[0][0] not in (before["db"].get(key), value):
                raise RuntimeError("回滚遇到外部图形改动，保留现场和备份: " + key)
        if ini_path.read_bytes() not in (original, changed):
            raise RuntimeError("回滚遇到外部INI改动，保留现场和备份")
        idle()
        for key in profile["db"]:
            db.execute(
                "UPDATE LocalStorage SET Value=? WHERE Key=?", (before["db"][key], key)
            )
        idle()
        atomic_ini(ini_path, original, (original, changed))
        db.commit()
    expected = {
        "db": {key: before["db"][key] for key in profile["db"]},
        "ini": before["ini"],
    }
    if (
        profile_mismatches(expected, read_graphics(db_path, ini_path))
        or ini_path.read_bytes() != original
    ):
        raise RuntimeError("回滚读回不一致，保留备份需排查")


def apply_profile(
    profile: Any, db_path: Any, ini_path: Any, backup_dir: Any = None, idle: Any = None
) -> Any:
    """写前核验、备份并应用指定的图像配置。"""
    if any(key not in DB_KEYS for key in profile["db"]):
        raise RuntimeError("非图形数据库字段被拒绝")
    for section, fields in profile["ini"].items():
        if section not in INI_KEYS or any(k not in INI_KEYS[section] for k in fields):
            raise RuntimeError("非图形INI字段被拒绝")
    idle = idle or ensure_idle
    idle()
    original = ini_path.read_bytes()
    bom = original.startswith(b"\xef\xbb\xbf")
    text = original.decode("utf-8-sig")
    changed = patch_ini(text, profile["ini"]).encode("utf-8")
    if bom:
        changed = b"\xef\xbb\xbf" + changed
    before = read_graphics(db_path, ini_path)
    backup_dir = Path(backup_dir) if backup_dir is not None else ini_path.parent / 'graphics-profile-backups'
    if backup_dir:
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        (backup_dir / (stamp + ".json")).write_text(
            json.dumps(before, ensure_ascii=False), encoding="utf-8"
        )
        with (backup_dir / (stamp + '.ini')).open('xb') as backup:
            write_staged(backup, original)
    with closing(sqlite3.connect(db_path, timeout=2)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        idle()
        if ini_path.read_bytes() != original:
            raise RuntimeError("提交前INI发生外部改动，保留现场和备份")
        for key, value in profile["db"].items():
            if not isinstance(value, str):
                raise RuntimeError("图形值必须来自原生配置快照")  # noqa: TRY004 配置契约失败，保持公开异常类型
            rows = db.execute(
                "SELECT Value FROM LocalStorage WHERE Key=?", (key,)
            ).fetchall()
            if len(rows) != 1 or rows[0][0] != before["db"].get(key):
                raise RuntimeError(
                    "提交前数据库发生外部改动或图形行缺失，保留现场和备份: " + key
                )
            cur = db.execute(
                "UPDATE LocalStorage SET Value=? WHERE Key=?", (value, key)
            )
            if cur.rowcount != 1:
                raise RuntimeError("图形行缺失或重复: " + key)
        ini_attempted = False
        try:
            idle()
            if ini_path.read_bytes() != original:
                raise RuntimeError("INI提交前发生外部改动，保留现场和备份")
            ini_attempted = True
            atomic_ini(ini_path, changed, (original,))
            db.commit()
        except Exception as error:
            if ini_attempted:
                try:
                    idle()
                    if ini_path.read_bytes() not in (original, changed):
                        raise RuntimeError("INI保存后发生外部改动")
                    if ini_path.read_bytes() != original:
                        atomic_ini(ini_path, original, (changed,))
                except Exception as rollback_error:  # noqa: BLE001 回滚失败仍须报告并保留原始写入错误
                    raise RuntimeError(
                        "INI提交失败且不能安全回滚，保留现场和备份: "
                        + str(rollback_error)
                    ) from error
            raise
    try:
        after = read_graphics(db_path, ini_path)
        if profile_mismatches(profile, after):
            raise RuntimeError("图形切换读回验证失败")
    except Exception as error:
        try:
            restore_owned_graphics(
                before, profile, original, changed, db_path, ini_path, idle
            )
        except Exception as rollback_error:  # noqa: BLE001 回滚失败仍须报告并保留原始写入错误
            raise RuntimeError(
                "图形核对失败且无法安全回滚；保留备份: " + str(rollback_error)
            ) from error
        raise RuntimeError("图形核对失败，已回滚并读回原设置") from error
