if __name__ == '__main__':
    from config import config
    from ok.OK import OK

    config = config
    config['ocr']['lib'] = 'paddleocr'
    ok = OK(config)
    ok.start()
