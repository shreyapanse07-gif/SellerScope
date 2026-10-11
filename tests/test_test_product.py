from app.scoring.test_product import match_product


def _opportunity(theme, features):
    return {
        "theme": theme,
        "pain_score": 0.8,
        "coverage_score": 0.2,
        "opportunity_score": 0.64,
        "interpretation": f"Opportunity for {theme}",
        "addressing_features": features,
    }


def test_splits_addressed_and_missed_opportunities():
    result = match_product(
        ["long_battery", "wireless"],
        ["long_battery", "wireless", "noise_cancelling"],
        [
            _opportunity("battery life", ["long_battery"]),
            _opportunity("wireless audio", ["wireless"]),
            _opportunity("noise cancellation", ["noise_cancelling"]),
        ],
    )

    assert result["matched_features"] == ["Long battery", "Wireless"]
    assert [item["theme"] for item in result["addressed_opportunities"]] == [
        "battery life",
        "wireless audio",
    ]
    assert [item["theme"] for item in result["missed_opportunities"]] == [
        "noise cancellation"
    ]
    assert result["coverage_summary"] == (
        "You address 2 of 3 major opportunities in this market"
    )


def test_no_matching_features_misses_every_opportunity():
    result = match_product(
        ["waterproof"],
        ["long_battery", "wireless"],
        [_opportunity("battery life", ["long_battery"])],
    )

    assert result["matched_features"] == []
    assert result["unmatched_features"] == ["Waterproof"]
    assert result["addressed_opportunities"] == []
    assert len(result["missed_opportunities"]) == 1


def test_fuzzy_matching_handles_typo_and_separator_variation():
    result = match_product(
        ["long batery"],
        ["long_battery"],
        [_opportunity("battery life", ["long_battery"])],
    )

    assert result["matched_features"] == ["Long battery"]
    assert result["unmatched_features"] == []
    assert len(result["addressed_opportunities"]) == 1


def test_typo_match_addresses_opportunity_by_exact_known_feature():
    opportunity = _opportunity("short battery life", ["long_battery"])

    result = match_product(
        ["long batery"],
        ["long_battery"],
        [opportunity],
    )

    assert result["matched_features"] == ["Long battery"]
    assert opportunity["addressing_features"] == ["long_battery"]
    assert result["addressed_opportunities"] == [
        {
            "theme": "short battery life",
            "opportunity_score": 0.64,
            "interpretation": "Opportunity for short battery life",
            "addressing_features": ["Long battery"],
        }
    ]
    assert result["missed_opportunities"] == []


def test_empty_seller_features_misses_all_opportunities():
    result = match_product(
        [],
        ["long_battery"],
        [_opportunity("battery life", ["long_battery"])],
    )

    assert result["matched_features"] == []
    assert result["unmatched_features"] == []
    assert result["addressed_opportunities"] == []
    assert len(result["missed_opportunities"]) == 1


def test_empty_opportunities_has_zero_coverage():
    result = match_product(["long_battery"], ["long_battery"], [])

    assert result["addressed_opportunities"] == []
    assert result["missed_opportunities"] == []
    assert result["coverage_summary"] == (
        "You address 0 of 0 major opportunities in this market"
    )
