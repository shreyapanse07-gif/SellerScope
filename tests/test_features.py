from types import SimpleNamespace

from app.supply import features


def _mock_client(monkeypatch, responses):
    calls = []

    class MockInteractions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text=responses.pop(0))

    class MockClient:
        def __init__(self, api_key):
            self.interactions = MockInteractions()

    monkeypatch.setattr(features.genai, "Client", MockClient)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return calls


def test_extract_features_valid_json_in_one_batched_call(monkeypatch):
    titles = ["Acme Wireless Headphones", "Widget Long Battery"]
    calls = _mock_client(
        monkeypatch,
        ['{"Acme Wireless Headphones":["wireless"],'
         '"Widget Long Battery":["long_battery"]}'],
    )

    result = features.extract_features(titles)

    assert result == {
        "Acme Wireless Headphones": ["wireless"],
        "Widget Long Battery": ["long_battery"],
    }
    assert len(calls) == 1
    assert "1. Acme Wireless Headphones" in calls[0]["input"]
    assert "2. Widget Long Battery" in calls[0]["input"]
    assert "Return ONLY valid JSON" in calls[0]["input"]


def test_extract_features_retries_once_after_invalid_json(monkeypatch):
    calls = _mock_client(
        monkeypatch,
        ["not json", '{"Product":["wireless"]}'],
    )

    assert features.extract_features(["Product"]) == {
        "Product": ["wireless"]
    }
    assert len(calls) == 2
    assert calls[1]["input"].startswith(calls[0]["input"])
    assert "Your previous response was not valid JSON" in calls[1]["input"]


def test_extract_features_returns_empty_lists_after_two_invalid_responses(
    monkeypatch, caplog
):
    calls = _mock_client(monkeypatch, ["not json", "still not json"])

    assert features.extract_features(["First", "Second"]) == {
        "First": [],
        "Second": [],
    }
    assert len(calls) == 2
    assert "invalid JSON twice" in caplog.text


def test_feature_coverage_counts_titles_once_per_feature():
    assert features.feature_coverage(
        {
            "First": ["wireless", "wireless", "long_battery"],
            "Second": ["wireless"],
            "Third": ["noise_cancelling"],
            "Fourth": ["long_battery"],
        }
    ) == {
        "wireless": 0.5,
        "long_battery": 0.5,
        "noise_cancelling": 0.25,
    }
