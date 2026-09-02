#!/usr/bin/env python3
"""
explain_risks.py — SHAP driver analysis for the two risk classifiers (SIH outcome f).

Answers: "which CUF fields drive the model's predictions, and by how much?"

Usage:
    python explain_risks.py --panel model_data/panel.csv --models model_data/ \
        --risk-scores model_data/risk_scores.csv --outdir model_data/

Note on scope: HistGradientBoostingClassifier trains its categorical features on
raw string values, which SHAP's TreeExplainer can't consume directly (it forces a
float numpy conversion). We work around this with a model-agnostic Explainer
(ordinal-coded categoricals fed through a wrapper that decodes them back to the
original strings before calling predict_proba) — correct, but ~3s/row per model,
so "global" importance is computed on a representative sample (the top-50 riskiest
projects + a random sample of the rest), not the full panel, to keep runtime sane.
"""

import argparse
import os

import joblib
import numpy as np
import pandas as pd
import shap

from feature_labels import build_X, combined_importance

SAMPLE_SIZE = 150   # additional random rows beyond the top-50, for "global" importance
BACKGROUND_SIZE = 15


def load_bundle(models_dir, name):
    # joblib.load executes pickle bytecode; safe here — these files were produced
    # locally by train_models.py earlier in this pipeline, not from an untrusted source.
    return joblib.load(os.path.join(models_dir, f"{name}.joblib"))


def ordinal_encode(X, cat_cols):
    """SHAP's model-agnostic masker needs pure-numeric input. Encode categoricals
    to integer codes, keep an inverse map so the predict wrapper can decode them."""
    maps, inv = {}, {}
    for c in cat_cols:
        cats = sorted(X[c].astype(object).fillna("__NA__").unique())
        maps[c] = {v: i for i, v in enumerate(cats)}
        inv[c] = {i: v for v, i in maps[c].items()}
    Xnum = X.copy()
    for c in cat_cols:
        Xnum[c] = X[c].astype(object).fillna("__NA__").map(maps[c]).astype(float)
    return Xnum, inv


def make_predict_fn(model, columns, cat_cols, inv):
    def f(data):
        df = pd.DataFrame(data, columns=columns)
        for c in cat_cols:
            decoded = df[c].round().astype(int).map(inv[c])
            df[c] = decoded.replace("__NA__", np.nan).astype("category")
        return model.predict_proba(df)[:, 1]
    return f


def shap_values_for(model, Xnum_all, cat_cols, sample_idx):
    f = make_predict_fn(model, Xnum_all.columns, cat_cols, Xnum_all.attrs["inv"])
    bg = shap.sample(Xnum_all, BACKGROUND_SIZE, random_state=0)
    explainer = shap.Explainer(f, bg)
    sv = explainer(Xnum_all.loc[sample_idx])
    return sv.values  # (n_samples, n_features)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="model_data/panel.csv")
    ap.add_argument("--models", default="model_data/")
    ap.add_argument("--risk-scores", default="model_data/risk_scores.csv")
    ap.add_argument("--outdir", default="model_data/")
    args = ap.parse_args()

    panel = pd.read_csv(args.panel, low_memory=False)
    risk = pd.read_csv(args.risk_scores, dtype={"uid": str})
    time_bundle = load_bundle(args.models, "model1_slippage_clf")
    cost_bundle = load_bundle(args.models, "model2_cost_clf")

    latest_month = panel["report_month"].max()
    latest = panel[panel.report_month == latest_month].reset_index(drop=True)
    top_agency = panel["agency"].value_counts().nlargest(200).index

    X = build_X(latest, time_bundle["features"], time_bundle["categorical"], top_agency)  # same for both models
    Xnum, inv = ordinal_encode(X, time_bundle["categorical"])
    Xnum.attrs["inv"] = inv

    top50 = risk.nlargest(50, "risk_score")
    top50_idx = latest.index[latest.uid.isin(top50.uid)]
    rng = np.random.default_rng(0)
    remaining = latest.index.difference(top50_idx)
    extra_idx = rng.choice(remaining, size=min(SAMPLE_SIZE, len(remaining)), replace=False)
    sample_idx = pd.Index(top50_idx).union(extra_idx)

    print(f"Computing SHAP for {len(sample_idx)} projects "
          f"({len(top50_idx)} top-risk + {len(extra_idx)} sampled) x 2 models...")

    shap_time = shap_values_for(time_bundle["model"], Xnum, time_bundle["categorical"], sample_idx)
    shap_cost = shap_values_for(cost_bundle["model"], Xnum, cost_bundle["categorical"], sample_idx)

    features = list(Xnum.columns)

    # ── global importance (sample-based, see module docstring) ──
    mean_abs_time = np.abs(shap_time).mean(axis=0)
    mean_abs_cost = np.abs(shap_cost).mean(axis=0)
    glob = pd.DataFrame({
        "feature": features,
        "mean_abs_shap_time": mean_abs_time,
        "mean_abs_shap_cost": mean_abs_cost,
    })
    glob["rank_time"] = glob["mean_abs_shap_time"].rank(ascending=False, method="min").astype(int)
    glob["rank_cost"] = glob["mean_abs_shap_cost"].rank(ascending=False, method="min").astype(int)
    glob = glob.sort_values("mean_abs_shap_time", ascending=False)
    glob.to_csv(os.path.join(args.outdir, "shap_global.csv"), index=False)

    print("\nTop 10 global drivers (by mean |SHAP|, time model):")
    combined_rank = combined_importance(glob).sort_values("combined", ascending=False)
    for _, r in combined_rank.head(10).iterrows():
        print(f"  {r.feature:28s} time={r.mean_abs_shap_time:.4f}  cost={r.mean_abs_shap_cost:.4f}")

    # ── per-project top-5 drivers for every project in the explained sample ──
    # (not just the top-50 -- the wider set is what cluster_archetypes.py needs
    # to find genuinely different failure patterns; the extreme top-50 alone
    # mostly all look like "everything is bad" and don't cluster meaningfully)
    combined_shap = 0.5 * shap_time + 0.5 * shap_cost  # contribution to risk_score/100, since
    # risk_score = (0.5*slip_prob + 0.5*cost_prob)*100 and both models' shap values are already
    # in predict_proba space (additive by construction of the wrapper).

    sample_uids = latest.loc[sample_idx, "uid"]
    risk_by_uid = risk.set_index("uid")[["project_name", "risk_score"]]

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

    sample_out = pd.DataFrame(rows)
    sample_out.to_csv(os.path.join(args.outdir, "shap_sample.csv"), index=False)

    top50_out = sample_out.nlargest(50, "risk_score")
    top50_out.to_csv(os.path.join(args.outdir, "shap_top50.csv"), index=False)

    print(f"\nSaved shap_global.csv ({len(glob)} features), "
          f"shap_sample.csv ({len(sample_out)} projects), and "
          f"shap_top50.csv ({len(top50_out)} projects) to {args.outdir}")


if __name__ == "__main__":
    main()
