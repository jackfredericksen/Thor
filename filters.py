# filters.py

def passes_filters(token_info):
    try:
        volume = float(token_info.get("daily_volume_usd", 0))
        age_hours = float(token_info.get("age_hours", 9999))
        holders = int(token_info.get("holder_count", 0))
        return volume < 1_500_000 and age_hours < 72 and holders > 7_500
    except Exception:
        return False
