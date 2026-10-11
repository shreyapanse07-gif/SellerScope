"""Pure scoring logic for product opportunity themes."""

from typing import Any

# Scores at or below this threshold are considered low pain.
LOW_PAIN_THRESHOLD = 0.33
# High pain combined with coverage at or below this threshold indicates
# a strong opportunity.
HIGH_PAIN_THRESHOLD = 0.67
LOW_COVERAGE_THRESHOLD = 0.33
# Coverage at or above this threshold is considered well-covered.
HIGH_COVERAGE_THRESHOLD = 0.67


def _interpretation(pain_score: float, coverage_score: float) -> str:
    if pain_score <= LOW_PAIN_THRESHOLD:
        return "Customers do not seem to feel this pain strongly, so this may be one to pass on."
    if (
        pain_score >= HIGH_PAIN_THRESHOLD
        and coverage_score <= LOW_COVERAGE_THRESHOLD
    ):
        return "Customers really want this, and almost nobody offers it. That leaves a strong opening for you."
    if coverage_score >= HIGH_COVERAGE_THRESHOLD:
        return "Customers feel this pain, but current products already address it well."
    return "Customers feel this pain, and there may still be room to improve on current options."


def compute_opportunity_scores(
    pain_themes: list[dict[str, Any]],
    feature_coverage: dict[str, float],
) -> list[dict[str, Any]]:
    """Score themes by pain frequency and existing feature coverage."""
    if not pain_themes:
        return []

    max_mentions = max(theme["mentions"] for theme in pain_themes)
    scored = []

    for theme in pain_themes:
        pain_score = theme["mentions"] / max_mentions if max_mentions else 0.0
        coverage_score = max(
            (
                feature_coverage.get(feature, 0.0)
                for feature in theme.get("addressing_features", [])
            ),
            default=0.0,
        )
        opportunity_score = pain_score * (1 - coverage_score)
        scored.append(
            {
                "theme": theme["theme"],
                "pain_score": pain_score,
                "coverage_score": coverage_score,
                "opportunity_score": opportunity_score,
                "interpretation": _interpretation(pain_score, coverage_score),
                "evidence_strength": theme["evidence_strength"],
                "example_snippet": theme["example_snippet"],
                "source_index": theme["source_index"],
                "addressing_features": theme.get("addressing_features", []),
            }
        )

    return sorted(
        scored, key=lambda item: item["opportunity_score"], reverse=True
    )
