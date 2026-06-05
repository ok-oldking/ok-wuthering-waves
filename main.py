import os
if 'PATH' not in os.environ:
    os.environ['PATH'] = r'C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem'

if __name__ == '__main__':
    from config import config
    from ok import OK

    config = config
    ok = OK(config)
    ok.start()