"""Match seller features to known features and market opportunities."""

import json
import logging
import os

from dotenv import load_dotenv
from google import genai
from pydantic import RootModel
from rapidfuzz import fuzz, process
from app.serp import client as serp_client

load_dotenv()
logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 80


class SemanticFeatureMatches(RootModel[dict[str, str | None]]):
    """Validated mapping from typed feature phrases to canonical tags."""


def _prompt_for_semantic_matches(
    unmatched_features: list[str], known_features: list[str]
) -> str:
    return (
        "Match each seller-typed product feature to a canonical feature tag only "
        "when there is a genuine conceptual match. Do not infer a feature from "
        "generic praise or appearance. For example, '40 hrs battery' matches "
        "'long_battery', and 'noise blocking' matches 'noise_cancelling'; "
        "'cool design' has no genuine match and must map to null.\n\n"
        f"Seller phrases: {json.dumps(unmatched_features)}\n"
        f"Known feature tags: {json.dumps(known_features)}\n\n"
        "Return ONLY valid JSON as an object whose keys are every exact seller "
        "phrase above and whose values are one exact known tag or null. Do not "
        "invent tags. Example: {\"40 hrs battery\": \"long_battery\", "
        "\"cool design\": null}"
    )


def _request_semantic_matches(prompt: str) -> str:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "models/gemini-flash-latest"),
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "max_output_tokens": 2048,
            "http_options": {"timeout": 30000},
        },
    )
    return response.text


def _cached_semantic_matches(prompt: str) -> str:
    """Use the shared SQLite response cache for identical Gemini prompts."""
    params = {
        "kind": "gemini_semantic_feature_matches",
        "model": os.getenv("GEMINI_MODEL", "models/gemini-flash-latest"),
        "prompt": prompt,
    }
    key = serp_client._cache_key(params)
    with serp_client._cache_connection() as connection:
        row = connection.execute(
            "SELECT response FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is not None:
            logger.info("Semantic feature match cache hit")
            return row[0]

        response_text = _request_semantic_matches(prompt)
        connection.execute(
            "INSERT OR REPLACE INTO cache (key, response) VALUES (?, ?)",
            (key, response_text),
        )
        connection.commit()
        return response_text


def _semantic_match_features(
    unmatched_features: list[str], known_features: list[str]
) -> dict[str, str | None]:
    """Semantically map all unmatched phrases in one Gemini request.

    Invalid responses and service failures produce no semantic matches, leaving
    the caller's fuzzy-only results intact.
    """
    if not unmatched_features or not known_features:
        return {}

    try:
        response_text = _cached_semantic_matches(
            _prompt_for_semantic_matches(unmatched_features, known_features)
        )
        parsed = SemanticFeatureMatches.model_validate(json.loads(response_text)).root
        if set(parsed) != set(unmatched_features) or any(
            tag is not None and tag not in known_features for tag in parsed.values()
        ):
            raise ValueError("Semantic matches must use supplied phrases and tags")
        return parsed
    except Exception as error:
        logger.warning(
            "Semantic feature matching failed; using fuzzy matches only: %s", error
        )
        return {}


def _normalize_feature(feature: str) -> str:
    """Normalize separators and whitespace before fuzzy comparison."""
    return " ".join(feature.lower().replace("_", " ").split())


def _readable_feature(feature: str) -> str:
    """Render canonical feature tags as title-cased, readable text."""
    return " ".join(feature.replace("_", " ").split()).capitalize()


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

    semantic_matches = _semantic_match_features(unmatched_features, known_features)
    still_unmatched = []
    for seller_feature in unmatched_features:
        known_feature = semantic_matches.get(seller_feature)
        if known_feature is None:
            still_unmatched.append(seller_feature)
        elif known_feature not in matched_features:
            matched_features.append(known_feature)
    unmatched_features = still_unmatched

    matched_set = set(matched_features)
    addressed_opportunities = []
    missed_opportunities = []

    for opportunity in opportunities:
        summary = {
            "theme": opportunity["theme"],
            "opportunity_score": opportunity["opportunity_score"],
            "interpretation": opportunity["interpretation"],
            "addressing_features": [
                _readable_feature(feature)
                for feature in opportunity.get("addressing_features", [])
            ],
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
        "matched_features": [
            _readable_feature(feature) for feature in matched_features
        ],
        "unmatched_features": [
            _readable_feature(feature) for feature in unmatched_features
        ],
        "addressed_opportunities": addressed_opportunities,
        "missed_opportunities": missed_opportunities,
        "coverage_summary": coverage_summary,
    }
