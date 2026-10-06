if __name__ == '__main__':
    from src.startup import close_system_informer

    close_system_informer()

    from config import config
    from ok import OK

    config = config
    ok = OK(config)
    ok.start()
