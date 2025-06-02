if __name__ == '__main__':
    from config import config
    from ok import OK

    config = config
    del config["ocr"]["params"]["Global.with_openvino"]
    config["profile_name"] = "direct-ml"

    ok = OK(config)
    ok.start()
