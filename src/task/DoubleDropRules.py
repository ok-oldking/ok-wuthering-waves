import re
from dataclasses import dataclass

DOUBLE_DROP_RULES = 'Double Drop Rules'
DOUBLE_DROP_SIMULATION_COUNT = 'Double Drop Simulation Count'
DOUBLE_DROP_SIMULATION_MATERIAL = 'Double Drop Simulation Material'
DOUBLE_DROP_FORGERY_COUNT = 'Double Drop Forgery Count'
DOUBLE_DROP_FORGERY_NUMBER = 'Double Drop Forgery Number'
DOUBLE_DROP_TACET_COUNT = 'Double Drop Tacet Count'
DOUBLE_DROP_TACET_NUMBER = 'Double Drop Tacet Number'

SIMULATION = 'Simulation Challenge'
FORGERY = 'Forgery Challenge'
TACET = 'Tacet Suppression'

MODE_ORDER = (SIMULATION, FORGERY, TACET)
MAX_DOMAIN_RUNS = 3
MAX_TACET_RUNS = 3
SIMULATION_MATERIALS = ('Resonator EXP', 'Weapon EXP', 'Shell Credit')

DOUBLE_DROP_DEFAULTS = {
    DOUBLE_DROP_RULES: False,
    DOUBLE_DROP_SIMULATION_COUNT: 0,
    DOUBLE_DROP_SIMULATION_MATERIAL: 'Shell Credit',
    DOUBLE_DROP_FORGERY_COUNT: 0,
    DOUBLE_DROP_FORGERY_NUMBER: 1,
    DOUBLE_DROP_TACET_COUNT: 0,
    DOUBLE_DROP_TACET_NUMBER: 1,
}

DOUBLE_DROP_CONFIG_KEYS = (
    DOUBLE_DROP_SIMULATION_COUNT,
    DOUBLE_DROP_SIMULATION_MATERIAL,
    DOUBLE_DROP_FORGERY_COUNT,
    DOUBLE_DROP_FORGERY_NUMBER,
    DOUBLE_DROP_TACET_COUNT,
    DOUBLE_DROP_TACET_NUMBER,
)

# Fixed badge slots on the in-game Material Acquisition page. Values are
# relative to the game frame so they scale with 16:9 resolutions.
DOUBLE_DROP_BADGE_ROIS = {
    SIMULATION: (0.300, 0.215, 0.365, 0.260),
    FORGERY: (0.300, 0.326, 0.365, 0.371),
    TACET: (0.300, 0.660, 0.365, 0.705),
}

UP_GOLD = {'r': (180, 255), 'g': (120, 235), 'b': (0, 130)}
UP_MIN_GOLD_RATIO = 0.002
UP_PATTERN = re.compile(r'^\s*UP\s*$', re.IGNORECASE)

_COUNT_LIMITS = {
    DOUBLE_DROP_SIMULATION_COUNT: (DOUBLE_DROP_FORGERY_COUNT, MAX_DOMAIN_RUNS),
    DOUBLE_DROP_FORGERY_COUNT: (DOUBLE_DROP_SIMULATION_COUNT, MAX_DOMAIN_RUNS),
    DOUBLE_DROP_TACET_COUNT: (None, MAX_TACET_RUNS),
}
_CONTENT_NUMBERS = (DOUBLE_DROP_FORGERY_NUMBER, DOUBLE_DROP_TACET_NUMBER)


@dataclass(frozen=True)
class DoubleDropPlanItem:
    mode: str
    count: int
    config: dict


def is_non_negative_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_double_drop_config(key, value, config):
    """Return (message msgid, format params) for an invalid value, or None when it is valid."""
    if key in _COUNT_LIMITS:
        if not is_non_negative_int(value):
            return '{key} must be a non-negative integer.', {'key': key}
        other_key, limit = _COUNT_LIMITS[key]
        other = (config or {}).get(other_key, 0) if other_key else 0
        if value > limit and other_key is None:
            return '{key} cannot exceed {limit}.', {'key': key, 'limit': limit}
        if value > limit or (is_non_negative_int(other) and value + other > limit):
            return '{key} and {other} cannot exceed {limit} in total.', {'key': key, 'other': other_key, 'limit': limit}
        return None
    if key in _CONTENT_NUMBERS:
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            return '{key} must be a positive integer.', {'key': key}
        return None
    if key == DOUBLE_DROP_SIMULATION_MATERIAL and value not in SIMULATION_MATERIALS:
        return '{key} must be one of {options}.', {'key': key, 'options': SIMULATION_MATERIALS}
    return None


def _valid_count(value, limit):
    if not is_non_negative_int(value) or value > limit:
        return 0
    return value


def build_double_drop_plan(config, activities):
    """Build an ordered plan from the activity flags and saved rule values."""
    config = config or {}
    activities = activities or {}
    plan = []
    simulation_count = _valid_count(config.get(DOUBLE_DROP_SIMULATION_COUNT, 0), MAX_DOMAIN_RUNS)
    forgery_count = _valid_count(config.get(DOUBLE_DROP_FORGERY_COUNT, 0), MAX_DOMAIN_RUNS)
    if simulation_count + forgery_count > MAX_DOMAIN_RUNS:
        raise ValueError(f'Simulation and Forgery counts cannot exceed {MAX_DOMAIN_RUNS} in total.')
    if activities.get(SIMULATION) and simulation_count > 0:
        material = config.get(DOUBLE_DROP_SIMULATION_MATERIAL, 'Shell Credit')
        if material not in SIMULATION_MATERIALS:
            material = 'Shell Credit'
        plan.append(DoubleDropPlanItem(SIMULATION, simulation_count, {'Material Selection': material}))

    if activities.get(FORGERY) and forgery_count > 0:
        number = config.get(DOUBLE_DROP_FORGERY_NUMBER, 1)
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            number = 1
        plan.append(DoubleDropPlanItem(FORGERY, forgery_count, {'Which Forgery Challenge to Farm': number}))

    tacet_count = _valid_count(config.get(DOUBLE_DROP_TACET_COUNT, 0), MAX_TACET_RUNS)
    if activities.get(TACET) and tacet_count > 0:
        number = config.get(DOUBLE_DROP_TACET_NUMBER, 1)
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            number = 1
        plan.append(DoubleDropPlanItem(TACET, tacet_count, {'Which Tacet Suppression to Farm': number}))
    return plan


def is_up_badge(ocr_names, gold_ratio):
    """The UP marker counts only when both OCR text and its gold glow are present."""
    return bool(ocr_names) and gold_ratio >= UP_MIN_GOLD_RATIO and any(
        UP_PATTERN.match(name or '') for name in ocr_names)
