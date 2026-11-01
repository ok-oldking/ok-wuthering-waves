import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from ok import og


def _tr(message):
    return og.app.tr(message) if og.app else message


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
    raise ValueError(_tr('Task is not registered or has been removed: {module}.{class_name}').format(module=reference['module'], class_name=reference['class']))


def validate_accounts(accounts, executor=None):
    if not isinstance(accounts, list):
        raise ValueError(_tr('accounts must be a list of accounts.'))
    seen = set()
    for account in accounts:
        if not isinstance(account, dict):
            raise ValueError(_tr('Account configuration must be an object.'))
        key = account.get('account_key')
        if (not isinstance(key, str) or not key.strip() or key != key.strip()
                or '*' in key or any(ord(char) < 32 for char in key)):
            raise ValueError(_tr('Use the login list text with all * removed as the account ID; it must not be empty or have leading or trailing spaces.'))
        if key in seen:
            raise ValueError(_tr('Duplicate account ID {account}; change it before saving.').format(account=key))
        seen.add(key)
        if not isinstance(account.get('enabled', True), bool):
            raise ValueError(_tr('Enabled state for account {account} must be a boolean.').format(account=key))
        if 'task' not in account:
            raise ValueError(_tr('Account {account} is missing its task field; select a task or None.').format(account=key))
        reference = account.get('task')
        if reference is not None:
            if (not isinstance(reference, dict)
                    or set(reference) != {'module', 'class'}
                    or not all(isinstance(value, str) for value in reference.values())):
                raise ValueError(_tr('Task reference must contain module and class.'))
            if (reference['module'], reference['class']) in MULTI_ACCOUNT_TASKS:
                raise ValueError(_tr('Multi-account configuration cannot select itself or the legacy multi-account task.'))
            if executor is not None and account.get('enabled', True):
                resolve_task(executor, reference)
        if not isinstance(account.get('config'), dict):
            raise ValueError(_tr('Task configuration for account {account} must be an object.').format(account=key))


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
            raise ValueError(_tr('Account run history must be an object.'))
        if any(not isinstance(result, dict)
               or result.get('status') not in {'success', 'failed', 'cancelled'}
               or not isinstance(result.get('finished_at'), str)
               for result in results.values()):
            raise ValueError(_tr('Invalid account run history format.'))
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
            raise ValueError(_tr('Multi-account configuration is missing the accounts list.'))
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
