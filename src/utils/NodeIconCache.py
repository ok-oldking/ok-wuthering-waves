"""Pure-logic helpers for building route-node icon URLs and cache filenames.

This module is part of the *pure-logic layer* of the map-overlay-interaction
feature. The helpers defined here (:func:`build_node_icon_url` and
:func:`cache_filename`) have **no** dependency on PySide6/Qt, networking, or
threads, so they can be imported and tested on a development machine
(conda env ``wuwa`` / local ``.venv``) without pulling in the game runtime.

The background downloader / on-disk cache (task 13.3) will be added to this same
module later. It must keep the Qt/networking/threading imports local to the
downloader implementation so these pure helpers stay importable in tests.

Design references:
- requirements.md 需求 11 (route node icon download & cache)
- Requirements 11.2 (URL construction), 11.3 (missing/empty positionImg),
  11.4 (cache filename = basename of positionImg).

Feature: map-overlay-interaction
"""

from __future__ import annotations

import posixpath
from typing import Optional

# Base host for Kurobbs static assets. Node icons are served under this host and
# transformed to webp via an OSS image-process query suffix.
# Requirement 11.2.
KUROBBS_BASE: str = "https://web-static.kurobbs.com/"

# Query suffix instructing the OSS image pipeline to return the image as webp.
# Requirement 11.2.
WEBP_SUFFIX: str = "?x-oss-process=image/format,webp"


def _clean_position_img(position_img: Optional[str]) -> Optional[str]:
    """Return the stripped ``position_img`` or ``None`` when missing/blank.

    A ``position_img`` is considered absent when it is ``None`` or, after
    stripping surrounding whitespace, an empty string. This centralizes the
    missing/empty/whitespace-only handling shared by both public helpers
    (Requirements 11.3, 11.4).
    """
    if position_img is None:
        return None
    stripped = position_img.strip()
    if not stripped:
        return None
    return stripped


def build_node_icon_url(position_img: Optional[str]) -> Optional[str]:
    """Build the Node_Icon_URL for a route node's ``positionImg``.

    The URL is ``KUROBBS_BASE + position_img + WEBP_SUFFIX``. For example a
    ``position_img`` of ``adminConfig/51/props_namephoto/1765961636454.png``
    yields
    ``https://web-static.kurobbs.com/adminConfig/51/props_namephoto/1765961636454.png?x-oss-process=image/format,webp``.

    Returns ``None`` when ``position_img`` is missing, empty, or whitespace-only
    (Requirement 11.3), so callers skip building a URL / issuing a download.

    Requirement 11.2, 11.3.
    """
    cleaned = _clean_position_img(position_img)
    if cleaned is None:
        return None
    return KUROBBS_BASE + cleaned + WEBP_SUFFIX


def cache_filename(position_img: Optional[str]) -> Optional[str]:
    """Return the local cache filename (basename) for a node's ``positionImg``.

    The cache filename is the final path segment of ``position_img`` (its
    basename), e.g. ``adminConfig/51/props_namephoto/1765961636454.png`` ->
    ``1765961636454.png``. Uses POSIX path semantics because ``positionImg``
    values use forward slashes regardless of host OS.

    Returns ``None`` when ``position_img`` is missing, empty, or whitespace-only
    (Requirement 11.4). Also returns ``None`` when the value has no basename
    component (e.g. ends with a trailing slash), so callers fall back to the
    ``qzx_04`` icon instead of using an empty filename.

    Requirement 11.4.
    """
    cleaned = _clean_position_img(position_img)
    if cleaned is None:
        return None
    base = posixpath.basename(cleaned)
    if not base:
        return None
    return base


# ---------------------------------------------------------------------------
# Background downloader / on-disk cache (task 13.3)
# ---------------------------------------------------------------------------
#
# Everything below implements the *runtime adapter* half of NodeIconCache: a
# single background worker thread that downloads route-node icons, caches them
# under ``assets/stitched/icon_cache/`` and decodes/scales the webp bytes for
# rendering. Its behaviour is manually verified on the game machine (network /
# webp decode / threading), so it is intentionally excluded from PBT.
#
# IMPORTANT (import discipline): the pure helpers above must stay importable in a
# Qt-free / network-free / thread-free environment for automated testing.
# Therefore this section adds **no** Qt / networking / threading imports at
# module top level -- every such import is deferred into ``__init__`` or the
# individual methods / the worker thread. Only ``logging`` (stdlib, Qt-free) and
# ``typing`` are used here at module scope.
#
# Requirements: 11.1, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10, 11.11, 11.12.

import logging
from typing import Iterable

logger = logging.getLogger(__name__)

# Default display size for a node icon, kept in sync with
# ``src.utils.MapItemOverlay.ICON_SIZE`` (30). Declared here as a plain int so
# this module keeps importing without Qt; the downloader scales decoded icons to
# this size to match the local ``qzx_0x`` icons (Requirement 11.10).
DEFAULT_ICON_SIZE: int = 30

# Per-download network timeout in seconds (Requirement 11.11).
DOWNLOAD_TIMEOUT: float = 10.0

# Maximum attempts per node icon: 1 initial + 2 retries = 3 (Requirement 11.12).
MAX_ATTEMPTS: int = 3

# Upper bound on how many nodes a single prefetch enqueues (Requirement 11.7).
MAX_PREFETCH: int = 1000


class NodeIconCache:
    """Single-threaded background downloader + on-disk cache for node icons.

    The detection loop only ever calls the read-only :meth:`get_pixmap`; all
    network / disk / decode work happens on one dedicated worker thread fed by a
    queue, so downloads never block the detection loop (Requirement 11.6).

    Lifecycle::

        cache = NodeIconCache()                 # starts the worker thread
        cache.prefetch(node.position_img ...)   # on entering Path_Mode
        pm = cache.get_pixmap(node.position_img)  # per-node during rendering
        cache.stop()                            # on task / mode exit

    Requirements: 11.1, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10, 11.11, 11.12.
    """

    def __init__(self, cache_dir: str = "assets/stitched/icon_cache",
                 icon_size: int = DEFAULT_ICON_SIZE) -> None:
        # Deferred imports keep the pure helpers above importable without a
        # threading runtime (import discipline, see module note).
        import os
        import queue
        import threading

        self._cache_dir = cache_dir
        try:
            self._icon_size = int(icon_size)
        except (TypeError, ValueError):
            self._icon_size = DEFAULT_ICON_SIZE
        if self._icon_size <= 0:
            self._icon_size = DEFAULT_ICON_SIZE

        # Ensure the cache directory exists before any read/write (Req 11.4).
        try:
            os.makedirs(self._cache_dir, exist_ok=True)
        except OSError:
            logger.exception("failed to create node icon cache dir %s", self._cache_dir)

        # Shared state guarded by ``_lock``.
        self._lock = threading.Lock()
        # position_img -> already scaled QImage (produced on the worker thread;
        # QImage is safe to build off the GUI thread, unlike QPixmap).
        self._ready: dict = {}
        # position_img -> QPixmap converted lazily on first get_pixmap.
        self._pixmaps: dict = {}
        # position_img values that have been permanently abandoned after
        # exhausting retries / being undecodable (Requirement 11.12).
        self._failed: set = set()
        # position_img values currently queued or in flight (dedupe guard).
        self._inflight: set = set()

        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(
            target=self._worker_loop, name="NodeIconCache", daemon=True
        )
        self._worker.start()

    # -- public API --------------------------------------------------------

    def prefetch(self, position_imgs: Iterable[str]) -> None:
        """Enqueue downloads for every node ``position_img`` (deduped, capped).

        Called after entering ``Path_Mode`` and loading the route. Blank /
        missing values are skipped, duplicates collapse, and at most
        :data:`MAX_PREFETCH` (~1000) nodes are enqueued (Requirement 11.7). This
        method never blocks on the network -- it only appends to the worker's
        queue.
        """
        if position_imgs is None:
            return
        seen: set = set()
        count = 0
        for raw in position_imgs:
            cleaned = _clean_position_img(raw)
            if cleaned is None or cleaned in seen:
                continue
            seen.add(cleaned)
            self._enqueue(cleaned)
            count += 1
            if count >= MAX_PREFETCH:
                break

    def get_pixmap(self, position_img):
        """Return the ready downloaded icon ``QPixmap`` for ``position_img``.

        Read-only, called from the detection loop. Returns ``None`` when the
        value is blank / missing, the icon is not yet ready, or the node has
        been abandoned after failures -- the caller then falls back to the
        ``qzx_04`` icon (Requirements 11.8, 11.9). Never raises.
        """
        try:
            cleaned = _clean_position_img(position_img)
            if cleaned is None:
                return None
            with self._lock:
                cached = self._pixmaps.get(cleaned)
                if cached is not None:
                    return cached
                image = self._ready.get(cleaned)
            if image is None:
                return None
            # Convert QImage -> QPixmap lazily and memoize it.
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap.fromImage(image)
            if pixmap.isNull():
                return None
            with self._lock:
                self._pixmaps[cleaned] = pixmap
            return pixmap
        except Exception:
            # A rendering-path read must never break the detection loop.
            logger.exception("get_pixmap failed for %r", position_img)
            return None

    def stop(self) -> None:
        """Signal the worker thread to exit and wait briefly for it to join."""
        self._stop_event.set()
        try:
            # Wake the worker if it is blocked on an empty queue.
            self._queue.put_nowait(None)
        except Exception:
            pass
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.is_alive():
            worker.join(timeout=2.0)

    # -- internals ---------------------------------------------------------

    def _enqueue(self, cleaned: str) -> None:
        """Queue ``cleaned`` for download unless already ready/failed/in flight."""
        with self._lock:
            if (cleaned in self._ready or cleaned in self._inflight
                    or cleaned in self._failed):
                return
            self._inflight.add(cleaned)
        self._queue.put(cleaned)

    def _worker_loop(self) -> None:
        """Consume the queue on a single background thread.

        Every task is wrapped so a failure of one node can never bubble up and
        kill the worker thread or, transitively, the detection loop
        (Requirement 11.12).
        """
        import queue

        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:  # stop sentinel
                self._queue.task_done()
                break
            try:
                self._process(item)
            except Exception:
                logger.exception("node icon task crashed for %r", item)
                with self._lock:
                    self._failed.add(item)
            finally:
                self._queue.task_done()

    def _process(self, cleaned: str) -> None:
        """Fetch/cache/decode a single node icon (runs on the worker thread)."""
        import os

        basename = cache_filename(cleaned)
        if basename is None:
            self._mark_failed(cleaned)
            return
        cache_path = os.path.join(self._cache_dir, basename)

        # Cache-first: reuse an existing cached file without re-downloading
        # (Requirement 11.5).
        if os.path.exists(cache_path):
            data = self._read_file(cache_path)
            image = self._decode_and_scale(data)
            if image is not None:
                self._store(cleaned, image)
                return
            # Corrupt/undecodable cache file -> fall through to re-download.

        url = build_node_icon_url(cleaned)
        if url is None:
            self._mark_failed(cleaned)
            return

        # Up to MAX_ATTEMPTS tries covering both download and decode failures
        # (Requirement 11.12); each download is bounded by DOWNLOAD_TIMEOUT
        # (Requirement 11.11).
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if self._stop_event.is_set():
                return
            try:
                data = self._download(url)
                image = self._decode_and_scale(data)
                if image is None:
                    raise ValueError("decode produced null image")
                self._write_file(cache_path, data)
                self._store(cleaned, image)
                return
            except Exception as exc:
                logger.warning(
                    "node icon attempt %d/%d failed for %s: %s",
                    attempt, MAX_ATTEMPTS, cleaned, exc,
                )

        # All attempts exhausted -> log an error and abandon the node; future
        # get_pixmap calls return None so the caller keeps using qzx_04.
        logger.error("giving up node icon after %d attempts: %s", MAX_ATTEMPTS, cleaned)
        self._mark_failed(cleaned)

    def _download(self, url: str) -> bytes:
        """Download ``url`` with a 10s timeout, returning the raw bytes.

        Prefers ``requests`` when available, else falls back to the stdlib
        ``urllib``. Import is deferred so the module stays network-free at
        import time. Requirement 11.11.
        """
        try:
            import requests  # type: ignore

            resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except ImportError:
            import urllib.request

            req = urllib.request.Request(
                url, headers={"User-Agent": "ok-ww-NodeIconCache/1.0"}
            )
            with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
                return resp.read()

    def _decode_and_scale(self, data):
        """Decode webp ``data`` to a QImage scaled to ``icon_size``.

        Tries Qt's built-in image reader first (webp via the imageformats
        plugin) and falls back to Pillow -> RGBA -> QImage. Returns ``None`` on
        any failure. Runs on the worker thread; QImage (unlike QPixmap) is safe
        to construct off the GUI thread. Requirement 11.10.
        """
        if not data:
            return None
        image = self._decode_qt(data)
        if image is None:
            image = self._decode_pillow(data)
        if image is None or image.isNull():
            return None
        return self._scale(image)

    def _decode_qt(self, data):
        try:
            from PySide6.QtGui import QImage

            image = QImage()
            if image.loadFromData(bytes(data)) and not image.isNull():
                return image
        except Exception:
            logger.exception("Qt webp decode failed")
        return None

    def _decode_pillow(self, data):
        try:
            import io

            from PIL import Image
            from PySide6.QtGui import QImage

            with Image.open(io.BytesIO(data)) as pil_img:
                rgba = pil_img.convert("RGBA")
            width, height = rgba.size
            raw = rgba.tobytes("raw", "RGBA")
            # ``.copy()`` detaches the QImage from the temporary ``raw`` buffer.
            image = QImage(raw, width, height, QImage.Format_RGBA8888).copy()
            if image.isNull():
                return None
            return image
        except Exception:
            logger.exception("Pillow webp decode failed")
            return None

    def _scale(self, image):
        try:
            from PySide6.QtCore import Qt

            return image.scaled(
                self._icon_size,
                self._icon_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        except Exception:
            logger.exception("icon scale failed")
            return None

    @staticmethod
    def _read_file(path: str):
        try:
            with open(path, "rb") as fh:
                return fh.read()
        except OSError:
            logger.exception("failed to read cached node icon %s", path)
            return None

    @staticmethod
    def _write_file(path: str, data: bytes) -> None:
        try:
            with open(path, "wb") as fh:
                fh.write(data)
        except OSError:
            logger.exception("failed to write node icon cache %s", path)

    def _store(self, cleaned: str, image) -> None:
        with self._lock:
            self._ready[cleaned] = image
            self._inflight.discard(cleaned)

    def _mark_failed(self, cleaned: str) -> None:
        with self._lock:
            self._failed.add(cleaned)
            self._inflight.discard(cleaned)
