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

load_dotenv()

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


def search(params: dict, force_live: bool = False) -> dict:
    """Return a cached SerpApi response, or fetch and cache it when force_live=True or LIVE=true."""
    key = _cache_key(params)

    with _cache_connection() as connection:
        row = connection.execute(
            "SELECT response FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is not None and not force_live:
            return json.loads(row[0])

        load_dotenv(PROJECT_ROOT / ".env")
        api_key = os.getenv("SERPAPI_KEY")
        if not api_key:
            raise RuntimeError(
                "SERPAPI_KEY is missing; add it to the project .env file. "
                "See .env.example for required environment variables."
            )

        try:
            response = Client(api_key=api_key).search(params)
            as_dict = getattr(response, "as_dict", None)
            plain_response = as_dict() if callable(as_dict) else dict(response)
            response_json = json.dumps(plain_response)
            plain_response = json.loads(response_json)
            connection.execute(
                "INSERT OR REPLACE INTO cache (key, response) VALUES (?, ?)",
                (key, response_json),
            )
            connection.commit()
            return plain_response
        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "quota" in error_msg:
                raise RuntimeError(
                    f"SerpApi rate limit or quota exceeded: {e}. "
                    "Check your SerpApi account for available credits."
                ) from e
            elif "api key" in error_msg or "authentication" in error_msg:
                raise RuntimeError(
                    f"SerpApi authentication failed: {e}. "
                    "Check that SERPAPI_KEY in your .env file is valid."
                ) from e
            elif "timeout" in error_msg:
                raise RuntimeError(
                    f"SerpApi request timed out: {e}. "
                    "Try again later or check your network connection."
                ) from e
            else:
                raise RuntimeError(
                    f"SerpApi request failed: {e}. "
                    "See logs for details."
                ) from e
