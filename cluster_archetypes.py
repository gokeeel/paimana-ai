#!/usr/bin/env python3
"""
cluster_archetypes.py — group the top-50 riskiest projects into "failure
archetypes" by the shape of their SHAP explanation, not just their score.

Two projects can both score 90+ for completely different reasons (one is
cost-driven, one is agency-track-record-driven) — this clusters on that
pattern so a policymaker gets "here are the 3-4 ways projects fail" instead
of 50 separate explanations.

Input: shap_sample.csv (already computed by explain_risks.py's full explained
sample -- top-50 riskiest + ~150 random projects, not just the top-50 alone.
This script doesn't re-run SHAP, just clusters the existing driver values.
The extreme top-50 alone mostly look like "everything is bad" and don't
cluster meaningfully -- the wider sample has real behavioral variety.

Usage:
    python cluster_archetypes.py --shap-sample model_data/shap_sample.csv --outdir model_data --k 4
"""

import argparse
import os

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from train_models import FEATURES, CATEGORICAL
from feature_labels import human_label

# Categoricals (ministry/sector/state/agency) stay in the clustering space --
# they're genuinely informative for grouping -- but are excluded from LABELS,
# since "State + Agency" isn't a failure-mode narrative, just identity, and at
# only 50 samples they dominate the distinctiveness ranking without meaning.
LABEL_CANDIDATES = [f for f in FEATURES if f not in CATEGORICAL]


def build_signed_matrix(shap_sample):
    """One row per project, one column per feature, value = that feature's
    signed SHAP contribution if it was in the project's top-5 drivers, else 0."""
    mat = pd.DataFrame(0.0, index=shap_sample.index, columns=FEATURES)
    for i in range(1, 6):
        feat_col, shap_col = f"driver_{i}_feature", f"driver_{i}_shap"
        for row_idx, feat, val in zip(shap_sample.index, shap_sample[feat_col], shap_sample[shap_col]):
            if feat in mat.columns:
                mat.at[row_idx, feat] = val
    return mat


def label_cluster(cluster_mean, global_mean, top_n=3):
    """Rank by how much this cluster DIFFERS from the overall average, not by
    raw magnitude -- otherwise a universally strong feature (e.g. agency) wins
    every cluster's label and they all look the same."""
    distinctiveness = (cluster_mean - global_mean).abs().loc[LABEL_CANDIDATES].sort_values(ascending=False)
    top_feats = distinctiveness.head(top_n).index
    return " + ".join(human_label(f) for f in top_feats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shap-sample", default="model_data/shap_sample.csv")
    ap.add_argument("--outdir", default="model_data")
    ap.add_argument("--k", type=int, default=4)
    args = ap.parse_args()

    shap_sample = pd.read_csv(args.shap_sample, dtype={"uid": str})
    if len(shap_sample) < args.k:
        print(f"Only {len(shap_sample)} projects, fewer than k={args.k} — nothing to cluster.")
        return

    X = build_signed_matrix(shap_sample)
    km = KMeans(n_clusters=args.k, random_state=0, n_init=10)
    labels = km.fit_predict(X)

    out = shap_sample[["uid", "project_name", "risk_score"]].copy()
    out["archetype_id"] = labels

    global_mean = X.mean(axis=0)
    summary_rows = []
    label_map = {}
    for cid in sorted(set(labels)):
        mask = labels == cid
        mean_vec = X[mask].mean(axis=0)
        label = label_cluster(mean_vec, global_mean)
        label_map[cid] = label
        summary_rows.append({
            "archetype_id": cid,
            "archetype_label": label,
            "n_projects": int(mask.sum()),
            "avg_risk_score": round(float(out.risk_score[mask].mean()), 1),
        })

    out["archetype_label"] = out["archetype_id"].map(label_map)
    out = out.sort_values(["archetype_id", "risk_score"], ascending=[True, False])
    out.to_csv(os.path.join(args.outdir, "risk_archetypes.csv"), index=False)

    summary = pd.DataFrame(summary_rows).sort_values("n_projects", ascending=False)
    summary.to_csv(os.path.join(args.outdir, "archetype_summary.csv"), index=False)

    print(f"Clustered {len(out)} top-risk projects into {args.k} archetypes:\n")
    for _, r in summary.iterrows():
        print(f"  [{r.archetype_id}] {r.archetype_label:45s} n={r.n_projects:3d}  avg risk={r.avg_risk_score}")
    print(f"\nSaved risk_archetypes.csv and archetype_summary.csv to {args.outdir}")


if __name__ == "__main__":
    main()
