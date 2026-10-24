import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path


MULTI_ACCOUNT_TASKS = {
    ('src.task.MultiAccountDailyTask', 'MultiAccountDailyTask'),
    ('src.task.MultiAccountConfigTask', 'MultiAccountConfigTask'),
}


def account_key_from_ocr(text):
    return text.replace('*', '').strip() if text else None


def display_account(key):
    return key


def task_reference(task):
    return {'module': type(task).__module__, 'class': type(task).__name__}


def collect_available_tasks(executor):
    return [task for task in executor.onetime_tasks
            if type(task).__module__.startswith('src.task.') and task.visible]


def resolve_task(executor, reference):
    if reference is None:
        return None
    for task in collect_available_tasks(executor):
        if task_reference(task) == reference:
            return task
    raise ValueError(f"任务未注册或已移除：{reference['module']}.{reference['class']}")


def validate_accounts(accounts, executor=None):
    if not isinstance(accounts, list):
        raise ValueError('accounts 必须是账号列表。')
    seen = set()
    for account in accounts:
        if not isinstance(account, dict):
            raise ValueError('账号配置必须是对象。')
        key = account.get('account_key')
        if (not isinstance(key, str) or not key.strip() or key != key.strip()
                or '*' in key or any(ord(char) < 32 for char in key)):
            raise ValueError('账号标识请填写登录列表文本去掉所有 * 后的剩余部分，不可为空或包含首尾空格。')
        if key in seen:
            raise ValueError(f'账号标识 {key} 重复，请修改后再保存。')
        seen.add(key)
        if not isinstance(account.get('enabled', True), bool):
            raise ValueError(f'账号 {key} 的启用状态必须是布尔值。')
        if 'task' not in account:
            raise ValueError(f'账号 {key} 缺少执行任务字段，请选择任务或“无”。')
        reference = account.get('task')
        if reference is not None:
            if (not isinstance(reference, dict)
                    or set(reference) != {'module', 'class'}
                    or not all(isinstance(value, str) for value in reference.values())):
                raise ValueError('任务标识必须包含 module 和 class。')
            if (reference['module'], reference['class']) in MULTI_ACCOUNT_TASKS:
                raise ValueError('不允许在“多账号配置”中选择多账号执行器自身或旧多账号任务。')
            if executor is not None and account.get('enabled', True):
                resolve_task(executor, reference)
        if not isinstance(account.get('config'), dict):
            raise ValueError(f'账号 {key} 的任务配置必须是对象。')


class MultiAccountConfigStore:
    def __init__(self, folder='configs'):
        self.path = Path(folder) / 'MultiAccountConfig.json'
        self.results_path = Path(folder) / 'MultiAccountResults.json'

    def load_results(self):
        if not self.results_path.exists():
            return {}
        with self.results_path.open(encoding='utf-8') as stream:
            results = json.load(stream)
        if not isinstance(results, dict):
            raise ValueError('账号运行记录必须是对象。')
        if any(not isinstance(result, dict)
               or result.get('status') not in {'success', 'failed', 'cancelled'}
               or not isinstance(result.get('finished_at'), str)
               for result in results.values()):
            raise ValueError('账号运行记录格式无效。')
        return results

    def record_result(self, account, status, message=''):
        results = self.load_results()
        results[account['account_key']] = {
            'status': status,
            'finished_at': datetime.now().astimezone().isoformat(timespec='seconds'),
            'task': deepcopy(account['task']),
            'message': message,
        }
        # Keep execution history separate so saving UI drafts cannot overwrite it.
        self._write_json(self.results_path, results)

    def load(self):
        if not self.path.exists():
            return []
        with self.path.open(encoding='utf-8') as stream:
            document = json.load(stream)
        if not isinstance(document, dict) or 'accounts' not in document:
            raise ValueError('多账号配置缺少 accounts 列表。')
        accounts = document['accounts']
        validate_accounts(accounts)
        return deepcopy(accounts)

    def save(self, accounts, executor=None):
        validate_accounts(accounts, executor)
        self._write_json(self.path, {'accounts': accounts})

    @staticmethod
    def _write_json(path, document):
        content = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Replace only after a full write; failed saves keep the previous file.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                             prefix='.MultiAccountConfig-', suffix='.tmp',
                                             delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
