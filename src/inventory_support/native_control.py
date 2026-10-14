from contextlib import contextmanager
import time
def wait_seconds(task, seconds, clock=time.monotonic):
    from ok import TaskDisabledException
    remaining = float(seconds)
    previous = clock()
    was_paused = bool(task.paused or task.executor.paused)
    while True:
        if task.executor.exit_event.is_set() or not task.enabled:
            raise TaskDisabledException()
        paused = bool(task.paused or task.executor.paused)
        now = clock()
        if not paused and (not was_paused):
            remaining -= max(0, now - previous)
        previous, was_paused = (now, paused)
        if remaining <= 0 and (not paused):
            return
        task.executor.exit_event.wait(min(0.1, max(0.01, remaining)))

def natural_reading(reading):
    current, _reserve, _total = reading
    if type(current) is not int or current < 0:
        raise RuntimeError('Natural stamina reading unavailable; no resource confirmation')
    return (current, 0, current)

@contextmanager
def natural_only(task, *, single=False, read_stamina=None):
    if read_stamina is not None and (not callable(read_stamina)):
        raise ValueError('Natural stamina reader must be callable')
    saved = {name: task.__dict__.get(name) for name in ('get_stamina', 'use_stamina')}
    present = {name: name in task.__dict__ for name in saved}
    native_read = task.get_stamina if read_stamina is None else read_stamina

    def read():
        return natural_reading(native_read())

    def use(once=60, must_use=0):
        if type(once) is not int or once <= 0:
            raise ValueError('Invalid stamina cost')
        task.sleep(1)
        current, _, _ = read()
        if current < once:
            task.back(after_sleep=1)
            raise RuntimeError('Natural stamina insufficient before reward claim')
        used = 2 * once if not single and current >= 2 * once else once
        if used == 2 * once:
            task.click_dialog_right_button()
        else:
            task.click_dialog_left_button()
        if task.wait_feature('gem_add_stamina', horizontal_variance=0.4, vertical_variance=0.05, time_out=2, settle_time=0.5):
            task.back(after_sleep=1)
            raise RuntimeError('Unexpected stamina refill dialog; refused reserve/purchase')
        return (current - used >= once, used)
    task.get_stamina, task.use_stamina = (read, use)
    try:
        yield
    finally:
        for name in saved:
            if present[name]:
                setattr(task, name, saved[name])
            else:
                task.__dict__.pop(name, None)

@contextmanager
def counted_natural(task, count, on_claim):
    """Only single natural-stamina rewards, never more than the requested count."""
    if type(count) is not int or count < 1:
        raise ValueError('Invalid remaining run count')
    with natural_only(task, single=True):
        natural_read, natural_use = (task.get_stamina, task.use_stamina)
        state = {'attempts': 0, 'used': 0}

        def read():
            current, _, _ = natural_read()
            limited = min(current, (count - state['attempts']) * task.stamina_once)
            return (limited, 0, limited)

        def use(once=60, must_use=0):
            if state['attempts'] >= count or once != task.stamina_once:
                raise RuntimeError('体力目标次数或单次消耗越界，拒绝领奖')
            current, _, _ = natural_read()
            on_claim(state['attempts'] + 1)
            _, used = natural_use(once=once, must_use=0)
            if used != once:
                raise RuntimeError('原生领奖消耗与单次计划不符')
            state['attempts'] += 1
            state['used'] += used
            return (state['attempts'] < count and current - used >= once, used)
        task.get_stamina, task.use_stamina = (read, use)
        try:
            yield state
        finally:
            task.get_stamina, task.use_stamina = (natural_read, natural_use)
