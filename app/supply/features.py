"""Extract canonical product feature tags from product titles."""

import json
import logging
import os
import time

from dotenv import load_dotenv
from google import genai
from pydantic import RootModel, ValidationError

load_dotenv()
logger = logging.getLogger(__name__)


class FeaturesByTitle(RootModel[dict[str, list[str]]]):
    """Validated mapping of product titles to feature tags."""


def _prompt_for_titles(titles: list[str]) -> str:
    title_lines = "\n".join(
        f"{index}. {title}" for index, title in enumerate(titles, start=1)
    )
    return (
        "Extract the product features stated in each product title below. "
        "Use canonical, lowercase, snake_case feature tags, such as "
        '"long_battery", "noise_cancelling", and "wireless". '
        "Use each exact title as its JSON key. Include an empty list when "
        "a title has no identifiable features.\n\n"
        f"Titles:\n{title_lines}\n\n"
        'Return ONLY valid JSON, no other text, matching exactly this schema: '
        '{"title": ["feature_tag", ...]}'
    )


def _request_features(prompt_text: str) -> str:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "models/gemini-flash-latest"),
        contents=prompt_text,
        config={
            "response_mime_type": "application/json",
            "max_output_tokens": 4096,
            "http_options": {"timeout": 30000},
        },
    )
    return response.text


def extract_features(titles: list[str]) -> dict[str, list[str]]:
    """Extract features for all titles in one batched model request."""
    if not titles:
        return {}

    prompt_text = _prompt_for_titles(titles)
    retry_note = (
        "\nYour previous response was not valid JSON. Return ONLY the JSON "
        "object, nothing else."
    )

    for attempt in range(3):
        prompt = prompt_text if attempt == 0 else prompt_text + retry_note
        try:
            result_text = _request_features(prompt)
            parsed = json.loads(result_text)
            validated = FeaturesByTitle.model_validate(parsed).root
            return validated
        except Exception as error:
            status_code = getattr(error, "status_code", getattr(error, "code", None))
            is_timeout = isinstance(error, TimeoutError) or (
                "timeout" in type(error).__name__.lower()
            )
            if (status_code == 503 or is_timeout) and attempt < 2:
                delay = 2**attempt
                error_kind = "503 error" if status_code == 503 else "timeout"
                print(
                    f"Retry {attempt + 1}/3 after {error_kind}, waiting {delay}s..."
                )
                time.sleep(delay)
                continue
            if status_code == 503 or is_timeout:
                logger.warning("Feature extraction failed after retries: %s", error)
                return {title: [] for title in titles}
            if isinstance(
                error, (json.JSONDecodeError, ValidationError, TypeError, ValueError)
            ):
                if attempt == 0:
                    continue
                logger.warning("Feature extraction returned invalid JSON twice.")
                break
            raise

    return {title: [] for title in titles}


def feature_coverage(
    features_by_title: dict[str, list[str]],
) -> dict[str, float]:
    """Return the share of titles containing each unique feature tag."""
    total_titles = len(features_by_title)
    if total_titles == 0:
        return {}

    counts: dict[str, int] = {}
    for features in features_by_title.values():
        for feature in set(features):
            counts[feature] = counts.get(feature, 0) + 1
    return {feature: count / total_titles for feature, count in counts.items()}
