#!/usr/bin/env python3
"""
evaluate_temporal.py — strict time-based holdout evaluation, addressing the gap
GroupKFold leaves open: GroupKFold stops the same project's rows splitting across
folds, but says nothing about the model training on later calendar time than it's
tested on. Here: train on report_month <= SPLIT_MONTH, test strictly after it.

Reports, on the held-out future period only: ROC-AUC, PR-AUC, Precision@10%,
Recall@10%, base rate, bootstrap 95% CI, confusion matrix -- for the trained model,
a logistic-regression baseline, and the is_past_orig_doc heuristic. Then a sector/
ministry breakdown, and a lead-time analysis: does the risk score cross the alert
threshold BEFORE the project's own status turns adverse, or only after?

Usage:
    python evaluate_temporal.py --train-forward model_data/train_forward.csv \
        --panel model_data/panel.csv --outdir model_data --split-month 2024-12
"""

import argparse
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from train_models import CATEGORICAL, FEATURES
from feature_labels import build_X as _build_X

NUMERIC = [f for f in FEATURES if f not in CATEGORICAL]
N_BOOTSTRAP = 500
ALERT_THRESHOLD = 0.5  # matches the "High" risk tier cutoff used in score_projects.py


def build_X(df, top_agency):
    return _build_X(df, FEATURES, CATEGORICAL, top_agency)


def precision_recall_at_k(y_true, score, frac=0.10):
    n = max(1, int(len(score) * frac))
    top_idx = np.argsort(score)[::-1][:n]
    precision = y_true.iloc[top_idx].mean()
    recall = y_true.iloc[top_idx].sum() / y_true.sum() if y_true.sum() else np.nan
    return precision, recall


def bootstrap_auc_ci(y_true, score, n=N_BOOTSTRAP, seed=0):
    rng = np.random.default_rng(seed)
    y_true = y_true.to_numpy()
    aucs = []
    idx_all = np.arange(len(y_true))
    for _ in range(n):
        idx = rng.choice(idx_all, size=len(idx_all), replace=True)
        if len(np.unique(y_true[idx])) < 2:
            continue
        aucs.append(roc_auc_score(y_true[idx], score[idx]))
    return np.percentile(aucs, [2.5, 97.5])


def logistic_baseline(X_train, y_train, X_test):
    """Simple numeric-only logistic regression -- no categorical encoding, to
    stay a genuinely 'simple' baseline rather than a second gradient-boosted model."""
    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=2000)),
    ])
    pipe.fit(X_train[NUMERIC], y_train)
    return pipe.predict_proba(X_test[NUMERIC])[:, 1]


def evaluate(name, y_test, scores_by_model, outlines):
    base_rate = y_test.mean()
    outlines.append(f"\n--- {name} --- (test n={len(y_test)}, base rate={base_rate:.1%})")
    for model_name, score in scores_by_model.items():
        auc = roc_auc_score(y_test, score)
        pr_auc = average_precision_score(y_test, score)
        p10, r10 = precision_recall_at_k(y_test, score)
        lo, hi = bootstrap_auc_ci(y_test, score)
        preds = (score >= 0.5).astype(int) if score.max() <= 1 else (score >= score.mean()).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_test, preds).ravel()
        outlines.append(
            f"  {model_name:22s} ROC-AUC={auc:.3f} (95% CI {lo:.3f}-{hi:.3f})  PR-AUC={pr_auc:.3f}  "
            f"P@10%={p10:.3f}  R@10%={r10:.3f}  TP={tp} FP={fp} FN={fn} TN={tn}"
        )


def subgroup_breakdown(df, y_col, score, dim, outlines, min_n=20):
    tmp = pd.DataFrame({"y": df[y_col].values, "score": score, "group": df[dim].values})
    outlines.append(f"\n  By {dim} (HGB model, min {min_n} rows, both classes present):")
    for g, sub in tmp.groupby("group"):
        if len(sub) < min_n or sub.y.nunique() < 2:
            continue
        auc = roc_auc_score(sub.y, sub.score)
        p10, _ = precision_recall_at_k(sub.y, sub.score)
        outlines.append(f"    {str(g):30s} n={len(sub):4d}  ROC-AUC={auc:.3f}  P@10%={p10:.3f}")


def lead_time_analysis(panel, test_uids, top_agency, clf, feature_cols, event_col, event_test, split_mi, outlines, label):
    """For test-period projects, score every historical month with the temporally-
    held-out model and compare when the alert first fires to when the project's own
    status first turns adverse. Positive lead_time_m = warned before the event."""
    hist = panel[panel.uid.isin(test_uids)].sort_values(["uid", "report_mi"]).copy()
    X = build_X(hist, top_agency)
    hist["score"] = clf.predict_proba(X)[:, 1]

    rows = []
    for uid, g in hist.groupby("uid"):
        g = g.sort_values("report_mi")
        event_rows = g[event_test(g[event_col])]
        if event_rows.empty:
            continue
        t_event = event_rows.report_mi.iloc[0]
        if t_event <= split_mi:
            continue  # event already happened before the holdout window -- not a future prediction
        pre_event = g[g.report_mi < t_event]
        alert_rows = pre_event[(pre_event.score >= ALERT_THRESHOLD) & (pre_event.report_mi > split_mi)]
        if alert_rows.empty:
            continue
        t_alert = alert_rows.report_mi.iloc[0]
        rows.append(t_event - t_alert)

    outlines.append(f"\n  Lead time -- {label}: {len(rows)} projects with a pre-event alert in the holdout window")
    if rows:
        arr = np.array(rows)
        outlines.append(
            f"    median={np.median(arr):.1f}mo  p25={np.percentile(arr,25):.1f}mo  "
            f"p75={np.percentile(arr,75):.1f}mo  (positive = warned before the event)"
        )
        outlines.append(f"    reactive (<=0 months lead): {(arr <= 0).sum()}/{len(arr)}")
    else:
        outlines.append("    no matched project had both a pre-event alert and a subsequent adverse event")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-forward", default="model_data/train_forward.csv")
    ap.add_argument("--panel", default="model_data/panel.csv")
    ap.add_argument("--outdir", default="model_data")
    ap.add_argument("--split-month", default="2024-12")
    args = ap.parse_args()

    tf = pd.read_csv(args.train_forward, low_memory=False, dtype={"uid": str})
    panel = pd.read_csv(args.panel, low_memory=False, dtype={"uid": str})

    train_df = tf[tf.report_month <= args.split_month].copy()
    test_df = tf[tf.report_month > args.split_month].copy()
    split_mi = train_df.report_mi.max()

    outlines = [
        f"TEMPORAL HOLDOUT EVALUATION -- train report_month <= {args.split_month} "
        f"({len(train_df)} rows), test > {args.split_month} ({len(test_df)} rows)",
        f"Train months: {sorted(train_df.report_month.unique())}",
        f"Test months:  {sorted(test_df.report_month.unique())}",
    ]

    top_agency = train_df["agency"].value_counts().nlargest(200).index  # fit on TRAIN only
    X_train = build_X(train_df, top_agency)
    X_test = build_X(test_df, top_agency)
    cat_idx = [FEATURES.index(c) for c in CATEGORICAL]

    targets = [
        ("TIME: y_slippage_flag", "y_slippage_flag", "is_past_orig_doc"),
        ("COST: y_cost_overrun_flag", "y_cost_overrun_flag", "is_past_orig_doc"),
    ]

    clfs = {}
    for label, target, heuristic_col in targets:
        y_train, y_test = train_df[target], test_df[target]

        clf = HistGradientBoostingClassifier(categorical_features=cat_idx, random_state=0)
        clf.fit(X_train, y_train)
        hgb_score = clf.predict_proba(X_test)[:, 1]
        clfs[target] = clf

        logit_score = logistic_baseline(X_train, y_train, X_test)
        heuristic_score = test_df[heuristic_col].to_numpy(dtype=float)

        evaluate(label, y_test, {
            "HistGradientBoosting": hgb_score,
            "Logistic Regression": logit_score,
            f"Heuristic ({heuristic_col})": heuristic_score,
        }, outlines)

        subgroup_breakdown(test_df, target, hgb_score, "sector", outlines)
        subgroup_breakdown(test_df, target, hgb_score, "ministry", outlines)

    outlines.append("\n\n=== LEAD TIME ANALYSIS ===")
    outlines.append("(uses only the temporally-held-out model above, scored across each test-period")
    outlines.append(" project's full monthly history -- never trained on the future it's evaluated against)")
    test_uids = test_df.uid.unique()

    lead_time_analysis(
        panel, test_uids, top_agency, clfs["y_slippage_flag"], FEATURES,
        "is_past_orig_doc", lambda s: s == 1, split_mi, outlines, "time (newly past original DoC)",
    )
    lead_time_analysis(
        panel, test_uids, top_agency, clfs["y_cost_overrun_flag"], FEATURES,
        "cost_revision_to_date_pct", lambda s: s > 10, split_mi, outlines, "cost (revision newly exceeds 10%)",
    )

    report = "\n".join(outlines)
    print(report)
    with open(os.path.join(args.outdir, "temporal_eval.txt"), "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nSaved to {args.outdir}/temporal_eval.txt")


if __name__ == "__main__":
    main()
