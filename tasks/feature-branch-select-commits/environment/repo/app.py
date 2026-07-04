def should_retry(status_code):
    return status_code >= 500
