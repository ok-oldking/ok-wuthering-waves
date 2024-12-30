if __name__ == '__main__':
    from config import config
    from ok import OK

    config = config
    config['ocr']['lib'] = 'paddleocr'
    ok = OK(config)
    ok.start()
