import ast
import importlib.util
import inspect
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from ok import Logger
from ok.util.config import Config

logger = Logger.get_logger(__name__)

CUSTOM_CHAR_FOLDER = "custom_chars"
CUSTOM_CHAR_MODES_FILE = "custom_chars.json"
CUSTOM_TEAM_FOLDER = "custom_teams"
TEAM_MANIFEST_FILE = "team.json"

CHARACTER_DISPLAY_NAMES = {
    "Douling": "Buling",
    "Xigelika": "Sigrika",
    "Linnai": "Lynae",
    "Luhesi": "Luuk Herssen",
    "Xiangliyao": "Xiangli Yao",
    "ShoreKeeper": "Shorekeeper",
    "HavocRover": "Rover",
    "YangYangSp": "Yangyang: Xuanling",
}

_custom_class_cache = {}
_team_class_cache = {}


def get_english_char_name(char_cls_or_name):
    class_name = _get_class_name(char_cls_or_name)
    return CHARACTER_DISPLAY_NAMES.get(class_name, class_name)


def normalize_team(team):
    class_names = sorted({_get_class_name(char) for char in team}, key=str.casefold)
    if len(class_names) != 3:
        raise ValueError("A team must contain 3 different characters")
    return tuple(class_names)


def get_team_key(team):
    return "__".join(normalize_team(team))


def get_custom_team_root(create=False):
    folder = Path(Config.config_folder) / CUSTOM_TEAM_FOLDER
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_custom_team_folder(team, create=False):
    folder = get_custom_team_root(create=create) / get_team_key(team)
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_team_char_file(team, char_cls_or_name):
    class_name = _get_class_name(char_cls_or_name)
    if class_name not in normalize_team(team):
        raise ValueError(f"{class_name} is not in this team")
    return get_custom_team_folder(team) / f"{class_name}.py"


def _default_team_manifest(team):
    english_names = sorted((get_english_char_name(name) for name in normalize_team(team)), key=str.casefold)
    return {
        "name": ", ".join(english_names),
        "description": "",
        "author": "",
        "version": "",
        "team": ", ".join(english_names),
    }


def create_custom_team(team):
    class_names = normalize_team(team)
    folder = get_custom_team_folder(class_names)
    if folder.exists():
        raise ValueError("This team already exists")
    classes = _registered_char_classes()
    missing = [name for name in class_names if name not in classes]
    if missing:
        raise ValueError(f"Unknown character: {missing[0]}")
    folder.mkdir(parents=True)
    try:
        for class_name in class_names:
            (folder / f"{class_name}.py").write_text(
                read_builtin_char_code(classes[class_name]), encoding="utf-8"
            )
        (folder / TEAM_MANIFEST_FILE).write_text(
            json.dumps(_default_team_manifest(class_names), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    clear_team_char_cache(class_names)
    return folder


def delete_custom_team(team):
    class_names = normalize_team(team)
    folder = get_custom_team_folder(class_names)
    if not folder.is_dir():
        raise ValueError("Team does not exist")
    shutil.rmtree(folder)
    clear_team_char_cache(class_names)
    return folder


def list_custom_teams():
    root = get_custom_team_root()
    try:
        if not root.exists():
            return []
        folders = list(root.iterdir())
    except OSError as e:
        logger.warning(f"list custom teams failed for {root}: {e}")
        return []
    teams = []
    for folder in folders:
        try:
            if not folder.is_dir():
                continue
            class_names = tuple(folder.name.split("__"))
            class_names = normalize_team(class_names)
            if all((folder / f"{name}.py").is_file() for name in class_names):
                teams.append(class_names)
        except ValueError:
            continue
        except OSError as e:
            logger.warning(f"skip unreadable custom team folder {folder}: {e}")
    return sorted(teams, key=lambda team: tuple(name.casefold() for name in team))


def read_team_char_code(team, char_cls):
    path = get_team_char_file(team, char_cls)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return read_builtin_char_code(char_cls)


def save_team_char_code(team, char_cls, code):
    class_names = normalize_team(team)
    class_name = _get_class_name(char_cls)
    if class_name not in class_names:
        raise ValueError(f"{class_name} is not in this team")
    path = get_team_char_file(class_names, class_name)
    _validate_character_code(code, class_name, path)
    old_code = path.read_text(encoding="utf-8") if path.exists() else None
    try:
        path.write_text(code, encoding="utf-8")
        clear_team_char_cache(class_names, class_name)
        _load_team_char_class_from_file(char_cls, class_names, path)
    except Exception:
        if old_code is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(old_code, encoding="utf-8")
        clear_team_char_cache(class_names, class_name)
        raise
    return path


def clear_team_char_cache(team=None, char_cls_or_name=None):
    if team is None:
        _team_class_cache.clear()
        return
    team_key = get_team_key(team)
    if char_cls_or_name is None:
        for key in [key for key in _team_class_cache if key[0] == team_key]:
            _team_class_cache.pop(key, None)
    else:
        _team_class_cache.pop((team_key, _get_class_name(char_cls_or_name)), None)


def load_team_char_class(char_cls, team):
    class_names = normalize_team(team)
    if char_cls.__name__ not in class_names:
        return char_cls
    path = get_custom_team_folder(class_names) / f"{char_cls.__name__}.py"
    if not path.exists():
        return char_cls
    try:
        if path.read_text(encoding="utf-8") == read_builtin_char_code(char_cls):
            return char_cls
        return _load_team_char_class_from_file(char_cls, class_names, path)
    except Exception as e:
        logger.error(f"load team character class failed for {char_cls.__name__}: {e}")
        clear_team_char_cache(class_names, char_cls)
        return char_cls


def _load_team_char_class_from_file(char_cls, team, path):
    team_key = get_team_key(team)
    cache_key = (team_key, char_cls.__name__)
    stat = path.stat()
    cached = _team_class_cache.get(cache_key)
    if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]
    custom_cls = _load_class_from_file(
        char_cls, path, f"ok_ww_team_{team_key}_{char_cls.__name__}_{stat.st_mtime_ns}"
    )
    _team_class_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, custom_cls)
    return custom_cls


def export_custom_team(team, destination, name, description, author, version):
    class_names = normalize_team(team)
    values = {"name": name, "description": description, "author": author, "version": version}
    for field, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field.title()} is required")
        values[field] = value.strip()
    folder = get_custom_team_folder(class_names)
    if not folder.is_dir():
        raise ValueError("Team does not exist")
    normalized_name = re.sub(r"\s+", "_", values["name"])
    manifest = dict(values)
    manifest["name"] = normalized_name
    manifest["team"] = ", ".join(sorted(
        (get_english_char_name(class_name) for class_name in class_names), key=str.casefold
    ))
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[<>:"/\\|?*]+', "_", normalized_name).strip(" .") or "team"
    safe_author = re.sub(r'[<>:"/\\|?*\s]+', "_", values["author"]).strip(" .") or "author"
    safe_version = re.sub(r'[<>:"/\\|?*]+', "_", values["version"]).strip(" .") or "version"
    archive_path = destination / f"{safe_name}_{safe_author}_{safe_version}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(TEAM_MANIFEST_FILE, json.dumps(manifest, ensure_ascii=False, indent=2))
        for class_name in class_names:
            code_path = folder / f"{class_name}.py"
            if not code_path.is_file():
                raise ValueError(f"Missing code for {get_english_char_name(class_name)}")
            archive.write(code_path, f"{class_name}.py")
    return archive_path


def inspect_team_archive(archive_path):
    archive_path = Path(archive_path)
    if not archive_path.is_file() or not zipfile.is_zipfile(archive_path):
        raise ValueError("Please select a valid zip file")
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if any(Path(name).name != name or name.startswith(("/", "\\")) for name in names):
            raise ValueError("Archive contains invalid paths")
        if TEAM_MANIFEST_FILE not in names:
            raise ValueError("Archive is missing team.json")
        if any(info.file_size > 2_000_000 for info in archive.infolist()):
            raise ValueError("Archive contains an oversized file")
        try:
            manifest = json.loads(archive.read(TEAM_MANIFEST_FILE).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError("team.json is not valid JSON") from e
        for field in ("name", "description", "author", "version", "team"):
            if not isinstance(manifest.get(field), str) or not manifest[field].strip():
                raise ValueError(f"team.json requires a non-empty {field}")
        english_names = [name.strip() for name in manifest["team"].split(",") if name.strip()]
        if english_names != sorted(english_names, key=str.casefold):
            raise ValueError("Team names must be ordered alphabetically")
        classes_by_english = {
            get_english_char_name(char_cls): char_cls for char_cls in _registered_char_classes().values()
        }
        try:
            char_classes = [classes_by_english[name] for name in english_names]
        except KeyError as e:
            raise ValueError(f"Unknown character: {e.args[0]}") from e
        class_names = normalize_team(char_classes)
        codes = {}
        expected = {TEAM_MANIFEST_FILE, *(f"{name}.py" for name in class_names)}
        if set(names) != expected:
            raise ValueError("Archive must contain team.json and exactly the team's 3 Python files")
        for class_name in class_names:
            try:
                code = archive.read(f"{class_name}.py").decode("utf-8")
            except UnicodeDecodeError as e:
                raise ValueError(f"{class_name}.py must be UTF-8") from e
            # Zip entries commonly use CRLF. Normalize before write_text() performs
            # the platform's newline conversion, otherwise Windows creates CRCRLF.
            code = code.replace("\r\n", "\n").replace("\r", "\n")
            _validate_character_code(code, class_name, f"{class_name}.py")
            codes[class_name] = code
    return {"manifest": manifest, "team": class_names, "codes": codes}


def import_custom_team(archive_info):
    class_names = normalize_team(archive_info["team"])
    codes = archive_info["codes"]
    folder = get_custom_team_folder(class_names)
    parent = get_custom_team_root(create=True)
    temp_folder = Path(tempfile.mkdtemp(prefix=f".{get_team_key(class_names)}-", dir=parent))
    try:
        for class_name in class_names:
            code = codes[class_name]
            _validate_character_code(code, class_name, f"{class_name}.py")
            (temp_folder / f"{class_name}.py").write_text(code, encoding="utf-8")
        (temp_folder / TEAM_MANIFEST_FILE).write_text(
            json.dumps(archive_info["manifest"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        backup = folder.with_name(folder.name + ".backup")
        if backup.exists():
            shutil.rmtree(backup)
        if folder.exists():
            folder.rename(backup)
        try:
            temp_folder.rename(folder)
        except Exception:
            if backup.exists():
                backup.rename(folder)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temp_folder.exists():
            shutil.rmtree(temp_folder, ignore_errors=True)
    clear_team_char_cache(class_names)
    return folder


def _registered_char_classes():
    from src.char.CharFactory import char_dict
    return {info["cls"].__name__: info["cls"] for info in char_dict.values()}


def _validate_character_code(code, class_name, path):
    if not isinstance(code, str):
        raise ValueError("Character code must be text")
    tree = ast.parse(code, filename=str(path))
    if not any(isinstance(node, ast.ClassDef) and node.name == class_name for node in tree.body):
        raise RuntimeError(f"Custom code must define class {class_name}")
    compile(tree, str(path), "exec")


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
    custom_cls = _load_class_from_file(char_cls, path, module_name)

    _custom_class_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, custom_cls)
    return custom_cls


def _load_class_from_file(char_cls, path, module_name):
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

    return custom_cls
