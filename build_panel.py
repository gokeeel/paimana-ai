#!/usr/bin/env python3
"""
build_panel.py — turn raw extracted CSVs into an ML-ready panel.

This is the ONE missing piece between your extractor (app.py / batch.py)
and model training. It does three things the raw CSVs don't:

  1. Unify project identity across legacy (N-prefixed) and portal (numeric)
     code systems using the cross-reference from months that carry both.
  2. Forward-fill missing fields (ministry, state, start_date) per project
     from whichever month had them.
  3. Compute forward labels: for each project at month t, what happened by
     month t+H? That's the training signal.

Usage:
    python build_panel.py --ongoing ongoing.csv --completed completed.csv --outdir model_data/

Outputs:
    model_data/panel.csv           Full panel, 1 row per project per month
    model_data/train_forward.csv   Labelled rows with 6-month and 12-month targets
    model_data/train_terminal.csv  Completed projects with ground truth
    model_data/feature_summary.txt Column descriptions for the ML pipeline

Dependencies: pandas (you already have it)
"""

import argparse
import os
import re
import sys

import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────────── identity

def build_unified_id(df):
    """Create a single `uid` column that works across legacy and portal formats.

    Portal-format months have `project_code` (numeric).
    Legacy-format months have `legacy_ocms_code` (N-prefixed).
    Feb/Mar 2026 have BOTH — that's the Rosetta Stone.
    """
    # Build cross-reference from rows that have both codes
    both = df[df.project_code.notna() & df.legacy_ocms_code.notna()]
    xref = both[['project_code', 'legacy_ocms_code']].drop_duplicates()
    lc_to_pc = dict(zip(xref.legacy_ocms_code.astype(str), xref.project_code.astype(str)))

    def _uid(row):
        pc = row.get('project_code')
        lc = row.get('legacy_ocms_code')
        if pd.notna(pc):
            return str(pc).split('.')[0]
        if pd.notna(lc):
            mapped = lc_to_pc.get(str(lc))
            if mapped:
                return mapped.split('.')[0]
            return f"LC_{lc}"
        return None

    df['uid'] = df.apply(_uid, axis=1)
    n_total = len(df)
    n_id = df.uid.notna().sum()
    print(f"  identity: {n_id}/{n_total} rows ({100*n_id/n_total:.1f}%) have uid, "
          f"{df[df.uid.notna()].uid.nunique()} unique projects")
    return df


# ──────────────────────────────────────────────────────────────── dates

def parse_date_col(s, name=""):
    """Convert MM/YYYY strings to month-index (year*12 + month) for arithmetic."""
    d = pd.to_datetime(s, format="%m/%Y", errors="coerce")
    return d.dt.year * 12 + d.dt.month


def mi_to_str(mi):
    """Month-index back to YYYY-MM string."""
    mi = pd.Series(mi, dtype="float")
    y = ((mi - 1) // 12).astype("Int64")
    m = (mi - 12 * y).astype("Int64")
    return y.astype(str) + "-" + m.astype(str).str.zfill(2)


# ──────────────────────────────────────────────────────────────── features

KEYWORDS = {
    "kw_bridge": r"bridge|viaduct|flyover|rob\b|rub\b",
    "kw_tunnel": r"tunnel",
    "kw_bypass": r"bypass|ring road",
    "kw_greenfield": r"greenfield|new construction",
    "kw_upgrade": r"upgrad|rehabilit|widening|strengthening|expansion",
    "kw_epc": r"\bepc\b",
    "kw_ham": r"\bham\b|hybrid annuity",
    "kw_bot": r"\bbot\b|\bppp\b|concession",
    "kw_doubling": r"doubling|third line|fourth line|gauge conversion",
    "kw_electrification": r"electrification",
    "kw_metro": r"metro",
    "kw_pipeline": r"pipeline",
    "kw_terminal": r"terminal",
}


def add_features(df):
    """Engineered features from sanction-time attributes + progress snapshot."""

    # Parse all date columns to month-index
    df['report_mi'] = pd.to_datetime(df['report_month'] + '-01').dt.year * 12 + \
                      pd.to_datetime(df['report_month'] + '-01').dt.month
    df['approval_mi'] = parse_date_col(df.get('approval_date'))
    df['start_mi'] = parse_date_col(df.get('start_date'))

    # Unify the DoC columns (different names across formats)
    df['orig_doc'] = df.get('original_doc', df.get('target_doc', pd.Series(dtype='object')))
    if 'target_doc' in df.columns and 'original_doc' not in df.columns:
        df['orig_doc'] = df['target_doc']
    elif 'original_doc' in df.columns:
        df['orig_doc'] = df['original_doc']
    if 'target_doc' in df.columns:
        df['orig_doc'] = df['orig_doc'].fillna(df['target_doc'])

    df['orig_doc_mi'] = parse_date_col(df['orig_doc'])
    df['rev_doc_mi'] = parse_date_col(df.get('revised_doc'))
    df['anticipated_doc_mi'] = df['rev_doc_mi'].fillna(df['orig_doc_mi'])

    # Cost: use revised if available, else original
    df['original_cost'] = pd.to_numeric(df['original_cost'], errors='coerce')
    df['revised_cost'] = pd.to_numeric(df.get('revised_cost'), errors='coerce')
    df['latest_cost'] = df['revised_cost'].fillna(df['original_cost'])

    # Expenditure and progress
    df['expenditure'] = pd.to_numeric(df['expenditure'], errors='coerce')
    df['physical_progress'] = pd.to_numeric(df.get('physical_progress'), errors='coerce')

    # ── Sanction-time features ──
    df['orig_duration_m'] = df['orig_doc_mi'] - df['start_mi']
    df['approval_to_start_lag_m'] = df['start_mi'] - df['approval_mi']
    df['sanction_year'] = ((df['approval_mi'] - 1) // 12).astype('Int64')
    df['log_original_cost'] = np.log1p(df['original_cost'])
    df['cost_per_month_planned'] = df['original_cost'] / df['orig_duration_m'].replace(0, np.nan)

    # ── Progress features (snapshot-time) ──
    df['months_elapsed'] = df['report_mi'] - df['start_mi']
    df['elapsed_ratio'] = df['months_elapsed'] / df['orig_duration_m'].replace(0, np.nan)
    df['financial_progress_pct'] = 100 * df['expenditure'] / df['original_cost'].replace(0, np.nan)
    df['progress_gap_pct'] = df['financial_progress_pct'] - df['physical_progress']
    df['months_past_orig_doc'] = (df['report_mi'] - df['orig_doc_mi']).clip(lower=0)
    df['is_past_orig_doc'] = (df['report_mi'] > df['orig_doc_mi']).astype('Int64')
    df['cost_revision_to_date_pct'] = 100 * (df['latest_cost'] - df['original_cost']) / \
                                      df['original_cost'].replace(0, np.nan)
    df['doc_slip_to_date_m'] = (df['anticipated_doc_mi'] - df['orig_doc_mi']).fillna(0)

    # ── Text-mined scope features ──
    name = df['project_name'].fillna('').str.lower()
    for col, pat in KEYWORDS.items():
        df[col] = name.str.contains(pat, regex=True, na=False).astype(int)
    km = name.str.extract(r'(\d{1,4}(?:\.\d+)?)\s*km', expand=False)
    df['scope_km'] = pd.to_numeric(km, errors='coerce')

    # ── Panel dynamics (needs uid + sorted) ──
    df = df.sort_values(['uid', 'report_mi']).reset_index(drop=True)
    g = df.groupby('uid', sort=False)
    df['snapshot_index'] = g.cumcount()
    df['d_physical_progress'] = g['physical_progress'].diff()
    df['d_expenditure'] = g['expenditure'].diff()
    df['progress_velocity_3m'] = g['physical_progress'].transform(
        lambda s: s.diff().rolling(3, min_periods=1).mean())
    df['is_stalled'] = ((df['d_physical_progress'].fillna(0).abs() < 0.01) &
                        (df['d_expenditure'].fillna(0).abs() < 0.01)).astype(int)

    # ── Data quality flags ──
    df['dq_doc_before_start'] = (df['orig_doc_mi'] < df['start_mi']).astype('Int64')
    df['dq_absurd_duration'] = (df['orig_duration_m'] > 360).astype('Int64')
    df['dq_cost_collapse'] = (df['cost_revision_to_date_pct'] < -50).astype('Int64')
    dq = [c for c in df.columns if c.startswith('dq_')]
    df['dq_any'] = df[dq].max(axis=1)

    return df


# ──────────────────────────────────────────────────────────────── forward labels

def build_forward_labels(panel, horizon):
    """For each project at month t, look up its state at t+horizon.
    The CHANGE is the label — not the absolute overrun."""

    future = panel[['uid', 'report_mi', 'latest_cost', 'anticipated_doc_mi',
                     'physical_progress']].copy()
    future['report_mi'] = future['report_mi'] - horizon
    future = future.rename(columns={
        'latest_cost': 'f_cost',
        'anticipated_doc_mi': 'f_doc_mi',
        'physical_progress': 'f_progress',
    })

    merged = panel.merge(future, on=['uid', 'report_mi'], how='inner')

    # Forward labels: what NEW deterioration appeared over the horizon?
    merged['y_cost_overrun_total_pct'] = 100 * (merged['f_cost'] - merged['original_cost']) / \
                                         merged['original_cost'].replace(0, np.nan)
    merged['y_time_overrun_total_m'] = merged['f_doc_mi'] - merged['orig_doc_mi']
    merged['y_new_cost_escalation_pct'] = 100 * (merged['f_cost'] - merged['latest_cost']) / \
                                          merged['original_cost'].replace(0, np.nan)
    merged['y_new_slippage_m'] = merged['f_doc_mi'] - merged['anticipated_doc_mi']

    # Classification targets
    merged['y_cost_overrun_flag'] = (merged['y_new_cost_escalation_pct'] > 1).astype(int)
    merged['y_slippage_flag'] = (merged['y_new_slippage_m'] > 0).astype(int)

    # Bands
    merged['y_time_band'] = pd.cut(merged['y_time_overrun_total_m'],
                                    [-np.inf, 0, 6, 24, np.inf],
                                    labels=['on_time', 'upto_6m', '6_24m', 'over_24m'])
    merged['y_cost_band'] = pd.cut(merged['y_cost_overrun_total_pct'],
                                    [-np.inf, 0, 10, 25, np.inf],
                                    labels=['none', 'upto_10pct', '10_25pct', 'over_25pct'])

    return merged


# ──────────────────────────────────────────────────────────────── completed

def build_terminal(completed_csv):
    """Completed projects = ground truth."""
    if not os.path.exists(completed_csv):
        return pd.DataFrame()
    c = pd.read_csv(completed_csv, low_memory=False)
    if c.empty:
        return c

    c['original_cost'] = pd.to_numeric(c['original_cost'], errors='coerce')
    c['revised_cost'] = pd.to_numeric(c.get('revised_cost'), errors='coerce')
    c['expenditure'] = pd.to_numeric(c['expenditure'], errors='coerce')
    c['final_cost'] = c['revised_cost'].fillna(c['original_cost'])

    # Use actual_completion if present, else commissioning_date
    actual = c.get('actual_completion', c.get('commissioning_date', pd.Series(dtype='object')))
    if 'commissioning_date' in c.columns:
        actual = actual.fillna(c['commissioning_date'])
    c['actual_mi'] = parse_date_col(actual)
    c['orig_doc_mi'] = parse_date_col(c.get('target_doc'))

    c['y_cost_overrun_pct'] = 100 * (c['final_cost'] - c['original_cost']) / \
                              c['original_cost'].replace(0, np.nan)
    c['y_time_overrun_m'] = c['actual_mi'] - c['orig_doc_mi']

    return c


# ──────────────────────────────────────────────────────────────── fill gaps

def forward_fill_per_project(df):
    """Fill missing ministry/state/start_date from other months of the same project."""
    fill_cols = ['ministry', 'state', 'start_date', 'approval_date', 'agency', 'sector']
    existing = [c for c in fill_cols if c in df.columns]
    df = df.sort_values(['uid', 'report_month'])
    for col in existing:
        df[col] = df.groupby('uid')[col].transform(lambda s: s.ffill().bfill())
    return df


# ──────────────────────────────────────────────────────────────── main

FEATURE_SUMMARY = """
=== FEATURE GROUPS ===

SANCTION-TIME (available at project approval — no leakage risk):
  original_cost, log_original_cost, orig_duration_m, approval_to_start_lag_m,
  sanction_year, cost_per_month_planned, ministry, sector, state, agency,
  scope_km, kw_bridge, kw_tunnel, kw_bypass, kw_greenfield, kw_upgrade,
  kw_epc, kw_ham, kw_bot, kw_doubling, kw_electrification, kw_metro,
  kw_pipeline, kw_terminal

PROGRESS (snapshot-time — allowed as features for forward prediction):
  months_elapsed, elapsed_ratio, physical_progress, financial_progress_pct,
  progress_gap_pct, months_past_orig_doc, is_past_orig_doc,
  cost_revision_to_date_pct, doc_slip_to_date_m, d_physical_progress,
  d_expenditure, progress_velocity_3m, is_stalled, snapshot_index

LABELS (y_ prefix — NEVER use as features):
  y_cost_overrun_total_pct, y_time_overrun_total_m,
  y_new_cost_escalation_pct, y_new_slippage_m,
  y_cost_overrun_flag, y_slippage_flag, y_time_band, y_cost_band

LEAKAGE RULE:
  latest_cost and revised_doc from the SAME month as the label are labels.
  Never feed them into a model that predicts that month's outcome.

SPLIT RULE:
  GroupKFold on uid (not random). Same project must not appear in train AND test.
  Time-based holdout: train on months ≤ T, test on months > T.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ongoing', required=True, help='Path to ongoing.csv')
    ap.add_argument('--completed', default=None, help='Path to completed.csv')
    ap.add_argument('--outdir', default='model_data')
    ap.add_argument('--horizon', type=int, default=12)
    ap.add_argument('--drop-invalid', action='store_true')
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Load and unify
    print("Loading ongoing.csv...")
    df = pd.read_csv(args.ongoing, low_memory=False)
    print(f"  {len(df)} rows, {df.report_month.nunique()} months")

    print("Building unified identity...")
    df = build_unified_id(df)
    df = df[df.uid.notna()].reset_index(drop=True)

    print("Forward-filling gaps per project...")
    df = forward_fill_per_project(df)

    print("Engineering features...")
    df = add_features(df)

    n_bad = int(df['dq_any'].sum())
    print(f"  data-quality flags: {n_bad} of {len(df)} rows ({100*n_bad/len(df):.1f}%)")
    if args.drop_invalid:
        df = df[df.dq_any == 0].reset_index(drop=True)

    # Save panel
    panel_path = os.path.join(args.outdir, 'panel.csv')
    df.to_csv(panel_path, index=False)
    print(f"\npanel.csv: {len(df)} rows, {df.uid.nunique()} projects, "
          f"{df.report_month.nunique()} months")

    # Forward labels
    print(f"\nBuilding forward labels (horizon={args.horizon}m)...")
    fwd = build_forward_labels(df, args.horizon)
    if len(fwd):
        fwd_path = os.path.join(args.outdir, 'train_forward.csv')
        fwd.to_csv(fwd_path, index=False)
        pos_cost = (fwd.y_cost_overrun_flag == 1).mean()
        pos_slip = (fwd.y_slippage_flag == 1).mean()
        print(f"  train_forward.csv: {len(fwd)} labelled rows")
        print(f"  cost escalation positive rate: {pos_cost:.2%}")
        print(f"  slippage positive rate: {pos_slip:.2%}")
        print(f"  median new slippage: {fwd.y_new_slippage_m.median():.1f} months")
        print(f"  median new cost escalation: {fwd.y_new_cost_escalation_pct.median():.2f}%")
    else:
        print(f"  0 labelled rows — need reports {args.horizon} months apart")

    # Terminal (completed projects)
    if args.completed:
        print("\nBuilding terminal labels from completed.csv...")
        term = build_terminal(args.completed)
        if len(term):
            term_path = os.path.join(args.outdir, 'train_terminal.csv')
            term.to_csv(term_path, index=False)
            print(f"  train_terminal.csv: {len(term)} completed projects")
            print(f"  median cost overrun: {term.y_cost_overrun_pct.median():.1f}%")
            print(f"  median time overrun: {term.y_time_overrun_m.median():.0f} months")

    # Feature summary
    summary_path = os.path.join(args.outdir, 'feature_summary.txt')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(FEATURE_SUMMARY)

    # Quick stats
    print(f"\n{'='*60}")
    print("NULL RATES ON KEY COLUMNS (after forward-fill):")
    key_cols = ['uid', 'ministry', 'state', 'agency', 'sector', 'approval_date',
                'start_date', 'original_cost', 'expenditure', 'physical_progress',
                'orig_doc_mi', 'sanction_year']
    for col in key_cols:
        if col in df.columns:
            pct = df[col].isna().mean() * 100
            print(f"  {col:30s} {pct:5.1f}%")

    print(f"\nDone. Files in {args.outdir}/")


if __name__ == '__main__':
    main()
