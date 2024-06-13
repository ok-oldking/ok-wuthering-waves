def get_char_by_pos(task, box, index):
    from src.char.Verina import Verina
    from src.char.Yinlin import Yinlin
    from src.char.Taoqi import Taoqi
    from src.char.BaseChar import BaseChar
    from src.char.HavocRover import HavocRover
    char_dict = {
        'char_yinlin': {'cls': Yinlin, 'res_cd': 12, 'echo_cd': 15},
        'char_verina': {'cls': Verina, 'res_cd': 12, 'echo_cd': 20},
        'char_taoqi': {'cls': Taoqi, 'res_cd': 15, 'echo_cd': 20},
        'char_rover': {'cls': HavocRover, 'res_cd': 12, 'echo_cd': 20}
    }

    for char_name, char_info in char_dict.items():
        feature = task.find_feature(char_name, box=box, threshold=0.9)
        if feature:
            task.log_info(f'found char {char_name}')
            return char_info.get('cls')(task, index, char_info.get('res_cd'))
    task.log_info(f'could not find char')
    return BaseChar(task, index)
