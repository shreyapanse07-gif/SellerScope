from app import pipeline


def test_run_analysis_assembles_contract_shape_without_api_calls(monkeypatch):
    calls = []

    def fake_search(params):
        calls.append(params)
        if params["engine"] == "google_shopping":
            return {
                "shopping_results": [
                    {
                        "title": "Acme Wireless Headphones",
                        "price": "$100.00",
                        "source": "Shop",
                        "rating": 4.5,
                    },
                    {
                        "title": "Acme Wireless Headphones",
                        "price": "$100.00",
                        "source": "Shop",
                        "rating": 4.5,
                    },
                ]
            }
        return {
            "organic_results": [
                {
                    "title": "Headphone problems",
                    "snippet": "The connection drops frequently.",
                    "link": "https://example.test/review",
                }
            ]
        }

    monkeypatch.setattr(pipeline.serp_client, "search", fake_search)
    monkeypatch.setattr(
        pipeline.features,
        "extract_features",
        lambda titles: {titles[0]: ["wireless"]},
    )
    monkeypatch.setattr(
        pipeline.features,
        "feature_coverage",
        lambda by_title: {"wireless": 1.0},
    )
    monkeypatch.setattr(
        pipeline.pain,
        "extract_pain_themes",
        lambda snippets, known_features: [
            {
                "theme": "connection drops",
                "mentions": 3,
                "example_snippet": snippets[0],
                "source_index": 1,
                "addressing_features": ["wireless"],
            }
        ],
    )

    result = pipeline.run_analysis("wireless headphones", "India", 120.0)

    assert set(result) == {
        "query",
        "products",
        "price_stats",
        "features",
        "pain_points",
        "opportunities",
        "news",
        "why_now",
    }
    assert result["query"] == {
        "product": "wireless headphones",
        "market": "India",
        "target_price": 120.0,
    }
    assert len(result["products"]) == 1
    assert result["products"][0]["features"] == ["wireless"]
    assert result["features"] == [
        {"name": "wireless", "count": 1, "coverage_pct": 100.0}
    ]
    assert result["pain_points"][0]["source_url"] == "https://example.test/review"
    assert result["opportunities"][0]["coverage_score"] == 1.0
    assert result["news"] == []
    assert result["why_now"] is None

    assert len(calls) == 2
    assert calls[0]["engine"] == "google_shopping"
    assert calls[0]["q"] == "wireless headphones"
    assert calls[1]["engine"] == "google"
    assert '"wireless headphones" problems OR complaints OR issues' == calls[1]["q"]
    for params in calls:
        assert params["gl"] == "in"
        assert params["hl"] == "en"
        assert params["location"] == "India"
