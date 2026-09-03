# PAIMANA-AI — Full-stack rebuild design (Postgres + FastAPI + React)

Status: approved, ready for implementation planning.
Supersedes the CSV-driven Streamlit dashboard as the officer-facing surface.
The ML pipeline's modeling logic (HistGradientBoosting + SHAP) is unchanged —
only its output sink and the presentation layer change.

## Scope of this build (Phase 1 — vertical slice)

Three officer-facing screens only: **Portfolio Home, Watchlist, Project
Detail**. Action Log, Ministry Rollup, and Export/Digest are Phase 2 —
schema for them is created now (cheap), but no endpoints or UI for them yet.

Everything ML-internal (risk_score's formula, slip_prob/cost_prob, SHAP
values/feature names, ROC-AUC/PR-AUC, model type, GroupKFold/temporal-split
language, quantile numbers) stays out of every officer-facing endpoint and
screen — this holds for Phase 1 and beyond. See `PRODUCTION_FEATURE_LIST.md`
for the full future feature list and exclusion list this build implements a
slice of.

## Decisions locked in this session

- **Local Postgres via native Windows install** (Docker Desktop was ruled
  out — insufficient disk space on the laptop). PostgreSQL 18 is installed
  at `D:\POSTGRESQL`, running as a Windows service on **port 5433** (not the
  default 5432 — a stray, unrelated PostgreSQL 17 service already owns 5432
  on this machine). Database name: `paimana`. Connection string lives in a
  gitignored `.env` at the repo root as `DATABASE_URL`, read by both
  `ml/db.py` and `backend/app/main.py` — never hardcoded, never committed.
- **Stub auth**: a seeded `users` row, no login screen yet. Action Log (phase
  2) still attributes actions to a real `officer_id`. Real JWT login is a
  later addition once real officers need separate accounts.
- **ML scripts write Postgres directly.** `score_projects.py` and
  `explain_risks.py` are modified to `INSERT`/upsert via SQLAlchemy instead
  of `to_csv`. `build_panel.py` and `train_models.py` are untouched — they
  still read/write CSVs (`panel.csv`, `train_forward.csv`, the `.joblib`
  models) since nothing downstream of them needs Postgres yet.
- **CSV stays the raw-data layer, not a shortcut around it.** PDF extraction
  writes CSV; humans will keep hand-adding CSV files for training. A future
  `load_raw_to_db.py` (Phase 2) automates loading `data/raw/*.csv` into a
  Postgres staging table — but PDF → Postgres direct is explicitly rejected
  (loses the audit trail, doesn't remove real work, breaks the "hand-add a
  CSV" workflow the user relies on).
- **Repo reorganization**, done as part of this build:
  - `extraction/` — `app.py`, `batch_all.py`, `debug_pdf.py`, `templates/`
    (everything that turns PDF → CSV; moved out of repo root).
  - `data/raw/` — `ongoing.csv`, `completed.csv`, `newly_added.csv` (moved
    out of repo root; this is where future hand-added CSVs also go).
  - `ml/` — existing pipeline scripts plus new `db.py` (shared SQLAlchemy
    engine/session) and (Phase 2) `load_raw_to_db.py`.
  - `backend/` — new FastAPI service.
  - `frontend/` — new React app.

## Architecture

```
paimana-extractor/
  .env                        # gitignored — DATABASE_URL, not committed
  extraction/
    app.py
    batch_all.py
    debug_pdf.py
    templates/
  data/
    raw/                      # ongoing.csv, completed.csv, newly_added.csv
  ml/
    db.py                     # NEW — shared SQLAlchemy engine/session
    build_panel.py            # unchanged, reads from data/raw/
    train_models.py           # unchanged
    score_projects.py         # MODIFIED — writes Postgres, not CSV
    explain_risks.py          # MODIFIED — writes Postgres, not CSV
    load_raw_to_db.py         # Phase 2 — not built now
  backend/
    app/
      main.py                 # FastAPI app, CORS for local Vite dev server
      models.py                # SQLAlchemy ORM — schema source of truth
      schemas.py                # Pydantic response shapes
      templates.py               # SHAP feature -> plain-sentence layer
      routers/
        portfolio.py
        watchlist.py
        projects.py
    alembic/                     # migrations generated from models.py
    requirements.txt
  frontend/
    (Vite + React + react-bootstrap + Recharts)
    src/
      pages/
        PortfolioHome.jsx
        Watchlist.jsx
        ProjectDetail.jsx
      api.js
```

**Backend stack:** FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 +
Uvicorn.

**Frontend stack:** Vite + React + `react-bootstrap` (npm package) +
Recharts (risk-trend line chart). Dev server on `localhost:5173` calls
FastAPI on `localhost:8000`.

## Data model (full 7-table schema, created now; Phase 1 populates 5 of them)

| Table | Populated in Phase 1? | Notes |
|---|---|---|
| `projects` | yes | static columns from `panel.csv` |
| `risk_scores` | yes | latest-month row per project |
| `risk_history` | yes | one row per project per month — feeds the trend chart |
| `risk_drivers` | yes | raw SHAP driver rows; officer view never reads this table directly, only through `templates.py` |
| `users` | yes | seeded with one stub officer row |
| `benchmarks` | schema only | Phase 2 (Ministry Rollup) |
| `action_log` | schema only | Phase 2 (Action Log screen) |

## Endpoints (Phase 1)

- `GET /api/portfolio/summary` — KPI strip (total projects, needs-attention
  count, ₹ at risk, new alerts since last run).
- `GET /api/watchlist?tier=amber,red` — alert feed cards: name, agency,
  status pill, one-sentence plain-language reason (via `templates.py`).
- `GET /api/projects/{uid}` — status card (status pill, progress-vs-plan,
  cost-vs-budget).
- `GET /api/projects/{uid}/history` — 12-month risk trend + plain
  improving/worsening label.
- `GET /api/projects/{uid}/reasons` — 2-3 plain sentences from
  `risk_drivers` via the templating layer.

## Templating layer

`backend/app/templates.py`: a `feature_name -> sentence template` dict
(~20-30 entries), extending the pattern `feature_labels.py` already uses for
short labels into full sentences with a value slot, e.g.
`progress_gap_pct` → `"Physical progress is {value}% behind where it should
be at this stage."` This is the only code standing between the model's
numbers and the officer's screen — gets its own unit test.

## Testing

Pytest against a test schema: one test per endpoint (response shape), plus
at least one test per templating case (given a driver row, the expected
sentence). Matches the existing pipeline's "one runnable check per
non-trivial logic unit" bar — no broader test framework.

## Explicitly out of scope for this design

Real JWT auth/login UI, Action Log screen + endpoint, Ministry Rollup screen
+ endpoint, Export/Digest screen + endpoint, `load_raw_to_db.py` automation,
any React visual/branding pass beyond default `react-bootstrap` styling.
These are Phase 2 and listed in `PRODUCTION_FEATURE_LIST.md`; do not build
them as part of this plan.
