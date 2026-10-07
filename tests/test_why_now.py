from datetime import datetime, timedelta, timezone

from app.scoring.why_now import build_why_now


def _recent_iso_date(days_ago=1):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace(
        "+00:00", "Z"
    )


def test_no_signals_returns_none():
    assert build_why_now([], {"coverage_score": 0.5}) is None


def test_news_only_signal():
    news = [{"iso_date": _recent_iso_date()}, {"iso_date": _recent_iso_date(5)}]

    assert build_why_now(news, {"coverage_score": 0.5}) == (
        "2 articles in the last 30 days mention this market — attention is picking up."
    )


def test_coverage_only_signal():
    assert build_why_now([], {"coverage_score": 0.15}) == (
        "Only 15% of competitors currently address the top gap — the window is still open."
    )


def test_news_and_coverage_signals_are_combined():
    news = [{"iso_date": _recent_iso_date()}, {"iso_date": _recent_iso_date(5)}]

    assert build_why_now(news, {"coverage_score": 0.1}) == (
        "2 articles in the last 30 days mention this market — attention is picking up. "
        "Only 10% of competitors currently address the top gap — the window is still open."
    )


def test_malformed_and_missing_iso_dates_are_skipped():
    news = [
        {"iso_date": "not a date"},
        {"iso_date": None},
        {},
        {"iso_date": _recent_iso_date()},
    ]

    assert build_why_now(news, None) is None
