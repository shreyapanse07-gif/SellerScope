"""Match seller features to known features and market opportunities."""

from rapidfuzz import fuzz, process


MATCH_THRESHOLD = 80


def _normalize_feature(feature: str) -> str:
    """Normalize separators and whitespace before fuzzy comparison."""
    return " ".join(feature.lower().replace("_", " ").split())


def match_product(
    seller_features: list[str],
    known_features: list[str],
    opportunities: list[dict],
) -> dict:
    """Match a product's features and summarize the opportunities it addresses."""
    matched_features = []
    unmatched_features = []
    normalized_known_features = [
        _normalize_feature(feature) for feature in known_features
    ]

    for seller_feature in seller_features:
        match = process.extractOne(
            _normalize_feature(seller_feature),
            normalized_known_features,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=MATCH_THRESHOLD,
        )
        if match is None:
            unmatched_features.append(seller_feature)
        else:
            # extractOne returns the chosen item's index; retain its exact
            # known_features spelling for the exact opportunity comparison.
            known_feature = known_features[match[2]]
            if known_feature not in matched_features:
                matched_features.append(known_feature)

    matched_set = set(matched_features)
    addressed_opportunities = []
    missed_opportunities = []

    for opportunity in opportunities:
        summary = {
            "theme": opportunity["theme"],
            "opportunity_score": opportunity["opportunity_score"],
            "interpretation": opportunity["interpretation"],
        }
        if matched_set.intersection(opportunity.get("addressing_features", [])):
            addressed_opportunities.append(summary)
        else:
            missed_opportunities.append(summary)

    total = len(opportunities)
    coverage_summary = (
        f"You address {len(addressed_opportunities)} of {total} "
        "major opportunities in this market"
    )

    return {
        "matched_features": matched_features,
        "unmatched_features": unmatched_features,
        "addressed_opportunities": addressed_opportunities,
        "missed_opportunities": missed_opportunities,
        "coverage_summary": coverage_summary,
    }
