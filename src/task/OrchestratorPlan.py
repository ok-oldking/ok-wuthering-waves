"""Independent ordered subsets; no personal paths or implicit steps."""
from copy import deepcopy
import uuid

PLAN_KEY = 'Task Plan'
CONTROL_STEPS = {'OpenGame', 'CloseGame', 'Wait', 'ExitScript'}
CATALOG = {
    'OpenGame': ('Open game', 'Use the native launcher; reuse an already running game.'),
    'CloseGame': ('Close game', 'Terminate only the selected verified game process, not the assistant.'),
    'Wait': ('Wait', 'Wait without a game frame; supports pause and stop.'),
    'ExitScript': ('Exit assistant', 'Exit the assistant, not the game. Must be the last step.'),
    'NightmareNest': ('Nightmare Nest', 'Daily capture or all configured nests, in a single step.'),
    'FarmStamina': ('Farm natural stamina', 'Use the configured farming plan, without reserve or recharge.'),
    'ClaimDaily': ('Claim daily rewards', 'Run the native daily reward claim at this position.'),
    'ClaimMail': ('Claim mail', 'Run the native mail claim.'),
    'ClaimBattlePass': ('Claim battle pass', 'Claim available rewards; do not purchase a pass.'),
    'WeeklyGarden': ('Weekly Garden', 'Skip when completed; otherwise run the native Garden task.'),
    'MergeEcho': ('Merge discarded Echoes', 'Run the native merge task; skip below its threshold.'),
    'Farm4CEcho': ('Farm boss Echoes', 'Reuse the native boss settings with a bounded repeat count.'),
}


def task_key(entry):
    return entry if isinstance(entry, str) else entry['task']


def entry_id(entry):
    return entry if isinstance(entry, str) else entry['id']


def new_entry(key):
    if key not in CATALOG:
        raise ValueError('Unknown task')
    if key not in CONTROL_STEPS:
        return key
    entry = {'task': key, 'id': 'control-' + uuid.uuid4().hex}
    if key == 'Wait':
        entry['seconds'] = 30
    return entry


def validate_plan(plan, allow_empty=False, execution=False):
    if not isinstance(plan, list):
        raise ValueError('Plan must be a list')
    if not plan and not allow_empty:
        raise ValueError('Add at least one step')
    ids, ordinary = set(), set()
    for entry in plan:
        if isinstance(entry, dict):
            if set(entry) - {'id', 'task', 'seconds'} or not isinstance(entry.get('task'), str) \
                    or entry['task'] not in CONTROL_STEPS \
                    or not isinstance(entry.get('id'), str) or not entry['id'].startswith('control-') \
                    or len(entry['id']) != 40 or any(c not in '0123456789abcdef' for c in entry['id'][8:]):
                raise ValueError('Invalid control step')
            if entry['task'] == 'Wait':
                if type(entry.get('seconds')) is not int or not 0 <= entry['seconds'] <= 86400:
                    raise ValueError('Wait seconds must be an integer from 0 to 86400')
            elif 'seconds' in entry:
                raise ValueError('This step has no wait parameter')
        elif not isinstance(entry, str) or entry not in CATALOG or entry in CONTROL_STEPS:
            raise ValueError('Unknown or invalid step')
        key, identity = task_key(entry), entry_id(entry)
        if identity in ids or (key not in CONTROL_STEPS and key in ordinary):
            raise ValueError('Business tasks may occur once; control steps need unique identities')
        ids.add(identity)
        ordinary.add(key)
    if execution and any(task_key(entry) == 'ExitScript' for entry in plan[:-1]):
        raise ValueError('Exit assistant must be the last step')
    return deepcopy(plan)


def boss_run_limit(value):
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError('Boss repeat count must be an integer from 1 to 100')
    return value


def executor_busy(executor, controller, own_task=None):
    if getattr(controller, 'starting', False):
        return True
    current = getattr(executor, 'current_task', None)
    if current is not None and not any(current is t for t in getattr(executor, 'trigger_tasks', [])):
        return True
    return any(getattr(t, 'enabled', False) for t in getattr(executor, 'onetime_tasks', []))


def transfer_plan(plan, key, source, target, index=None):
    result = validate_plan(plan, allow_empty=True)
    if source not in ('library', 'queue') or target not in ('library', 'queue'):
        raise ValueError('Invalid drag source/target')
    identities = [entry_id(entry) for entry in result]
    if source == 'library' and (key not in CATALOG or (key not in CONTROL_STEPS and key in identities)):
        raise ValueError('Unknown or duplicate task')
    if source == 'queue' and key not in identities:
        raise ValueError('Queue changed; retry the drag')
    if target == 'library':
        if source == 'queue':
            result.pop(identities.index(key))
        return result
    if index is None:
        index = len(result)
    if type(index) is not int or not 0 <= index <= len(result):
        raise ValueError('Invalid insertion index')
    if source == 'queue':
        previous = identities.index(key)
        entry = result.pop(previous)
        if previous < index:
            index -= 1
    else:
        entry = new_entry(key)
    result.insert(index, entry)
    return result
