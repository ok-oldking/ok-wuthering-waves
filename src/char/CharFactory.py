from src.char.Baizhi import Baizhi
from src.char.Calcharo import Calcharo
from src.char.Changli import Changli
from src.char.CharSkillButton import is_float
from src.char.Chixia import Chixia
from src.char.Danjin import Danjin
from src.char.Jinhsi import Jinhsi
from src.char.Jiyan import Jiyan
from src.char.Mortefi import Mortefi
from src.char.ShoreKeeper import ShoreKeeper
from src.char.Xiangliyao import Xiangliyao
from src.char.Yuanwu import Yuanwu
from src.char.Zhezhi import Zhezhi
from src.char.Verina import Verina
from src.char.Yinlin import Yinlin
from src.char.Taoqi import Taoqi
from src.char.BaseChar import BaseChar, WWRole
from src.char.HavocRover import HavocRover
from src.char.Sanhua import Sanhua
from src.char.Jianxin import Jianxin
from src.char.Encore import Encore
from typing import Type
from dataclasses import dataclass
@dataclass
class Character:
    char_name: str
    cls: Type
    res_cd: int
    echo_cd: int
    role: WWRole
    full_con_swap_to: WWRole

def get_char_by_pos(task, box, index):
    char_list = [
        # Healers
        Character('char_verina', Verina, 12, 20, WWRole.Healer, WWRole.Default),
        Character('char_shorekeeper', ShoreKeeper, 15, 20, WWRole.Healer, WWRole.Default),
        Character('char_baizhi', Baizhi, 16, 20, WWRole.Healer, WWRole.MainDps),
        # Supportive
        Character('char_jianxin', Jianxin, 12, 20, WWRole.Default, WWRole.Default),
        Character('char_taoqi', Taoqi, 15, 20, WWRole.Default, WWRole.MainDps),
        Character('char_yuanwu', Yuanwu, 3, 20, WWRole.Default, WWRole.Default),
        # Rest
        Character('char_rover', HavocRover, 12, 20, WWRole.MainDps, WWRole.Default),
        Character('char_rover_male', HavocRover, 12, 20, WWRole.MainDps, WWRole.Default),
        Character('char_encore', Encore, 10, 20, WWRole.MainDps, WWRole.Default),
        Character('char_danjin', Danjin, 9999999, 20, WWRole.SubDps, WWRole.MainDps),
        Character('char_mortefi', Mortefi, 14, 20, WWRole.SubDps, WWRole.MainDps),
        Character('char_yinlin', Yinlin, 12, 15, WWRole.Default, WWRole.Default),
        Character('char_sanhua', Sanhua, 10, 20, WWRole.Default, WWRole.Default),
        Character('char_jinhsi', Jinhsi, 3, 20, WWRole.Default, WWRole.Default),
        Character('chang_changli', Changli, 12, 20, WWRole.Default, WWRole.Default),
        Character('char_chixia', Chixia, 9, 20, WWRole.Default, WWRole.Default),
        Character('char_calcharo', Calcharo, 99999, 20, WWRole.Default, WWRole.Default),
        Character('char_jiyan', Jiyan, 16, 20, WWRole.Default, WWRole.Default),
        Character('char_zhezhi', Zhezhi, 6, 20, WWRole.Default, WWRole.Default),
        Character('char_xiangliyao', Xiangliyao, 5, 20, WWRole.Default, WWRole.Default),
    ]
    highest_confidence = 0
    charinfo = None
    for char in char_list:
        feature = task.find_one(char.char_name, box=box, threshold=0.6)
        if feature:
            task.log_info(f'found char {char.char_name} {feature.confidence} {highest_confidence}')
        if feature and feature.confidence > highest_confidence:
            highest_confidence = feature.confidence
            charinfo = char
    if charinfo is not None:
        return char.cls(task, index, char.res_cd, char.echo_cd, char.role,char.full_con_swap_to)
    task.log_info(f'could not find char {charinfo} {highest_confidence}')
    has_cd = task.ocr(box=box)
    if has_cd and is_float(has_cd[0].name):
        task.log_info(f'found char {has_cd[0]} wait and reload')
        task.next_frame()
        return get_char_by_pos(task, box, index)
    if task.debug:
        task.screenshot(f'could not find char {index}')
    return BaseChar(task, index)
