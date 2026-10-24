from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Shared bounded inspection-plan validation; no native imports or input."""
import json
import importlib.util
from pathlib import Path

def config_path(root, name):
    if not isinstance(name, str) or not name or len(name) > 256:
        raise ValueError('Named inventory calibration required')
    base = (Path(root) / 'config').resolve()
    path = (base / name).resolve(strict=True)
    if not path.is_relative_to(base) or path.suffix != '.json' or path.stat().st_size > 1024 * 1024:
        raise ValueError('Inventory configuration outside bounded local config scope')
    return path

def read_calibration(root, name, game):
    from src.inventory_support import inventory_native_probe as module
    return module.load_calibration(config_path(root, name), game)

def read_navigation(root, name, game):
    path = config_path(root, name)
    raw = path.read_bytes()
    value = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('Navigation object required')
    if value.get('schema') == 'native-inventory-version-candidate/v1':
        from src.inventory_support import inventory_version_candidate as module
        return module.resolve(path, value, game, 'navigation', lambda file, selected_game: read_calibration(root, file.name, selected_game))
    import hashlib
    value['_dependency_sha256'] = {str(path): hashlib.sha256(raw).hexdigest()}
    return value

def prepare(root, bridge, navigation, game, selected_ids=None):
    if game not in ('wuwa', 'zzz'):
        raise ValueError('Unsupported native inspection game')
    path = config_path(root, game + '-inventory-task-plan.json')
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict) or value.get('schema') != 'inventory-inspection-plan/v1' or value.get('game') != game or (value.get('ready') is not True) or (type(value.get('budget_seconds')) is not int) or (not 1 <= value['budget_seconds'] <= 600):
        raise ValueError('Native inventory task plan pending verification; no input')
    if not isinstance(value.get('pages'), list) or not 1 <= len(value['pages']) <= 128:
        raise ValueError('Expected 1..128 calibrated selected pages')
    if value.get('scan_mode', 'selected') not in ('selected', 'single_pass', 'grouped'):
        raise ValueError('Explicit supported inventory scan mode required')
    selections, seen = ([], set())
    for entry in value['pages']:
        if not isinstance(entry, dict) or set(entry) != {'calibration', 'material_id'} or (not isinstance(entry['material_id'], str)) or (not entry['material_id']):
            raise ValueError('Each page needs an explicit calibrated material identity')
        file = config_path(root, entry['calibration'])
        key = (file, entry['material_id'])
        if key in seen:
            raise ValueError('Duplicate selected material detail')
        seen.add(key)
        selections.append((file, entry['material_id']))
    if selected_ids is not None:
        if not isinstance(selected_ids, (list, tuple)) or not selected_ids or any((not isinstance(key, str) or not key for key in selected_ids)) or (len(set(selected_ids)) != len(selected_ids)):
            raise ValueError('Expected unique selected inventory identities')
        available = [key for _, key in selections]
        if any((available.count(key) != 1 for key in selected_ids)):
            raise ValueError('Target material lacks an unambiguous calibrated inspection page')
        selections = [(file, key) for file, key in selections if key in selected_ids]
    selected = bridge.validate_pages(game, [file for file, _ in selections])
    manifest = read_navigation(root, value.get('navigation'), game)
    for (_, page), (_, material_id) in zip(selected, selections):
        navigation.navigation_calibration(manifest, page)
        if not any((row['id'] == material_id for row in page['materials'])):
            raise ValueError('Selected material not bound to this detail calibration')
    if value.get('scan_mode') == 'single_pass':
        navigation.batch_selection([(page, material_id) for (_, page), (_, material_id) in zip(selected, selections)], manifest)
    elif value.get('scan_mode') == 'grouped':
        navigation.grouped_selection([(page, material_id) for (_, page), (_, material_id) in zip(selected, selections)], manifest)
    return (value, selections, manifest)

class NativeVersions:
    """Fresh resource catalog; cache binary hash only while file stat is stable."""

    def __init__(self, probe, executable, game='wuwa'):
        if game not in ('wuwa', 'zzz'):
            raise ValueError('Unsupported native inspection game')
        self.probe, self.executable, self.game = (probe, Path(executable), game)
        self.signature, self.digest = (None, None)

    def __call__(self):
        stat = self.executable.stat()
        signature = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
        if signature != self.signature:
            self.digest = self.probe.file_sha256(self.executable)
            self.signature = signature
        return {'game_exe_sha256': self.digest, 'resource_fingerprints': self.probe.native_resource_fingerprints(self.game, self.executable)}
