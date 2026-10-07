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


def detect_seasonal_pattern(data_points: list[dict]) -> str | None:
    """Identify a recurring annual peak that is expected within about 60 days."""
    dated_points = []
    for point in data_points:
        if not isinstance(point, dict) or not isinstance(point.get("date"), str):
            continue
        date = _point_date(point)
        try:
            value = float(point.get("value"))
        except (ValueError, TypeError):
            continue
        if date is not None:
            dated_points.append((date, value))

    years = {date.year for date, _ in dated_points}
    if len(years) < 2:
        return None

    overall_average = sum(value for _, value in dated_points) / len(dated_points)
    if overall_average <= 0:
        return None

    now = datetime.now(timezone.utc)
    # Find the actual highest observation for each year first. Use those
    # points to test whether a peak recurs near the same calendar date.
    yearly_peaks = []
    for year in years:
        observations = [(date, value) for date, value in dated_points if date.year == year]
        yearly_peaks.append(max(observations, key=lambda item: item[1]))

    best = None
    for candidate_date, _ in yearly_peaks:
        candidate_day = candidate_date.timetuple().tm_yday
        matching = [
            (date, value)
            for date, value in yearly_peaks
            if min(
                abs(date.timetuple().tm_yday - candidate_day),
                366 - abs(date.timetuple().tm_yday - candidate_day),
            ) <= 21
        ]
        if len(matching) < 2:
            continue
        average = sum(value for _, value in matching) / len(matching)
        if best is None or average > best[0]:
            best = (average, candidate_date, matching)

    if best is None or best[0] < overall_average * 1.25:
        return None

    _, peak_date, matching_peaks = best
    # Print the historical observations selected as the recurring peak so
    # the month used for the upcoming occurrence is straightforward to audit.
    print("Seasonal peak data points:", matching_peaks)
    month, day = peak_date.month, peak_date.day
    try:
        next_peak = datetime(now.year, month, day, tzinfo=timezone.utc)
    except ValueError:  # Handle Feb 29 in a non-leap year.
        next_peak = datetime(now.year, 2, 28, tzinfo=timezone.utc)
    if next_peak < now:
        try:
            next_peak = datetime(now.year + 1, month, day, tzinfo=timezone.utc)
        except ValueError:
            next_peak = datetime(now.year + 1, 2, 28, tzinfo=timezone.utc)
    if next_peak - now > timedelta(days=60):
        return None

    month_name = next_peak.strftime("%B")
    return (
        f"Interest has historically peaked around {month_name} — "
        "worth planning your launch accordingly."
    )
