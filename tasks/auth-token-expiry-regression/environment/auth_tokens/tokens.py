from datetime import datetime, timezone
def is_expired(token, now=None):
    current = now or datetime.now(timezone.utc)
    return float(token["expires_at"]) <= current.timestamp()
def can_login(token, now=None): return bool(token.get("user_id")) and not is_expired(token, now)
