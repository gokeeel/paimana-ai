# PAIMANA-AI Phase 1 (Postgres + FastAPI + React) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the CSV-driven Streamlit dashboard with a Postgres-backed
FastAPI + React officer-facing app, covering the Phase 1 vertical slice
(Portfolio Home, Watchlist, Project Detail).

**Architecture:** `ml/` scripts (`score_projects.py`, `explain_risks.py`)
write directly into Postgres via a shared SQLAlchemy engine. A FastAPI
backend (`backend/`) reads that same schema and exposes 5 read-only
endpoints, translating SHAP output into plain-English sentences before it
ever reaches an endpoint. A Vite/React frontend (`frontend/`) with
`react-bootstrap` + Recharts consumes those endpoints across 3 pages.

**Tech Stack:** PostgreSQL 18 (native Windows install), SQLAlchemy 2.0,
Alembic, FastAPI, Pydantic v2, pytest, Vite, React, react-bootstrap,
react-router-dom, Recharts.

**Spec:** `docs/superpowers/specs/2026-09-03-paimana-fullstack-design.md`

## Global Constraints

- Database: `paimana` on native Postgres, host `localhost`, port `5433`
  (not 5432 — a stray unrelated PostgreSQL 17 service already owns 5432 on
  this machine). Connection string lives in `DATABASE_URL` in a gitignored
  `.env` at the repo root — never hardcoded, never committed.
- No officer-facing endpoint or schema may expose: `slip_prob`, `cost_prob`,
  `risk_score`'s formula, raw SHAP values, feature names, ROC-AUC/PR-AUC,
  model type, GroupKFold/temporal-split language, or quantile numbers.
- `build_panel.py` and `train_models.py` are untouched — still read/write
  CSVs and `.joblib` files. Only `score_projects.py` and `explain_risks.py`
  change their output sink.
- Action Log, Ministry Rollup, and Export/Digest screens/endpoints, real
  JWT auth, and `load_raw_to_db.py` are explicitly out of scope for this
  plan (Phase 2).
- This change breaks `dashboard.py` (the old Streamlit app) since it reads
  `risk_scores.csv`/`risk_history.csv`, which this plan stops writing —
  expected and approved in the spec ("supersedes the CSV-driven Streamlit
  dashboard").

---

### Task 1: Repo reorganization

**Files:**
- Move: `app.py` → `extraction/app.py`
- Move: `batch_all.py` → `extraction/batch_all.py`
- Move: `debug_pdf.py` → `extraction/debug_pdf.py`
- Move: `templates/` → `extraction/templates/`
- Move: `ongoing.csv` → `data/raw/ongoing.csv`
- Move: `completed.csv` → `data/raw/completed.csv`
- Move: `newly_added.csv` → `data/raw/newly_added.csv`
- Modify: `generate_jury_doc.py:114`
- Modify: `README.md`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `data/raw/*.csv` — the path every later task and every human
  hand-adding a training CSV reads from and writes to.

- [ ] **Step 1: Verify current file locations**

Run: `ls "C:/Users/Gokul Jayachandran/paimana-extractor"`
Expected: `app.py`, `batch_all.py`, `debug_pdf.py`, `templates/`,
`ongoing.csv`, `completed.csv`, `newly_added.csv` all present at repo root.

- [ ] **Step 2: Move the extraction files and raw CSVs with git mv**

```bash
cd "C:/Users/Gokul Jayachandran/paimana-extractor"
mkdir -p extraction data/raw
git mv app.py extraction/app.py
git mv batch_all.py extraction/batch_all.py
git mv debug_pdf.py extraction/debug_pdf.py
git mv templates extraction/templates
git mv ongoing.csv data/raw/ongoing.csv
git mv completed.csv data/raw/completed.csv
git mv newly_added.csv data/raw/newly_added.csv
```

- [ ] **Step 3: Fix the one hardcoded raw-CSV path**

In `generate_jury_doc.py`, change:

```python
    ongoing_path = "ongoing.csv"
```

to:

```python
    ongoing_path = "data/raw/ongoing.csv"
```

- [ ] **Step 4: Update README usage instructions**

In `README.md`, change the extraction/build_panel instructions block to:

```
# 1. Extract raw tables from PDF flash reports (already done — the CSVs
#    live in data/raw/). Only rerun if you add new monthly PDFs: put them
#    in your Downloads folder, add the filename to
#    extraction/batch_all.py's FILES list, then:
python extraction/batch_all.py

# 2. Feature engineering + forward labels
python build_panel.py --ongoing data/raw/ongoing.csv --completed data/raw/completed.csv --outdir model_data
```

- [ ] **Step 5: Add new dependencies to requirements.txt**

Append to `requirements.txt`:

```
sqlalchemy
psycopg2-binary
alembic
python-dotenv
fastapi
uvicorn[standard]
pytest
httpx
```

- [ ] **Step 6: Verify nothing else references the old root-level paths**

Run: `grep -rn "\"ongoing.csv\"\|'ongoing.csv'\|\"completed.csv\"\|'completed.csv'\|\"newly_added.csv\"\|'newly_added.csv'" --include=*.py .`
Expected: no matches (build_panel.py takes these as CLI args, already
updated in README; nothing else hardcodes them).

- [ ] **Step 7: Verify the moved extraction module still imports cleanly**

Run: `python -c "import sys; sys.path.insert(0, 'extraction'); import app; import debug_pdf; print('extraction imports OK')"`
Expected: `extraction imports OK` (no ImportError — `debug_pdf.py` does
`from app import TABLES, extract_table, report_month_from_pdf`, which still
resolves because both files moved together).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Reorganize repo: extraction/ and data/raw/ folders

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Shared database module and ORM schema

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/app/__init__.py`
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`
- Create: `ml/db.py`
- Test: manual connection check (Step 6 below) — schema has no branching
  logic to unit-test; the check that matters is "does it connect and match
  the real DB."

**Interfaces:**
- Produces: `backend.app.database.engine`, `backend.app.database.SessionLocal`,
  `backend.app.database.get_db()` (FastAPI dependency, yields a `Session`).
- Produces: `backend.app.models.Base` (declarative base, `.metadata` used by
  Alembic) and ORM classes `Project`, `RiskScore`, `RiskHistory`,
  `RiskDriver`, `User`, `Benchmark`, `ActionLog`.
- Produces: `ml.db.engine`, `ml.db.SessionLocal` (re-exports of the above,
  so ML scripts and the API never define the schema twice).

- [ ] **Step 1: Create package init files**

```bash
cd "C:/Users/Gokul Jayachandran/paimana-extractor"
mkdir -p backend/app
touch backend/__init__.py backend/app/__init__.py
```

- [ ] **Step 2: Write `backend/app/database.py`**

```python
"""Single source of truth for the SQLAlchemy engine/session. Both the
FastAPI backend and the ml/ pipeline scripts import from here (via
ml/db.py) so there is exactly one place that knows how to connect."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

engine = create_engine(os.environ["DATABASE_URL"], future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Write `backend/app/models.py`**

```python
"""SQLAlchemy ORM models — the schema source of truth for both the FastAPI
backend and the ml/ pipeline. Alembic migrations are generated from
Base.metadata here; never edit the database schema by hand."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    uid = Column(String, primary_key=True)
    project_name = Column(String, nullable=False)
    agency = Column(String)
    ministry = Column(String)
    sector = Column(String)
    state = Column(String)
    original_cost = Column(Float)
    latest_cost = Column(Float)


class RiskScore(Base):
    __tablename__ = "risk_scores"

    uid = Column(String, ForeignKey("projects.uid"), primary_key=True)
    report_month = Column(String, nullable=False)
    physical_progress = Column(Float)
    slip_prob = Column(Float)
    cost_prob = Column(Float)
    risk_score = Column(Float, nullable=False)
    risk_tier = Column(String, nullable=False)
    alert_type = Column(String)
    risk_score_delta = Column(Float)


class RiskHistory(Base):
    __tablename__ = "risk_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String, ForeignKey("projects.uid"), nullable=False)
    report_month = Column(String, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_tier = Column(String, nullable=False)


class RiskDriver(Base):
    __tablename__ = "risk_drivers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String, ForeignKey("projects.uid"), nullable=False)
    report_month = Column(String, nullable=False)
    driver_rank = Column(Integer, nullable=False)
    feature = Column(String, nullable=False)
    shap_value = Column(Float, nullable=False)
    feature_value = Column(String)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="officer")
    ministry_scope = Column(String)


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dim = Column(String, nullable=False)
    dim_value = Column(String, nullable=False)
    report_month = Column(String, nullable=False)
    pct_on_budget = Column(Float)
    pct_on_time = Column(Float)
    n_projects = Column(Integer)


class ActionLog(Base):
    __tablename__ = "action_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String, ForeignKey("projects.uid"), nullable=False)
    officer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: Write `ml/db.py`**

```python
"""Thin re-export so ml/ pipeline scripts share the exact same engine and
schema as the FastAPI backend — backend/app/database.py and
backend/app/models.py are the single source of truth, this just makes them
importable from scripts run as `python ml/score_projects.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.database import SessionLocal, engine  # noqa: E402,F401
from backend.app.models import Base  # noqa: E402,F401
```

- [ ] **Step 5: Verify `.env` has DATABASE_URL set**

Run: `cat "C:/Users/Gokul Jayachandran/paimana-extractor/.env"`
Expected: a line `DATABASE_URL=postgresql+psycopg2://postgres:<password>@localhost:5433/paimana`
(already created earlier this session — confirm it's still there, don't
recreate it).

- [ ] **Step 6: Verify the module connects to the real database**

Run: `python -c "from ml.db import engine; conn = engine.connect(); print('connected:', conn.execute(__import__('sqlalchemy').text('SELECT 1')).scalar()); conn.close()"`
Expected: `connected: 1`

- [ ] **Step 7: Commit**

```bash
git add backend/__init__.py backend/app/__init__.py backend/app/database.py backend/app/models.py ml/db.py
git commit -m "Add shared SQLAlchemy engine and ORM schema

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Alembic migrations, applied to the real database

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/` (generated migration lands here)

**Interfaces:**
- Consumes: `backend.app.models.Base.metadata` (Task 2).
- Produces: the 7 tables physically existing in the `paimana` database —
  every later task that reads/writes via SQLAlchemy depends on this having
  run.

- [ ] **Step 1: Create the alembic directory structure**

```bash
cd "C:/Users/Gokul Jayachandran/paimana-extractor"
mkdir -p backend/alembic/versions
```

- [ ] **Step 2: Write `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Write `backend/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Write `backend/alembic/env.py`**

```python
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from backend.app.models import Base  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5: Verify no tables exist yet**

Run: `"D:/POSTGRESQL/bin/psql.exe" -U postgres -h localhost -p 5433 -d paimana -c "\dt"`
Expected: `Did not find any relations.`

- [ ] **Step 6: Generate the initial migration**

```bash
cd "C:/Users/Gokul Jayachandran/paimana-extractor/backend"
alembic revision --autogenerate -m "initial schema"
```

Expected: a new file under `backend/alembic/versions/` detecting all 7
tables (`projects`, `risk_scores`, `risk_history`, `risk_drivers`, `users`,
`benchmarks`, `action_log`).

- [ ] **Step 7: Apply the migration**

```bash
alembic upgrade head
```

- [ ] **Step 8: Verify the tables now exist**

Run: `"D:/POSTGRESQL/bin/psql.exe" -U postgres -h localhost -p 5433 -d paimana -c "\dt"`
Expected: 8 rows listed — the 7 schema tables plus `alembic_version`.

- [ ] **Step 9: Commit**

```bash
cd "C:/Users/Gokul Jayachandran/paimana-extractor"
git add backend/alembic.ini backend/alembic/
git commit -m "Add Alembic migrations, apply initial schema to paimana DB

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Rewire `score_projects.py` to write Postgres

**Files:**
- Modify: `score_projects.py`

**Interfaces:**
- Consumes: `ml.db.SessionLocal` (Task 2), `backend.app.models.Project`,
  `RiskScore`, `RiskHistory` (Task 2).
- Produces: populated `projects`, `risk_scores`, `risk_history` tables —
  Task 6 (endpoint tests) and Task 8 (frontend) both read this data.

- [ ] **Step 1: Add the DB imports and upsert helper**

In `score_projects.py`, add near the top (after the existing imports):

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ml.db import SessionLocal
from backend.app import models

PROJECT_COLS = ["uid", "project_name", "agency", "ministry", "sector", "state",
                "original_cost", "latest_cost"]


def upsert_projects(session, df):
    rows = df[PROJECT_COLS].drop_duplicates("uid").where(pd.notna(df[PROJECT_COLS]), None).to_dict("records")
    if not rows:
        return
    stmt = pg_insert(models.Project.__table__).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["uid"],
        set_={c: stmt.excluded[c] for c in PROJECT_COLS if c != "uid"},
    )
    session.execute(stmt)


def write_risk_scores(session, df):
    session.query(models.RiskScore).delete()
    cols = ["uid", "report_month", "physical_progress", "slip_prob", "cost_prob",
            "risk_score", "risk_tier", "alert_type", "risk_score_delta"]
    rows = df[cols].where(pd.notna(df[cols]), None).to_dict("records")
    session.bulk_insert_mappings(models.RiskScore, rows)


def write_risk_history(session, df):
    session.query(models.RiskHistory).delete()
    cols = ["uid", "report_month", "risk_score", "risk_tier"]
    rows = df[cols].where(pd.notna(df[cols]), None).to_dict("records")
    session.bulk_insert_mappings(models.RiskHistory, rows)
```

- [ ] **Step 2: Replace the CSV writes in `main()`**

Find this block in `main()`:

```python
    os.makedirs(args.outdir, exist_ok=True)
    result.to_csv(os.path.join(args.outdir, "risk_scores.csv"), index=False)
```

Change it to:

```python
    os.makedirs(args.outdir, exist_ok=True)

    with SessionLocal() as session:
        upsert_projects(session, result)
        write_risk_scores(session, result)
        session.commit()
    print(f"Wrote {len(result)} rows to risk_scores (Postgres)")
```

Find this block near the end of `main()`:

```python
    hist = scored_all[["uid", "project_name", "report_month", "risk_score", "risk_tier"]]
    hist.to_csv(os.path.join(args.outdir, "risk_history.csv"), index=False)
    print(f"Saved risk_history.csv ({len(hist)} rows) to {args.outdir}")
```

Change it to:

```python
    hist = scored_all[["uid", "report_month", "risk_score", "risk_tier"]]
    with SessionLocal() as session:
        write_risk_history(session, hist)
        session.commit()
    print(f"Wrote {len(hist)} rows to risk_history (Postgres)")
```

Leave `risk_summary.json` writing untouched — `generate_jury_doc.py` and
`generate_report.py` still read it and are out of scope for this plan.

- [ ] **Step 3: Verify the script still runs end-to-end**

Run: `python score_projects.py --panel model_data/panel.csv --models model_data/ --outdir model_data/`
Expected: the existing console output (tier distribution, alert counts, top
10 riskiest) plus the two new lines `Wrote N rows to risk_scores (Postgres)`
and `Wrote N rows to risk_history (Postgres)`, no traceback.

- [ ] **Step 4: Verify the data actually landed**

Run: `"D:/POSTGRESQL/bin/psql.exe" -U postgres -h localhost -p 5433 -d paimana -c "SELECT count(*) FROM projects; SELECT count(*) FROM risk_scores; SELECT count(*) FROM risk_history;"`
Expected: `projects` and `risk_scores` counts match the total project count
printed by the script; `risk_history` count matches total panel rows
scored across all months.

- [ ] **Step 5: Commit**

```bash
git add score_projects.py
git commit -m "Rewire score_projects.py to write Postgres instead of CSV

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Rewire `explain_risks.py` to write Postgres

**Files:**
- Modify: `explain_risks.py`

**Interfaces:**
- Consumes: `ml.db.SessionLocal`, `backend.app.models.RiskDriver` (Task 2).
- Produces: populated `risk_drivers` table (including `feature_value`,
  the raw value each SHAP contribution is computed from) — Task 7's
  templating layer and Task 8's `/reasons` endpoint depend on this column
  existing and being populated.

- [ ] **Step 1: Add the DB imports**

Near the top of `explain_risks.py`, add:

```python
from ml.db import SessionLocal
from backend.app import models
```

- [ ] **Step 2: Capture `report_month` and the raw feature value per driver**

Find this loop in `main()`:

```python
    rows = []
    for pos, row_idx in enumerate(sample_idx):
        uid = sample_uids.loc[row_idx]
        if uid not in risk_by_uid.index:
            continue
        contrib = combined_shap[pos] * 100  # scale to risk_score points
        order = np.argsort(-np.abs(contrib))[:5]
        rec = {"uid": uid, "project_name": risk_by_uid.loc[uid, "project_name"],
               "risk_score": risk_by_uid.loc[uid, "risk_score"]}
        for i, j in enumerate(order, start=1):
            rec[f"driver_{i}_feature"] = features[j]
            rec[f"driver_{i}_shap"] = round(float(contrib[j]), 3)
        rows.append(rec)
```

Replace it with a version that also builds a flat `db_rows` list (one row
per driver, not one row per project) carrying the raw feature value:

```python
    rows = []
    db_rows = []
    for pos, row_idx in enumerate(sample_idx):
        uid = sample_uids.loc[row_idx]
        if uid not in risk_by_uid.index:
            continue
        contrib = combined_shap[pos] * 100  # scale to risk_score points
        order = np.argsort(-np.abs(contrib))[:5]
        report_month = latest.loc[row_idx, "report_month"]
        rec = {"uid": uid, "project_name": risk_by_uid.loc[uid, "project_name"],
               "risk_score": risk_by_uid.loc[uid, "risk_score"]}
        for rank, j in enumerate(order, start=1):
            feature = features[j]
            raw_value = latest.loc[row_idx, feature] if feature in latest.columns else None
            rec[f"driver_{rank}_feature"] = feature
            rec[f"driver_{rank}_shap"] = round(float(contrib[j]), 3)
            db_rows.append({
                "uid": uid,
                "report_month": report_month,
                "driver_rank": rank,
                "feature": feature,
                "shap_value": round(float(contrib[j]), 3),
                "feature_value": None if pd.isna(raw_value) else str(raw_value),
            })
        rows.append(rec)
```

- [ ] **Step 3: Write `db_rows` to Postgres**

Find, near the end of `main()`:

```python
    sample_out = pd.DataFrame(rows)
    sample_out.to_csv(os.path.join(args.outdir, "shap_sample.csv"), index=False)

    top50_out = sample_out.nlargest(50, "risk_score")
    top50_out.to_csv(os.path.join(args.outdir, "shap_top50.csv"), index=False)
```

Leave those two CSV writes as-is (they still feed `cluster_archetypes.py`,
out of scope here) and add immediately after:

```python
    with SessionLocal() as session:
        session.query(models.RiskDriver).delete()
        session.bulk_insert_mappings(models.RiskDriver, db_rows)
        session.commit()
    print(f"Wrote {len(db_rows)} driver rows to risk_drivers (Postgres)")
```

- [ ] **Step 4: Verify the script still runs end-to-end**

Run: `python explain_risks.py --panel model_data/panel.csv --models model_data/ --risk-scores model_data/risk_scores.csv --outdir model_data/`

Note: `--risk-scores` still points at the CSV path as a script argument —
this is fine, that file is stale after Task 4 but the argument itself is
only used to build `risk_by_uid` for display; if `model_data/risk_scores.csv`
no longer exists because you deleted it, regenerate it once via
`python score_projects.py ...` writing to CSV manually, or edit this one
line to read from Postgres instead — call this out to the user if the file
is missing rather than silently failing.

Expected: existing console output plus `Wrote N driver rows to risk_drivers
(Postgres)`, no traceback.

- [ ] **Step 5: Verify the data landed, including feature_value**

Run: `"D:/POSTGRESQL/bin/psql.exe" -U postgres -h localhost -p 5433 -d paimana -c "SELECT uid, feature, shap_value, feature_value FROM risk_drivers LIMIT 5;"`
Expected: 5 rows, `feature_value` column populated (not all NULL).

- [ ] **Step 6: Commit**

```bash
git add explain_risks.py
git commit -m "Rewire explain_risks.py to write Postgres risk_drivers

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: Plain-language templating layer

**Files:**
- Create: `backend/app/templates.py`
- Test: `backend/tests/test_templates.py`
- Create: `backend/tests/__init__.py`

**Interfaces:**
- Produces: `driver_to_sentence(feature: str, feature_value: str | None) ->
  str | None` and `TIER_TO_STATUS: dict[str, str]` — both consumed by
  Task 7's routers.

- [ ] **Step 1: Create the tests package**

```bash
mkdir -p "C:/Users/Gokul Jayachandran/paimana-extractor/backend/tests"
touch "C:/Users/Gokul Jayachandran/paimana-extractor/backend/tests/__init__.py"
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_templates.py`:

```python
from backend.app.templates import TIER_TO_STATUS, driver_to_sentence


def test_numeric_template_formats_percentage():
    result = driver_to_sentence("elapsed_ratio", "0.5")
    assert result == "The project has used up 50% of its planned schedule."


def test_categorical_template():
    result = driver_to_sentence("agency", "NHAI")
    assert result == "The implementing agency is NHAI."


def test_unknown_feature_returns_none():
    assert driver_to_sentence("kw_bridge", "1") is None


def test_non_numeric_value_for_numeric_template_returns_none():
    assert driver_to_sentence("elapsed_ratio", "not-a-number") is None


def test_missing_value_returns_none():
    assert driver_to_sentence("elapsed_ratio", None) is None


def test_tier_to_status_mapping():
    assert TIER_TO_STATUS == {"Green": "On Track", "Amber": "Needs Attention", "Red": "Critical"}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd "C:/Users/Gokul Jayachandran/paimana-extractor" && python -m pytest backend/tests/test_templates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.templates'`

- [ ] **Step 4: Write `backend/app/templates.py`**

```python
"""Feature -> plain-English sentence templates. This is the only code
standing between a SHAP driver row and the officer's screen — every
officer-facing endpoint must go through driver_to_sentence(), never expose
a raw feature name or SHAP value directly."""

TIER_TO_STATUS = {"Green": "On Track", "Amber": "Needs Attention", "Red": "Critical"}

NUMERIC_TEMPLATES = {
    "elapsed_ratio": lambda v: f"The project has used up {v * 100:.0f}% of its planned schedule.",
    "doc_slip_to_date_m": lambda v: f"The completion date has already slipped by {v:.0f} months.",
    "progress_gap_pct": lambda v: f"Physical progress is {v:.0f} percentage points behind financial progress.",
    "cost_revision_to_date_pct": lambda v: f"The project cost has already been revised up by {v:.0f}%.",
    "months_past_orig_doc": lambda v: f"The project is {v:.0f} months past its original completion date.",
    "physical_progress": lambda v: f"Physical progress stands at {v:.0f}%.",
    "financial_progress_pct": lambda v: f"{v:.0f}% of the sanctioned budget has been spent.",
    "d_physical_progress": lambda v: f"Physical progress changed by {v:+.1f} points since last month.",
    "progress_velocity_3m": lambda v: (
        f"Progress has been trending {'downward' if v < 0 else 'upward'} over the last 3 months."
    ),
    "orig_duration_m": lambda v: f"The project's original planned duration was {v:.0f} months.",
    "approval_to_start_lag_m": lambda v: (
        f"There was a {v:.0f}-month gap between approval and the actual start."
    ),
}

CATEGORICAL_TEMPLATES = {
    "agency": lambda v: f"The implementing agency is {v}.",
    "ministry": lambda v: f"This falls under {v}.",
    "sector": lambda v: f"This is a {v} sector project.",
    "state": lambda v: f"Located in {v}.",
}


def driver_to_sentence(feature, feature_value):
    """feature_value is the raw value as stored in risk_drivers.feature_value
    (string form, or None). Returns a plain-English sentence, or None if
    this feature has no template — callers must skip None, never fall back
    to showing the raw feature name."""
    if feature_value is None:
        return None
    if feature in NUMERIC_TEMPLATES:
        try:
            v = float(feature_value)
        except (TypeError, ValueError):
            return None
        return NUMERIC_TEMPLATES[feature](v)
    if feature in CATEGORICAL_TEMPLATES:
        return CATEGORICAL_TEMPLATES[feature](feature_value)
    return None
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest backend/tests/test_templates.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/templates.py backend/tests/
git commit -m "Add SHAP-to-plain-English templating layer

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: FastAPI schemas, routers, and app

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/portfolio.py`
- Create: `backend/app/routers/watchlist.py`
- Create: `backend/app/routers/projects.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_portfolio.py`
- Create: `backend/tests/test_watchlist.py`
- Create: `backend/tests/test_projects.py`

**Interfaces:**
- Consumes: `backend.app.database.get_db`, `backend.app.models.*` (Task 2),
  `backend.app.templates.driver_to_sentence`, `TIER_TO_STATUS` (Task 6).
- Produces: a running FastAPI app at `backend.app.main:app` exposing
  `GET /api/portfolio/summary`, `GET /api/watchlist`,
  `GET /api/projects/{uid}`, `GET /api/projects/{uid}/history`,
  `GET /api/projects/{uid}/reasons` — Task 8 (frontend) calls these.

- [ ] **Step 1: Write `backend/app/schemas.py`**

```python
from typing import Optional

from pydantic import BaseModel


class PortfolioSummary(BaseModel):
    total_projects: int
    needs_attention: int
    at_risk_cost: float
    new_alerts: int
    report_month: str


class WatchlistItem(BaseModel):
    uid: str
    project_name: str
    agency: str
    ministry: str
    status: str
    reason: Optional[str] = None


class ProjectStatus(BaseModel):
    uid: str
    project_name: str
    agency: str
    ministry: str
    sector: str
    state: str
    status: str
    physical_progress: Optional[float]
    original_cost: Optional[float]
    latest_cost: Optional[float]
    report_month: str


class HistoryPoint(BaseModel):
    report_month: str
    risk_score: float
    risk_tier: str


class ProjectHistory(BaseModel):
    uid: str
    points: list[HistoryPoint]
    trend: str


class ProjectReasons(BaseModel):
    uid: str
    reasons: list[str]
```

- [ ] **Step 2: Write the test fixtures**

Create `backend/tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models import Base

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 3: Write the failing portfolio test**

Create `backend/tests/test_portfolio.py`:

```python
from backend.app.models import Project, RiskScore


def test_portfolio_summary(client, db_session):
    db_session.add(Project(uid="1", project_name="Bridge A", agency="NHAI",
                            ministry="MoRTH", sector="Roads", state="UP",
                            original_cost=100.0, latest_cost=120.0))
    db_session.add(Project(uid="2", project_name="Bridge B", agency="NHAI",
                            ministry="MoRTH", sector="Roads", state="UP",
                            original_cost=200.0, latest_cost=200.0))
    db_session.add(RiskScore(uid="1", report_month="2026-07", risk_score=85.0,
                              risk_tier="Red", alert_type="Rapidly Deteriorating"))
    db_session.add(RiskScore(uid="2", report_month="2026-07", risk_score=10.0,
                              risk_tier="Green", alert_type=None))
    db_session.commit()

    resp = client.get("/api/portfolio/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_projects"] == 2
    assert body["needs_attention"] == 1
    assert body["at_risk_cost"] == 120.0
    assert body["new_alerts"] == 1
    assert body["report_month"] == "2026-07"
```

- [ ] **Step 4: Run it to verify it fails**

Run: `cd "C:/Users/Gokul Jayachandran/paimana-extractor" && python -m pytest backend/tests/test_portfolio.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.app.main'`

- [ ] **Step 5: Write `backend/app/routers/__init__.py`** (empty file)

```bash
mkdir -p "C:/Users/Gokul Jayachandran/paimana-extractor/backend/app/routers"
touch "C:/Users/Gokul Jayachandran/paimana-extractor/backend/app/routers/__init__.py"
```

- [ ] **Step 6: Write `backend/app/routers/portfolio.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=schemas.PortfolioSummary)
def get_summary(db: Session = Depends(get_db)):
    latest_month = db.query(func.max(models.RiskScore.report_month)).scalar() or ""
    q = db.query(models.RiskScore).filter(models.RiskScore.report_month == latest_month)
    total = q.count()
    needs_attention = q.filter(models.RiskScore.risk_tier.in_(["Amber", "Red"])).count()
    at_risk_cost = (
        db.query(func.coalesce(func.sum(models.Project.latest_cost), 0.0))
        .join(models.RiskScore, models.RiskScore.uid == models.Project.uid)
        .filter(models.RiskScore.report_month == latest_month, models.RiskScore.risk_tier == "Red")
        .scalar()
    )
    new_alerts = q.filter(models.RiskScore.alert_type.isnot(None)).count()
    return schemas.PortfolioSummary(
        total_projects=total,
        needs_attention=needs_attention,
        at_risk_cost=float(at_risk_cost or 0.0),
        new_alerts=new_alerts,
        report_month=latest_month,
    )
```

- [ ] **Step 7: Write `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import portfolio

app = FastAPI(title="PAIMANA-AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router)
```

- [ ] **Step 8: Run the portfolio test to verify it passes**

Run: `python -m pytest backend/tests/test_portfolio.py -v`
Expected: 1 passed.

- [ ] **Step 9: Write the failing watchlist test**

Create `backend/tests/test_watchlist.py`:

```python
from backend.app.models import Project, RiskDriver, RiskScore


def test_watchlist_returns_flagged_projects_with_a_reason(client, db_session):
    db_session.add(Project(uid="1", project_name="Bridge A", agency="NHAI",
                            ministry="MoRTH", sector="Roads", state="UP"))
    db_session.add(Project(uid="2", project_name="Bridge B", agency="NHAI",
                            ministry="MoRTH", sector="Roads", state="UP"))
    db_session.add(RiskScore(uid="1", report_month="2026-07", risk_score=85.0, risk_tier="Red"))
    db_session.add(RiskScore(uid="2", report_month="2026-07", risk_score=10.0, risk_tier="Green"))
    db_session.add(RiskDriver(uid="1", report_month="2026-07", driver_rank=1,
                               feature="elapsed_ratio", shap_value=9.0, feature_value="0.9"))
    db_session.commit()

    resp = client.get("/api/watchlist?tier=amber,red")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["uid"] == "1"
    assert body[0]["status"] == "Critical"
    assert body[0]["reason"] == "The project has used up 90% of its planned schedule."
```

- [ ] **Step 10: Run it to verify it fails**

Run: `python -m pytest backend/tests/test_watchlist.py -v`
Expected: FAIL — 404 (no `/api/watchlist` route registered yet).

- [ ] **Step 11: Write `backend/app/routers/watchlist.py`**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..templates import TIER_TO_STATUS, driver_to_sentence

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[schemas.WatchlistItem])
def get_watchlist(tier: str = Query("amber,red"), db: Session = Depends(get_db)):
    tiers = [t.strip().capitalize() for t in tier.split(",")]
    latest_month = db.query(func.max(models.RiskScore.report_month)).scalar() or ""
    rows = (
        db.query(models.RiskScore, models.Project)
        .join(models.Project, models.Project.uid == models.RiskScore.uid)
        .filter(models.RiskScore.report_month == latest_month, models.RiskScore.risk_tier.in_(tiers))
        .order_by(models.RiskScore.risk_score.desc())
        .all()
    )
    items = []
    for score, project in rows:
        driver = (
            db.query(models.RiskDriver)
            .filter(models.RiskDriver.uid == project.uid, models.RiskDriver.report_month == latest_month)
            .order_by(models.RiskDriver.driver_rank)
            .first()
        )
        reason = driver_to_sentence(driver.feature, driver.feature_value) if driver else None
        items.append(schemas.WatchlistItem(
            uid=project.uid,
            project_name=project.project_name,
            agency=project.agency or "",
            ministry=project.ministry or "",
            status=TIER_TO_STATUS.get(score.risk_tier, score.risk_tier),
            reason=reason,
        ))
    return items
```

- [ ] **Step 12: Register the router in `backend/app/main.py`**

```python
from .routers import portfolio, watchlist
```

and add:

```python
app.include_router(watchlist.router)
```

- [ ] **Step 13: Run the watchlist test to verify it passes**

Run: `python -m pytest backend/tests/test_watchlist.py -v`
Expected: 1 passed.

- [ ] **Step 14: Write the failing projects tests**

Create `backend/tests/test_projects.py`:

```python
from backend.app.models import Project, RiskDriver, RiskHistory, RiskScore


def _seed_project(db_session):
    db_session.add(Project(uid="1", project_name="Bridge A", agency="NHAI",
                            ministry="MoRTH", sector="Roads", state="UP",
                            original_cost=100.0, latest_cost=120.0))
    db_session.add(RiskScore(uid="1", report_month="2026-07", physical_progress=40.0,
                              risk_score=85.0, risk_tier="Red"))
    db_session.commit()


def test_get_project_status(client, db_session):
    _seed_project(db_session)
    resp = client.get("/api/projects/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "Critical"
    assert body["physical_progress"] == 40.0


def test_get_project_status_404_for_unknown_uid(client, db_session):
    resp = client.get("/api/projects/does-not-exist")
    assert resp.status_code == 404


def test_get_project_history_trend(client, db_session):
    _seed_project(db_session)
    db_session.add(RiskHistory(uid="1", report_month="2026-01", risk_score=20.0, risk_tier="Green"))
    db_session.add(RiskHistory(uid="1", report_month="2026-07", risk_score=85.0, risk_tier="Red"))
    db_session.commit()

    resp = client.get("/api/projects/1/history")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["points"]) == 2
    assert body["trend"] == "worsening"


def test_get_project_reasons(client, db_session):
    _seed_project(db_session)
    db_session.add(RiskDriver(uid="1", report_month="2026-07", driver_rank=1,
                               feature="elapsed_ratio", shap_value=9.0, feature_value="0.9"))
    db_session.add(RiskDriver(uid="1", report_month="2026-07", driver_rank=2,
                               feature="kw_bridge", shap_value=1.0, feature_value="1"))
    db_session.commit()

    resp = client.get("/api/projects/1/reasons")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reasons"] == ["The project has used up 90% of its planned schedule."]
```

- [ ] **Step 15: Run them to verify they fail**

Run: `python -m pytest backend/tests/test_projects.py -v`
Expected: FAIL — 404 (no `/api/projects/*` routes registered yet).

- [ ] **Step 16: Write `backend/app/routers/projects.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..templates import TIER_TO_STATUS, driver_to_sentence

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _latest_score(db, uid):
    return (
        db.query(models.RiskScore)
        .filter(models.RiskScore.uid == uid)
        .order_by(models.RiskScore.report_month.desc())
        .first()
    )


@router.get("/{uid}", response_model=schemas.ProjectStatus)
def get_project(uid: str, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.uid == uid).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    score = _latest_score(db, uid)
    if score is None:
        raise HTTPException(status_code=404, detail="No risk score for this project")
    return schemas.ProjectStatus(
        uid=project.uid,
        project_name=project.project_name,
        agency=project.agency or "",
        ministry=project.ministry or "",
        sector=project.sector or "",
        state=project.state or "",
        status=TIER_TO_STATUS.get(score.risk_tier, score.risk_tier),
        physical_progress=score.physical_progress,
        original_cost=project.original_cost,
        latest_cost=project.latest_cost,
        report_month=score.report_month,
    )


@router.get("/{uid}/history", response_model=schemas.ProjectHistory)
def get_project_history(uid: str, db: Session = Depends(get_db)):
    rows = (
        db.query(models.RiskHistory)
        .filter(models.RiskHistory.uid == uid)
        .order_by(models.RiskHistory.report_month)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No history for this project")
    points = [
        schemas.HistoryPoint(report_month=r.report_month, risk_score=r.risk_score, risk_tier=r.risk_tier)
        for r in rows
    ]
    if len(points) >= 2:
        delta = points[-1].risk_score - points[0].risk_score
        trend = "worsening" if delta > 5 else "improving" if delta < -5 else "stable"
    else:
        trend = "stable"
    return schemas.ProjectHistory(uid=uid, points=points, trend=trend)


@router.get("/{uid}/reasons", response_model=schemas.ProjectReasons)
def get_project_reasons(uid: str, db: Session = Depends(get_db)):
    latest_month = (
        db.query(func.max(models.RiskDriver.report_month))
        .filter(models.RiskDriver.uid == uid)
        .scalar()
    )
    drivers = (
        db.query(models.RiskDriver)
        .filter(models.RiskDriver.uid == uid, models.RiskDriver.report_month == latest_month)
        .order_by(models.RiskDriver.driver_rank)
        .all()
    )
    reasons = []
    for d in drivers:
        sentence = driver_to_sentence(d.feature, d.feature_value)
        if sentence:
            reasons.append(sentence)
        if len(reasons) == 3:
            break
    return schemas.ProjectReasons(uid=uid, reasons=reasons)
```

- [ ] **Step 17: Register the router in `backend/app/main.py`**

```python
from .routers import portfolio, projects, watchlist
```

and add:

```python
app.include_router(projects.router)
```

- [ ] **Step 18: Run the full backend test suite**

Run: `python -m pytest backend/tests/ -v`
Expected: all tests pass (1 portfolio + 1 watchlist + 4 projects + 6
templating = 12 passed).

- [ ] **Step 19: Commit**

```bash
git add backend/app/ backend/tests/
git commit -m "Add FastAPI schemas, routers, and app (portfolio/watchlist/projects)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Run the API against the real database

**Files:** none (verification task)

**Interfaces:**
- Consumes: Tasks 4-7 (real data in Postgres, working FastAPI app).

- [ ] **Step 1: Start the API server**

Run (from repo root, in its own terminal/background process):
`uvicorn backend.app.main:app --reload --port 8000`
Expected: `Uvicorn running on http://127.0.0.1:8000`

- [ ] **Step 2: Verify the summary endpoint against real data**

Run: `curl http://localhost:8000/api/portfolio/summary`
Expected: a JSON object with `total_projects` matching the project count
from Task 4's verification step.

- [ ] **Step 3: Verify the watchlist endpoint against real data**

Run: `curl "http://localhost:8000/api/watchlist?tier=amber,red"`
Expected: a JSON array; spot-check that at least one item has a non-null
`reason` string with no feature names or numbers-as-jargon in it (plain
English only).

- [ ] **Step 4: Verify a project detail + history + reasons for a real uid**

Pick a `uid` from the Step 3 output, then:

```bash
curl http://localhost:8000/api/projects/<uid>
curl http://localhost:8000/api/projects/<uid>/history
curl http://localhost:8000/api/projects/<uid>/reasons
```

Expected: 200 responses from all three, `history.points` length equals the
number of months that uid appears in `panel.csv`, `reasons.reasons` has 0-3
plain-English sentences.

No commit — this task produces no file changes, only confirms Tasks 4-7
work together against the real database before frontend work begins.

---

### Task 9: React frontend (Vite + react-bootstrap + Recharts)

**Files:**
- Create: `frontend/` (Vite-scaffolded React app)
- Create: `frontend/src/api.js`
- Create: `frontend/src/App.jsx` (overwrite Vite's default)
- Create: `frontend/src/main.jsx` (overwrite Vite's default)
- Create: `frontend/src/pages/PortfolioHome.jsx`
- Create: `frontend/src/pages/Watchlist.jsx`
- Create: `frontend/src/pages/ProjectDetail.jsx`

**Interfaces:**
- Consumes: the 5 endpoints from Task 7, served by Task 8's running
  `uvicorn` process at `http://localhost:8000`.

- [ ] **Step 1: Scaffold the Vite React app**

```bash
cd "C:/Users/Gokul Jayachandran/paimana-extractor"
mkdir frontend
cd frontend
npm create vite@latest . -- --template react
npm install
npm install react-bootstrap bootstrap recharts react-router-dom
```

- [ ] **Step 2: Write `frontend/src/api.js`**

```javascript
const BASE_URL = "http://localhost:8000/api";

async function getJSON(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`Request to ${path} failed (${res.status})`);
  return res.json();
}

export const getPortfolioSummary = () => getJSON("/portfolio/summary");
export const getWatchlist = (tier = "amber,red") => getJSON(`/watchlist?tier=${tier}`);
export const getProject = (uid) => getJSON(`/projects/${uid}`);
export const getProjectHistory = (uid) => getJSON(`/projects/${uid}/history`);
export const getProjectReasons = (uid) => getJSON(`/projects/${uid}/reasons`);
```

- [ ] **Step 3: Write `frontend/src/pages/PortfolioHome.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Alert, Card, Col, Row, Spinner } from "react-bootstrap";
import { getPortfolioSummary } from "../api";

export default function PortfolioHome() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getPortfolioSummary().then(setSummary).catch((e) => setError(e.message));
  }, []);

  if (error) return <Alert variant="danger">{error}</Alert>;
  if (!summary) return <Spinner animation="border" />;

  const tiles = [
    ["Total Projects", summary.total_projects],
    ["Needs Attention", summary.needs_attention],
    ["₹ at Risk (Cr)", summary.at_risk_cost.toFixed(0)],
    ["New Alerts", summary.new_alerts],
  ];

  return (
    <Row className="g-3">
      {tiles.map(([label, value]) => (
        <Col md={3} key={label}>
          <Card body>
            <Card.Title>{label}</Card.Title>
            <h2>{value}</h2>
          </Card>
        </Col>
      ))}
    </Row>
  );
}
```

- [ ] **Step 4: Write `frontend/src/pages/Watchlist.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Alert, Badge, Card, Spinner } from "react-bootstrap";
import { Link } from "react-router-dom";
import { getWatchlist } from "../api";

const STATUS_VARIANT = { "On Track": "success", "Needs Attention": "warning", Critical: "danger" };

export default function Watchlist() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getWatchlist().then(setItems).catch((e) => setError(e.message));
  }, []);

  if (error) return <Alert variant="danger">{error}</Alert>;
  if (!items) return <Spinner animation="border" />;

  return (
    <div className="d-flex flex-column gap-2">
      {items.map((item) => (
        <Card key={item.uid} body>
          <div className="d-flex justify-content-between align-items-start">
            <div>
              <Link to={`/projects/${item.uid}`}>{item.project_name}</Link>
              <div className="text-muted small">{item.agency} — {item.ministry}</div>
              {item.reason && <div className="mt-1">{item.reason}</div>}
            </div>
            <Badge bg={STATUS_VARIANT[item.status] || "secondary"}>{item.status}</Badge>
          </div>
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Write `frontend/src/pages/ProjectDetail.jsx`**

```jsx
import { useEffect, useState } from "react";
import { Alert, Badge, Card, ListGroup, Spinner } from "react-bootstrap";
import { useParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getProject, getProjectHistory, getProjectReasons } from "../api";

const STATUS_VARIANT = { "On Track": "success", "Needs Attention": "warning", Critical: "danger" };

export default function ProjectDetail() {
  const { uid } = useParams();
  const [project, setProject] = useState(null);
  const [history, setHistory] = useState(null);
  const [reasons, setReasons] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([getProject(uid), getProjectHistory(uid), getProjectReasons(uid)])
      .then(([p, h, r]) => {
        setProject(p);
        setHistory(h);
        setReasons(r);
      })
      .catch((e) => setError(e.message));
  }, [uid]);

  if (error) return <Alert variant="danger">{error}</Alert>;
  if (!project || !history || !reasons) return <Spinner animation="border" />;

  return (
    <div className="d-flex flex-column gap-3">
      <Card body>
        <div className="d-flex justify-content-between align-items-center">
          <div>
            <Card.Title>{project.project_name}</Card.Title>
            <div className="text-muted">{project.agency} — {project.ministry} — {project.state}</div>
          </div>
          <Badge bg={STATUS_VARIANT[project.status] || "secondary"}>{project.status}</Badge>
        </div>
        <div className="mt-2">Physical progress: {project.physical_progress?.toFixed(0)}%</div>
        <div>Cost: ₹{project.latest_cost} Cr (sanctioned ₹{project.original_cost} Cr)</div>
      </Card>

      <Card body>
        <Card.Title>Risk Trend ({history.trend})</Card.Title>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={history.points}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="report_month" />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Line type="monotone" dataKey="risk_score" stroke="#0d6efd" />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Card body>
        <Card.Title>Why Flagged</Card.Title>
        <ListGroup variant="flush">
          {reasons.reasons.length === 0 && <ListGroup.Item>No specific drivers identified.</ListGroup.Item>}
          {reasons.reasons.map((r, i) => (
            <ListGroup.Item key={i}>{r}</ListGroup.Item>
          ))}
        </ListGroup>
      </Card>
    </div>
  );
}
```

- [ ] **Step 6: Write `frontend/src/App.jsx`** (overwrite the Vite default)

```jsx
import { Container, Nav, Navbar } from "react-bootstrap";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import PortfolioHome from "./pages/PortfolioHome";
import ProjectDetail from "./pages/ProjectDetail";
import Watchlist from "./pages/Watchlist";

export default function App() {
  return (
    <BrowserRouter>
      <Navbar bg="dark" variant="dark">
        <Container>
          <Navbar.Brand as={Link} to="/">PAIMANA-AI</Navbar.Brand>
          <Nav>
            <Nav.Link as={Link} to="/">Portfolio</Nav.Link>
            <Nav.Link as={Link} to="/watchlist">Watchlist</Nav.Link>
          </Nav>
        </Container>
      </Navbar>
      <Container className="mt-4">
        <Routes>
          <Route path="/" element={<PortfolioHome />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/projects/:uid" element={<ProjectDetail />} />
        </Routes>
      </Container>
    </BrowserRouter>
  );
}
```

- [ ] **Step 7: Write `frontend/src/main.jsx`** (overwrite the Vite default)

```jsx
import "bootstrap/dist/css/bootstrap.min.css";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 8: Manual verification (the frontend's "one runnable check")**

With the Task 8 `uvicorn` server still running in one terminal, run in a
second terminal:

```bash
cd "C:/Users/Gokul Jayachandran/paimana-extractor/frontend"
npm run dev
```

Open `http://localhost:5173` in a browser and confirm:
1. Portfolio Home shows 4 non-zero-looking KPI tiles with real numbers.
2. Watchlist shows cards for Red/Amber projects, each with a status badge
   and (where a driver exists) a plain-English reason sentence — no
   feature names like `elapsed_ratio` visible anywhere on screen.
3. Clicking a project name navigates to its detail page, showing the
   status card, a rendered line chart, and a "Why Flagged" list.

- [ ] **Step 9: Commit**

```bash
cd "C:/Users/Gokul Jayachandran/paimana-extractor"
git add frontend/
git commit -m "Add React frontend (Portfolio Home, Watchlist, Project Detail)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-review notes

- **Spec coverage:** repo reorg (Task 1), Postgres schema (Task 2-3), ML
  pipeline rewiring (Task 4-5), templating layer (Task 6), all 5 Phase-1
  endpoints (Task 7), end-to-end verification (Task 8), all 3 Phase-1
  screens (Task 9) — every section of the spec's Phase 1 scope has a task.
  Action Log, Ministry Rollup, Export/Digest, and real auth are correctly
  absent — spec marks them Phase 2.
- **Type consistency checked:** `driver_to_sentence(feature, feature_value)`
  signature is identical everywhere it's called (Task 6 tests, Task 7's
  `watchlist.py` and `projects.py`). `TIER_TO_STATUS` keys (`Green`/`Amber`/
  `Red`) match `risk_tier` values written by `score_projects.py`'s existing
  `risk_tier()` function (untouched, still returns those exact strings).
  `RiskDriver.feature_value` (Task 2) is written by Task 5 and read by
  Task 6/7 — same column, same type (`String`, nullable).
