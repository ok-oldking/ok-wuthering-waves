from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Exact 1.x/2.x shared and 3.x forgery families, low -> premium.

Not navigation/calibration evidence. Regional duplicate dungeons are NOT new
material families. No monster byproducts, field/boss/weekly drops included.
Sources: wuthering.gg/zh-Hans/items/development-materials and current native
3.7.14 rewards. No third generation found in the reviewed current catalog.
"""
from copy import deepcopy
FAMILIES = (('sword-old', '迅刀', '旧', '金属液滴', ('惰性金属液滴', '活性金属液滴', '极化金属液滴', '异构金属液滴')), ('broadblade-old', '长刃', '旧', '海蚀嵌合体', tuple(('海蚀嵌合体' + n for n in ('210', '226', '235', '239')))), ('pistol-old', '佩枪', '旧', '晶化燃素', tuple((n + '晶化燃素' for n in ('含杂', '粗萃', '精馏', '高纯')))), ('gauntlet-old', '臂铠', '旧', '声律', tuple(('声律' + n for n in ('种核', '萌芽', '新叶', '花蕾')))), ('rectifier-old', '音感仪', '旧', '涡流', tuple((n + '涡流' for n in ('慢板', '柔板', '行板', '急板')))), ('sword-new', '迅刀', '新', '偏振体', tuple((n + '偏振体' for n in ('残翼', '单翼', '多翼', '叠翼')))), ('broadblade-new', '长刃', '新', '切削晶块', tuple((n + '切削晶块' for n in ('低频', '中频', '高频', '全频')))), ('pistol-new', '佩枪', '新', '聚燃体', tuple((n + '聚燃体' for n in ('缺损', '余音', '残响', '回音')))), ('gauntlet-new', '臂铠', '新', '海蚀碎晶', tuple((n + '海蚀碎晶' for n in ('低频', '中频', '高频', '全频')))), ('rectifier-new', '音感仪', '新', '弦线', tuple((n + '的弦线' for n in ('拼凑', '断续', '凝固', '如歌')))))

def families():
    return deepcopy([dict(id=key, weapon=weapon, generation=generation, name=name, qualities=[dict(name=value, quality=quality) for quality, value in zip(('basic', 'medium', 'advanced', 'premium'), members)]) for key, weapon, generation, name, members in FAMILIES])

def coverage(options):
    """Actual menu bindings, not guessed readiness from a family definition."""
    by_name = {item['name']: item for item in options}
    result = families()
    for family in result:
        for item in family['qualities']:
            match = by_name.get(item['name'])
            item['selectable'] = match is not None
            item['material_id'] = match['id'] if match else None
            item['route'] = match['route'] if match else None
    return result
EXISTING_IDS = {'叠翼偏振体': 'weapon-skill-dieyipianzhenti', '多翼偏振体': 'weapon-skill-duoyipianzhenti', '单翼偏振体': 'weapon-skill-danyipianzhenti', '断续的弦线': 'skill-duanxudexianxian', '如歌的弦线': 'skill-rugedexianxian', '凝固的弦线': 'skill-ninggudexianxian', '高频切削晶块': 'weapon-skill-gaopinqiexuejingkuai', '高频海蚀碎晶': 'weapon-skill-gaopinhaishisuijing', '残响聚燃体': 'weapon-skill-canxiangjuran'}

def material_rows():
    return [dict(id=EXISTING_IDS.get(item['name'], 'forgery-' + family['id'] + '-' + item['quality']), name=item['name'], category='weapon_promotion', quality=item['quality'], family=family['id']) for family in families() for item in family['qualities']]

def routes():
    rows = material_rows()
    return {'forgery-family-' + f['id']: dict(name='凝素领域 · ' + f['weapon'] + ' · ' + f['generation'] + ' · ' + f['name'], kind='Forgery', cost=40, native_index=1, reward_names=[item['name'] for item in f['qualities']], materials=[row['id'] for row in rows if row['family'] == f['id']]) for f in families()}
