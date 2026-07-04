from vendor_notifier import notify_user

def send_alert(user_id, subject, body):
    return notify_user(user_id=user_id, title=subject, message=body)
