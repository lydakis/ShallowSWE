import json
from pathlib import Path
_CACHE = {}
def get_feature_flags(path):
    key=str(Path(path).resolve())
    if key not in _CACHE: _CACHE[key]=json.loads(Path(path).read_text())
    return dict(_CACHE[key])
