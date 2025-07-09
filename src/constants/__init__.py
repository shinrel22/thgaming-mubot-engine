import os
import config

TMP_DIR = os.path.join(config.ROOT_DIR, 'tmp')
os.makedirs(TMP_DIR, exist_ok=True)

DATA_DIR = os.path.join(config.ROOT_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

LOG_DIR = os.path.join(config.ROOT_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

