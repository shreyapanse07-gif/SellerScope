"""Helpers for converting raw Google Shopping results into tabular data."""

import math
import re

import pandas as pd


PRODUCT_COLUMNS = [
    "title",
    "brand",
    "price",
    "merchant",
    "rating",
    "reviews_count",
]


def extract_brand(title: str) -> str:
    """Guess a product brand from the first word of its title."""
    if not isinstance(title, str):
        return ""
    words = title.strip().split()
    return words[0] if words else ""


def parse_price(price_str: str) -> float | None:
    """Parse a price after removing currency symbols and thousands separators."""
    if not isinstance(price_str, str):
        return None
    normalized = re.sub(r"[^\d.\-]", "", price_str.replace(",", ""))
    if not normalized or normalized in {".", "-", "-."}:
        return None
    try:
        value = float(normalized)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def clean_products(raw_response: dict) -> pd.DataFrame:
    """Convert a raw SerpApi Google Shopping response to a clean DataFrame."""
    results = raw_response.get("shopping_results", [])
    rows = []
    for product in results if isinstance(results, list) else []:
        if not isinstance(product, dict):
            continue
        title = product.get("title") or ""
        price = (
            product["extracted_price"]
            if "extracted_price" in product
            else parse_price(product.get("price"))
        )
        rows.append(
            {
                "title": title,
                "brand": extract_brand(title),
                "price": price,
                "merchant": product.get("source") or product.get("merchant") or "",
                "rating": product.get("rating", None),
                "reviews_count": product.get("reviews", None),
            }
        )
    return pd.DataFrame(rows, columns=PRODUCT_COLUMNS)


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate products with the same title and merchant."""
    return df.drop_duplicates(subset=["title", "merchant"]).reset_index(drop=True)


def price_stats(df: pd.DataFrame) -> dict:
    """Summarize prices and count them across up to five data driven bands."""
    prices = pd.to_numeric(df.get("price", pd.Series(dtype=float)), errors="coerce")
    prices = prices.dropna()
    if prices.empty:
        return {"min": None, "median": None, "max": None, "buckets": []}

    minimum, median, maximum = float(prices.min()), float(prices.median()), float(prices.max())
    if minimum == maximum:
        return {
            "min": minimum,
            "median": median,
            "max": maximum,
            "buckets": [{"range": f"{minimum:g}-{maximum:g}", "count": int(len(prices))}],
        }

    bucket_count = min(5, max(1, int(math.ceil(math.sqrt(len(prices))))))
    width = (maximum - minimum) / bucket_count
    counts = [0] * bucket_count
    for price in prices:
        index = min(int((float(price) - minimum) / width), bucket_count - 1)
        counts[index] += 1
    buckets = [
        {
            "range": f"{minimum + i * width:.2f}-{minimum + (i + 1) * width:.2f}",
            "count": count,
        }
        for i, count in enumerate(counts)
    ]
    return {"min": minimum, "median": median, "max": maximum, "buckets": buckets}
