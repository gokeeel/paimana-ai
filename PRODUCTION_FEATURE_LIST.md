# PAIMANA-AI — Production Feature List (Officer View)

Stack: PostgreSQL + FastAPI (REST) + React/Bootstrap. ML stays Python
(HistGradientBoosting + SHAP) — it becomes a batch job that writes into
Postgres instead of CSVs; nothing about the modeling changes.

Audience: **IPMD Monitoring Officer only** (Ravi persona). The
Analyst/Jury view (ROC-AUC, SHAP values, model comparison, temporal eval) is
a separate route (`/analyst`) behind a different role — out of scope for
this list, and never shown on these screens.

---

## 1. Postgres schema (minimal — maps 1:1 to files you already generate)

| Table | Replaces | Key columns |
|---|---|---|
| `projects` | static columns from `panel.csv` | `uid` (PK), `project_name`, `agency`, `ministry`, `sector`, `state`, `original_cost`, `latest_cost` |
| `risk_scores` | `risk_scores.csv` (latest month only) | `uid` (FK), `report_month`, `risk_score`, `risk_tier`, `alert_type`, `risk_score_delta` |
| `risk_history` | `risk_history.csv` | `uid` (FK), `report_month`, `risk_score`, `risk_tier` — one row per project per month, feeds the trend chart |
| `risk_drivers` | `shap_sample.csv` / `shap_top50.csv` | `uid` (FK), `report_month`, `driver_rank` (1-3), `feature`, `shap_value` — analyst-only raw form; officer view reads it through the phrase-template layer, never raw |
| `benchmarks` | current Tab 3 aggregates | `dim` (`ministry`/`sector`/`agency`), `dim_value`, `report_month`, `pct_on_budget`, `pct_on_time`, `n_projects` |
| `action_log` | *new — doesn't exist yet* | `id` (PK), `uid` (FK), `officer_id` (FK → `users`), `action` (`reviewed`/`escalated`/`false_alarm`), `note`, `created_at` |
| `users` | *new* | `id`, `name`, `role` (`officer`/`analyst`/`admin`), `ministry_scope` (nullable — restricts an officer to their ministry's projects) |

`risk_scores`/`risk_history`/`risk_drivers`/`benchmarks` are populated by a
nightly/monthly batch (`score_projects.py`, `explain_risks.py` rewritten to
`INSERT` instead of `to_csv`) — the ML pipeline's cadence and logic don't
change, only the sink.

---

## 2. Feature list

### Screen 1 — Portfolio Home
| Feature | Officer sees | API | Source |
|---|---|---|---|
| KPI strip | Total projects, Needs Attention count (Red+Amber), ₹ at risk, New alerts since last login | `GET /api/portfolio/summary` | `SELECT` aggregate over `risk_scores` |
| Ministry-scoped view | If officer's `ministry_scope` is set, everything below filters to it automatically | — | `users.ministry_scope` join |

### Screen 2 — This Month's Watchlist
| Feature | Officer sees | API | Source |
|---|---|---|---|
| Alert feed | Cards, one per flagged project: name, agency, status pill (On Track / Needs Attention / Critical), one-sentence reason | `GET /api/watchlist?tier=amber,red` | `risk_scores` joined to `risk_drivers` → phrase template |
| Filter/sort | By ministry, sector, alert type, ₹ size | same endpoint, query params | — |
| Sentence templates | `feature → plain phrase` map (extends existing `feature_labels.py`) | server-side, not exposed as an endpoint | new lookup table, ~20-30 entries |

### Screen 3 — Project Detail
| Feature | Officer sees | API | Source |
|---|---|---|---|
| Status card | Status pill, progress-vs-plan bar, cost-vs-budget bar | `GET /api/projects/{uid}` | `projects` + latest `risk_scores` row |
| Risk trend | Line chart, last 12 months, plain "improving/worsening" label under it | `GET /api/projects/{uid}/history` | `risk_history` |
| Why flagged | 2-3 plain sentences | `GET /api/projects/{uid}/reasons` | `risk_drivers` → template layer |
| Peer comparison | "68% of similar {sector} projects under {agency} are on schedule; this one isn't." | `GET /api/projects/{uid}/peers` | `benchmarks` filtered to same `sector`/`agency` |

### Screen 4 — Action Log (new capability, needs the DB)
| Feature | Officer sees | API | Source |
|---|---|---|---|
| Mark reviewed/escalated/false alarm | Button + optional note on any flagged project | `POST /api/projects/{uid}/actions` | writes `action_log` |
| Action history | Who reviewed this project, when, with what outcome | `GET /api/projects/{uid}/actions` | reads `action_log` joined to `users` |
| This is also your evidence trail | Later: join `action_log` against outcomes to prove/refute the lead-time claim in real deployment | — | reporting query, not a screen |

### Screen 5 — Ministry/Sector Rollup
| Feature | Officer sees | API | Source |
|---|---|---|---|
| Ranked bars | Ministry/sector name, % at risk, ₹ exposure | `GET /api/benchmarks?dim=ministry` | `benchmarks` |
| Trend | Improving/worsening arrow per ministry over time | same endpoint + `report_month` range | `benchmarks` time series |

### Screen 6 — Export / Digest
| Feature | Officer sees | API | Source |
|---|---|---|---|
| CSV/PDF export | Same as today, now server-generated | `GET /api/export?format=csv\|pdf` | query over current filtered view |
| Scheduled email digest | Opt-in monthly summary email | `POST /api/subscriptions` + a cron job (APScheduler or OS-level) | `users` + `risk_scores` |

---

## 3. Explicitly excluded from every officer screen

`slip_prob`, `cost_prob`, `risk_score`'s formula, SHAP values/feature names,
ROC-AUC/PR-AUC/precision@k, GroupKFold/temporal-split language, model type,
quantile (q50/q90) numbers, confidence intervals. These exist in the DB and
power the Analyst view, but no officer-facing endpoint returns them raw —
the templating layer in Screens 2/3 is the only thing standing between the
model's numbers and the officer's screen, and it's the piece that needs the
most care.

---

## 4. Explicitly not in this list (say so if asked, don't build unprompted)

Auth/RBAC implementation, the FastAPI route handlers themselves, the
React component tree, and the Postgres migration scripts — this document is
the contract those get built against, not the build itself.
