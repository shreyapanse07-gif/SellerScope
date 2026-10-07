"""Analyze Google Trends interest over time."""

from datetime import datetime, timedelta, timezone


def _timeline(response: dict) -> list:
    interest = response.get("interest_over_time") or {}
    if not isinstance(interest, dict):
        return []
    points = interest.get("timeline_data") or []
    return points if isinstance(points, list) else []


def _point_date(point: dict):
    timestamp = point.get("timestamp")
    if timestamp is not None:
        try:
            return datetime.fromtimestamp(float(timestamp), timezone.utc)
        except (ValueError, TypeError, OverflowError, OSError):
            pass
    label = point.get("date")
    if isinstance(label, str):
        for fmt in ("%b %d, %Y", "%b %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(label, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            parsed = datetime.fromisoformat(label.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except ValueError:
            pass
    return None


def _point_value(point: dict):
    values = point.get("values") or []
    if not values or not isinstance(values[0], dict):
        return None
    value = values[0].get("extracted_value", values[0].get("value"))
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def analyze_trend(trends_response: dict) -> dict:
    """Compare average interest in the most recent and prior three months."""
    data_points = []
    for point in _timeline(trends_response if isinstance(trends_response, dict) else {}):
        if not isinstance(point, dict):
            continue
        value = _point_value(point)
        date = _point_date(point)
        if value is None or date is None:
            continue
        data_points.append({"date": point.get("date", date.isoformat()), "value": value, "_date": date})

    default = {"direction": "stable", "change_pct": 0.0, "data_points": []}
    if not data_points:
        return default

    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(days=91)
    previous_start = now - timedelta(days=182)
    recent = [p["value"] for p in data_points if recent_start <= p["_date"] <= now]
    previous = [p["value"] for p in data_points if previous_start <= p["_date"] < recent_start]
    public_points = [{"date": p["date"], "value": p["value"]} for p in data_points]
    if not recent or not previous:
        return {**default, "data_points": public_points}

    previous_average = sum(previous) / len(previous)
    if previous_average == 0:
        change_pct = 0.0 if sum(recent) == 0 else 100.0
    else:
        change_pct = ((sum(recent) / len(recent) - previous_average) / previous_average) * 100
    direction = "rising" if change_pct > 15 else "falling" if change_pct < -15 else "stable"
    return {
        "direction": direction,
        "change_pct": round(change_pct, 2),
        "data_points": public_points,
    }
