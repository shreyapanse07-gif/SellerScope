"""Extract product-specific customer pain themes from snippets."""

import json
import logging
import os
from typing import Literal

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

load_dotenv()
logger = logging.getLogger(__name__)

LOW_EVIDENCE_MAX_MENTIONS = 2
MODERATE_EVIDENCE_MAX_MENTIONS = 6


class PainTheme(BaseModel):
    """A validated product-specific pain theme."""

    model_config = ConfigDict(extra="forbid")

    theme: str
    mentions: int = Field(gt=0, strict=True)
    example_snippet: str
    source_index: int
    addressing_features: list[str]

    @field_validator("addressing_features")
    @classmethod
    def features_must_be_known(cls, value: list[str], info):
        known_features = info.context.get("known_features", [])
        if any(feature not in known_features for feature in value):
            raise ValueError("addressing_features must contain only known features")
        return value


class PainThemes(BaseModel):
    """Validated response containing pain themes."""

    model_config = ConfigDict(extra="forbid")
    themes: list[PainTheme]


def _prompt_for_snippets(
    snippets: list[str], known_features: list[str]
) -> str:
    snippet_lines = "\n".join(
        f"{index}. {snippet}" for index, snippet in enumerate(snippets, start=1)
    )
    features = "\n".join(f"- {feature}" for feature in known_features) or "- (none)"
    return (
        "Analyze all customer snippets below for pain themes specific to the "
        "exact product type represented by the snippets.\n\n"
        f"Snippets:\n{snippet_lines}\n\n"
        f"Known features (you may reference only these):\n{features}\n\n"
        "Reject any theme that could apply to ANY product category "
        "(e.g. 'poor quality', 'bad service', 'not worth it'). Only return "
        "themes specific to this exact product type, quoting the specific "
        "complaint language used.\n"
        "Only include a feature in addressing_features if fixing or having "
        "that exact feature would directly and specifically solve this "
        "complaint - not just a loosely related concept. For example, "
        "'wireless' does not address 'connection drops', since a product "
        "can be wireless and still disconnect; a feature like "
        "'stable_connection' would, if present. If no feature in "
        "known_features directly solves the complaint, return an empty list "
        "for that theme rather than a loose match.\n"
        "If fewer than 3 snippets mention a theme, still include it but it "
        "will be marked low-evidence downstream.\n"
        "Return ONLY valid JSON matching this schema:\n"
        '{"themes": [{"theme": string, "mentions": int, '
        '"example_snippet": string, "source_index": int, '
        '"addressing_features": [string from known_features only]}]}'
    )


def _request_pain_themes(prompt_text: str) -> str:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    interaction = client.interactions.create(
        model=os.getenv("GEMINI_MODEL", "models/gemini-flash-latest"),
        input=prompt_text,
        generation_config={
            "max_output_tokens": 4096,
            "thinking_level": "low",
        },
    )
    return interaction.output_text


def extract_pain_themes(
    snippets: list[str], known_features: list[str]
) -> list[dict]:
    """Extract pain themes for all snippets in one batched model request."""
    if not snippets:
        return []

    prompt_text = _prompt_for_snippets(snippets, known_features)
    retry_note = (
        "\nYour previous response was invalid. Return ONLY the JSON object, "
        "nothing else."
    )

    for attempt in range(2):
        prompt = prompt_text if attempt == 0 else prompt_text + retry_note
        try:
            result_text = _request_pain_themes(prompt)
            parsed = json.loads(result_text)
            validated = PainThemes.model_validate(
                parsed, context={"known_features": known_features}
            )
            return [theme.model_dump() for theme in validated.themes]
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
            if attempt == 0:
                continue
            logger.warning("Pain theme extraction returned invalid output twice.")

    return []


def label_evidence_strength(themes: list[dict]) -> list[dict]:
    """Add evidence strength based on each theme's mention count."""
    labeled = []
    for theme in themes:
        result = dict(theme)
        mentions = result["mentions"]
        if mentions <= LOW_EVIDENCE_MAX_MENTIONS:
            strength: Literal["low", "moderate", "strong"] = "low"
        elif mentions <= MODERATE_EVIDENCE_MAX_MENTIONS:
            strength = "moderate"
        else:
            strength = "strong"
        result["evidence_strength"] = strength
        labeled.append(result)
    return labeled
