import json
import re
import shutil
import threading
import time
from pathlib import Path

from ok import Logger
from ok.util.config import Config

logger = Logger.get_logger(__name__)

TEAM_PRESET_FOLDER_NAME = "team_presets"
PRESET_INDEX_FILE = "index.json"
PRESET_META_FILE = "preset.json"
PRESET_EXPORT_VERSION = 1
TEAM_LOGIC_ERROR_FILE = "team_logic_error.json"


def _safe_folder_name(name):
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", str(name or "")).strip()
    cleaned = cleaned.rstrip(".")
    return cleaned or "preset"


class TeamPresetSlot:
    """一个角色位:对应一支队伍中的某个角色。"""

    def __init__(self, char="", enabled=True, note="", params=None, custom_code="",
                 required=False):
        self.char = char or ""
        self.enabled = bool(enabled)
        self.note = note or ""
        self.params = dict(params or {})
        self.custom_code = custom_code or ""
        self.required = bool(required)

    def to_dict(self):
        return {
            "char": self.char,
            "enabled": self.enabled,
            "note": self.note,
            "params": self.params,
            "custom_code": self.custom_code,
            "required": self.required,
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
            required=data.get("required", False),
        )


class TeamPreset:
    """一套队伍配对配置。"""

    def __init__(self, id=None, name=None, note="", created_from="", auto_match=True,
                 slots=None, description=""):
        self.id = id or ""
        self.name = name or ""
        self.note = note or ""
        self.created_from = created_from or ""
        self.auto_match = bool(auto_match)
        self.slots = slots or []
        self.description = description or ""

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "note": self.note,
            "created_from": self.created_from,
            "auto_match": self.auto_match,
            "description": self.description,
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
            description=data.get("description", ""),
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
            logger.error(f"load team preset index failed ({e}), rebuilding from folders")
            return cls.rebuild_index()
        return data if isinstance(data, dict) else {}

    @classmethod
    def _save_index(cls, index):
        cls._index_path().write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def rebuild_index(cls):
        """从每个预设文件夹里的 preset.json 重建索引(保留 active / 匹配状态)。

        用于 index.json 丢失或损坏时找回预设;返回重建后的索引 dict。
        """
        folder = cls._folder(create=True)
        presets = []
        for child in sorted(folder.iterdir()):
            meta = child / PRESET_META_FILE
            if not meta.is_file():
                continue
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"rebuild index: skip broken preset meta {child.name}: {e}")
                continue
            if not isinstance(data, dict) or not data.get("id"):
                continue
            data["id"] = _safe_folder_name(data["id"])
            if data["id"] != child.name:
                data["id"] = child.name
            presets.append(data)
        old = {}
        try:
            old = json.loads(cls._index_path().read_text(encoding="utf-8"))
        except Exception:
            pass
        if not isinstance(old, dict):
            old = {}
        old["presets"] = presets
        cls._save_index(old)
        logger.info(f'rebuilt team preset index from folders: {len(presets)} presets')
        return old

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
    def get_last_match_attempts(cls):
        """最近一次自动匹配对每个预设的评分结果(供日志/GUI 排查)。"""
        return cls._load_index().get("last_match_attempts", []) or []

    @classmethod
    def record_match_attempts(cls, attempts):
        try:
            with cls._lock:
                index = cls._load_index()
                index["last_match_attempts"] = attempts or []
                cls._save_index(index)
        except Exception as e:
            logger.debug(f"record match attempts failed: {e}")

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
    def _preset_match(cls, preset, team):
        """计算预设与队伍的匹配结果。

        Returns:
            (score, missing_required, hit_names):
                score: 命中启用角色数 / 启用角色数(0 表示不匹配)。
                missing_required: 队伍里缺失的必选角色(非空则不匹配)。
                hit_names: 命中的角色名。
        """
        enabled = [slot for slot in preset.slots if slot.enabled and slot.char]
        if not enabled:
            return 0.0, [], []
        team = {str(c) for c in (team or []) if c}
        missing_required = [slot.char for slot in enabled if slot.required and slot.char not in team]
        if missing_required:
            return 0.0, missing_required, []
        hit_names = [slot.char for slot in enabled if slot.char in team]
        return len(hit_names) / len(enabled), [], hit_names

    @classmethod
    def resolve_preset_for_team(cls, char_names, use_forced=True):
        """选一个适用于检测到的队伍角色的预设。

        强制预设优先(如果存在且未卸载);否则按"匹配分数"选最优:
        分数 = 命中启用角色数 / 启用角色数,全匹配(1.0)优先于子集匹配;
        同分时按列表顺序(即预设优先级)。必选(required)角色不在队伍中则不匹配。
        每次都会记录匹配详情(供日志与 GUI 排查)。
        """
        if use_forced:
            forced = cls.get_forced_preset()
            if forced is not None:
                return forced
        team = [str(c) for c in (char_names or []) if c]
        attempts = []
        best = None
        best_score = 0.0
        for preset in cls.list_presets():
            if not preset.auto_match:
                continue
            score, missing_required, hit_names = cls._preset_match(preset, team)
            attempts.append({
                "preset": preset.name or preset.id,
                "score": score,
                "missing_required": missing_required,
                "hits": hit_names,
            })
            if score <= 0 or score < best_score:
                continue
            if score > best_score:
                best = preset
                best_score = score
        cls.record_match_attempts(attempts)
        return best

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
    def _save_meta(cls, preset):
        """把预设元数据落盘到自己的文件夹,供索引重建兜底。"""
        path = cls._preset_folder(preset.id, create=True) / PRESET_META_FILE
        try:
            path.write_text(json.dumps(preset.to_dict(), ensure_ascii=False, indent=2),
                            encoding="utf-8")
        except Exception as e:
            logger.warning(f"save preset meta failed for {preset.id}: {e}")

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
        cls._save_meta(preset)
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
        cls._save_meta(preset)
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

    # ---------- 队伍级出招逻辑代码 ----------

    @classmethod
    def get_team_code_path(cls, preset_id):
        return cls._preset_folder(preset_id, create=True) / "team_code.py"

    @classmethod
    def has_team_code(cls, preset_id):
        return cls.get_team_code_path(preset_id).exists()

    @classmethod
    def read_team_code(cls, preset_id):
        path = cls.get_team_code_path(preset_id)
        return path.read_text(encoding="utf-8") if path.exists() else None

    @classmethod
    def save_team_code(cls, preset_id, code):
        path = cls.get_team_code_path(preset_id)
        compile(code, str(path), "exec")
        path.write_text(code, encoding="utf-8")
        _clear_team_logic_cache(preset_id)
        return path

    @classmethod
    def remove_team_code(cls, preset_id):
        path = cls.get_team_code_path(preset_id)
        path.unlink(missing_ok=True)
        _clear_team_logic_cache(preset_id)

    # ---------- 队伍逻辑运行错误记录 ----------

    @classmethod
    def get_team_logic_error_path(cls, preset_id):
        return cls._preset_folder(preset_id, create=True) / TEAM_LOGIC_ERROR_FILE

    @classmethod
    def record_team_logic_error(cls, preset_id, message):
        """记录某预设队伍逻辑的运行错误;message 为空则清除。"""
        path = cls.get_team_logic_error_path(preset_id)
        if not message:
            path.unlink(missing_ok=True)
            return
        data = {"preset_id": preset_id, "message": str(message)[:300], "time": time.time()}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def get_last_team_logic_error(cls):
        """读取当前生效预设(强制优先,否则最近自动匹配)的错误记录;无则 None。"""
        for candidate in (cls.get_forced_name(),
                          cls._load_index().get("last_auto_match", "") or ""):
            if not candidate:
                continue
            path = cls._preset_folder(candidate) / TEAM_LOGIC_ERROR_FILE
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.error(f"load team logic error failed: {e}")
                    return None
        return None

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
        team_code_error = None
        folder = cls._preset_folder(preset_id)
        if folder.exists():
            for py in folder.glob("*.py"):
                text = py.read_text(encoding="utf-8")
                custom_code[py.name] = text
                if py.name == "team_code.py":
                    try:
                        compile(text, str(py), "exec")
                    except Exception as e:
                        team_code_error = str(e)
        return {
            "type": "ok_ww_team_preset",
            "version": PRESET_EXPORT_VERSION,
            "preset": preset.to_dict(),
            "custom_code": custom_code,
            "team_code_error": team_code_error,
            "description": preset.description,
        }

    @classmethod
    def export_preset_to_file(cls, preset_id, path):
        data = cls.export_preset(preset_id)
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8")
        return data

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
            stem = _safe_folder_name(Path(filename).stem)
            if not stem:
                continue
            if filename == "team_code.py":
                try:
                    cls.save_team_code(preset.id, code)
                except Exception as e:
                    logger.warning(
                        f"import team code failed for {preset.id}: {e}, saving raw code")
                    cls.get_team_code_path(preset.id).write_text(code, encoding="utf-8")
            else:
                cls.save_custom_code(preset.id, stem, code)
        return preset

    @classmethod
    def import_preset_from_file(cls, path):
        path = Path(path)
        return cls.import_preset(json.loads(path.read_text(encoding="utf-8")))

    # ---------- 内置模板 ----------
    # 约定:仓库根目录 presets/<模板名>/ 下放 preset.json(与导出的数据格式一致,
    # 可选顶层 "description"),同目录的 *.py 会被打包为 custom_code(开发者直接
    # 写文件即可分发,无需手工嵌进 JSON)。

    @classmethod
    def builtin_templates_folder(cls):
        return Path(__file__).resolve().parents[2] / "presets"

    @classmethod
    def list_builtin_templates(cls):
        """扫描内置模板,返回 [{"folder", "name", "description"}, ...]。"""
        folder = cls.builtin_templates_folder()
        if not folder.is_dir():
            return []
        templates = []
        for child in sorted(folder.iterdir()):
            preset_file = child / "preset.json"
            if not preset_file.is_file():
                continue
            try:
                data = json.loads(preset_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"load builtin template {child.name} failed: {e}")
                continue
            if not isinstance(data, dict):
                continue
            preset_data = data.get("preset", data) or {}
            name = preset_data.get("name") or child.name
            description = data.get("description") or preset_data.get("description") or ""
            templates.append({
                "folder": child.name,
                "name": str(name),
                "description": str(description),
            })
        return templates

    @classmethod
    def install_builtin_template(cls, folder_name):
        """安装内置模板为一个新预设(可重复安装,自动去重 id)。返回新预设。"""
        folder = cls.builtin_templates_folder() / folder_name
        preset_file = folder / "preset.json"
        data = json.loads(preset_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"invalid builtin template: {folder_name}")
        custom_code = dict(data.get("custom_code", {}) or {})
        if not custom_code:
            for py in sorted(folder.glob("*.py")):
                custom_code[py.name] = py.read_text(encoding="utf-8")
        data["custom_code"] = custom_code
        return cls.import_preset(data)


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


def _clear_team_logic_cache(preset_id):
    from src.team_preset.TeamLogicLoader import clear_team_logic_cache
    clear_team_logic_cache(preset_id)