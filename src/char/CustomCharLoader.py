import importlib.util
import inspect
import json
from pathlib import Path

from ok import Logger
from ok.util.config import Config

logger = Logger.get_logger(__name__)

CUSTOM_CHAR_FOLDER = "custom_chars"
CUSTOM_CHAR_MODES_FILE = "custom_chars.json"

_custom_class_cache = {}


def get_custom_char_folder(create=False):
    folder = Path(Config.config_folder) / CUSTOM_CHAR_FOLDER
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_custom_char_modes_file():
    return get_custom_char_folder(create=True) / CUSTOM_CHAR_MODES_FILE


def get_custom_char_file(char_cls_or_name):
    class_name = _get_class_name(char_cls_or_name)
    return get_custom_char_folder(create=True) / f"{class_name}.py"


def _get_class_name(char_cls_or_name):
    if isinstance(char_cls_or_name, str):
        return char_cls_or_name
    return char_cls_or_name.__name__


def load_custom_char_modes():
    path = get_custom_char_modes_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"load custom char modes failed: {e}")
        return {}
    return data if isinstance(data, dict) else {}


def save_custom_char_modes(modes):
    path = get_custom_char_modes_file()
    path.write_text(json.dumps(modes, ensure_ascii=False, indent=2), encoding="utf-8")


def is_custom_char_enabled(char_cls_or_name):
    class_name = _get_class_name(char_cls_or_name)
    return bool(load_custom_char_modes().get(class_name, {}).get("use_custom"))


def set_custom_char_enabled(char_cls_or_name, enabled):
    class_name = _get_class_name(char_cls_or_name)
    modes = load_custom_char_modes()
    modes.setdefault(class_name, {})["use_custom"] = bool(enabled)
    save_custom_char_modes(modes)
    clear_custom_char_cache(class_name)


def has_custom_char_code(char_cls_or_name):
    return get_custom_char_file(char_cls_or_name).exists()


def remove_custom_char_code(char_cls_or_name):
    path = get_custom_char_file(char_cls_or_name)
    path.unlink(missing_ok=True)
    set_custom_char_enabled(char_cls_or_name, False)
    return path


def read_builtin_char_code(char_cls):
    path = inspect.getsourcefile(char_cls)
    if not path:
        raise RuntimeError(f"Cannot find source file for {char_cls.__name__}")
    return Path(path).read_text(encoding="utf-8")


def read_custom_or_builtin_char_code(char_cls):
    path = get_custom_char_file(char_cls)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return read_builtin_char_code(char_cls)


def save_custom_char_code(char_cls, code, use_custom=True):
    path = get_custom_char_file(char_cls)
    old_code = path.read_text(encoding="utf-8") if path.exists() else None
    old_enabled = is_custom_char_enabled(char_cls)
    compile(code, str(path), "exec")
    try:
        path.write_text(code, encoding="utf-8")
        clear_custom_char_cache(char_cls)
        if use_custom:
            _load_custom_char_class_from_file(char_cls, path)
        set_custom_char_enabled(char_cls, use_custom)
    except Exception:
        if old_code is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(old_code, encoding="utf-8")
        set_custom_char_enabled(char_cls, old_enabled)
        raise
    return path


def clear_custom_char_cache(char_cls_or_name=None):
    if char_cls_or_name is None:
        _custom_class_cache.clear()
    else:
        _custom_class_cache.pop(_get_class_name(char_cls_or_name), None)


def load_custom_char_class(char_cls):
    if not is_custom_char_enabled(char_cls):
        return char_cls

    path = get_custom_char_file(char_cls)
    if not path.exists():
        return char_cls

    try:
        return _load_custom_char_class_from_file(char_cls, path)
    except Exception as e:
        logger.error(f"load custom char class failed for {char_cls.__name__}: {e}")
        clear_custom_char_cache(char_cls)
        return char_cls


def _load_custom_char_class_from_file(char_cls, path):
    cache_key = char_cls.__name__
    stat = path.stat()
    cached = _custom_class_cache.get(cache_key)
    if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]

    module_name = f"ok_ww_custom_char_{char_cls.__name__}_{stat.st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load custom char module: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    custom_cls = getattr(module, char_cls.__name__, None)
    if custom_cls is None:
        raise RuntimeError(f"Custom code must define class {char_cls.__name__}")

    from src.char.BaseChar import BaseChar
    if not isinstance(custom_cls, type) or not issubclass(custom_cls, BaseChar):
        raise RuntimeError(f"{char_cls.__name__} must inherit BaseChar")

    _custom_class_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, custom_cls)
    return custom_cls
