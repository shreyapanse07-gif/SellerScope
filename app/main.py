"""MarketGap - Stage 1: seller input layer (Person B).

Run:  pip install -r requirements.txt
      uvicorn app.main:app --reload
Open: http://127.0.0.1:8000
"""
import json
import re
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="SellerScope")
BASE = Path(__file__).parent
# In-memory single-analysis storage — hackathon scope only, not safe for multiple concurrent users.
_last_analysis: dict | None = None

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


class TestProductRequest(BaseModel):
    features: list[str]


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


# ---------- Part 4: analysis pipeline ----------
def run_analysis(ctx: dict) -> dict:
    """Adapt the request context to the analysis pipeline interface."""
    from app.pipeline import run_analysis as analyze_product

    return analyze_product(
        product=ctx["product"],
        market=ctx["market"],
        target_price=ctx["target_price"],
    )


def load_demo_cache(product: str) -> dict:
    f = BASE.parent / "data" / "demo_cache.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    raise HTTPException(
        503,
        "Demo data not available yet — run a live analysis or add data/demo_cache.json",
    )


# ---------- Part 5: the endpoints ----------
@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    global _last_analysis
    if req.demo_mode:
        result = load_demo_cache(req.product)
    else:
        try:
            result = run_analysis(build_context(req))
        except HTTPException:
            raise
        except Exception as e:                      # SerpApi down, credits gone, etc.
            raise HTTPException(status_code=502, detail=f"Analysis failed: {e}")
    _last_analysis = result
    return result


@app.post("/api/test-product")
def test_product(body: TestProductRequest):
    if _last_analysis is None:
        raise HTTPException(400, "Run a market analysis first.")
    known_features = list(_last_analysis["features"].keys())
    opportunities = _last_analysis["opportunities"]
    from app.scoring.test_product import match_product
    return match_product(body.features, known_features, opportunities)


@app.get("/")
def home():
    return FileResponse(BASE / "static" / "index.html")
