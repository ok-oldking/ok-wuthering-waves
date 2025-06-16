if __name__ == '__main__':
    from config import config
    from ok import OK
    from ok import ConfigOption

    config = config
    del config['windows']['hwnd_class']
    del config['windows']['calculate_pc_exe_path']
    config['debug'] = True
    config['windows']['exe'] = ['chrome.exe', 'msedge.exe']
        'Color for Cloud Wuwa': True
        }, description='Setting for Cloud Wuwa', config_description={
        'Color for Cloud Wuwa': 'Color in Cloud Wuwa may be unreal. Turn on for adjust the color setting'
    config['global_configs'][3] = cloud_config_option
    ok = OK(config)
    ok.start()
