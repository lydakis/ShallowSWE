from __future__ import annotations
import json
from pathlib import Path
def load_settings(path: str | Path) -> dict[str, object]:
    data = json.loads(Path(path).read_text())
    notifications = data["notifications"]
    return {"theme": data.get("theme", "light"), "notifications": {"email": bool(notifications["email"]), "sms": bool(notifications["sms"])}}
