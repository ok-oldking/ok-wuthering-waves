"""Opt-in daily farming from current stamina, without reserve or recharge."""
from contextlib import contextmanager


def natural_reading(reading):
    current, _reserve, _total = reading
    if type(current) is not int or current < 0:
        raise RuntimeError('Natural stamina reading unavailable; no resource confirmation')
    return current, 0, current


@contextmanager
def natural_only(task):
    saved = {name: task.__dict__.get(name) for name in ('get_stamina', 'use_stamina')}
    present = {name: name in task.__dict__ for name in saved}
    native_read = task.get_stamina

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
        used = 2 * once if current >= 2 * once else once
        if used == 2 * once:
            task.click_dialog_right_button()
        else:
            task.click_dialog_left_button()
        if task.wait_feature('gem_add_stamina', horizontal_variance=0.4,
                             vertical_variance=0.05, time_out=2, settle_time=0.5):
            task.back(after_sleep=1)
            raise RuntimeError('Unexpected stamina refill dialog; refused reserve/purchase')
        return current - used >= once, used

    task.get_stamina, task.use_stamina = read, use
    try:
        yield
    finally:
        for name in saved:
            if present[name]:
                setattr(task, name, saved[name])
            else:
                task.__dict__.pop(name, None)


def farm_current_stamina(parent):
    from src.task.TacetTask import TacetTask
    from src.task.ForgeryTask import ForgeryTask
    from src.task.SimulationTask import SimulationTask
    target = parent.config.get('Which to Farm', parent.support_tasks[0])
    choices = {parent.support_tasks[0]: (TacetTask, 'farm_tacet'),
               parent.support_tasks[1]: (ForgeryTask, 'farm_forgery'),
               parent.support_tasks[2]: (SimulationTask, 'farm_simulation')}
    if target not in choices:
        raise ValueError('Unknown configured farming plan')
    cls, method = choices[target]
    child = parent.get_task_by_class(cls)
    with natural_only(child):
        getattr(child, method)(daily=False, used_stamina=0, config=parent.config)
        child.ensure_main(time_out=60)
        child.openF2Book('gray_book_boss')
        remaining, _, _ = child.get_stamina()
        child.back(after_sleep=1)
        if remaining >= child.stamina_once:
            raise RuntimeError('Farm returned while natural stamina still permits the configured plan')
        parent.log_info(f'NaturalStaminaPlan/v1 completed current={remaining} cost={child.stamina_once}')
