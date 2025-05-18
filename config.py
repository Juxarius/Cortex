from pathlib import Path
import json

CONFIG_FILE_PATH = Path(__file__).parent / 'config.json'

with open(CONFIG_FILE_PATH, 'r') as f:
    config = json.load(f)

