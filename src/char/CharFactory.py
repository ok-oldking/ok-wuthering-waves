from src.Labels import Labels
from src.char.Aemeath import Aemeath
from src.char.Augusta import Augusta
from src.char.Baizhi import Baizhi
from src.char.BaseChar import BaseChar, CharType, Elements, get_default_buff_time
from src.char.Brant import Brant
from src.char.Calcharo import Calcharo
from src.char.Camellya import Camellya
from src.char.Cantarella import Cantarella
from src.char.Carlotta import Carlotta
from src.char.Cartethyia import Cartethyia
from src.char.Changli import Changli
from src.char.Chisa import Chisa
from src.char.Chixia import Chixia
from src.char.Ciaccona import Ciaccona
from src.char.Danjin import Danjin
from src.char.Denia import Denia
from src.char.Douling import Douling
from src.char.Encore import Encore
from src.char.Galbrena import Galbrena
from src.char.HavocRover import HavocRover
from src.char.Hiyuki import Hiyuki
from src.char.Iuno import Iuno
from src.char.Jianxin import Jianxin
from src.char.Jinhsi import Jinhsi
from src.char.Jiyan import Jiyan
from src.char.Linnai import Linnai
from src.char.Luhesi import Luhesi
from src.char.Lupa import Lupa
from src.char.Mortefi import Mortefi
from src.char.Mornye import Mornye
from src.char.Phoebe import Phoebe
from src.char.Phrolova import Phrolova
from src.char.Qiuyuan import Qiuyuan
from src.char.Roccia import Roccia
from src.char.Sanhua import Sanhua
from src.char.ShoreKeeper import ShoreKeeper
from src.char.Taoqi import Taoqi
from src.char.Verina import Verina
from src.char.Xiangliyao import Xiangliyao
from src.char.Xigelika import Xigelika
from src.char.Yinlin import Yinlin
from src.char.Youhu import Youhu
from src.char.Yuanwu import Yuanwu
from src.char.Zani import Zani
from src.char.Zhezhi import Zhezhi

_char_dict_raw = {
    Labels.char_yinlin: {'cls': Yinlin, 'char_type': CharType.SUB_DPS,
                         'ring_index': Elements.ELECTRIC},
    Labels.char_verina: {'cls': Verina, 'char_type': CharType.HEALER,
                         'ring_index': Elements.SPECTRO},
    Labels.char_shorekeeper: {'cls': ShoreKeeper, 'char_type': CharType.HEALER,
                              'ring_index': Elements.SPECTRO},
    Labels.char_taoqi: {'cls': Taoqi, 'char_type': CharType.HEALER,
                        'ring_index': Elements.HAVOC},
    (Labels.char_rover, Labels.char_rover_male): {'cls': HavocRover, 'char_type': CharType.MAIN_DPS},
    Labels.char_encore: {'cls': Encore, 'char_type': CharType.MAIN_DPS,
                         'ring_index': Elements.FIRE},
    Labels.char_jianxin: {'cls': Jianxin, 'char_type': CharType.HEALER,
                          'ring_index': Elements.WIND},
    (Labels.char_sanhua, Labels.char_sanhua2): {'cls': Sanhua, 'char_type': CharType.SUB_DPS,
                                                'ring_index': Elements.ICE},
    (Labels.char_jinhsi, Labels.char_jinhsi2): {'cls': Jinhsi, 'char_type': CharType.MAIN_DPS,
                                                'ring_index': Elements.SPECTRO},
    Labels.char_yuanwu: {'cls': Yuanwu, 'char_type': CharType.SUB_DPS,
                         'ring_index': Elements.ELECTRIC},
    (Labels.chang_changli, Labels.char_changli2): {'cls': Changli, 'char_type': CharType.MAIN_DPS,
                                                   'ring_index': Elements.FIRE},
    Labels.char_chixia: {'cls': Chixia, 'char_type': CharType.MAIN_DPS,
                         'ring_index': Elements.FIRE},
    Labels.char_danjin: {'cls': Danjin, 'char_type': CharType.SUB_DPS,
                         'ring_index': Elements.HAVOC},
    Labels.char_baizhi: {'cls': Baizhi, 'char_type': CharType.HEALER,
                         'ring_index': Elements.ICE},
    Labels.char_calcharo: {'cls': Calcharo, 'char_type': CharType.MAIN_DPS,
                           'ring_index': Elements.ELECTRIC},
    Labels.char_jiyan: {'cls': Jiyan, 'char_type': CharType.MAIN_DPS,
                        'ring_index': Elements.WIND},
    Labels.char_mortefi: {'cls': Mortefi, 'char_type': CharType.SUB_DPS,
                          'ring_index': Elements.FIRE},
    Labels.char_zhezhi: {'cls': Zhezhi, 'char_type': CharType.SUB_DPS,
                         'ring_index': Elements.ICE},
    Labels.char_xiangliyao: {'cls': Xiangliyao, 'char_type': CharType.MAIN_DPS,
                             'ring_index': Elements.ELECTRIC},
    Labels.char_camellya: {'cls': Camellya, 'char_type': CharType.MAIN_DPS,
                           'ring_index': Elements.HAVOC},
    Labels.char_youhu: {'cls': Youhu, 'char_type': CharType.HEALER,
                        'ring_index': Elements.ICE},
    (Labels.char_carlotta, Labels.char_carlotta2): {'cls': Carlotta, 'char_type': CharType.MAIN_DPS,
                                                    'ring_index': Elements.ICE},
    Labels.char_roccia: {'cls': Roccia, 'char_type': CharType.SUB_DPS, 'ring_index': Elements.HAVOC},
    Labels.char_phoebe: {'cls': Phoebe, 'char_type': CharType.SUB_DPS, 'ring_index': Elements.SPECTRO},
    Labels.char_brant: {'cls': Brant, 'char_type': CharType.HEALER, 'ring_index': Elements.FIRE},
    Labels.char_cantarella: {'cls': Cantarella, 'char_type': CharType.HEALER, 'ring_index': Elements.HAVOC},
    (Labels.char_zani, Labels.char_zani2): {'cls': Zani, 'char_type': CharType.MAIN_DPS,
                                            'ring_index': Elements.SPECTRO},
    Labels.char_ciaccona: {'cls': Ciaccona, 'char_type': CharType.SUB_DPS, 'ring_index': Elements.WIND},
    Labels.char_cartethyia: {'cls': Cartethyia, 'char_type': CharType.MAIN_DPS, 'ring_index': Elements.WIND},
    Labels.char_lupa: {'cls': Lupa, 'char_type': CharType.SUB_DPS, 'ring_index': Elements.FIRE},
    Labels.char_phrolova: {'cls': Phrolova, 'char_type': CharType.MAIN_DPS, 'ring_index': Elements.HAVOC},
    Labels.Augusta: {'cls': Augusta, 'char_type': CharType.MAIN_DPS, 'ring_index': Elements.ELECTRIC},
    Labels.char_iuno: {'cls': Iuno, 'char_type': CharType.SUB_DPS,
                       'ring_index': Elements.WIND},
    Labels.char_galbrena: {'cls': Galbrena, 'char_type': CharType.MAIN_DPS, 'ring_index': Elements.FIRE},
    Labels.char_chouyuan: {'cls': Qiuyuan, 'char_type': CharType.SUB_DPS, 'ring_index': Elements.WIND},
    Labels.char_chisa: {'cls': Chisa, 'char_type': CharType.HEALER, 'ring_index': Elements.HAVOC},
    Labels.char_denia: {'cls': Denia, 'char_type': CharType.SUB_DPS, 'buff_time': 14, 'ring_index': Elements.FIRE},
    Labels.char_douling: {'cls': Douling, 'char_type': CharType.HEALER, 'ring_index': Elements.ELECTRIC},
    Labels.char_linnai: {'cls': Linnai, 'char_type': CharType.SUB_DPS, 'ring_index': Elements.SPECTRO},
    (Labels.char_moning, Labels.char_moning_new): {'cls': Mornye, 'char_type': CharType.HEALER,
                                                   'ring_index': Elements.FIRE},
    Labels.char_aemeath: {'cls': Aemeath, 'char_type': CharType.MAIN_DPS, 'ring_index': Elements.FIRE},
    Labels.char_xigelika: {'cls': Xigelika, 'char_type': CharType.MAIN_DPS, 'ring_index': Elements.WIND},
    Labels.char_luhesi: {'cls': Luhesi, 'char_type': CharType.MAIN_DPS, 'ring_index': Elements.SPECTRO},
    Labels.char_hiyuki: {'cls': Hiyuki, 'char_type': CharType.MAIN_DPS, 'ring_index': Elements.ICE},
}

char_dict = {}
for keys, value in _char_dict_raw.items():
    value = dict(value)
    value.setdefault('buff_time', get_default_buff_time(value.get('char_type', CharType.MAIN_DPS)))
    if isinstance(keys, tuple):
        for key in keys:
            char_dict[key] = value
    else:
        char_dict[keys] = value

char_names = char_dict.keys()


def _get_char_type(task, info):
    char_config = getattr(task, 'char_config', {})
    if info.get('cls') is Iuno and char_config.get('Iuno C6'):
        return CharType.MAIN_DPS
    return info.get('char_type', CharType.MAIN_DPS)


def _get_buff_time(task, info):
    char_type = _get_char_type(task, info)
    if info.get('cls') is Iuno and char_type == CharType.MAIN_DPS:
        return get_default_buff_time(CharType.MAIN_DPS)
    return info.get('buff_time', get_default_buff_time(char_type))


def _apply_char_config(task, char, info):
    if char and info:
        char.set_char_type(_get_char_type(task, info))
        char.set_buff_time(_get_buff_time(task, info))
    return char


def get_char_by_pos(task, box, index, old_char):
    highest_confidence = 0
    info = None
    name = "unknown"
    char = None
    if old_char and old_char.confidence > 0.92 and old_char.char_name in char_names:
        char = task.find_one(old_char.char_name, box=box, threshold=0.6)
        if char:
            _apply_char_config(task, old_char, char_dict.get(old_char.char_name))
            return old_char
    if not char:
        char = task.find_best_match_in_box(box, char_names, threshold=0.6)
        if char:
            info = char_dict.get(char.name)
            name = char.name
            cls = info.get('cls')
            return cls(task, index, char_name=name, confidence=char.confidence, ring_index=info.get('ring_index', -1),
                       char_type=_get_char_type(task, info), buff_time=_get_buff_time(task, info))
    task.log_info(f'could not find char {index} {info} {highest_confidence}')
    if old_char:
        return old_char
    if task.debug:
        task.screenshot(f'could not find char {index}')
    return BaseChar(task, index, char_name=name)


def is_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
