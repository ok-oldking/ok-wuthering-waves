"""地图附加层资源包（``assets.zip``）的下载与覆盖解压。

资源包托管在 GitHub Release（``wuwa-map``），内容为 ``stitched/`` 目录下的特征文件
（``*_siftgz.npz``）、物品数据库（``map_items.db``）、坐标/参数配置
（``map_coords.json`` / ``setting.json``）、图标以及版本号文件 ``version.txt``。

本模块只依赖标准库（``zipfile`` / ``os`` / ``shutil``）与 ``requests``（不可用时回退
``urllib``），**不引入 Qt**，因此可以在没有游戏运行环境的机器上直接导入与测试：

- :func:`read_asset_version` 读取本地资源版本（面板展示用）；
- :func:`missing_required_assets` 判断特征文件 / 数据库等关键资源是否缺失，供启用
  附加功能时自动触发下载；
- :func:`download_and_extract` 下载 zip 到临时文件后覆盖解压到 ``assets`` 目录，
  并通过 ``progress`` 回调上报下载进度与解压状态。
"""

from __future__ import annotations

import math
import os
import shutil
import time
import zipfile

# 资源包下载地址（GitHub Release 的 latest 直链）。
ASSETS_URL = 'https://github.com/9268/wuwa-map/releases/latest/download/assets.zip'

# 资源包内的版本号文件名；zip 中位于 ``stitched/version.txt``。
VERSION_FILE_NAME = 'version.txt'

# 关键资源（相对 assets 目录，使用 '/' 分隔）：缺任意一项即认为资源不完整。
REQUIRED_ASSET_FILES = (
    'stitched/map_coords.json',
    'stitched/map_items.db',
    'stitched/setting.json',
)

# 特征文件后缀：至少要存在一个地图特征文件才算资源可用。
FEATURE_SUFFIX = '_siftgz.npz'

# 单次网络请求超时（秒）。资源包约 20MB+，给足流式读取时间。
DOWNLOAD_TIMEOUT = 60.0

# 下载分块大小（字节）。
CHUNK_SIZE = 1 << 18

# 进度回调最小间隔（秒），避免高频刷新面板信息。
PROGRESS_INTERVAL = 0.3

# 解压时允许剥离的顶层目录：zip 若打包成 ``assets/stitched/...`` 也能正确落盘。
STRIP_TOP_DIRS = ('assets',)


def format_size(size_bytes) -> str:
    """把字节数格式化为人类可读字符串（B/KB/MB/GB）。"""
    try:
        size_bytes = int(size_bytes)
    except (TypeError, ValueError):
        return '0 B'
    if size_bytes <= 0:
        return '0 B'
    units = ('B', 'KB', 'MB', 'GB', 'TB')
    i = min(int(math.floor(math.log(size_bytes, 1024))), len(units) - 1)
    value = size_bytes / math.pow(1024, i)
    return f'{value:.1f} {units[i]}'


def version_file_path(assets_dir) -> str | None:
    """返回本地版本号文件路径，找不到返回 ``None``。

    优先 ``assets/stitched/version.txt``（与 zip 内布局一致），兼容
    ``assets/version.txt``。
    """
    candidates = (
        os.path.join(assets_dir, 'stitched', VERSION_FILE_NAME),
        os.path.join(assets_dir, VERSION_FILE_NAME),
    )
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def read_asset_version(assets_dir) -> str | None:
    """读取本地资源版本号（``version.txt`` 首行），不可用时返回 ``None``。"""
    path = version_file_path(assets_dir)
    if path is None:
        return None
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    except OSError:
        return None
    version = text.strip().splitlines()[0].strip() if text.strip() else ''
    return version or None


def missing_required_assets(assets_dir) -> list:
    """返回缺失的关键资源（相对路径列表），全部就绪时返回空列表。"""
    missing = []
    for rel in REQUIRED_ASSET_FILES:
        if not os.path.isfile(os.path.join(assets_dir, *rel.split('/'))):
            missing.append(rel)
    stitched = os.path.join(assets_dir, 'stitched')
    try:
        has_feature = any(
            name.endswith(FEATURE_SUFFIX) for name in os.listdir(stitched)
        )
    except OSError:
        has_feature = False
    if not has_feature:
        missing.append(f'stitched/*{FEATURE_SUFFIX}')
    return missing


def assets_ready(assets_dir) -> bool:
    """关键资源是否齐全（特征文件、数据库、坐标与参数配置）。"""
    return not missing_required_assets(assets_dir)


def target_relative_path(name) -> str | None:
    """把 zip 成员名映射为相对 ``assets`` 目录的安全路径。

    - 目录项、空名返回 ``None``（无需单独创建，写文件时会建目录）；
    - 剥离可能的顶层 ``assets/`` 前缀，使 ``assets/stitched/x`` 与 ``stitched/x``
      两种打包方式都落到同一位置；
    - 拒绝绝对路径、盘符与 ``..``（防 zip slip）。
    """
    if not name or name.endswith('/') or name.endswith('\\'):
        return None
    normalized = name.replace('\\', '/')
    parts = [p for p in normalized.split('/') if p not in ('', '.')]
    if not parts:
        return None
    if any(p == '..' for p in parts) or os.path.isabs(normalized) or ':' in parts[0]:
        return None
    if len(parts) > 1 and parts[0].lower() in STRIP_TOP_DIRS:
        parts = parts[1:]
    if not parts:
        return None
    return '/'.join(parts)


def _notify(progress, stage, message, percent=-1.0):
    """调用进度回调 ``progress(stage, message, percent)``。

    ``percent`` 为 0..100 的完成百分比，无法计算时为负数（例如服务器未返回
    ``content-length``），调用方可据此保持进度条原样 / 显示忙碌状态。
    """
    if progress is None:
        return
    try:
        progress(stage, message, percent)
    except Exception:  # pragma: no cover - 回调异常不应影响下载
        pass


def _download_to_file(url, dest_path, progress=None):
    """流式下载 ``url`` 到 ``dest_path``，按间隔上报下载进度。"""
    os.makedirs(os.path.dirname(dest_path) or '.', exist_ok=True)
    if os.path.exists(dest_path):
        try:
            os.remove(dest_path)
        except OSError:
            pass

    total = 0
    downloaded = 0
    last_report = 0.0

    def report(force=False):
        nonlocal last_report
        now = time.time()
        if not force and now - last_report < PROGRESS_INTERVAL:
            return
        last_report = now
        if total > 0:
            percent = min(downloaded / total * 100.0, 100.0)
            _notify(progress, 'download',
                    f'下载中 {percent:.1f}% '
                    f'({format_size(downloaded)}/{format_size(total)})', percent)
        else:
            _notify(progress, 'download', f'下载中 {format_size(downloaded)}')

    try:
        import requests  # type: ignore

        with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get('content-length') or 0)
            with open(dest_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    report()
    except ImportError:  # pragma: no cover - requests 缺失时的回退
        import urllib.request

        req = urllib.request.Request(
            url, headers={'User-Agent': 'ok-ww-AssetsDownloader/1.0'}
        )
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            total = int(resp.headers.get('content-length') or 0)
            with open(dest_path, 'wb') as f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    report()
    report(force=True)
    return downloaded


def extract_zip_over(zip_path, assets_dir, progress=None) -> int:
    """把 ``zip_path`` 覆盖解压到 ``assets_dir``，返回写入的文件数。

    逐个成员写入（同名文件直接覆盖），路径经 :func:`target_relative_path` 规范化，
    因此不会写出 ``assets_dir`` 之外的位置。
    """
    written = 0
    with zipfile.ZipFile(zip_path) as zf:
        members = [
            (info, target_relative_path(info.filename))
            for info in zf.infolist()
        ]
        members = [(info, rel) for info, rel in members if rel]
        total = len(members)
        last_report = 0.0
        for index, (info, rel) in enumerate(members, start=1):
            target = os.path.join(assets_dir, *rel.split('/'))
            os.makedirs(os.path.dirname(target) or '.', exist_ok=True)
            with zf.open(info) as src, open(target, 'wb') as dst:
                shutil.copyfileobj(src, dst, CHUNK_SIZE)
            written += 1
            now = time.time()
            if now - last_report >= PROGRESS_INTERVAL or index == total:
                last_report = now
                percent = index / total * 100.0 if total else -1.0
                _notify(progress, 'extract',
                        f'解压中 {index}/{total} {rel}', percent)
    return written


def download_and_extract(assets_dir, url=ASSETS_URL, progress=None) -> str | None:
    """下载资源包并覆盖解压到 ``assets_dir``，返回解压后的版本号。

    ``progress(stage, message)`` 回调的 ``stage`` 取值：``'download'``（下载进度）、
    ``'extract'``（解压状态）、``'done'``（完成，含版本号）。失败时抛出异常，由调用方
    负责上报错误信息。
    """
    os.makedirs(assets_dir, exist_ok=True)
    tmp_zip = os.path.join(assets_dir, '.assets_download.zip')
    _notify(progress, 'download', '开始下载资源包', 0.0)
    try:
        size = _download_to_file(url, tmp_zip, progress=progress)
        _notify(progress, 'extract', f'下载完成 {format_size(size)}，开始解压', 0.0)
        count = extract_zip_over(tmp_zip, assets_dir, progress=progress)
    finally:
        if os.path.exists(tmp_zip):
            try:
                os.remove(tmp_zip)
            except OSError:
                pass
    version = read_asset_version(assets_dir)
    _notify(progress, 'done',
            f'资源更新完成，共 {count} 个文件，版本 {version or "未知"}', 100.0)
    return version
