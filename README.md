# PAIMANA-AI

Predictive analytics and early-warning system for central-sector infrastructure
projects, built on MoSPI PAIMANA flash report data. SIH26103.

## Setup (one time)

```
pip install -r requirements.txt
```

## Full pipeline, in order

Run from the project root. Each step reads the previous step's output.

```
# 1. Extract raw tables from PDF flash reports (already done — ongoing.csv,
#    completed.csv, newly_added.csv are already in this folder). Only rerun if
#    you add new monthly PDFs: put them in your Downloads folder, add the
#    filename to batch_all.py's FILES list, then:
python batch_all.py

# 2. Feature engineering + forward labels
python build_panel.py --ongoing ongoing.csv --completed completed.csv --outdir model_data

# 3. Train the 5 models (~1 min)
python train_models.py --data model_data/train_forward.csv --outdir model_data

# 4. Score every project, generate risk tiers + alerts (~10 sec)
python score_projects.py --panel model_data/panel.csv --models model_data/ --outdir model_data/

# 5. SHAP explanations (~1-2 min — model-agnostic explainer, see the file's docstring for why)
python explain_risks.py --panel model_data/panel.csv --models model_data/ --risk-scores model_data/risk_scores.csv --outdir model_data/

# 6. One-page PDF executive summary
python generate_report.py --data model_data --out model_data/risk_report.pdf

# 7. Launch the dashboard
streamlit run dashboard.py
```

Open `http://localhost:8501` in a browser. Steps 1–6 only need rerunning when a
new month's flash report PDF is added — step 7 always reads whatever is
currently in `model_data/`.

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
| `app.py` | PDF table extraction (Flask app + `process_uploads`) |
| `batch_all.py` | Batch-runs `app.py` over all monthly PDFs |
| `build_panel.py` | Raw CSVs → ML-ready panel + forward labels |
| `train_models.py` | Trains the 5 models, saves `.joblib` + `model_comparison.csv` |
| `score_projects.py` | Runs models on latest month → risk scores, tiers, alerts |
| `explain_risks.py` | SHAP driver analysis |
| `generate_report.py` | One-page PDF executive summary |
| `evaluate_temporal.py` | Strict future-holdout evaluation (separate from the main pipeline) |
| `feature_labels.py` | Shared plain-English feature name map (used by dashboard + PDF report) |
| `dashboard.py` | Streamlit UI — reads only pre-computed files, no live model inference |
| `.streamlit/config.toml` | Pinned light theme (GOV.UK-style palette) |

## Notes

- No LLM/cloud API is used anywhere in this pipeline — everything runs locally.
- `dashboard.py` never re-runs a model; it only reads files that steps 2–6 produce.
- If `streamlit run dashboard.py` shows a "required data files are missing"
  message, it's telling you exactly which of steps 2–6 to run.
