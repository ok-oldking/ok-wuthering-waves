import os
if 'PATH' not in os.environ:
    os.environ['PATH'] = os.defpath

if __name__ == '__main__':
    from config import config
    from ok import OK

    config = config
    ok = OK(config)
    ok.start()