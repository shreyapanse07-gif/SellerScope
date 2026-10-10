import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import pytest

from app.serp import client


@pytest.fixture
def cache_db(monkeypatch):
    fd, cache_db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_path = Path(cache_db)
    monkeypatch.setattr(client, "CACHE_DB_PATH", db_path)
    try:
        yield db_path
    finally:
        os.remove(cache_db)


def test_cache_miss_without_api_key_raises_even_when_live_false(cache_db, monkeypatch):
    monkeypatch.setenv("LIVE", "false")
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    monkeypatch.setattr(client, "load_dotenv", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="SERPAPI_KEY is missing"):
        client.search({"engine": "google", "q": "desk"}, force_live=False)


def test_cache_hit_returns_stored_data_without_calling_client(
    cache_db, monkeypatch
):
    params = {"engine": "google", "q": "desk"}
    expected = {"organic_results": [{"title": "Cached result"}]}
    key = client._cache_key(params)

    with closing(sqlite3.connect(cache_db)) as connection:
        connection.execute(
            "CREATE TABLE cache (key TEXT PRIMARY KEY, response TEXT)"
        )
        connection.execute(
            "INSERT INTO cache (key, response) VALUES (?, ?)",
            (key, json.dumps(expected)),
        )
        connection.commit()

    def unexpected_client(*args, **kwargs):
        pytest.fail("SerpApi client should not be called on a cache hit")

    monkeypatch.setattr(client, "Client", unexpected_client)
    monkeypatch.setenv("LIVE", "false")

    assert client.search(params) == expected


def test_live_cache_miss_calls_once_then_uses_cache(cache_db, monkeypatch):
    params = {"engine": "google", "q": "desk"}
    expected = {"organic_results": [{"title": "Live result"}]}
    calls = []

    class MockClient:
        def __init__(self, api_key):
            assert api_key == "test-api-key"

        def search(self, received_params):
            calls.append(received_params)
            return expected

    monkeypatch.setattr(client, "Client", MockClient)
    monkeypatch.setenv("LIVE", "true")
    monkeypatch.setenv("SERPAPI_KEY", "test-api-key")

    assert client.search(params) == expected
    assert client.search(params) == expected
    assert calls == [params]

    with closing(sqlite3.connect(cache_db)) as connection:
        stored = connection.execute(
            "SELECT response FROM cache WHERE key = ?",
            (client._cache_key(params),),
        ).fetchone()
    assert json.loads(stored[0]) == expected


def test_live_response_object_is_converted_to_plain_dict(cache_db, monkeypatch):
    params = {"engine": "google", "q": "desk"}
    expected = {"organic_results": [{"title": "Live result"}]}

    class MockSerpResults:
        def as_dict(self):
            return expected

    class MockClient:
        def __init__(self, api_key):
            pass

        def search(self, received_params):
            return MockSerpResults()

    monkeypatch.setattr(client, "Client", MockClient)
    monkeypatch.setenv("LIVE", "true")
    monkeypatch.setenv("SERPAPI_KEY", "test-api-key")

    result = client.search(params)

    assert type(result) is dict
    assert result == expected
    assert type(result["organic_results"]) is list
    assert client.search(params) == expected
