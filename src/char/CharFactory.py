from src.Labels import Labels
from src.char.Aemeath import Aemeath
from src.char.Augusta import Augusta
from src.char.Baizhi import Baizhi
from src.char.BaseChar import BaseChar, Elements
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
from src.char.Douling import Douling
from src.char.Encore import Encore
from src.char.Galbrena import Galbrena
from src.char.HavocRover import HavocRover
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
from src.char.Yinlin import Yinlin
from src.char.Youhu import Youhu
from src.char.Yuanwu import Yuanwu
from src.char.Zani import Zani
from src.char.Zhezhi import Zhezhi

char_dict = {
    Labels.char_yinlin: {'cls': Yinlin, 'res_cd': 12, 'echo_cd': 25, 'ring_index': Elements.ELECTRIC},
    Labels.char_verina: {'cls': Verina, 'res_cd': 12, 'echo_cd': 25, 'ring_index': Elements.SPECTRO},
    Labels.char_shorekeeper: {'cls': ShoreKeeper, 'res_cd': 15, 'echo_cd': 25, 'ring_index': Elements.SPECTRO},
    Labels.char_taoqi: {'cls': Taoqi, 'res_cd': 15, 'echo_cd': 25, 'ring_index': Elements.HAVOC},
    Labels.char_rover: {'cls': HavocRover, 'res_cd': 12, 'echo_cd': 25},
    Labels.char_rover_male: {'cls': HavocRover, 'res_cd': 12, 'echo_cd': 25},
    Labels.char_encore: {'cls': Encore, 'res_cd': 10, 'echo_cd': 25, 'ring_index': Elements.FIRE},
    Labels.char_jianxin: {'cls': Jianxin, 'res_cd': 12, 'echo_cd': 25, 'ring_index': Elements.WIND},
    Labels.char_sanhua: {'cls': Sanhua, 'res_cd': 10, 'echo_cd': 25, 'ring_index': Elements.ICE},
    Labels.char_sanhua2: {'cls': Sanhua, 'res_cd': 10, 'echo_cd': 25, 'ring_index': Elements.ICE},
    Labels.char_jinhsi: {'cls': Jinhsi, 'res_cd': 3, 'echo_cd': 25, 'ring_index': Elements.SPECTRO},
    Labels.char_jinhsi2: {'cls': Jinhsi, 'res_cd': 3, 'echo_cd': 25, 'ring_index': Elements.SPECTRO},
    Labels.char_yuanwu: {'cls': Yuanwu, 'res_cd': 3, 'echo_cd': 25, 'ring_index': Elements.ELECTRIC},
    Labels.chang_changli: {'cls': Changli, 'res_cd': 12, 'echo_cd': 25, 'ring_index': Elements.FIRE},
    Labels.char_changli2: {'cls': Changli, 'res_cd': 12, 'echo_cd': 25, 'ring_index': Elements.FIRE},
    Labels.char_chixia: {'cls': Chixia, 'res_cd': 9, 'echo_cd': 25, 'ring_index': Elements.FIRE},
    Labels.char_danjin: {'cls': Danjin, 'res_cd': 9999999, 'echo_cd': 25, 'ring_index': Elements.HAVOC},
    Labels.char_baizhi: {'cls': Baizhi, 'res_cd': 16, 'echo_cd': 25, 'ring_index': Elements.ICE},
    Labels.char_calcharo: {'cls': Calcharo, 'res_cd': 99999, 'echo_cd': 25, 'ring_index': Elements.ELECTRIC},
    Labels.char_jiyan: {'cls': Jiyan, 'res_cd': 16, 'echo_cd': 25, 'ring_index': Elements.WIND},
    Labels.char_mortefi: {'cls': Mortefi, 'res_cd': 14, 'echo_cd': 25, 'ring_index': Elements.FIRE},
    Labels.char_zhezhi: {'cls': Zhezhi, 'res_cd': 6, 'echo_cd': 25, 'ring_index': Elements.ICE},
    Labels.char_xiangliyao: {'cls': Xiangliyao, 'res_cd': 5, 'echo_cd': 25, 'ring_index': Elements.ELECTRIC},
    Labels.char_camellya: {'cls': Camellya, 'res_cd': 4, 'echo_cd': 25, 'ring_index': Elements.HAVOC},
    Labels.char_youhu: {'cls': Youhu, 'res_cd': 4, 'echo_cd': 25, 'ring_index': Elements.ICE},
    Labels.char_carlotta: {'cls': Carlotta, 'res_cd': 10, 'echo_cd': 25, 'ring_index': Elements.ICE},
    Labels.char_carlotta2: {'cls': Carlotta, 'res_cd': 10, 'echo_cd': 25, 'ring_index': Elements.ICE},
    Labels.char_roccia: {'cls': Roccia, 'res_cd': 10, 'echo_cd': 25, 'liberation_cd': 20, 'ring_index': Elements.HAVOC},
    Labels.char_phoebe: {'cls': Phoebe, 'res_cd': 12, 'echo_cd': 25, 'liberation_cd': 25,
                         'ring_index': Elements.SPECTRO},
    Labels.char_brant: {'cls': Brant, 'res_cd': 4, 'echo_cd': 25, 'liberation_cd': 24, 'ring_index': Elements.FIRE},
    Labels.char_cantarella: {'cls': Cantarella, 'res_cd': 10, 'echo_cd': 25, 'liberation_cd': 25,
                             'ring_index': Elements.HAVOC},
    Labels.char_zani: {'cls': Zani, 'res_cd': 5, 'echo_cd': 25, 'ring_index': Elements.SPECTRO},
    Labels.char_zani2: {'cls': Zani, 'res_cd': 5, 'echo_cd': 25, 'ring_index': Elements.SPECTRO},
    Labels.char_ciaccona: {'cls': Ciaccona, 'res_cd': 10, 'echo_cd': 25, 'liberation_cd': 20,
                           'ring_index': Elements.WIND},
    Labels.char_cartethyia: {'cls': Cartethyia, 'res_cd': 14, 'echo_cd': 25, 'liberation_cd': 20,
                             'ring_index': Elements.WIND},
    Labels.char_lupa: {'cls': Lupa, 'res_cd': 14, 'echo_cd': 25, 'liberation_cd': 20,
                       'ring_index': Elements.FIRE},
    Labels.char_phrolova: {'cls': Phrolova, 'res_cd': 12, 'echo_cd': 25, 'liberation_cd': 20,
                           'ring_index': Elements.HAVOC},
    Labels.Augusta: {'cls': Augusta, 'res_cd': 15, 'echo_cd': 25, 'liberation_cd': 25,
                     'ring_index': Elements.ELECTRIC},
    Labels.char_iuno: {'cls': Iuno, 'res_cd': 8, 'echo_cd': 20, 'liberation_cd': 25,
                       'ring_index': Elements.WIND},
    Labels.char_galbrena: {'cls': Galbrena, 'res_cd': 5, 'echo_cd': 20, 'liberation_cd': 25,
                           'ring_index': Elements.FIRE},
    Labels.char_chouyuan: {'cls': Qiuyuan, 'res_cd': 10, 'echo_cd': 20, 'liberation_cd': 25,
                           'ring_index': Elements.WIND},
    Labels.char_chisa: {'cls': Chisa, 'res_cd': 10, 'echo_cd': 20, 'liberation_cd': 25,
                        'ring_index': Elements.HAVOC},
    Labels.char_douling: {'cls': Douling, 'res_cd': 15, 'echo_cd': 25, 'liberation_cd': 25,
                          'ring_index': Elements.ELECTRIC},
    Labels.char_linnai: {'cls': Linnai, 'res_cd': 15, 'echo_cd': 25, 'liberation_cd': 25,
                         'ring_index': Elements.SPECTRO},
    Labels.char_moning: {'cls': Mornye, 'res_cd': 15, 'echo_cd': 25, 'liberation_cd': 25, 'ring_index': Elements.FIRE},
    Labels.char_aemeath: {'cls': Aemeath, 'res_cd': 4, 'echo_cd': 25, 'liberation_cd': 25, 'ring_index': Elements.FIRE},
    Labels.char_luhesi: {'cls': Luhesi, 'res_cd': 4, 'echo_cd': 25, 'liberation_cd': 25,
                         'ring_index': Elements.SPECTRO},
}

char_names = char_dict.keys()


def get_char_by_pos(task, box, index, old_char):
    highest_confidence = 0
    info = None
    name = "unknown"
    char = None
    if old_char and old_char.confidence > 0.92 and old_char.char_name in char_names:
        char = task.find_one(old_char.char_name, box=box, threshold=0.6)
        if char:
            return old_char
    if not char:
        char = task.find_best_match_in_box(box, char_names, threshold=0.6)
        if char:
            info = char_dict.get(char.name)
            name = char.name
            cls = info.get('cls')
            return cls(task, index, info.get('res_cd'), info.get('echo_cd'), info.get('liberation_cd') or 25,
                       char_name=name, confidence=char.confidence, ring_index=info.get('ring_index', -1))
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
