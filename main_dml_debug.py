if __name__ == '__main__':
    from config import config
    from ok import OK

    config = config
    config["ocr"]["params"]["use_openvino"] = False
    config["profile_name"] = "direct-ml"
    config['debug'] = True

    ok = OK(config)
    ok.start()
