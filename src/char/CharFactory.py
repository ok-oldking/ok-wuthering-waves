from src.char.Changli import Changli
from src.char.CharSkillButton import is_float
from src.char.Jinhsi import Jinhsi
from src.char.Yuanwu import Yuanwu


def get_char_by_pos(task, box, index):
    from src.char.Verina import Verina
    from src.char.Yinlin import Yinlin
    from src.char.Taoqi import Taoqi
    from src.char.BaseChar import BaseChar
    from src.char.HavocRover import HavocRover
    from src.char.Sanhua import Sanhua
    from src.char.Jianxin import Jianxin
    from src.char.Encore import Encore
    char_dict = {
        'char_yinlin': {'cls': Yinlin, 'res_cd': 12, 'echo_cd': 15},
        'char_verina': {'cls': Verina, 'res_cd': 12, 'echo_cd': 20},
        'char_taoqi': {'cls': Taoqi, 'res_cd': 15, 'echo_cd': 20},
        'char_rover': {'cls': HavocRover, 'res_cd': 12, 'echo_cd': 20},
        'char_encore': {'cls': Encore, 'res_cd': 10, 'echo_cd': 20},
        'char_jianxin': {'cls': Jianxin, 'res_cd': 12, 'echo_cd': 20},
        'char_sanhua': {'cls': Sanhua, 'res_cd': 10, 'echo_cd': 20},
        'char_jinhsi': {'cls': Jinhsi, 'res_cd': 3, 'echo_cd': 20},
        'char_yuanwu': {'cls': Yuanwu, 'res_cd': 3, 'echo_cd': 20},
        'chang_changli': {'cls': Changli, 'res_cd': 12, 'echo_cd': 20}
    }
    highest_confidence = 0
    info = None
    for char_name, char_info in char_dict.items():
        feature = task.find_one(char_name, box=box, threshold=0.7)
        if feature:
            task.log_info(f'found char {char_name} {feature.confidence} {highest_confidence}')
        if feature and feature.confidence > highest_confidence:
            highest_confidence = feature.confidence
            info = char_info
    if info is not None:
        cls = info.get('cls')
        return cls(task, index, info.get('res_cd'), info.get('echo_cd'))
    task.log_info(f'could not find char {info} {highest_confidence}')
    has_cd = task.ocr(box=box)
    if has_cd and is_float(has_cd[0].name):
        task.log_info(f'found char {has_cd[0]} wait and reload')
        task.next_frame()
        return get_char_by_pos(task, box, index)
    if task.debug:
        task.screenshot(f'could not find char {index}')
    return BaseChar(task, index)
