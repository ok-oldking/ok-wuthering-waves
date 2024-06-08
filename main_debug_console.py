from config import config
from ok.OK import OK

config = config
config['debug'] = True
config['use_gui'] = False
config['onetime_tasks'][1].enable()
ok = OK(config)
ok.start()
