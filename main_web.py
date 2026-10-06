if __name__ == "__main__":
    from src.startup import close_system_informer

    close_system_informer()

    from config import config
    from ok import OK

    config = config
    config["gui"] = {
        "type": "web",
        "launch_mode": "pywebview",  # default
    }
    ok = OK(config)
    ok.start()
