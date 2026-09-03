# PAIMANA-AI

Predictive analytics and early-warning system for central-sector infrastructure
projects, built on MoSPI PAIMANA flash report data. SIH26103.

## Setup (one time)

```
pip install -r requirements.txt
```

### Postgres

Native Postgres install, listening on port 5433, database `paimana`. Set
`DATABASE_URL` in a repo-root `.env` (see `.env` for the format already in
use: `postgresql+psycopg2://<user>:<password>@localhost:5433/paimana`).

Then create the schema:

```
cd backend && python -m alembic upgrade head
```

This also seeds a single placeholder `users` row (no login screen yet).

## Full pipeline, in order

Run from the project root. Each step reads the previous step's output.
Steps 4-5 write to Postgres (not CSVs) — the backend/frontend read from
there, not from `model_data/`.

```
# 1. Extract raw tables from PDF flash reports (already done — the CSVs
#    live in data/raw/). Only rerun if you add new monthly PDFs: put them
#    in your Downloads folder, add the filename to
#    extraction/batch_all.py's FILES list, then:
python extraction/batch_all.py

# 2. Feature engineering + forward labels
python build_panel.py --ongoing data/raw/ongoing.csv --completed data/raw/completed.csv --outdir model_data

# 3. Train the 5 models (~1 min)
python train_models.py --data model_data/train_forward.csv --outdir model_data

# 4. Score every project, generate risk tiers + alerts (~10 sec)
#    Writes to the `risk_scores` / `risk_history` Postgres tables (and
#    risk_summary.json to model_data/) — it no longer writes risk_scores.csv.
python score_projects.py --panel model_data/panel.csv --models model_data/ --outdir model_data/

# 5. SHAP driver analysis — writes to the `risk_drivers` Postgres table
#    (reads risk scores/tiers live from Postgres, not a CSV). Computes
#    drivers for every Amber/Red project plus a random Green sample, so
#    runtime scales with how many projects are currently Amber/Red
#    (model-agnostic SHAP explainer, ~3s/row/model — see the file's
#    docstring). Can take tens of minutes on the full portfolio.
python explain_risks.py --panel model_data/panel.csv --models model_data/ --outdir model_data/

# 6. One-page PDF executive summary
python generate_report.py --data model_data --out model_data/risk_report.pdf
```

## Running the app (Postgres + FastAPI + React)

```
# Backend (from repo root)
uvicorn backend.app.main:app --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

The frontend talks to the backend at `http://localhost:8000/api` (see
`frontend/src/api.js`). Steps 1-6 above only need rerunning when a new
month's flash report PDF is added — the backend always reads whatever is
currently in Postgres.

## Legacy: Streamlit dashboard (deprecated)

`dashboard.py` predates the Postgres/FastAPI/React rebuild and reads
`risk_scores.csv`/`risk_history.csv` directly. **These files are no longer
written by `score_projects.py`** (it now writes to Postgres instead), so
`streamlit run dashboard.py` will show stale or missing data unless you
still have old CSVs lying around from before the rebuild. Use the FastAPI +
React stack above instead; this section is kept only for reference until
`dashboard.py` is removed.

## Optional: rigorous evaluation report (not required for the dashboard)

```
python evaluate_temporal.py --train-forward model_data/train_forward.csv --panel model_data/panel.csv --outdir model_data --split-month 2024-12
```

Writes `model_data/temporal_eval.txt` — strict time-based holdout (not
GroupKFold), recall/precision/base-rate/lead-time, sector and ministry
breakdown. Referenced from the dashboard's "Model & Field Analysis" tab.

## File map

| File | Role |
|---|---|
| `extraction/` | PDF table extraction (`app.py` Flask app, `batch_all.py` batch runner, `debug_pdf.py`) |
| `build_panel.py` | Raw CSVs → ML-ready panel + forward labels |
| `train_models.py` | Trains the 5 models, saves `.joblib` + `model_comparison.csv` |
| `score_projects.py` | Runs models on latest month → risk scores, tiers, alerts (writes to Postgres) |
| `explain_risks.py` | SHAP driver analysis (writes to Postgres) |
| `generate_report.py` | One-page PDF executive summary |
| `evaluate_temporal.py` | Strict future-holdout evaluation (separate from the main pipeline) |
| `feature_labels.py` | Shared plain-English feature name map (used by dashboard + PDF report) |
| `backend/` | FastAPI app (`backend/app/`), SQLAlchemy models, Alembic migrations |
| `frontend/` | React (Vite) dashboard UI |
| `data/raw/` | Raw flash-report CSVs extracted from PDFs |
| `dashboard.py` | Legacy Streamlit UI — deprecated, see above |
| `.streamlit/config.toml` | Pinned light theme (GOV.UK-style palette) for the legacy dashboard |

## Notes

- No LLM/cloud API is used anywhere in this pipeline — everything runs locally.
- The backend/frontend never re-run a model; they only read what steps 2-5
  have written to Postgres.
- `model_data/risk_scores.csv` may still exist on disk as a leftover
  artifact from before the Postgres rebuild — it is not regenerated by
  `score_projects.py` anymore and nothing in the current pipeline reads it.
  Safe to ignore or delete.
