from app.scoring.opportunity import compute_opportunity_scores


def _theme(name, mentions, addressing_features):
    return {
        "theme": name,
        "mentions": mentions,
        "example_snippet": f"Example for {name}",
        "source_index": 1,
        "addressing_features": addressing_features,
        "evidence_strength": "moderate",
    }


def test_scores_and_ranks_themes_by_opportunity():
    themes = [
        _theme("well covered", 10, ["common_feature"]),
        _theme("uncovered", 8, ["missing_feature"]),
        _theme("moderate coverage", 6, ["somewhat_common"]),
    ]

    result = compute_opportunity_scores(
        themes,
        {
            "common_feature": 0.9,
            "somewhat_common": 0.5,
            "missing_feature": 0.0,
        },
    )

    assert [item["theme"] for item in result] == [
        "uncovered",
        "moderate coverage",
        "well covered",
    ]


def test_empty_addressing_features_have_zero_coverage():
    result = compute_opportunity_scores(
        [_theme("unaddressed", 3, [])], {}
    )

    assert result[0]["coverage_score"] == 0.0


def test_unknown_feature_has_zero_coverage():
    result = compute_opportunity_scores(
        [_theme("unknown", 3, ["not_in_coverage"])], {}
    )

    assert result[0]["coverage_score"] == 0.0


def test_single_theme_has_full_pain_score():
    result = compute_opportunity_scores(
        [_theme("only theme", 4, [])], {}
    )

    assert result[0]["pain_score"] == 1.0


def test_empty_themes_return_empty_list():
    assert compute_opportunity_scores([], {}) == []


def test_opportunity_score_is_pain_times_uncovered_fraction():
    result = compute_opportunity_scores(
        [_theme("known example", 4, ["feature"])],
        {"feature": 0.25},
    )[0]

    assert result["pain_score"] == 1.0
    assert result["coverage_score"] == 0.25
    assert result["opportunity_score"] == (
        result["pain_score"] * (1 - result["coverage_score"])
    )
