"""MarketGap - Stage 1: seller input layer (Person B).

Run:  pip install -r requirements.txt
      uvicorn main:app --reload
Open: http://127.0.0.1:8000
"""
import json
import re
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="MarketGap")
BASE = Path(__file__).parent

# ---------- Part 1: the markets we support -> SerpApi parameters ----------
MARKETS = {
    "India": {"gl": "in", "hl": "en", "location": "India", "currency": "INR"},
    "United States": {"gl": "us", "hl": "en", "location": "United States", "currency": "USD"},
}


# ---------- Part 2: the request shape (FastAPI validates this for us) ----------
class AnalyzeRequest(BaseModel):
    product: str = Field(min_length=2, max_length=80)
    market: str = "India"
    target_price: Optional[float] = Field(default=None, gt=0)
    proposed_features: List[str] = []
    demo_mode: bool = False

    @field_validator("product")
    @classmethod
    def clean_product(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v).strip()
        if len(v) < 2:
            raise ValueError("Enter at least 2 characters for the product")
        return v


# ---------- Part 3: turn raw input into a clean context for the pipeline ----------
def build_context(req: AnalyzeRequest) -> dict:
    if req.market not in MARKETS:
        raise HTTPException(status_code=400, detail=f"Unsupported market: {req.market}")
    return {
        "product": req.product.lower(),          # lowercase = stable cache key
        "market": req.market,
        "params": MARKETS[req.market],           # gl / hl / location for SerpApi
        "target_price": req.target_price,
        "proposed_features": [f.strip() for f in req.proposed_features if f.strip()],
    }


# ---------- Part 4: stub of Person A's pipeline (same shape as contract.md) ----------
def run_analysis(ctx: dict) -> dict:
    """Replace this import with: from pipeline import run_analysis"""
    return {
        "query": {"product": ctx["product"], "market": ctx["market"], "target_price": ctx["target_price"]},
        "products": [
            {"title": "Foldable Aluminium Laptop Stand", "brand": "Portronics", "merchant": "Amazon.in",
             "price": 1299, "rating": 4.2, "features": ["foldable", "aluminum", "adjustable"]},
            {"title": "Adjustable Laptop Stand 360 Rotation", "brand": "Lifelong", "merchant": "Flipkart",
             "price": 1499, "rating": 3.9, "features": ["adjustable", "360 rotation"]},
        ],
        "price_stats": {"min": 599, "median": 1299, "max": 2999, "buckets": []},
        "features": [{"name": "foldable", "count": 14, "coverage_pct": 70}],
        "pain_points": [{"theme": "Stability", "mentions": 37, "example_snippet": "wobbles at max height", "source_url": ""}],
        "opportunities": [{"theme": "Stability", "pain_score": 0.9, "coverage_score": 0.2,
                           "opportunity_score": 0.72, "interpretation": "Potential gap worth investigating."}],
        "news": [],
    }


def load_demo_cache(product: str) -> dict:
    f = BASE / "demo_cache.json"          # Person A drops the frozen demo data here
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return run_analysis(build_context(AnalyzeRequest(product=product)))


# ---------- Part 5: the endpoints ----------
@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    if req.demo_mode:
        return load_demo_cache(req.product)
    try:
        return run_analysis(build_context(req))
    except HTTPException:
        raise
    except Exception as e:                      # SerpApi down, credits gone, etc.
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}")


@app.get("/")
def home():
    return FileResponse(BASE / "index.html")