"""Sequential steps with visible results; cancellation always propagates."""
import time
from ok import Logger, TaskDisabledException

logger = Logger.get_logger(__name__)


class StepPipeline:
    STEP_RETRY_KEY = 'Step Retry Count'
    STEP_BUDGET_KEY = 'Step Time Budget (s)'

    def pipeline_reset(self):
        self.step_status, self.step_elapsed = {}, {}
        self._pipeline_failed_required, self._pipeline_failed_optional = [], []

    def _set_status(self, name, status):
        self.step_status[name] = status
        self.info_set(f'Step: {name}', status)

    def step(self, name, func, *args, required=True, **kwargs):
        # Never blindly retry a resource-consuming operation.
        self._set_status(name, 'running')
        start = time.monotonic()
        try:
            func(*args, **kwargs)
        except TaskDisabledException:
            raise
        except Exception as exc:
            self.log_error(f'step {name} failed', exc)
            self.screenshot(f'step_{name}')
            self._set_status(name, 'failed')
            failures = self._pipeline_failed_required if required else self._pipeline_failed_optional
            failures.append((name, str(exc)))
            return False
        else:
            self._set_status(name, 'success')
            return True
        finally:
            self.step_elapsed[name] = round(time.monotonic() - start, 1)

    def pipeline_finish(self, message='Selected tasks completed'):
        summary = ', '.join(f'{name}={status}' for name, status in self.step_status.items())
        self.info_set('Pipeline Result', summary)
        logger.info(f'pipeline finished: {summary}')
        if self._pipeline_failed_optional:
            logger.warning(f'optional steps failed: {self._pipeline_failed_optional}')
        if self._pipeline_failed_required:
            detail = '; '.join(f'{name}: {error}' for name, error in self._pipeline_failed_required)
            raise RuntimeError(f'pipeline finished with failed steps: {detail}')
        self.log_info(message, notify=True)
