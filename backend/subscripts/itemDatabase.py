"""Read the bundled item catalogue; no Unity extraction dependency needed."""
from pathlib import Path
import json, os

def load_item_database():
    path=Path(os.environ['VIKINGEDITOR_DATA_DIR'])/'valheim_items.json'
    return {int(key):item['prefab'] for key,item in json.loads(path.read_text(encoding='utf-8'))['items'].items()}
