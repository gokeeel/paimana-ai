#!/usr/bin/env python3
"""
train_models.py — train time-overrun and cost-overrun models on train_forward.csv.

Usage:
    python train_models.py --data model_data/train_forward.csv --outdir model_data

MODEL 1 (time): y_slippage_flag (classification) + y_new_slippage_m (regression)
MODEL 2 (cost): y_cost_overrun_flag (classification) + y_new_cost_escalation_pct
                (quantile regression, p50/p90 — the distribution is heavily skewed)

Baseline for every target: "flag everything past its original DoC" (is_past_orig_doc == 1).
Split: GroupKFold(5) on uid — never random, a project never appears in both folds.
"""

import argparse
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.metrics import (
    average_precision_score, mean_absolute_error, mean_pinball_loss, roc_auc_score,
)

CATEGORICAL = ["ministry", "sector", "state", "agency"]

SANCTION_FEATURES = [
    "original_cost", "log_original_cost", "orig_duration_m", "approval_to_start_lag_m",
    "sanction_year", "cost_per_month_planned", "scope_km",
    "kw_bridge", "kw_tunnel", "kw_bypass", "kw_greenfield", "kw_upgrade", "kw_epc",
    "kw_ham", "kw_bot", "kw_doubling", "kw_electrification", "kw_metro", "kw_pipeline",
    "kw_terminal",
] + CATEGORICAL

PROGRESS_FEATURES = [
    "months_elapsed", "elapsed_ratio", "physical_progress", "financial_progress_pct",
    "progress_gap_pct", "months_past_orig_doc", "is_past_orig_doc",
    "cost_revision_to_date_pct", "doc_slip_to_date_m", "d_physical_progress",
    "d_expenditure", "progress_velocity_3m", "is_stalled", "snapshot_index",
]

FEATURES = SANCTION_FEATURES + PROGRESS_FEATURES

LEAKY = {"latest_cost", "revised_doc", "f_cost", "f_doc_mi", "f_progress"}


def check_no_leakage(features):
    bad = [f for f in features if f.startswith("y_") or f in LEAKY]
    assert not bad, f"Leaky columns in feature set: {bad}"


def prep_X(df):
    X = df[FEATURES].copy()
    # HistGradientBoosting caps categorical cardinality at 255; agency has 493 uniques.
    top_agency = X["agency"].value_counts().nlargest(200).index
    X["agency"] = X["agency"].where(X["agency"].isin(top_agency), "Other")
    for c in CATEGORICAL:
        X[c] = X[c].astype("category")
    return X


def precision_at_top_k(y_true, score, frac=0.10):
    n = max(1, int(len(score) * frac))
    top_idx = np.argsort(score)[::-1][:n]
    return y_true.iloc[top_idx].mean() if hasattr(y_true, "iloc") else y_true[top_idx].mean()


def baseline_binary_report(y_true, baseline_flag):
    """is_past_orig_doc as a fixed 0/1 rule — no training, just scored as a predictor."""
    return {
        "roc_auc": roc_auc_score(y_true, baseline_flag),
        "pr_auc": average_precision_score(y_true, baseline_flag),
        "precision@top10%": precision_at_top_k(y_true, baseline_flag),
        "flagged_pct": baseline_flag.mean(),
    }


def train_classifier(X, y, groups, cat_idx):
    clf = HistGradientBoostingClassifier(categorical_features=cat_idx, random_state=0)
    gkf = GroupKFold(n_splits=5)
    proba = cross_val_predict(clf, X, y, groups=groups, cv=gkf, method="predict_proba")[:, 1]
    metrics = {
        "roc_auc": roc_auc_score(y, proba),
        "pr_auc": average_precision_score(y, proba),
        "precision@top10%": precision_at_top_k(y, proba),
    }
    clf.fit(X, y)  # final model on all data
    return clf, metrics


def train_regressor(X, y, groups, cat_idx):
    reg = HistGradientBoostingRegressor(categorical_features=cat_idx, random_state=0)
    gkf = GroupKFold(n_splits=5)
    pred = cross_val_predict(reg, X, y, groups=groups, cv=gkf)
    naive_pred = np.full_like(y, fill_value=y.median(), dtype=float)  # baseline: predict median
    metrics = {
        "mae": mean_absolute_error(y, pred),
        "mae_baseline_median": mean_absolute_error(y, naive_pred),
    }
    reg.fit(X, y)
    return reg, metrics


def train_quantile(X, y, groups, cat_idx, quantile):
    reg = HistGradientBoostingRegressor(
        loss="quantile", quantile=quantile, categorical_features=cat_idx, random_state=0
    )
    gkf = GroupKFold(n_splits=5)
    pred = cross_val_predict(reg, X, y, groups=groups, cv=gkf)
    metrics = {
        "pinball_loss": mean_pinball_loss(y, pred, alpha=quantile),
        "coverage": (y <= pred).mean(),  # should be ~= quantile if well calibrated
        "target_coverage": quantile,
    }
    reg.fit(X, y)
    return reg, metrics


def save(obj, path):
    joblib.dump({"model": obj, "features": FEATURES, "categorical": CATEGORICAL}, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="model_data/train_forward.csv")
    ap.add_argument("--outdir", default="model_data")
    args = ap.parse_args()

    check_no_leakage(FEATURES)

    df = pd.read_csv(args.data, low_memory=False)
    df = df.dropna(subset=["y_slippage_flag", "y_new_slippage_m",
                            "y_cost_overrun_flag", "y_new_cost_escalation_pct"])
    print(f"Training on {len(df)} rows, {df.uid.nunique()} unique projects\n")

    X = prep_X(df)
    groups = df["uid"]
    cat_idx = [FEATURES.index(c) for c in CATEGORICAL]
    baseline_flag = df["is_past_orig_doc"]

    rows = []

    # ── MODEL 1: TIME ──
    print("=== MODEL 1: time overrun ===")
    clf1, m1c = train_classifier(X, df["y_slippage_flag"], groups, cat_idx)
    base1c = baseline_binary_report(df["y_slippage_flag"], baseline_flag)
    reg1, m1r = train_regressor(X, df["y_new_slippage_m"], groups, cat_idx)
    save(clf1, os.path.join(args.outdir, "model1_slippage_clf.joblib"))
    save(reg1, os.path.join(args.outdir, "model1_slippage_reg.joblib"))
    rows += [
        ["time: y_slippage_flag", "model", f"{m1c['roc_auc']:.3f}", f"{m1c['pr_auc']:.3f}", f"{m1c['precision@top10%']:.3f}", "-"],
        ["time: y_slippage_flag", "baseline(is_past_orig_doc)", f"{base1c['roc_auc']:.3f}", f"{base1c['pr_auc']:.3f}", f"{base1c['precision@top10%']:.3f}", "-"],
        ["time: y_new_slippage_m", "model", "-", "-", "-", f"MAE={m1r['mae']:.2f}"],
        ["time: y_new_slippage_m", "baseline(median)", "-", "-", "-", f"MAE={m1r['mae_baseline_median']:.2f}"],
    ]

    # ── MODEL 2: COST ──
    print("=== MODEL 2: cost overrun ===")
    clf2, m2c = train_classifier(X, df["y_cost_overrun_flag"], groups, cat_idx)
    base2c = baseline_binary_report(df["y_cost_overrun_flag"], baseline_flag)
    q50, m2q50 = train_quantile(X, df["y_new_cost_escalation_pct"], groups, cat_idx, 0.5)
    q90, m2q90 = train_quantile(X, df["y_new_cost_escalation_pct"], groups, cat_idx, 0.9)
    save(clf2, os.path.join(args.outdir, "model2_cost_clf.joblib"))
    save(q50, os.path.join(args.outdir, "model2_cost_q50.joblib"))
    save(q90, os.path.join(args.outdir, "model2_cost_q90.joblib"))
    rows += [
        ["cost: y_cost_overrun_flag", "model", f"{m2c['roc_auc']:.3f}", f"{m2c['pr_auc']:.3f}", f"{m2c['precision@top10%']:.3f}", "-"],
        ["cost: y_cost_overrun_flag", "baseline(is_past_orig_doc)", f"{base2c['roc_auc']:.3f}", f"{base2c['pr_auc']:.3f}", f"{base2c['precision@top10%']:.3f}", "-"],
        ["cost: y_new_cost_escalation_pct (p50)", "model", "-", "-", "-", f"pinball={m2q50['pinball_loss']:.2f}, coverage={m2q50['coverage']:.2f} (target 0.50)"],
        ["cost: y_new_cost_escalation_pct (p90)", "model", "-", "-", "-", f"pinball={m2q90['pinball_loss']:.2f}, coverage={m2q90['coverage']:.2f} (target 0.90)"],
    ]

    print("\n=== COMPARISON TABLE (5-fold GroupKFold CV, out-of-fold) ===")
    summary = pd.DataFrame(rows, columns=["target", "model", "roc_auc", "pr_auc", "precision@top10%", "other"])
    print(summary.to_string(index=False))
    summary.to_csv(os.path.join(args.outdir, "model_comparison.csv"), index=False)
    print(f"\nSaved 5 .joblib models + model_comparison.csv to {args.outdir}/")


if __name__ == "__main__":
    main()
