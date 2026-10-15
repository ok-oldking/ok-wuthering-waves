"""包内导入与独立运行数据；不依赖开发者电脑路径。"""
from importlib import import_module
from pathlib import Path
import shutil
import os
import uuid

MODULES = frozenset(['inventory_task_config', 'inventory_task_session', 'inventory_native_probe', 'inventory_native_navigation', 'inventory_scrollbar', 'inventory_entry_navigation', 'inventory_zzz_entry_navigation', 'inventory_deficit_policy', 'inventory_material_equivalence', 'inventory_wuwa_families', 'inventory_zzz_families', 'inventory_wuwa_destination', 'inventory_replay_report', 'inventory_version_candidate', 'inventory_observation'])

def inventory_root():
    root = Path(__file__).resolve().parents[2] / 'config' / 'inventory_extension'
    target = root / 'config'
    sync_assets(Path(__file__).parent / 'assets', target)
    return root

def sync_assets(source_dir, target):
    """仅更新随包识别资源，不覆盖用户目标或扣体力记录。"""
    target.mkdir(parents=True, exist_ok=True)
    for source in source_dir.glob('*.json'):
        destination = target / source.name
        data = source.read_bytes()
        if destination.exists() and destination.read_bytes() == data:
            continue
        stage = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            with stage.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(stage, destination)
        finally:
            stage.unlink(missing_ok=True)

def import_support(path):
    module = Path(path).stem.replace('-', '_')
    if module not in MODULES:
        raise ValueError('未知的库存模块')
    aliases = {'inventory_deficit_policy': 'src.inventory.deficit_policy', 'inventory_material_equivalence': 'src.inventory.material_equivalence'}
    if module.startswith('inventory_zzz_'):
        raise ValueError('鸣潮库存不加载绝区零适配')
    return import_module(aliases.get(module, 'src.inventory_support.' + module))

def valid_game_path(game, value):
    names = {'wuwa':'Client-Win64-Shipping.exe','zzz':'ZenlessZoneZero.exe'}
    return isinstance(value,str) and Path(value).is_absolute() and Path(value).name.casefold()==names.get(game,'').casefold()
