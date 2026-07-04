def parse_retry_row(row):
    return {"job_id": row["job_id"], "attempts": int(row["attempts"]), "delay_seconds": int(row["delay_seconds"]), "mode": row.get("mode", "standard") or "standard"}
