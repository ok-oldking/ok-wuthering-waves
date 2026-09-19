import base64
import io
import json
from pathlib import Path

from ok import WebCustomTab, WebTabConfig, task_tab_action, task_tab_query
from PIL import Image

from src.char.CharFactory import char_dict
from src.char.CustomCharLoader import (
    has_custom_char_code,
    is_custom_char_enabled,
    load_custom_char_class,
    read_builtin_char_code,
    read_custom_or_builtin_char_code,
    remove_custom_char_code,
    save_custom_char_code,
    set_custom_char_enabled,
)


BASE_CHAR_URL = "https://raw.githubusercontent.com/ok-oldking/ok-wuthering-waves/refs/heads/master/src/char/BaseChar.py"
CONTRIBUTE_CHAR_URL = "https://github.com/ok-oldking/ok-wuthering-waves/edit/master/src/char/{class_name}.py"
CHARACTER_DISPLAY_NAMES = {
    "LuukHerssen": "Luuk Herssen",
    "XiangliYao": "Xiangli Yao",
    "YangyangXuanling": "Yangyang: Xuanling",
}


class CharacterCodeTask(WebCustomTab):
    """Task-backed API for the Character Code browser tab.

    The existing Qt CharacterCodeTab remains independent. This task exposes
    the same persistence and live-reload behavior without using the executor
    directly; task discovery goes through BaseTask.get_tasks().
    """

    web_tab = WebTabConfig(
        id="character-code",
        name="Character Code",
        icon="code",
        asset_dir=Path(__file__).resolve().parents[1] / "web" / "character_code",
        add_after_default_tabs=True,
        task_controls=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Character Code"
        self._char_feature_index = None
        self._char_feature_images = {}

    def _characters_by_name(self):
        characters = {}
        label_by_class = {}
        for label, info in char_dict.items():
            char_cls = info.get("cls")
            if char_cls is None:
                continue
            characters[char_cls.__name__] = char_cls
            label_by_class.setdefault(char_cls.__name__, getattr(label, "value", label))
        return characters, label_by_class

    def _character_class(self, class_name):
        characters, _labels = self._characters_by_name()
        char_cls = characters.get(str(class_name or ""))
        if char_cls is None:
            raise ValueError(f"Unknown character: {class_name}")
        return char_cls

    def _character_payload(self, char_cls):
        builtin_code = read_builtin_char_code(char_cls)
        has_custom = has_custom_char_code(char_cls)
        use_custom = has_custom and is_custom_char_enabled(char_cls)
        return {
            "class_name": char_cls.__name__,
            "display_name": CHARACTER_DISPLAY_NAMES.get(char_cls.__name__, char_cls.__name__),
            "has_custom": has_custom,
            "use_custom": use_custom,
            "builtin_code": builtin_code,
            "custom_code": read_custom_or_builtin_char_code(char_cls),
            "code": read_custom_or_builtin_char_code(char_cls) if use_custom else builtin_code,
            "image_data_url": self._character_image_data_url(char_cls),
            "base_char_url": BASE_CHAR_URL,
            "contribute_url": CONTRIBUTE_CHAR_URL.format(class_name=char_cls.__name__),
        }

    def _load_char_feature_index(self):
        feature_index = {}
        coco_path = Path(__file__).resolve().parents[2] / "assets" / "coco_annotations.json"
        if not coco_path.is_file():
            return feature_index
        try:
            data = json.loads(coco_path.read_text(encoding="utf-8"))
            image_by_id = {
                image["id"]: image["file_name"]
                for image in data.get("images", [])
            }
            category_by_id = {
                category["id"]: category["name"]
                for category in data.get("categories", [])
            }
            for annotation in data.get("annotations", []):
                category_name = category_by_id.get(annotation.get("category_id"))
                image_name = image_by_id.get(annotation.get("image_id"))
                bbox = annotation.get("bbox", [])
                if category_name and image_name and len(bbox) == 4:
                    feature_index[category_name] = (
                        coco_path.parent / image_name,
                        tuple(round(value) for value in bbox),
                    )
        except (OSError, TypeError, ValueError, KeyError) as error:
            self.logger.error(f"load char feature image index failed: {error}")
        return feature_index

    def _character_image_data_url(self, char_cls):
        class_name = char_cls.__name__
        if class_name in self._char_feature_images:
            return self._char_feature_images[class_name]
        if self._char_feature_index is None:
            self._char_feature_index = self._load_char_feature_index()
        _characters, label_by_class = self._characters_by_name()
        image_info = self._char_feature_index.get(label_by_class.get(class_name))
        if image_info is None:
            self._char_feature_images[class_name] = None
            return None
        image_path, (x, y, width, height) = image_info
        try:
            with Image.open(image_path) as source:
                image = source.crop((x, y, x + width, y + height))
                image.thumbnail((48, 48), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                image.save(output, format="PNG")
            data_url = "data:image/png;base64," + base64.b64encode(
                output.getvalue()
            ).decode("ascii")
        except (OSError, ValueError) as error:
            self.logger.error(f"load character image failed for {class_name}: {error}")
            data_url = None
        self._char_feature_images[class_name] = data_url
        return data_url

    @task_tab_query("characters")
    def characters(self):
        characters, label_by_class = self._characters_by_name()
        result = []
        for class_name, char_cls in characters.items():
            result.append({
                "class_name": class_name,
                "display_name": CHARACTER_DISPLAY_NAMES.get(class_name, class_name),
                "label_name": label_by_class.get(class_name, ""),
                "has_custom": has_custom_char_code(char_cls),
                "use_custom": (
                    has_custom_char_code(char_cls)
                    and is_custom_char_enabled(char_cls)
                ),
            })
        result.sort(key=lambda item: (not item["has_custom"], item["display_name"].lower()))
        return result

    @task_tab_query("character")
    def character(self, payload):
        return self._character_payload(
            self._character_class(payload.get("class_name"))
        )

    @task_tab_action("mode")
    def set_mode(self, payload):
        char_cls = self._character_class(payload.get("class_name"))
        use_custom = bool(payload.get("use_custom"))
        if use_custom and not has_custom_char_code(char_cls):
            raise ValueError("Save custom code before enabling custom mode")
        set_custom_char_enabled(char_cls, use_custom)
        result = self._character_payload(char_cls)
        self.emit_web_event("character-changed", result)
        return result

    @task_tab_action("save")
    def save(self, payload):
        char_cls = self._character_class(payload.get("class_name"))
        code = payload.get("code")
        if not isinstance(code, str):
            raise ValueError("Character code must be text")
        builtin_code = read_builtin_char_code(char_cls)
        if code == builtin_code:
            remove_custom_char_code(char_cls)
            reloaded = self._reload_live_char_code(char_cls)
            message = "Custom code matches built in code. Removed custom code and switched to built in."
        else:
            save_custom_char_code(char_cls, code, use_custom=True)
            reloaded = self._reload_live_char_code(char_cls)
            message = "Custom character code saved and reloaded."
        result = self._character_payload(char_cls)
        result.update({"message": message, "reloaded": reloaded})
        self.emit_web_event("character-changed", result)
        return result

    @task_tab_action("reset")
    def reset(self, payload):
        char_cls = self._character_class(payload.get("class_name"))
        remove_custom_char_code(char_cls)
        reloaded = self._reload_live_char_code(char_cls)
        result = self._character_payload(char_cls)
        result.update({
            "message": "Custom code reset to built in code.",
            "reloaded": reloaded,
        })
        self.emit_web_event("character-changed", result)
        return result

    def _reload_live_char_code(self, char_cls):
        new_cls = load_custom_char_class(char_cls)
        reloaded = 0
        for task in self.get_tasks():
            chars = getattr(task, "chars", None)
            if not chars:
                continue
            for index, char in enumerate(chars):
                if char is None or not isinstance(char, char_cls) or type(char) is new_cls:
                    continue
                replacement = new_cls(
                    task,
                    char.index,
                    char_name=char.char_name,
                    confidence=char.confidence,
                    ring_index=char.ring_index,
                    char_type=char.char_type,
                    buff_time=char.buff_time,
                )
                replacement.is_current_char = char.is_current_char
                replacement.has_intro = char.has_intro
                replacement.has_sub_dps_intro = char.has_sub_dps_intro
                replacement.last_switch_time = char.last_switch_time
                replacement.last_switch_in_time = char.last_switch_in_time
                replacement.last_res = char.last_res
                replacement.last_echo = char.last_echo
                replacement.last_liberation = char.last_liberation
                replacement.last_buff_time = char.last_buff_time
                chars[index] = replacement
                reloaded += 1
        return reloaded
