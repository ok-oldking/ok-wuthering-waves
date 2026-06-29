ZPR_ROTATION_ATTR = "_zani_phoebe_rover_rotation"

ZPR_PHASES = [
    ("Phoebe", "phoebe_long_e_r_e_q"),
    ("Zani", "zani_e_a"),
    ("HavocRover", "rover_r"),
    ("Zani", "zani_a"),
    ("Phoebe", "phoebe_aaa_dodge_aaa_dodge_aaa_z"),
    ("Zani", "zani_e"),
    ("Phoebe", "phoebe_aaa"),
    ("Zani", "zani_q_r_aaa"),
    ("HavocRover", "rover_a_z_a_e_q"),
    ("Zani", "zani_aaa"),
    ("Phoebe", "phoebe_z"),
    ("HavocRover", "rover_a_z_a"),
    ("Zani", "zani_aaa"),
    ("HavocRover", "rover_e"),
    ("Phoebe", "phoebe_intro"),
    ("HavocRover", "rover_r"),
    ("Zani", "zani_aa"),
    ("Phoebe", "phoebe_long_e_r_e_q"),
    ("Zani", "zani_a"),
    ("HavocRover", "rover_a_z_a"),
    ("Zani", "zani_r_e_a"),
    ("HavocRover", "rover_e"),
    ("Phoebe", "phoebe_aaa_dodge_z_dodge_aaa_f"),
    ("Zani", "zani_e_q_r_aaa"),
    ("HavocRover", "rover_e_q"),
    ("Phoebe", "phoebe_z"),
    ("HavocRover", "rover_a"),
    ("Zani", "zani_aaa"),
    ("HavocRover", "rover_a_z_a_r"),
    ("Phoebe", "phoebe_intro"),
    ("Zani", "zani_aaa"),
    ("HavocRover", "rover_e"),
    ("Phoebe", "phoebe_e_dodge_long_e_r_q"),
    ("Zani", "zani_aaa"),
    ("HavocRover", "rover_a_z_a"),
    ("Zani", "zani_r_e_a"),
]

ZPR_LOOP_START = 21

CQC_ROTATION_ATTR = "_cartethyia_qiuyuan_chisa_rotation"

CQC_PHASES = [
    ("Chisa", "cqc_chisa_e"),
    ("Cartethyia", "cqc_cart_e_r_e_e"),
    ("Chisa", "cqc_chisa_a"),
    ("Qiuyuan", "cqc_qiuyuan_aae_jump_a"),
    ("Chisa", "cqc_chisa_a3"),
    ("Cartethyia", "cqc_cart_a3_a4"),
    ("Chisa", "cqc_chisa_a4"),
    ("Qiuyuan", "cqc_qiuyuan_aae_jump_z"),
    ("Cartethyia", "cqc_cart_a5_r1"),
    ("Chisa", "cqc_chisa_r_e"),
    ("Cartethyia", "cqc_cart_a3"),
    ("Qiuyuan", "cqc_qiuyuan_r"),
    ("Chisa", "cqc_chisa_z2_dodge_a3"),
    ("Cartethyia", "cqc_cart_a4_z_q"),
    ("Chisa", "cqc_chisa_a4"),
    ("Cartethyia", "cqc_cart_drop_a_z_e3_a_e_e_r"),
]

CQC_LOOP_START = 0


def _find_char(task, char_cls):
    if hasattr(task, "has_char"):
        return task.has_char(char_cls)
    return next((char for char in getattr(task, "chars", []) if isinstance(char, char_cls)), None)


def is_zani_phoebe_rover_team(task):
    from src.char.BaseChar import Elements
    from src.char.HavocRover import HavocRover
    from src.char.Phoebe import Phoebe
    from src.char.Zani import Zani

    rover = _find_char(task, HavocRover)
    return bool(
        _find_char(task, Zani)
        and _find_char(task, Phoebe)
        and rover
        and rover.ring_index in (-1, Elements.SPECTRO)
    )


def ensure_zani_phoebe_rover_rotation(task):
    if not is_zani_phoebe_rover_team(task):
        return None
    rotation = getattr(task, ZPR_ROTATION_ATTR, None)
    if rotation is None:
        rotation = {"phase": 0}
        setattr(task, ZPR_ROTATION_ATTR, rotation)
    return rotation


def get_zpr_phase(task):
    rotation = ensure_zani_phoebe_rover_rotation(task)
    if rotation is None:
        return None
    phase = rotation.get("phase", 0)
    if phase < 0 or phase >= len(ZPR_PHASES):
        phase = ZPR_LOOP_START
        rotation["phase"] = phase
    return ZPR_PHASES[phase]


def advance_zpr_phase(task):
    rotation = ensure_zani_phoebe_rover_rotation(task)
    if rotation is None:
        return
    phase = rotation.get("phase", 0) + 1
    if phase >= len(ZPR_PHASES):
        phase = ZPR_LOOP_START
    rotation["phase"] = phase


def is_cartethyia_qiuyuan_chisa_team(task):
    from src.char.Cartethyia import Cartethyia
    from src.char.Chisa import Chisa
    from src.char.Qiuyuan import Qiuyuan

    return bool(
        _find_char(task, Cartethyia)
        and _find_char(task, Qiuyuan)
        and _find_char(task, Chisa)
    )


def ensure_cartethyia_qiuyuan_chisa_rotation(task):
    if not is_cartethyia_qiuyuan_chisa_team(task):
        return None
    rotation = getattr(task, CQC_ROTATION_ATTR, None)
    if rotation is None:
        rotation = {"phase": 0}
        setattr(task, CQC_ROTATION_ATTR, rotation)
    return rotation


def get_cqc_phase(task):
    rotation = ensure_cartethyia_qiuyuan_chisa_rotation(task)
    if rotation is None:
        return None
    phase = rotation.get("phase", 0)
    if phase < 0 or phase >= len(CQC_PHASES):
        phase = CQC_LOOP_START
        rotation["phase"] = phase
    return CQC_PHASES[phase]


def advance_cqc_phase(task):
    rotation = ensure_cartethyia_qiuyuan_chisa_rotation(task)
    if rotation is None:
        return
    phase = rotation.get("phase", 0) + 1
    if phase >= len(CQC_PHASES):
        phase = CQC_LOOP_START
    rotation["phase"] = phase
