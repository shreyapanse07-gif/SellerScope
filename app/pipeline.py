"""Coordinate product, complaint, feature, and opportunity analysis."""

import logging

from app.demand import pain
from app.scoring import opportunity
from app.scoring.why_now import build_why_now
from app.serp import client as serp_client
from app.supply import cleaning, features, trends
from app.main import MARKETS

logger = logging.getLogger(__name__)


def _search_params(engine: str, query: str, market_params: dict) -> dict:
    return {
        "engine": engine,
        "q": query,
        "gl": market_params["gl"],
        "hl": market_params["hl"],
        "location": market_params["location"],
    }


def _complaint_snippets(response: dict) -> tuple[list[str], list[str]]:
    snippets = []
    source_urls = []
    for result in response.get("organic_results", []):
        if not isinstance(result, dict):
            continue
        snippet = result.get("snippet") or result.get("title")
        if not snippet:
            continue
        snippets.append(str(snippet))
        source_urls.append(result.get("link", ""))
    return snippets, source_urls


def run_analysis(product: str, market: str, target_price: float | None) -> dict:
    """Run the analysis pipeline, returning partial results when stages fail."""
    if market not in MARKETS:
        raise ValueError(f"Unsupported market: {market}")

    market_params = MARKETS[market]
    query = {"product": product, "market": market, "target_price": target_price}

    shopping_response = {}
    print("[1/5] Fetching shopping data...")
    try:
        shopping_response = serp_client.search(
            _search_params("google_shopping", product, market_params)
        )
    except Exception:
        logger.warning("Shopping search failed for %r", product, exc_info=True)

    complaint_response = {}
    print("[2/5] Fetching complaint data...")
    try:
        complaint_response = serp_client.search(
            _search_params(
                "google", f'"{product}" problems OR complaints OR issues', market_params
            )
        )
    except Exception:
        logger.warning("Complaint search failed for %r", product, exc_info=True)

    trends_response = {}
    try:
        trends_response = serp_client.search(
            {
                "engine": "google_trends",
                "q": product,
                "geo": market_params["gl"],
                "data_type": "TIMESERIES",
            }
        )
    except Exception:
        logger.warning("Trends search failed for %r", product, exc_info=True)
    trend = trends.analyze_trend(trends_response)

    products = []
    stats = {"min": None, "median": None, "max": None, "buckets": []}
    try:
        product_frame = cleaning.dedupe(cleaning.clean_products(shopping_response))
        stats = cleaning.price_stats(product_frame)
        products = product_frame.where(product_frame.notna(), None).to_dict("records")
    except Exception:
        logger.warning("Product cleaning failed for %r", product, exc_info=True)
        product_frame = None

    features_by_title = {}
    coverage = {}
    print("[3/5] Extracting features...")
    try:
        titles = product_frame["title"].dropna().tolist() if product_frame is not None else []
        features_by_title = features.extract_features(titles)
        coverage = features.feature_coverage(features_by_title)
    except Exception:
        logger.warning("Feature extraction failed for %r", product, exc_info=True)
        if product_frame is None:
            titles = []
        else:
            titles = product_frame["title"].dropna().tolist()

    for item in products:
        item["features"] = features_by_title.get(item.get("title"), [])

    feature_counts = {
        feature: round(fraction * len(products)) for feature, fraction in coverage.items()
    }
    feature_rows = [
        {
            "name": feature,
            "count": feature_counts[feature],
            "coverage_pct": fraction * 100,
        }
        for feature, fraction in coverage.items()
    ]

    snippets, source_urls = _complaint_snippets(complaint_response)
    pain_themes = []
    print("[4/5] Extracting pain themes...")
    try:
        pain_themes = pain.extract_pain_themes(snippets, known_features=list(coverage))
    except Exception:
        logger.warning("Pain extraction failed for %r", product, exc_info=True)

    labeled_themes = pain.label_evidence_strength(pain_themes)
    pain_points = []
    for theme in labeled_themes:
        source_index = theme.get("source_index", 0)
        source_url = (
            source_urls[source_index - 1]
            if isinstance(source_index, int) and 0 < source_index <= len(source_urls)
            else ""
        )
        pain_points.append(
            {
                "theme": theme["theme"],
                "mentions": theme["mentions"],
                "example_snippet": theme["example_snippet"],
                "source_url": source_url,
                "evidence_strength": theme["evidence_strength"],
            }
        )

    print("[5/5] Scoring...")
    try:
        opportunities = opportunity.compute_opportunity_scores(
            labeled_themes, coverage
        )
    except Exception:
        logger.warning("Opportunity scoring failed for %r", product, exc_info=True)
        opportunities = []

    news = []
    return {
        "query": query,
        "products": products,
        "price_stats": stats,
        "features": feature_rows,
        "pain_points": pain_points,
        "opportunities": opportunities,
        "news": news,
        "why_now": build_why_now(news, opportunities[0] if opportunities else None),
        "trend": trend,
    }
