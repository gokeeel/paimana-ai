#!/usr/bin/env python3
"""
score_projects.py — run the trained models on the latest panel snapshot and
produce a ranked risk list + early-warning alerts (SIH outcomes c + d).

Usage:
    python score_projects.py --panel model_data/panel.csv --models model_data/ --outdir model_data/
"""

import argparse
import json
import os

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert

from feature_labels import build_X
from ml.db import SessionLocal
from backend.app import models

MODEL_NAMES = [
    "model1_slippage_clf", "model1_slippage_reg",
    "model2_cost_clf", "model2_cost_q50", "model2_cost_q90",
]

PROJECT_COLS = ["uid", "project_name", "agency", "ministry", "sector", "state",
                "original_cost", "latest_cost"]


def upsert_projects(session, df):
    # Sort by report_month first and keep the *last* occurrence per uid: some
    # early panel snapshots have a null project_name that gets filled in by a
    # later month for the same uid (real data-quality artifact in the source
    # CSV, not something the brief's original drop_duplicates("uid") -- which
    # keeps the *first* row -- accounted for). A couple of uids never get a
    # name in any month; fall back to the uid itself so the NOT NULL
    # constraint on projects.project_name is satisfied.
    subset = df.sort_values("report_month")[PROJECT_COLS].drop_duplicates("uid", keep="last")
    subset["project_name"] = subset["project_name"].fillna(subset["uid"])
    rows = subset.where(pd.notna(subset), None).to_dict("records")
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


def load_models(models_dir):
    # joblib.load executes pickle bytecode; safe here since these .joblib files
    # were produced locally by train_models.py in this same pipeline, not from
    # an untrusted source.
    return {n: joblib.load(os.path.join(models_dir, f"{n}.joblib")) for n in MODEL_NAMES}


def risk_tier(score):
    """3-band traffic light per PRD FR-C2: Green 0-39, Amber 40-69, Red 70-100."""
    if score >= 70:
        return "Red"
    if score >= 40:
        return "Amber"
    return "Green"


def score_slice(df, models, top_agency):
    """Attach model predictions + composite risk score to a snapshot of rows."""
    bundle = models["model1_slippage_clf"]
    X = build_X(df, bundle["features"], bundle["categorical"], top_agency)

    out = df.copy()
    out["slip_prob"] = models["model1_slippage_clf"]["model"].predict_proba(X)[:, 1]
    out["slip_months_pred"] = models["model1_slippage_reg"]["model"].predict(X)
    out["cost_prob"] = models["model2_cost_clf"]["model"].predict_proba(X)[:, 1]
    out["cost_q50_pred"] = models["model2_cost_q50"]["model"].predict(X)
    out["cost_q90_pred"] = models["model2_cost_q90"]["model"].predict(X)
    out["risk_score"] = (0.5 * out["slip_prob"] + 0.5 * out["cost_prob"]) * 100
    out["risk_tier"] = out["risk_score"].apply(risk_tier)
    return out


def classify_alert(row):
    if pd.notna(row.get("risk_score_prev")) and (row["risk_score"] - row["risk_score_prev"]) > 15:
        return "Rapidly Deteriorating"
    if pd.notna(row.get("risk_score_prev")) and row["risk_score_prev"] < 40 <= row["risk_score"]:
        return "Newly At Risk"
    if row["slip_prob"] > 0.8 and row.get("physical_progress", 100) < 50 and row.get("is_past_orig_doc") == 1:
        return "Stalled and Overdue"
    return None


def to_native(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return round(float(v), 2)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="model_data/panel.csv")
    ap.add_argument("--models", default="model_data/")
    ap.add_argument("--outdir", default="model_data/")
    args = ap.parse_args()

    panel = pd.read_csv(args.panel, low_memory=False)
    models = load_models(args.models)
    top_agency = panel["agency"].value_counts().nlargest(200).index

    # Score every month once; latest/prev are slices of this, not separate
    # inference passes -- avoids running all 5 models twice on the same rows.
    scored_all = score_slice(panel, models, top_agency)

    months = sorted(panel["report_month"].unique())
    latest_month = months[-1]
    prev_month = months[-2] if len(months) >= 2 else None

    latest = scored_all[scored_all.report_month == latest_month].copy()

    if prev_month is not None:
        prev = scored_all[scored_all.report_month == prev_month]
        latest = latest.merge(
            prev[["uid", "risk_score"]].rename(columns={"risk_score": "risk_score_prev"}),
            on="uid", how="left",
        )
    else:
        latest["risk_score_prev"] = np.nan

    latest["alert_type"] = latest.apply(classify_alert, axis=1)
    latest["risk_score_delta"] = latest["risk_score"] - latest["risk_score_prev"]
    latest = latest.sort_values("risk_score", ascending=False)

    cols = ["uid", "project_name", "agency", "ministry", "sector", "state",
            "original_cost", "latest_cost", "physical_progress", "report_month",
            "slip_prob", "slip_months_pred", "cost_prob", "cost_q50_pred", "cost_q90_pred",
            "risk_score", "risk_tier", "alert_type", "risk_score_delta"]
    result = latest[cols]

    os.makedirs(args.outdir, exist_ok=True)

    with SessionLocal() as session:
        # Use scored_all (every uid across every panel month), not just the
        # latest-month `result` slice: risk_history below carries uids from
        # earlier months too, and its FK to projects.uid needs all of them
        # present, not only the ones still active in the latest snapshot.
        upsert_projects(session, scored_all)
        write_risk_scores(session, result)
        session.commit()
    print(f"Wrote {len(result)} rows to risk_scores (Postgres)")

    tiers = result["risk_tier"].value_counts()
    summary = {
        "report_month": latest_month,
        "total_projects": int(len(result)),
        "red": int(tiers.get("Red", 0)),
        "amber": int(tiers.get("Amber", 0)),
        "green": int(tiers.get("Green", 0)),
        "alerts": {
            "rapidly_deteriorating": int((result.alert_type == "Rapidly Deteriorating").sum()),
            "newly_at_risk": int((result.alert_type == "Newly At Risk").sum()),
            "stalled_and_overdue": int((result.alert_type == "Stalled and Overdue").sum()),
        },
        "top_10_riskiest": [
            {"uid": to_native(r.uid), "project_name": r.project_name, "risk_score": to_native(r.risk_score)}
            for r in result.head(10).itertuples()
        ],
    }
    with open(os.path.join(args.outdir, "risk_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Scored {summary['total_projects']} projects for {latest_month} "
          f"(previous month: {prev_month})\n")
    print("Risk tier distribution:")
    for tier in ["Red", "Amber", "Green"]:
        print(f"  {tier:10s} {summary[tier.lower()]}")
    print("\nAlerts:")
    for k, v in summary["alerts"].items():
        print(f"  {k:25s} {v}")
    print("\nTop 10 riskiest projects:")
    for row in summary["top_10_riskiest"]:
        print(f"  {row['risk_score']:6.1f}  {row['project_name'][:70]}")
    print(f"\nSaved risk_scores.csv ({len(result)} rows) and risk_summary.json to {args.outdir}")

    hist = scored_all[["uid", "report_month", "risk_score", "risk_tier"]]
    with SessionLocal() as session:
        write_risk_history(session, hist)
        session.commit()
    print(f"Wrote {len(hist)} rows to risk_history (Postgres)")


if __name__ == "__main__":
    main()
