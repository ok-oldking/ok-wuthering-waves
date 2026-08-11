import json
import re
import shutil
import threading
from pathlib import Path

from ok import Logger
from ok.util.config import Config

logger = Logger.get_logger(__name__)

TEAM_PRESET_FOLDER_NAME = "team_presets"
PRESET_INDEX_FILE = "index.json"
PRESET_EXPORT_VERSION = 1


def _safe_folder_name(name):
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", str(name or "")).strip()
    cleaned = cleaned.rstrip(".")
    return cleaned or "preset"


class TeamPresetSlot:
    """一个角色位:对应一支队伍中的某个角色。"""

    def __init__(self, char="", enabled=True, note="", params=None, custom_code=""):
        self.char = char or ""
        self.enabled = bool(enabled)
        self.note = note or ""
        self.params = dict(params or {})
        self.custom_code = custom_code or ""

    def to_dict(self):
        return {
            "char": self.char,
            "enabled": self.enabled,
            "note": self.note,
            "params": self.params,
            "custom_code": self.custom_code,
        }

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            char=data.get("char", ""),
            enabled=data.get("enabled", True),
            note=data.get("note", ""),
            params=data.get("params", {}) or {},
            custom_code=data.get("custom_code", ""),
        )


class TeamPreset:
    """一套队伍配对配置。"""

    def __init__(self, id=None, name=None, note="", created_from="", auto_match=True, slots=None):
        self.id = id or ""
        self.name = name or ""
        self.note = note or ""
        self.created_from = created_from or ""
        self.auto_match = bool(auto_match)
        self.slots = slots or []

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "note": self.note,
            "created_from": self.created_from,
            "auto_match": self.auto_match,
            "slots": [slot.to_dict() for slot in self.slots],
        }

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        slots = [TeamPresetSlot.from_dict(s) for s in (data.get("slots", []) or [])]
        return cls(
            id=data.get("id", ""),
            name=data.get("name", data.get("id", "")),
            note=data.get("note", ""),
            created_from=data.get("created_from", ""),
            auto_match=data.get("auto_match", True),
            slots=slots,
        )

    @property
    def folder_name(self):
        return _safe_folder_name(self.id)

    def merged_char_config(self):
        """把启用角色的参数合并成运行时的扁平字典(向下兼容 task.char_config)。"""
        merged = {}
        for slot in self.slots:
            if slot.enabled:
                merged.update(slot.params or {})
        return merged

    def get_slot(self, char_name):
        for slot in self.slots:
            if slot.char == char_name:
                return slot
        return None


class TeamPresetStore:
    """team_presets 的持久化与读写。"""

    _lock = threading.Lock()

    # 测试或特殊场景下可指向自定义基目录(默认用 ok 的 config 目录)
    override_folder = None

    # ---------- 路径 ----------

    @classmethod
    def _folder(cls, create=False):
        folder = cls._base_folder() / TEAM_PRESET_FOLDER_NAME
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    @classmethod
    def _base_folder(cls):
        if cls.override_folder:
            return Path(cls.override_folder)
        return Path(Config.config_folder)

    @classmethod
    def _index_path(cls):
        return cls._folder(create=True) / PRESET_INDEX_FILE

    @classmethod
    def _preset_folder(cls, preset_id, create=False):
        folder = cls._folder(create=True) / _safe_folder_name(preset_id)
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    # ---------- 索引读写 ----------

    @classmethod
    def _load_index(cls):
        path = cls._index_path()
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"load team preset index failed: {e}")
            return {}
        return data if isinstance(data, dict) else {}

    @classmethod
    def _save_index(cls, index):
        cls._index_path().write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 强制 / 自动匹配 ----------
    # index 里的 "active" 键语义为"强制使用"的预设,key 保留兼容旧配置。

    @classmethod
    def get_forced_name(cls):
        return cls._load_index().get("active", "") or ""

    @classmethod
    def get_forced_preset(cls):
        forced = cls.get_forced_name()
        if not forced:
            return None
        return cls.get_preset(forced)

    @classmethod
    def set_forced(cls, preset_id):
        with cls._lock:
            index = cls._load_index()
            index["active"] = preset_id or ""
            cls._save_index(index)

    @classmethod
    def get_last_auto_match(cls):
        return cls.get_preset(cls._load_index().get("last_auto_match", "") or "")

    @classmethod
    def record_auto_match(cls, preset_id):
        with cls._lock:
            index = cls._load_index()
            index["last_auto_match"] = preset_id or ""
            cls._save_index(index)

    @classmethod
    def get_last_detected_team(cls):
        return cls._load_index().get("last_detected_team", []) or []

    @classmethod
    def record_detected_team(cls, char_classes):
        with cls._lock:
            index = cls._load_index()
            index["last_detected_team"] = list(char_classes or [])
            cls._save_index(index)

    @classmethod
    def char_names_to_classes(cls, char_names):
        """把角色模板名(如 'char_iuno')映射为角色类名(如 'Iuno'),未知的忽略。"""
        from src.char.CharFactory import char_dict
        result = []
        for name in (char_names or []):
            info = char_dict.get(name)
            if info is not None:
                result.append(info["cls"].__name__)
        return result

    @classmethod
    def resolve_preset_for_team(cls, char_names, use_forced=True):
        """选一个适用于检测到的队伍角色的预设。

        强制预设优先(如果存在且未卸载);否则按列表顺序(即优先级)取第一个
        auto_match 且启用角色全部出现在队伍中的预设。返回预设或 None。
        """
        if use_forced:
            forced = cls.get_forced_preset()
            if forced is not None:
                return forced
        team = {str(c) for c in (char_names or []) if c}
        if not team:
            return None
        for preset in cls.list_presets():
            if not preset.auto_match:
                continue
            needs = {slot.char for slot in preset.slots if slot.enabled and slot.char}
            if needs and needs <= team:
                return preset
        return None

    @classmethod
    def move_preset(cls, preset_id, delta):
        """按列表顺序调整预设优先级:delta=-1 上移, delta=1 下移。"""
        with cls._lock:
            index = cls._load_index()
            presets = index.get("presets", []) or []
            i = next((i for i, p in enumerate(presets) if p.get("id") == preset_id), -1)
            j = i + delta
            if i < 0 or j < 0 or j >= len(presets):
                return False
            presets[i], presets[j] = presets[j], presets[i]
            index["presets"] = presets
            cls._save_index(index)
            return True

    # ---------- 预设 CRUD ----------

    @classmethod
    def _list_preset_entries(cls):
        return cls._load_index().get("presets", []) or []

    @classmethod
    def list_presets(cls):
        return [TeamPreset.from_dict(entry) for entry in cls._list_preset_entries()]

    @classmethod
    def list_preset_ids(cls):
        return {entry.get("id") for entry in cls._list_preset_entries()}

    @classmethod
    def get_preset(cls, preset_id):
        for entry in cls._list_preset_entries():
            if entry.get("id") == preset_id:
                return TeamPreset.from_dict(entry)
        return None

    @classmethod
    def add_preset(cls, preset):
        with cls._lock:
            index = cls._load_index()
            presets = index.get("presets", []) or []
            if any(existing.get("id") == preset.id for existing in presets):
                raise ValueError(f"team preset id already exists: {preset.id}")
            presets.append(preset.to_dict())
            index["presets"] = presets
            cls._save_index(index)
        return preset.id

    @classmethod
    def save_preset(cls, preset):
        if not preset.id:
            raise ValueError("preset id is required")
        with cls._lock:
            index = cls._load_index()
            presets = index.get("presets", []) or []
            for i, existing in enumerate(presets):
                if existing.get("id") == preset.id:
                    presets[i] = preset.to_dict()
                    break
            else:
                presets.append(preset.to_dict())
            index["presets"] = presets
            cls._save_index(index)
        return preset.id

    @classmethod
    def delete_preset(cls, preset_id):
        with cls._lock:
            index = cls._load_index()
            presets = [p for p in index.get("presets", []) or [] if p.get("id") != preset_id]
            index["presets"] = presets
            if index.get("active") == preset_id:
                index["active"] = ""
            if index.get("last_auto_match") == preset_id:
                index["last_auto_match"] = ""
            cls._save_index(index)
        shutil.rmtree(cls._preset_folder(preset_id), ignore_errors=True)

    @classmethod
    def generate_id(cls, name, existing_ids=None):
        existing_ids = existing_ids if existing_ids is not None else cls.list_preset_ids()
        base = _safe_folder_name(name) or "preset"
        candidate = base
        counter = 2
        while candidate in existing_ids:
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    # ---------- 角色位自定义代码 ----------

    @classmethod
    def get_custom_code_path(cls, preset_id, char_name):
        return cls._preset_folder(preset_id, create=True) / f"{_safe_folder_name(char_name)}.py"

    @classmethod
    def has_custom_code(cls, preset_id, char_name):
        return cls.get_custom_code_path(preset_id, char_name).exists()

    @classmethod
    def read_custom_code(cls, preset_id, char_name):
        path = cls.get_custom_code_path(preset_id, char_name)
        return path.read_text(encoding="utf-8") if path.exists() else None

    @classmethod
    def save_custom_code(cls, preset_id, char_name, code):
        path = cls.get_custom_code_path(preset_id, char_name)
        compile(code, str(path), "exec")
        path.write_text(code, encoding="utf-8")
        _clear_char_cache(char_name, preset_id)
        return path

    @classmethod
    def remove_custom_code(cls, preset_id, char_name):
        path = cls.get_custom_code_path(preset_id, char_name)
        path.unlink(missing_ok=True)

    # ---------- 复制 / 创建 ----------

    @classmethod
    def duplicate_preset(cls, preset_id):
        preset = cls.get_preset(preset_id)
        if preset is None:
            raise ValueError(f"preset not found: {preset_id}")
        new_id = cls.generate_id(f"{preset.name} Copy")
        new_preset = TeamPreset(
            id=new_id,
            name=f"{preset.name} Copy",
            note=preset.note,
            created_from=preset.created_from,
            auto_match=preset.auto_match,
            slots=[TeamPresetSlot.from_dict(slot.to_dict()) for slot in preset.slots],
        )
        cls.add_preset(new_preset)
        source_folder = cls._preset_folder(preset_id)
        if source_folder.exists():
            dest_folder = cls._preset_folder(new_id, create=True)
            for source in source_folder.glob("*.py"):
                shutil.copy2(source, dest_folder / source.name)
        return new_preset

    @classmethod
    def create_from_current_config(cls, name):
        """从当前全局 Character Config 与全局自定义角色代码生成一个新配对。"""
        new_id = cls.generate_id(name)
        preset = TeamPreset(id=new_id, name=name, created_from="Character Config")
        slots_by_char = {}

        try:
            current = Config("Character Config", {})
        except Exception as e:
            logger.error(f"read Character Config failed: {e}")
            current = {}

        for key, value in (current or {}).items():
            char_class = _infer_char_class_from_param_key(key)
            slot = slots_by_char.setdefault(char_class or "", TeamPresetSlot(char=char_class or ""))
            slot.params[key] = value

        for cls_ in _enabled_custom_char_classes():
            slot = slots_by_char.setdefault(cls_, TeamPresetSlot(char=cls_))
            slot.custom_code = f"{cls_}.py"
            source = cls._base_folder() / "custom_chars" / f"{cls_}.py"
            if source.exists():
                cls.save_custom_code(new_id, cls_, source.read_text(encoding="utf-8"))

        preset.slots = list(slots_by_char.values())
        cls.add_preset(preset)
        return preset

    # ---------- 导入导出 ----------

    @classmethod
    def export_preset(cls, preset_id):
        preset = cls.get_preset(preset_id)
        if preset is None:
            raise ValueError(f"preset not found: {preset_id}")
        custom_code = {}
        folder = cls._preset_folder(preset_id)
        if folder.exists():
            for py in folder.glob("*.py"):
                custom_code[py.name] = py.read_text(encoding="utf-8")
        return {
            "type": "ok_ww_team_preset",
            "version": PRESET_EXPORT_VERSION,
            "preset": preset.to_dict(),
            "custom_code": custom_code,
        }

    @classmethod
    def export_preset_to_file(cls, preset_id, path):
        Path(path).write_text(
            json.dumps(cls.export_preset(preset_id), ensure_ascii=False, indent=2),
            encoding="utf-8")

    @classmethod
    def import_preset(cls, data):
        if not isinstance(data, dict):
            raise ValueError("invalid preset data")
        if data.get("type") == "ok_ww_team_preset":
            preset_data = data.get("preset", data)
            custom_code = data.get("custom_code", {}) or {}
        else:
            preset_data = data
            custom_code = {}
        preset = TeamPreset.from_dict(preset_data)
        if not preset.id or preset.id in cls.list_preset_ids():
            preset.id = cls.generate_id(preset.name, cls.list_preset_ids())
        cls.add_preset(preset)
        for filename, code in (custom_code or {}).items():
            char_name = _safe_folder_name(Path(filename).stem)
            if char_name:
                cls.save_custom_code(preset.id, char_name, code)
        return preset

    @classmethod
    def import_preset_from_file(cls, path):
        path = Path(path)
        return cls.import_preset(json.loads(path.read_text(encoding="utf-8")))


def _infer_char_from_param_key(key):
    """尽量从参数键推断角色类名(如 'Iuno C6' -> 'Iuno')。"""
    from src.char.CharFactory import char_dict
    key_lower = str(key).lower()
    for info in char_dict.values():
        cls_name = info.get("cls").__name__
        if len(cls_name) >= 2 and key_lower.startswith(cls_name.lower()):
            return cls_name
    return None


def _enabled_custom_char_classes():
    from src.char.CustomCharLoader import load_custom_char_modes
    modes = load_custom_char_modes()
    return [name for name, mode in modes.items()
            if isinstance(mode, dict) and mode.get("use_custom")]


def _clear_char_cache(char_name, preset_id=None):
    from src.char.CustomCharLoader import clear_custom_char_cache
    clear_custom_char_cache(char_name, preset_id=preset_id)