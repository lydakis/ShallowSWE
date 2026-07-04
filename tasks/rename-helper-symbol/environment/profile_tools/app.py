from .helpers import format_user_key

def describe_user(raw):
    return f"user:{format_user_key(raw)}"
