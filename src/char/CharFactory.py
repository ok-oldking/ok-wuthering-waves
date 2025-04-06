from src.char.Baizhi import Baizhi
from src.char.BaseChar import BaseChar
from src.char.Brant import Brant
from src.char.Calcharo import Calcharo
from src.char.Camellya import Camellya
from src.char.Cantarella import Cantarella
from src.char.Carlotta import Carlotta
from src.char.Changli import Changli
from src.char.CharSkillButton import is_float
from src.char.Chixia import Chixia
from src.char.Danjin import Danjin
from src.char.Encore import Encore
from src.char.HavocRover import HavocRover
from src.char.Jianxin import Jianxin
from src.char.Jinhsi import Jinhsi
from src.char.Jiyan import Jiyan
from src.char.Mortefi import Mortefi
from src.char.Phoebe import Phoebe
from src.char.Roccia import Roccia
from src.char.Sanhua import Sanhua
from src.char.ShoreKeeper import ShoreKeeper
from src.char.Taoqi import Taoqi
from src.char.Verina import Verina
from src.char.Xiangliyao import Xiangliyao
from src.char.Yinlin import Yinlin
from src.char.Youhu import Youhu
from src.char.Yuanwu import Yuanwu
from src.char.Zhezhi import Zhezhi

char_dict = {
        'char_yinlin': {'cls': Yinlin, 'res_cd': 12, 'echo_cd': 25},
        'char_verina': {'cls': Verina, 'res_cd': 12, 'echo_cd': 25},
        'char_shorekeeper': {'cls': ShoreKeeper, 'res_cd': 15, 'echo_cd': 25},
        'char_taoqi': {'cls': Taoqi, 'res_cd': 15, 'echo_cd': 25},
        'char_rover': {'cls': HavocRover, 'res_cd': 12, 'echo_cd': 25},
        'char_rover_male': {'cls': HavocRover, 'res_cd': 12, 'echo_cd': 25},
        'char_encore': {'cls': Encore, 'res_cd': 10, 'echo_cd': 25},
        'char_jianxin': {'cls': Jianxin, 'res_cd': 12, 'echo_cd': 25},
        'char_sanhua': {'cls': Sanhua, 'res_cd': 10, 'echo_cd': 25},
        'char_sanhua2': {'cls': Sanhua, 'res_cd': 10, 'echo_cd': 25},
        'char_jinhsi': {'cls': Jinhsi, 'res_cd': 3, 'echo_cd': 25},
        'char_jinhsi2': {'cls': Jinhsi, 'res_cd': 3, 'echo_cd': 25},
        'char_yuanwu': {'cls': Yuanwu, 'res_cd': 3, 'echo_cd': 25},
        'chang_changli': {'cls': Changli, 'res_cd': 12, 'echo_cd': 25},
        'char_chixia': {'cls': Chixia, 'res_cd': 9, 'echo_cd': 25},
        'char_danjin': {'cls': Danjin, 'res_cd': 9999999, 'echo_cd': 25},
        'char_baizhi': {'cls': Baizhi, 'res_cd': 16, 'echo_cd': 25},
        'char_calcharo': {'cls': Calcharo, 'res_cd': 99999, 'echo_cd': 25},
        'char_jiyan': {'cls': Jiyan, 'res_cd': 16, 'echo_cd': 25},
        'char_mortefi': {'cls': Mortefi, 'res_cd': 14, 'echo_cd': 25},
        'char_zhezhi': {'cls': Zhezhi, 'res_cd': 6, 'echo_cd': 25},
        'char_xiangliyao': {'cls': Xiangliyao, 'res_cd': 5, 'echo_cd': 25},
        'char_camellya': {'cls': Camellya, 'res_cd': 4, 'echo_cd': 25},
        'char_youhu': {'cls': Youhu, 'res_cd': 4, 'echo_cd': 25},
        'char_carlotta': {'cls': Carlotta, 'res_cd': 10, 'echo_cd': 25},
        'char_roccia': {'cls': Roccia, 'res_cd': 10, 'echo_cd': 25, 'liberation_cd': 20},
        'char_phoebe': {'cls': Phoebe, 'res_cd': 12, 'echo_cd': 25, 'liberation_cd': 25},
        'char_brant': {'cls': Brant, 'res_cd': 4, 'echo_cd': 25, 'liberation_cd': 24},
        'char_cantarella': {'cls': Cantarella, 'res_cd': 10, 'echo_cd': 25, 'liberation_cd': 25},
    }

char_names = char_dict.keys()

def get_char_by_pos(task, box, index, old_char):
    highest_confidence = 0
    info = None
    name = "unknown"
    char = None
    if old_char and old_char.name in char_names:
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
                       char_name=name)
    task.log_info(f'could not find char {info} {highest_confidence}')
    if old_char:
        return old_char
    has_cd = task.ocr(box=box)
    if has_cd and is_float(has_cd[0].name):
        task.log_info(f'found char {has_cd[0]} wait and reload')
        task.next_frame()
        return get_char_by_pos(task, box, index, old_char)
    if task.debug:
        task.screenshot(f'could not find char {index}')
    return BaseChar(task, index, char_name=name)
