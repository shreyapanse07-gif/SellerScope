# Project structure

- `app/main.py`: FastAPI application and endpoint definitions.
- `app/pipeline.py`: analysis pipeline module (currently unused by `main.py`).
- `app/serp/client.py`: SerpApi client module (planned).
- `app/llm/`, `app/supply/`, `app/demand/`: analysis components.
- `app/scoring/`: scoring code; `app/scoring/static/index.html` is served at `/`.
- `data/tests/`: test data and tests.

Run the application from the project root with:

```sh
uvicorn app.main:app --reload
```
