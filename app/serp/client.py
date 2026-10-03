"""SerpApi search client with a local SQLite response cache."""

import hashlib
import json
import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from serpapi import Client

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DB_PATH = PROJECT_ROOT / "data" / "cache.db"


@contextmanager
def _cache_connection() -> Iterator[sqlite3.Connection]:
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(CACHE_DB_PATH)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                response TEXT
            )
            """
        )
        connection.commit()
        yield connection


def _cache_key(params: dict) -> str:
    serialized = json.dumps(params, sort_keys=True)
    return hashlib.md5(serialized.encode("utf-8")).hexdigest()


def search(params: dict) -> dict:
    """Return a cached SerpApi response, or fetch and cache it when LIVE=true."""
    key = _cache_key(params)

    with _cache_connection() as connection:
        row = connection.execute(
            "SELECT response FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is not None:
            return json.loads(row[0])

        if os.getenv("LIVE", "false") != "true":
            raise RuntimeError(
                "SerpApi cache miss while LIVE is not 'true'; "
                "set LIVE=true to allow a live API request."
            )

        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("SERPAPI_KEY")
        if not api_key:
            raise RuntimeError(
                "SERPAPI_KEY is missing; add it to the project .env file."
            )

        response = Client(api_key=api_key).search(params)
        as_dict = getattr(response, "as_dict", None)
        plain_response = as_dict() if callable(as_dict) else dict(response)
        response_json = json.dumps(plain_response)
        plain_response = json.loads(response_json)
        connection.execute(
            "INSERT INTO cache (key, response) VALUES (?, ?)",
            (key, response_json),
        )
        connection.commit()
        return plain_response
