import psutil


def close_system_informer():
    for process in psutil.process_iter(['name']):
        try:
            if (process.info['name'] or '').casefold() != 'systeminformer.exe':
                continue
            process.kill()
            process.wait(timeout=5)
        except psutil.NoSuchProcess:
            continue
        except (psutil.AccessDenied, psutil.TimeoutExpired) as error:
            raise RuntimeError(
                f'Unable to close SystemInformer.exe (PID {process.pid}). '
                'Run OK-WW as administrator or close System Informer manually before starting.'
            ) from error
