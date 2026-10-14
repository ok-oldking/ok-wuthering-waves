from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Exact ordinary cultivation families, reusing native20-charge missions.

Identity/route registry only, not per-item live OCR or combat acceptance.
Sources: https://wiki.biligame.com/zzz/沙盒1 and installed
assets/game_data/compendium_data.yml. No drive discs or random equipment.
"""
from copy import deepcopy
PROMOTIONS = (('attack', '强攻', '先行者认证章', 'pioneer-certification-seal'), ('stun', '击破', '破阵者认证章', 'buster-certification-seal'), ('anomaly', '异常', '掌控者认证章', 'controller-certification-seal'), ('support', '支援', '统御者认证章', 'ruler-certification-seal'), ('defense', '防护', '捍卫者认证章', 'defender-certification-seal'), ('rupture', '命破', '裁决者认证章', 'arbiter-certification-seal'), ('edge', '锋御', '执锋者认证章', 'edge-certification-seal'))
SKILLS = (('physical', '物理', '刚性测试'), ('freeze', '冰结', '冰结测试'), ('burn', '引燃', '升温测试'), ('shock', '电击', '电流测试'), ('ether', '以太', '共鸣测试'), ('wind', '风蚀', '风切测试'), ('lumen', '流明', '琢光测试'))
WEAPONS = (('attack', '强攻', '强攻极片试验'), ('stun', '击破', '击破振膜试验'), ('anomaly', '异常', '异常磁体试验'), ('support', '支援', '支援分频试验'), ('defense', '防护', '防护音圈试验'), ('rupture', '命破', '命破共鸣试验'), ('edge', '锋御', '锋御耦合试验'))

def families():
    """Low→high identities with ONE native mission per family."""
    result = []
    for key, name, top, top_id in PROMOTIONS:
        result.append(dict(id=key + '-certification', category='character_promotion', type='代理人晋升', mission=name + '演练', members=[dict(id='basic-' + key + '-seal', name='初阶' + name + '认证章'), dict(id='advanced-' + key + '-seal', name='高阶' + name + '认证章'), dict(id=top_id, name=top)]))
    for key, name, mission in SKILLS:
        result.append(dict(id=key + '-skill', category='skill', type='代理人技能', mission=mission, members=[dict(id=q + '-' + key + '-chip', name=prefix + name + '芯片') for q, prefix in (('basic', '基础'), ('advanced', '进阶'), ('specialized', '特化'))]))
    for key, name, mission in WEAPONS:
        result.append(dict(id=key + '-wengine-promotion', category='weapon_promotion', type='音擎改装', mission=mission, members=[dict(id=key + '-component', name=name + '组件'), dict(id='reinforced-' + key + '-component', name='增强型' + name + '组件'), dict(id='specialized-' + key + '-component', name='特化型' + name + '组件')]))
    result.extend([dict(id='agent-experience', category='character_exp', type='基础材料', mission='调查专项', members=[dict(id='trainee-investigator-log', name='见习调查员记录'), dict(id='official-investigator-log', name='正式调查员记录'), dict(id='senior-investigator-log', name='资深调查员记录')]), dict(id='wengine-experience', category='weapon_exp', type='基础材料', mission='音擎专项', members=[dict(id='w-engine-battery', name='音擎蓄电池'), dict(id='w-engine-power-supply', name='变频音擎电源'), dict(id='w-engine-energy-module', name='音擎能源模块')])])
    return deepcopy(result)

def routes():
    return {item['id']: dict(name=family['mission'], type=family['type'], mission=family['mission'], cost=20, materials=[item['id']]) for family in families() for item in family['members']}

def preview_materials():
    return {item['id']: (item['name'], family['category'], family['type'], family['mission']) for family in families() for item in family['members']}
EXPERT_DROPS = (('death-notice', '凶刑讣告', '恶名·杜拉罕'), ('crimson-awe', '殷红震慑', '祸首·通缉打手'), ('pursuing-phantom', '追袭骸影', '恶名·装甲哈提'), ('steel-malice', '钢铁恶意', '汉斯·蓄能型'), ('destructive-advance', '毁荡突进', '「提丰·重击者型」'), ('falling-fist', '拳坠如陨', '蛮横力士'), ('stealth-phantom', '潜袭魅影', '多佩冈亚·简'), ('thunderous-scales', '游鳞雷动', '色雷斯人'), ('life-cutting', '索命切割', '伐木机'), ('corrupted-elytra', '鞘翅秽种', '秽息蚀者·阿瓦鲁斯'), ('venomous-edge', '诡运毒锋', '牲鬼·凶魁愚者'), ('dream-corroded-iron', '蚀梦残铁', '秽蚀·狛野真斗'), ('caustic-thorn', '淬刺蚀芯', '秽息行者·蝎骸'), ('deep-corrosion-circuit', '深蚀回路', '空域戒戍者'), ('bloodstained-feather', '喋血秽羽', '牲鬼·卫律使者'), ('simulated-core', '拟造核心', '征服者'))
WEEKLY_DROPS = (('ferocious-grip', '腥风之握', '初生死路屠夫'), ('living-drive', '活态驱动', '未知复合侵蚀体'), ('finale-dance-shoes', '终幕舞鞋', '冥宁芙·双子'), ('scarlet-engine', '猩红引擎', '「霸主侵蚀体·庞培」'), ('fanatic-sculpture', '狂信之塑', '牲鬼·布林格'), ('refined-exuvia', '塑炼遗蜕', '秽息司祭'), ('foul-red-crystal-spike', '秽红晶刺', '彷徨猎手'), ('turbid-patterned-crystal', '浊纹晶质', '魇缚者·叶释渊'), ('marrow-thorn', '吮髓之棘', '猎血清道夫'), ('fate-exuvia', '刻命残蜕', '基塔布鲁'), ('counterfeit-core', '赝造离核', '库萨里库'))

def named_materials():
    return [dict(id='higher-dimensional-data-' + key, name='高维数据：' + name, category='core_skill_expert', native=boss) for key, name, boss in EXPERT_DROPS] + [dict(id=key, name=name, category='weekly_boss', native=boss) for key, name, boss in WEEKLY_DROPS]

def named_routes():
    result = {}
    for item in named_materials():
        category = '专业挑战室' if item['category'] == 'core_skill_expert' else '恶名狩猎'
        result[item['id']] = dict(name=category + ' · ' + item['native'], category=category, type=item['native'], mission=None, cost=40 if category == '专业挑战室' else 60, materials=[item['id']])
    return result
NATIVE_EXTENSIONS = (('实战模拟室', '代理人晋升', '锋御演练'), ('实战模拟室', '音擎改装', '锋御耦合试验'), ('专业挑战室', '征服者', None), ('恶名狩猎', '库萨里库', None))

def extended_native_service(original):
    from copy import copy
    from zzz_od.game_data.compendium import CompendiumMissionType, CompendiumMission
    service = copy(original)
    service.data = deepcopy(original.data)
    for category_name, type_name, mission_name in NATIVE_EXTENSIONS:
        category = service.get_category_data('训练', category_name)
        if category is None:
            raise ValueError('原生手册分类缺失，不创建未知分类')
        kind = service.get_mission_type_data('训练', category_name, type_name)
        if kind is None:
            kind = CompendiumMissionType(type_name)
            kind.set_category(category)
            category.mission_type_list.append(kind)
        if mission_name is not None and (not any((m.mission_name == mission_name for m in kind.mission_list))):
            mission = CompendiumMission(mission_name)
            mission.set_mission_type(kind)
            kind.mission_list.append(mission)
    return service
