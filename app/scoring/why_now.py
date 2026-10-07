"""Build a short explanation of why a market opportunity is timely."""

from datetime import datetime, timedelta, timezone


def build_why_now(news: list[dict], top_opportunity: dict) -> str | None:
    signals = []

    now = datetime.now(timezone.utc)
    recent_count = 0
    for article in news:
        iso_date = article.get("iso_date")
        if not iso_date:
            continue
        try:
            article_date = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            if now - article_date <= timedelta(days=30):
                recent_count += 1
        except (ValueError, TypeError):
            continue

    if recent_count >= 2:
        signals.append(
            f"{recent_count} articles in the last 30 days "
            "mention this market — attention is picking up."
        )

    if top_opportunity and top_opportunity.get("coverage_score", 1) < 0.2:
        pct = int(top_opportunity["coverage_score"] * 100)
        signals.append(
            f"Only {pct}% of competitors currently address "
            "the top gap — the window is still open."
        )

    if not signals:
        return None
    return " ".join(signals)
