from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Pure pixel geometry for a calibrated native bag scroll track; no input.

Only an unambiguous, bounded thumb is accepted. Grid animations, selected item
glows and changing world backgrounds never establish page identity or stock.
"""
import hashlib
import json

def validate(value):
    if not isinstance(value, dict) or set(value) != {'roi', 'columns', 'min_channel', 'min_span', 'max_span', 'top_max_offset'}:
        raise ValueError('Exact native scrollbar calibration required')
    r = value['roi']
    if not isinstance(r, list) or len(r) != 4 or any((type(n) is not int for n in r)) or (r[0] < 0) or (r[1] < 0) or (r[2] < 3) or (r[3] < 10) or (r[0] + r[2] > 1920) or (r[1] + r[3] > 1080):
        raise ValueError('Scrollbar ROI outside canonical frame')
    columns = value['columns']
    if not isinstance(columns, list) or len(columns) != 2 or any((type(n) is not int for n in columns)) or (not 0 <= columns[0] < columns[1] <= r[2]) or (columns[1] - columns[0] < 2):
        raise ValueError('Invalid calibrated scrollbar sampling columns')
    if type(value['min_channel']) is not int or not 1 <= value['min_channel'] <= 255 or type(value['min_span']) is not int or (type(value['max_span']) is not int) or (not 2 <= value['min_span'] <= value['max_span'] < r[3]):
        raise ValueError('Invalid native thumb color/span bounds')
    if type(value['top_max_offset']) is not int or not 0 <= value['top_max_offset'] <= 30:
        raise ValueError('Exact natively evidenced top tolerance required')
    return value

def thumb(crop, value):
    import numpy as np
    validate(value)
    if getattr(crop, 'dtype', None) != np.uint8 or getattr(crop, 'shape', None) != (value['roi'][3], value['roi'][2], 3):
        raise ValueError('Scrollbar crop shape or pixel type changed')
    left, right = value['columns']
    rows = np.flatnonzero((crop[:, left:right].min(axis=2) >= value['min_channel']).all(axis=1))
    starts = [0] + (np.flatnonzero(np.diff(rows) > 1) + 1).tolist() if len(rows) else []
    ends = starts[1:] + [len(rows)]
    runs = [(int(rows[s]), int(rows[e - 1]) + 1) for s, e in zip(starts, ends)]
    valid = [run for run in runs if value['min_span'] <= run[1] - run[0] <= value['max_span']]
    if len(valid) != 1 or any((end - start >= value['min_span'] for start, end in runs if (start, end) not in valid)):
        raise RuntimeError(f"Native thumb missing, ambiguous or span changed; runs={runs[:8]}; run_count={len(runs)}; span_bounds=({value['min_span']},{value['max_span']})")
    return valid[0]

def signature(position):
    if not isinstance(position, tuple) or len(position) != 2 or any((type(n) is not int for n in position)) or (not 0 <= position[0] < position[1]):
        raise ValueError('Exact thumb position required')
    return hashlib.sha256(json.dumps(position, separators=(',', ':')).encode('ascii')).hexdigest()

def track_point(position, value, direction):
    validate(value)
    signature(position)
    if type(direction) is not int or direction not in (-1, 1):
        raise ValueError('Expected a single bounded scroll direction')
    start, end = position
    x, y, w, h = value['roi']
    if end > h:
        raise ValueError('Thumb outside calibrated track')
    offset = max(1, start - 10) if direction < 0 else min(h - 2, end + 10)
    return (x + (value['columns'][0] + value['columns'][1] - 1) // 2, y + offset)

def at_top(position, value):
    validate(value)
    signature(position)
    if position[1] > value['roi'][3]:
        raise ValueError('Thumb outside calibrated track')
    return position[0] <= value['top_max_offset']
