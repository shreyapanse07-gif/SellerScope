import pandas as pd

from app.supply.cleaning import clean_products, dedupe, parse_price, price_stats


def test_clean_products_parses_normal_prices_and_fields():
    frame = clean_products(
        {
            "shopping_results": [
                {
                    "title": "Acme Wireless Headphones",
                    "price": "₹1,499",
                    "source": "Shop One",
                    "rating": 4.5,
                    "reviews": 120,
                },
                {
                    "title": "Widget Pro",
                    "price": "$29.99",
                    "source": "Shop Two",
                },
            ]
        }
    )

    assert list(frame.columns) == [
        "title", "brand", "price", "merchant", "rating", "reviews_count"
    ]
    assert frame.loc[0, "brand"] == "Acme"
    assert frame.loc[0, "price"] == 1499.0
    assert frame.loc[0, "merchant"] == "Shop One"
    assert frame.loc[0, "rating"] == 4.5
    assert frame.loc[0, "reviews_count"] == 120
    assert frame.loc[1, "price"] == 29.99


def test_missing_price_and_unparseable_price_are_missing():
    frame = clean_products(
        {"shopping_results": [{"title": "No Price", "source": "Shop"},
                              {"title": "Unknown Price", "price": "Call for price"}]}
    )

    assert pd.isna(frame.loc[0, "price"])
    assert pd.isna(frame.loc[1, "price"])
    assert parse_price("not a price") is None


def test_clean_products_accepts_serpapi_extracted_price_without_optional_fields():
    frame = clean_products(
        {
            "shopping_results": [
                {
                    "title": "Example Wireless Headphones",
                    "extracted_price": 1499,
                    "price": "₹1,499",
                    "source": "Example Store",
                }
            ]
        }
    )

    assert frame.loc[0, "price"] == 1499
    assert pd.isna(frame.loc[0, "rating"])
    assert pd.isna(frame.loc[0, "reviews_count"])


def test_dedupe_uses_title_and_merchant():
    frame = clean_products(
        {
            "shopping_results": [
                {"title": "Acme Item", "price": "$10", "source": "Shop"},
                {"title": "Acme Item", "price": "$12", "source": "Shop"},
                {"title": "Acme Item", "price": "$10", "source": "Other Shop"},
            ]
        }
    )

    result = dedupe(frame)
    assert len(result) == 2
    assert result.loc[0, "price"] == 10.0


def test_empty_results_return_empty_frame_and_stats():
    frame = clean_products({"shopping_results": []})

    assert frame.empty
    assert list(frame.columns) == [
        "title", "brand", "price", "merchant", "rating", "reviews_count"
    ]
    assert price_stats(frame) == {
        "min": None,
        "median": None,
        "max": None,
        "buckets": [],
    }
