from types import SimpleNamespace

from app.demand import pain


def _mock_client(monkeypatch, responses):
    calls = []

    class MockInteractions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text=responses.pop(0))

    class MockClient:
        def __init__(self, api_key):
            self.interactions = MockInteractions()

    monkeypatch.setattr(pain.genai, "Client", MockClient)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return calls


def test_extract_pain_themes_batches_snippets_and_labels_evidence(monkeypatch):
    snippets = ["Battery drains during calls", "Battery dies during calls"]
    response = (
        '{"themes": ['
        '{"theme":"battery drains during calls","mentions":2,'
        '"example_snippet":"Battery drains during calls","source_index":1,'
        '"addressing_features":["long_battery"]},'
        '{"theme":"weak noise cancellation","mentions":4,'
        '"example_snippet":"Noise cancellation barely blocks traffic",'
        '"source_index":2,"addressing_features":["noise_cancelling"]}'
        ']}'
    )
    calls = _mock_client(monkeypatch, [response])

    themes = pain.extract_pain_themes(
        snippets, ["long_battery", "noise_cancelling"]
    )
    labeled = pain.label_evidence_strength(themes)

    assert [theme["evidence_strength"] for theme in labeled] == ["low", "moderate"]
    assert len(calls) == 1
    assert "1. Battery drains during calls" in calls[0]["input"]
    assert "2. Battery dies during calls" in calls[0]["input"]
    assert "long_battery" in calls[0]["input"]
    assert "Only return themes specific to this exact product type" in calls[0]["input"]


def test_extract_pain_themes_retries_invalid_json(monkeypatch):
    calls = _mock_client(
        monkeypatch,
        ["not json", '{"themes": []}'],
    )

    assert pain.extract_pain_themes(["Snippet"], ["wireless"]) == []
    assert len(calls) == 2
    assert calls[1]["input"].startswith(calls[0]["input"])
    assert "Return ONLY the JSON object" in calls[1]["input"]


def test_extract_pain_themes_returns_empty_after_two_invalid_responses(
    monkeypatch, caplog
):
    calls = _mock_client(monkeypatch, ["not json", "still not json"])

    assert pain.extract_pain_themes(["Snippet"], []) == []
    assert len(calls) == 2
    assert "invalid output twice" in caplog.text


def test_extract_pain_themes_rejects_unknown_feature(monkeypatch):
    invalid_theme = (
        '{"themes": [{"theme":"battery drains during calls","mentions":1,'
        '"example_snippet":"Battery dies during calls","source_index":1,'
        '"addressing_features":["unknown_feature"]}]}'
    )
    calls = _mock_client(monkeypatch, [invalid_theme, invalid_theme])

    assert pain.extract_pain_themes(["Snippet"], ["long_battery"]) == []
    assert len(calls) == 2


def test_label_evidence_strength_threshold_boundaries():
    themes = [
        {"theme": f"theme-{mentions}", "mentions": mentions}
        for mentions in (2, 3, 6, 7)
    ]

    labeled = pain.label_evidence_strength(themes)

    assert [theme["evidence_strength"] for theme in labeled] == [
        "low",
        "moderate",
        "moderate",
        "strong",
    ]
