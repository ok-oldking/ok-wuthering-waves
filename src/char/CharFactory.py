def get_char_by_pos(task, box, index):
    from src.char.Verina import Verina
    from src.char.Yinlin import Yinlin
    from src.char.Taoqi import Taoqi
    char_dict = {
        'char_yinlin': Yinlin,
        'char_verina': Verina,
        'char_taoqi': Taoqi
    }

    for char_name, char in char_dict.items():
        feature = task.find_feature(char_name, box=box, threshold=0.9)
        if feature:
            task.log_info(f'found char {char_name}')
            return char(task, index)
    task.log_info(f'could not find char')
    return None
