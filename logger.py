from pathlib import Path
import logging
import os
from datetime import datetime as dt
from config import config


LOG_FILE_PATH = Path(__file__).parent / 'logs' / 'cortex.log'

# Logging
def rotate_logs() -> None:
    if os.path.exists(LOG_FILE_PATH):
        os.rename(LOG_FILE_PATH, f'{LOG_FILE_PATH}.{dt.now().strftime("%Y-%m-%d_%H-%M-%S")}')

rotate_logs()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(LOG_FILE_PATH, 'a', 'utf-8')
handler.setLevel(logging.getLevelNamesMapping()[config['logLevel']])
handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
logger.addHandler(handler)
debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical