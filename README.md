# SellerScope

**Market intelligence for sellers — validate a product idea before you build it.**

SellerScope answers one question for a first-time or early-stage seller: *"Is this product idea actually worth pursuing?"* It combines live market data (SerpApi) with AI analysis (Gemini) to show real competitor pricing, real customer pain points with evidence, demand trends, and a clear, explainable opportunity score — instead of a black-box recommendation.

Built for the **SerpApi India Hackathon 2026** — Track 4: Commerce & Market Intelligence.

---

## What it does

1. **Enter a product idea** (e.g. "wireless earbuds"), a target market, and a target price.
2. SellerScope fetches real competitor listings and real customer complaints via SerpApi.
3. Gemini extracts canonical product features from listings, and specific, evidence-backed pain themes from complaints — each with a source quote.
4. An opportunity score (`pain × (1 − competitor coverage)`) ranks which gaps are most worth filling, with a plain-language interpretation for each.
5. A demand trend (Google Trends) and a "why now" summary add urgency context.
6. **Test My Product**: enter your own product's features and see exactly which market gaps it would address — and which it would still miss.

Every insight links back to its source — no black-box scoring.

## Tech stack

- **Backend**: Python, FastAPI, Pandas
- **Data**: SerpApi (Google Shopping, Google Search, Google Trends)
- **AI**: Google Gemini API (feature extraction, pain-theme extraction)
- **Frontend**: HTML, CSS, vanilla JavaScript
- **Caching**: SQLite (avoids repeat API spend on identical queries)

## Setup

```bash
git clone <this-repo-url>
cd SellerScope
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your own keys to run a **live** analysis:

```
SERPAPI_KEY=your_serpapi_key
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=models/gemini-flash-latest
LIVE=false
```

No keys are required to see the app working — see **Demo mode** below.

## Run it

```bash
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**

## Demo mode (no API keys needed)

Check **"Use saved demo data"** on the Test My Product page before clicking Analyze. This instantly returns a pre-saved, realistic analysis with zero API calls and zero cost — this is the easiest way to see the full app working without any setup.

Uncheck it to run a real, live analysis on any product (requires your own API keys in `.env`, takes 15–40 seconds).

## Project structure

```
app/
  main.py              # FastAPI endpoints
  pipeline.py          # Orchestrates the full analysis
  serp/client.py       # Cached SerpApi client
  supply/              # Product cleaning, feature extraction, trends
  demand/               # Complaint/pain-point extraction
  scoring/              # Opportunity scoring, Test My Product matching, why-now signal
  static/index.html     # Frontend
data/
  demo_cache.json       # Frozen demo analysis data
tests/                  # Automated tests for every backend module
```

## Testing

```bash
pytest -v
```

## Notes

- All SerpApi and Gemini calls are cached locally (SQLite) to avoid repeat spend during development.
- A `LIVE=false` safety flag (in `.env`) prevents accidental live API calls — set to `true` deliberately to run real analyses.
- Error handling degrades gracefully: if an AI call fails, the app returns partial results instead of crashing.
