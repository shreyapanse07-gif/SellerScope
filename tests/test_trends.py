from datetime import datetime, timedelta, timezone

from app.supply.trends import analyze_trend, detect_seasonal_pattern


def _response(recent_value, previous_value):
    now = datetime.now(timezone.utc)
    points = []
    for days_ago in (150, 120, 100):
        points.append({
            "date": (now - timedelta(days=days_ago)).strftime("%b %d, %Y"),
            "timestamp": str(int((now - timedelta(days=days_ago)).timestamp())),
            "values": [{"query": "headphones", "extracted_value": previous_value}],
        })
    for days_ago in (60, 30, 5):
        points.append({
            "date": (now - timedelta(days=days_ago)).strftime("%b %d, %Y"),
            "timestamp": str(int((now - timedelta(days=days_ago)).timestamp())),
            "values": [{"query": "headphones", "extracted_value": recent_value}],
        })
    return {"interest_over_time": {"timeline_data": points}}


def test_rising_trend():
    assert analyze_trend(_response(80, 50))["direction"] == "rising"


def test_falling_trend():
    assert analyze_trend(_response(30, 50))["direction"] == "falling"


def test_stable_trend():
    result = analyze_trend(_response(55, 50))
    assert result["direction"] == "stable"
    assert result["change_pct"] == 10.0


def test_empty_and_malformed_data_return_safe_default():
    expected = {"direction": "stable", "change_pct": 0.0, "data_points": []}
    assert analyze_trend({}) == expected
    assert analyze_trend({"interest_over_time": {"timeline_data": [None, {}, {"values": "bad"}]}}) == expected


def test_detects_clear_peak_near_upcoming_date():
    upcoming = datetime.now(timezone.utc) + timedelta(days=30)
    prior_year = upcoming.replace(year=upcoming.year - 1)
    points = []
    for peak in (upcoming, prior_year):
        points.extend(
            [
                {"date": (peak - timedelta(days=7)).strftime("%Y-%m-%d"), "value": 90},
                {"date": peak.strftime("%Y-%m-%d"), "value": 100},
                {"date": (peak + timedelta(days=7)).strftime("%Y-%m-%d"), "value": 90},
            ]
        )
    points.extend(
        {"date": (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d"), "value": 10}
        for days in (300, 250, 200, 150, 100)
    )

    note = detect_seasonal_pattern(points)

    assert note is not None
    assert upcoming.strftime("%B") in note


def test_no_clear_peak_returns_none():
    now = datetime.now(timezone.utc)
    points = [
        {"date": (now - timedelta(days=days)).strftime("%Y-%m-%d"), "value": 10}
        for days in range(0, 730, 7)
    ]

    assert detect_seasonal_pattern(points) is None


def test_insufficient_history_returns_none():
    now = datetime.now(timezone.utc)
    points = [
        {"date": (now - timedelta(days=days)).strftime("%Y-%m-%d"), "value": value}
        for days, value in ((70, 10), (40, 50), (10, 10))
    ]

    assert detect_seasonal_pattern(points) is None
