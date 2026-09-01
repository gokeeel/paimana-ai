# Table of Contents

[Table of Contents](#table-of-contents-1)

[1. Executive Summary](#executive-summary)

[1.1 One-line Pitch](#one-line-pitch)

[1.2 Why This Matters](#why-this-matters)

[2. Problem Statement & Background](#problem-statement-background)

[2.1 Institutional Context](#institutional-context)

[2.2 Current Portfolio Scale (as of April 2026)](#current-portfolio-scale-as-of-april-2026)

[2.3 The Core Problem](#the-core-problem)

[2.4 Hackathon Scope of Work (as issued)](#hackathon-scope-of-work-as-issued)

[3. Goals, Objectives & Success Metrics](#goals-objectives-success-metrics)

[3.1 Product Goals](#product-goals)

[3.2 Non-Goals (Explicitly Out of Scope for the Hackathon MVP)](#non-goals-explicitly-out-of-scope-for-the-hackathon-mvp)

[3.3 Success Metrics](#success-metrics)

[3.3.1 Current Model Results](#current-model-results-implementation-not-aspirational-targets)

[4. Target Users & Personas](#target-users-personas)

[Persona 1 — IPMD Monitoring Officer ("Ravi")](#persona-1-ipmd-monitoring-officer-ravi)

[Persona 2 — Ministry-level Project Administrator ("Meera")](#persona-2-ministry-level-project-administrator-meera)

[Persona 3 — Policy Analyst / Researcher ("Dr. Anand")](#persona-3-policy-analyst-researcher-dr.-anand)

[Persona 4 — Hackathon Evaluator / Jury](#persona-4-hackathon-evaluator-jury)

[5. Data Requirements](#data-requirements)

[5.1 Primary Data Source — Common Upload Form (CUF) Fields](#primary-data-source-common-upload-form-cuf-fields)

[5.1.1 Assumed / Expected CUF Field Groups](#assumed-expected-cuf-field-groups)

[5.1.2 Derived / Engineered Features (built from CUF, not separately submitted)](#derived-engineered-features-built-from-cuf-not-separately-submitted)

[5.2 Historical Training Data — OCMS Archive](#historical-training-data-ocms-archive)

[5.3 Data Volume & Storage Envelope](#data-volume-storage-envelope)

[5.4 Fallback Strategy If Real Historical Data Is Restricted](#fallback-strategy-if-real-historical-data-is-restricted)

[6. Functional Requirements](#functional-requirements)

[6.1 Module A — Cost Overrun Prediction Model](#module-a-cost-overrun-prediction-model)

[6.2 Module B — Time Overrun Prediction Model](#module-b-time-overrun-prediction-model)

[6.3 Module C — Project Risk Scoring Framework](#module-c-project-risk-scoring-framework)

[6.4 Module D — Early Warning Alert System](#module-d-early-warning-alert-system)

[6.5 Module E — Benchmarking & Comparative Analytics](#module-e-benchmarking-comparative-analytics)

[6.6 Module F — Cost Escalation Driver Analysis](#module-f-cost-escalation-driver-analysis)

[6.7 Module G — AI-Powered Monitoring Dashboard](#module-g-ai-powered-monitoring-dashboard)

[6.8 Module H — LLM-Enabled Project Intelligence Assistant](#module-h-llm-enabled-project-intelligence-assistant)

[6.9 Module I — Documentation & Deployment Framework](#module-i-documentation-deployment-framework)

[6.10 Research Dimension B — Statistical vs AI/ML Comparison](#research-dimension-b-statistical-vs-aiml-comparison)

[Statistical / classical baselines](#statistical-classical-baselines)

[AI / ML models](#ai-ml-models)

[6.11 Research Dimension C — CUF Field Attribution Study](#research-dimension-c-cuf-field-attribution-study)

[7. System Architecture](#system-architecture)

[7.1 High-Level Architecture](#high-level-architecture)

[7.2 Architecture Diagram (Textual)](#architecture-diagram-textual)

[7.3 Design Principles](#design-principles)

[8. Technology Stack — Free-Tier & Open-Source Constrained](#technology-stack-free-tier-open-source-constrained)

[8.1 Data Processing & Modelling (all open-source, run locally / in free CI — no cost regardless of scale)](#data-processing-modelling-all-open-source-run-locally-in-free-ci-no-cost-regardless-of-scale)

[8.2 Storage — Free-Tier Comparison](#storage-free-tier-comparison)

[8.3 Backend / API Layer](#backend-api-layer)

[8.4 Dashboard / Frontend — Two Viable Free Paths](#dashboard-frontend-two-viable-free-paths)

[Path 1 (Recommended for hackathon speed): Streamlit or Dash](#path-1-recommended-for-hackathon-speed-streamlit-or-dash)

[Path 2 (If more frontend polish is desired / time permits): React + a charting library](#path-2-if-more-frontend-polish-is-desired-time-permits-react-a-charting-library)

[8.5 LLM / RAG Assistant (Module H) — Free-Tier Options, Ranked](#llm-rag-assistant-module-h-free-tier-options-ranked)

[8.6 Vector Store for RAG (if Module H is built)](#vector-store-for-rag-if-module-h-is-built)

[8.7 Development, Version Control & CI](#development-version-control-ci)

[8.8 Consolidated Free-Tier Cost Summary](#consolidated-free-tier-cost-summary)

[9. Data Science Methodology](#data-science-methodology)

[9.1 Problem Framing](#problem-framing)

[9.2 Train / Validation / Test Split Strategy](#train-validation-test-split-strategy)

[9.3 Handling Data Realities](#handling-data-realities)

[9.4 Model Selection Process](#model-selection-process)

[9.5 Evaluation Metrics — Full Set to Report](#evaluation-metrics-full-set-to-report)

[10. External Validation & Prospective Evaluation](#external-validation-prospective-evaluation)

[11. Model Limitations & Claims Discipline](#model-limitations-claims-discipline)

**PRODUCT REQUIREMENTS DOCUMENT**

**PAIMANA-AI**

AI-Powered Predictive Analytics & Early Warning System

for Central Sector Infrastructure Project Monitoring

*Built on the PAIMANA / OCMS Data Ecosystem — IPMD, Ministry of Statistics and Programme Implementation (MoSPI)*

Prepared for: National AI Hackathon Submission — 'AI for Infrastructure Monitoring'

Prepared by: Gokul (Gokeeel) — B.Tech CSBS, Sai Ram Engineering College, Chennai

Document Version: 1.0

Date: 25 August 2026

**Development Constraint: Zero / near-zero budget — free-tier and open-source stack only**

# **Table of Contents**

# **1. Executive Summary**

PAIMANA-AI is a predictive analytics and early-warning decision-support system designed for the hackathon problem statement issued by the Infrastructure & Project Monitoring Division (IPMD), Ministry of Statistics and Programme Implementation (MoSPI). The system ingests historical and ongoing project-monitoring data from the OCMS/PAIMANA data ecosystem — covering 1,981 ongoing Central Sector infrastructure projects worth approximately ₹42.78 lakh crore (revised cost) across 17 Ministries/Departments and 22 sectors — and applies statistical and machine-learning models to rank projects by probability of cost overrun, schedule slippage, and implementation risk. The system is intended to provide early-warning value, but any claim of a specific advance-warning horizon must be demonstrated through temporal validation and lead-time analysis rather than assumed from cross-validation performance.

The product converts PAIMANA from a descriptive monitoring platform into a predictive decision-support system. It surfaces project-level risk scores, ranks projects by urgency, generates plain-language early-warning alerts, and (optionally) answers natural-language questions about the portfolio through a Retrieval-Augmented Generation (RAG) assistant. Every component is built exclusively from open-source software and free-tier cloud services so that the solution can be developed, demonstrated, and (if selected) piloted at effectively zero infrastructure cost — a hard constraint for a self-funded student team.

## **1.1 One-line Pitch**

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>The Pitch</strong></p>
<p>"An early-warning radar for India's ₹40+ lakh crore infrastructure pipeline — built entirely on free and open-source tools, that ranks which projects are most likely to deteriorate and surfaces the factors behind the risk, with lead-time claims validated separately."</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## **1.2 Why This Matters**

- Cost and time overruns on Central Sector projects are a chronic, well-documented problem; even a modest reduction in overrun incidence across a ₹42.78 lakh crore portfolio represents enormous public value.

- PAIMANA/OCMS already contains ~20 years of structured project data — a uniquely rich, underexploited dataset for supervised ML in the Indian public-infrastructure context.

- Moving from descriptive dashboards to predictive alerts changes the intervention model from reactive (react after a delay is reported) to proactive (flag the risk before the delay compounds).

- A working, well-documented open-source reference implementation has re-use value beyond the hackathon — it can be adapted by other central/state monitoring bodies (e.g., PRAGATI, state PWDs) facing the same problem.

# **2. Problem Statement & Background**

## **2.1 Institutional Context**

IPMD/MoSPI monitors Central Sector Infrastructure Projects costing ₹150 crore and above across all infrastructure Ministries/Departments. Monitoring has historically run through:

1.  OCMS (Online Computerised Monitoring System) — operational since 2006, the primary historical repository of project cost, expenditure, timeline and implementation-status data.

2.  PAIMANA (Project Assessment, Infrastructure Monitoring and Analytics for Nation-building) — the modernised successor portal, providing an integrated, API-accessible, role-based monitoring ecosystem with monthly data updates.

## **2.2 Current Portfolio Scale (as of April 2026)**

| **Metric**                               | **Value**                                                                                                    |
|------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| Ongoing projects tracked                 | 1,981                                                                                                        |
| Central Ministries / Departments covered | 17                                                                                                           |
| Infrastructure sectors covered           | 22                                                                                                           |
| Aggregate original cost                  | ≈ ₹37.13 lakh crore                                                                                          |
| Aggregate revised cost                   | ≈ ₹42.78 lakh crore                                                                                          |
| Cumulative expenditure to date           | ≈ ₹20.36 lakh crore                                                                                          |
| Major sectors                            | Transport & Logistics, Energy, Water & Sanitation, Communication, Social Infrastructure, Coal, Steel, Mining |

## **2.3 The Core Problem**

Despite comprehensive data capture, projects routinely experience cost overruns, time overruns, delayed milestones, contractual/implementation bottlenecks, resource constraints, and execution risk. PAIMANA today is descriptive: it tells administrators what has already happened. It does not yet tell them what is about to happen. The gap between data availability and predictive insight is the opportunity this PRD addresses.

## **2.4 Hackathon Scope of Work (as issued)**

The problem statement asks students to develop, using open-source tools only, an AI-powered Predictive Analytics and Early Warning System that:

- Analyses PAIMANA-scale project data to identify projects likely to face cost escalation, schedule delay, or implementation risk before the issues materialise.

- Assists policymakers, project administrators, and monitoring agencies in prioritising interventions.

- Evaluates statistical models against AI/ML models for accuracy and early-warning value (Dimension B).

- Builds models on the existing Common Upload Form (CUF) fields and explicitly assesses how much predictive power comes from current CUF fields versus fields not currently captured (Dimension C).

This PRD treats all three technical dimensions (statistical modelling, AI/ML value-add assessment, CUF-field attribution) as first-class product requirements, not optional extras — see Section 6.

# **3. Goals, Objectives & Success Metrics**

## **3.1 Product Goals**

- **G1 — Predict cost overrun risk:** Produce a probability / risk score that a given project will exceed its approved cost by a material margin, updated as new CUF data arrives.

- **G2 — Predict time overrun risk:** Produce a probability / risk score that a project will miss a clearly defined completion target. For the deployed implementation, the primary event is missing the latest valid anticipated completion date by more than a configurable threshold; any original-schedule-based target is treated as a separate sensitivity analysis.

- **G3 — Unified project risk scoring:** Combine cost-risk, time-risk, and other signals (agency track record, sector base rate, expenditure-vs-time pace mismatch) into a single 0–100 Project Risk Score with a traffic-light banding (Green/Amber/Red).

- **G4 — Early-warning alerting:** Automatically flag projects that cross a risk threshold or show a significant month-over-month deterioration, with a human-readable explanation. The system shall separately measure whether an alert precedes a subsequent adverse event and by how much; a high contemporaneous classification score alone shall not be described as proof of early warning.

- **G5 — Decision-support dashboard:** Give a monitoring officer a ranked, filterable, drillable view of the portfolio by ministry, sector, agency, and risk band.

- **G6 — Method comparison (research deliverable):** Quantitatively compare classical statistical models against ML/AI models on the same task/data split, and report where the gain is (or isn't) worth the added complexity.

- **G7 — CUF field attribution (research deliverable):** Quantify how much of model performance is attributable to existing CUF fields alone versus performance achievable with engineered/additional features, and recommend CUF schema changes if warranted.

- **G8 — Zero/near-zero cost delivery:** Build and demo the entire system on free-tier infrastructure, open-source models, and open-source software with no recurring paid dependency required to run the MVP.

## **3.2 Non-Goals (Explicitly Out of Scope for the Hackathon MVP)**

- Direct write-back integration into the production PAIMANA/OCMS system (read-only / offline analysis only for the MVP).

- Automated workflow actions (e.g., auto-generating letters to implementing agencies) — the system recommends, it does not act.

- Legally binding audit or compliance certification of any project.

- Real-time (sub-daily) data ingestion — PAIMANA itself updates monthly, so monthly-batch is the appropriate cadence.

- Mobile native app — a responsive web dashboard is sufficient for the MVP.

- Full production-grade security hardening / STQC certification — noted as a post-hackathon roadmap item (Section 13).

## **3.3 Success Metrics**

| **Metric**                            | **Target for MVP / Demo**                                                   | **Type**                 |
|---------------------------------------|-----------------------------------------------------------------------------|--------------------------|
| Cost-overrun model — ROC-AUC          | ≥ 0.75 on a strictly temporal held-out test set                             | Model quality            |
| Time-overrun model — ROC-AUC          | ≥ 0.72 on a strictly temporal held-out test set                             | Model quality            |
| Precision @ Top-10% riskiest projects | ≥ 60%, reported with class prevalence and confidence interval               | Operational usefulness   |
| Explainability coverage               | 100% of Red/Amber alerts carry a feature-based explanation                  | Trust / adoption         |
| Dashboard load time (portfolio view)  | \< 3 seconds on free-tier hosting                                           | UX                       |
| Model comparison completeness         | ≥ 3 statistical baselines vs ≥ 2 ML models, benchmarked on identical splits | Research rigor (Dim. B)  |
| CUF attribution completeness          | Feature-ablation study isolating CUF-only vs CUF+engineered performance     | Research rigor (Dim. C)  |
| Monthly infra cost to run MVP         | ₹0 (free tier only)                                                         | Cost constraint          |

# **4. Target Users & Personas**

### **Persona 1 — IPMD Monitoring Officer ("Ravi")**

- Role: Reviews monthly CUF submissions for a set of Ministries; escalates problem projects.

- Need: A ranked list of "projects to worry about this month" instead of manually scanning hundreds of rows.

- Success looks like: Opens the dashboard, sees Red/Amber projects for his portfolio, understands why in one glance, exports a shortlist for the monthly review meeting.

### **Persona 2 — Ministry-level Project Administrator ("Meera")**

- Role: Owns execution for a specific Ministry's project portfolio (e.g., Ministry of Road Transport).

- Need: Early signal on projects under her charge before they show up as overruns in a quarterly report to Parliament/Cabinet.

- Success looks like: Receives a monthly digest highlighting projects that moved from Green→Amber, with the top 2–3 contributing factors.

### **Persona 3 — Policy Analyst / Researcher ("Dr. Anand")**

- Role: Evaluates whether AI/ML approaches meaningfully outperform existing statistical monitoring and whether the CUF form itself needs revision.

- Need: A transparent, reproducible comparison of methods and a clear view of which data fields actually drive predictive power.

- Success looks like: Can read the model-comparison report and CUF-attribution study and cite it in a policy recommendation.

### **Persona 4 — Hackathon Evaluator / Jury**

- Role: Assesses the submission against the stated problem statement and expected outcomes.

- Need: Clear mapping from the problem statement's technical dimensions (a, b, c) and expected outcomes (a–i) to concrete, demonstrable deliverables.

- Success looks like: Can trace every requirement in the original brief to a working feature or a documented finding in under 10 minutes.

# **5. Data Requirements**

## **5.1 Primary Data Source — Common Upload Form (CUF) Fields**

The CUF is the monthly data-submission format used by implementing agencies to update PAIMANA. Because the hackathon problem statement explicitly requires modelling on "existing CUF fields" (Dimension c), the PRD defines an assumed CUF schema below based on the fields described in the brief and standard OCMS/PAIMANA project-monitoring practice. If the actual CUF field list/data dictionary is provided by MoSPI at hackathon kickoff, this schema must be reconciled against it in Sprint 0 (Section 12).

### **5.1.1 Assumed / Expected CUF Field Groups**

| **Field Group**    | **Representative Fields**                                                                                                                           | **Likely Type**           |
|--------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------|
| Project Identity   | Project ID, Project name, Ministry/Department, Implementing agency, Sector, Sub-sector, State/UT, District, Location coordinates                    | Categorical / text / geo  |
| Financials         | Approved cost, Latest revised cost, Cumulative expenditure, Expenditure this period, Foreign exchange component, Funding source (Budgetary/EBR/PPP) | Numeric (currency)        |
| Timeline           | Original scheduled start, Original scheduled completion, Latest anticipated completion, Actual start date, Number of revisions to completion date   | Date / numeric            |
| Physical Progress  | Physical progress %, Milestone list with planned vs. actual dates, Milestone completion status                                                      | Numeric / structured list |
| Status & Narrative | Current status (On-track / Delayed / Stalled / Completed), Reasons for delay (free text / coded reason list), Remarks                               | Categorical / free text   |
| Administrative     | Contract award date, Contractor/EPC details, Land acquisition status, Environmental/forest clearance status, Statutory approval status              | Categorical / date        |
| Reporting Meta     | Reporting month, Data submission date, Data quality flags                                                                                           | Date / categorical        |

### **5.1.2 Derived / Engineered Features (built from CUF, not separately submitted)**

- Cost overrun ratio to date = (Revised cost − Approved cost) / Approved cost

- Expenditure pace = Cumulative expenditure / Elapsed time since start (₹ crore per month)

- Time slippage ratio = (Latest anticipated completion − Original scheduled completion) / Original planned duration

- Progress-vs-time gap = Physical progress % minus Expected progress % if on schedule

- Milestone miss rate = Missed milestones / Total milestones due to date

- Revision frequency = Count of completion-date revisions to date

- Agency historical performance = Agency's average overrun % across its other tracked projects (leave-one-out to avoid leakage)

- Sector base rate = Sector-level historical overrun incidence (leave-one-out)

- Delay-reason category (NLP-derived) = Text classification of the free-text "reasons for delay" field into standard buckets: land acquisition, clearances, funding delay, contractor default, litigation, force majeure, design change, other

- Project size band = Cost decile / quartile, since overrun dynamics differ for ₹150 cr projects vs ₹10,000+ cr mega-projects

- Project age = Months since original scheduled start

## **5.2 Historical Training Data — OCMS Archive**

OCMS's ~20-year archive (2006 onward) is the primary source of labelled historical outcomes (i.e., projects that are now complete, so their final cost and time overrun is known with certainty). This is essential: the current 1,981 ongoing PAIMANA projects have not yet resolved, so they cannot supply outcome labels — they are the projects the trained model will score, not the projects it learns from.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>Data Access Note</strong></p>
<p>This PRD assumes hackathon organisers will provide either (a) a bulk historical extract/export of OCMS+PAIMANA data, or (b) sandboxed API/portal access with a dataset dictionary. If neither is available at kickoff, Section 5.4 below defines a fallback synthetic-data strategy so development is never blocked.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## **5.3 Data Volume & Storage Envelope**

| **Dataset**                                    | **Estimated Rows**             | **Estimated Raw Size**                 | **Storage Plan**                                             |
|------------------------------------------------|--------------------------------|----------------------------------------|--------------------------------------------------------------|
| Historical completed projects (OCMS, ~20 yrs)  | ~15,000–40,000 projects (est.) | 50–300 MB (structured) + optional text | Parquet/CSV in Git-LFS-free repo or free-tier object storage |
| Current ongoing projects (PAIMANA)             | 1,981                          | \< 10 MB                               | Same as above; refreshed monthly                             |
| Monthly time-series milestone/progress history | ~10–20 rows/project/year       | 100–500 MB                             | Compressed Parquet (Snappy)                                  |
| Free-text delay reasons (for NLP feature)      | ~1 field × all rows            | \< 50 MB                               | Embedded in main table                                       |

All of the above comfortably fits within free tiers of Supabase (500 MB Postgres + 1 GB storage), Neon (0.5 GB Postgres), or even a flat-file approach (DuckDB + Parquet on disk / GitHub repo, effectively unlimited for this scale) — see Section 7 for the specific free-tier services selected.

## **5.4 Fallback Strategy If Real Historical Data Is Restricted**

Given that government project-monitoring data may be access-controlled, the PRD defines a three-tier fallback so the project is never blocked on data access:

3.  Tier 1 (Preferred): Official OCMS/PAIMANA historical extract or sandbox access, if provided by MoSPI/IPMD for the hackathon.

4.  Tier 2: Public-domain proxy datasets with a similar structure — e.g., data.gov.in infrastructure project datasets, Ministry of Road Transport & Highways (MoRTH) project status data, Standing Committee on Finance reports on "projects with cost/time overruns" (published periodically and machine-readable in tabular annexures), and RBI/CGA capital expenditure data — blended to approximate a CUF-like schema.

5.  Tier 3: A carefully constructed synthetic dataset generated with documented, realistic statistical assumptions (e.g., overrun distributions informed by publicly reported aggregate overrun statistics), used strictly to demonstrate the modelling pipeline end-to-end, with a clear disclosure label in the demo that synthetic data was used for a given portion of the training set. This keeps the team's engineering work fully valid and re-runnable the moment real data is supplied.

# **6. Functional Requirements**

Requirements are grouped by the outcome components (a–i) listed in the original problem statement, each mapped to a module in this system, plus the two research dimensions (b, c).

## **6.1 Module A — Cost Overrun Prediction Model**

| **ID** | **Requirement**                                                                                                                                                        | **Priority** |
|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|
| FR-A1  | System shall predict, for each ongoing project, the probability that final/revised cost will exceed approved cost by more than a configurable threshold (default 20%). | Must         |
| FR-A2  | System shall also produce a regression estimate of expected % cost overrun (continuous value), not just a binary flag.                                                 | Should       |
| FR-A3  | Predictions shall be regenerated on each monthly data refresh and version-stamped.                                                                                     | Must         |
| FR-A4  | Each prediction shall be accompanied by the top 3–5 contributing features (via SHAP or equivalent).                                                                    | Must         |
| FR-A5  | Model shall support per-sector and per-ministry sub-models or sector as a strong feature, since overrun drivers differ by sector.                                      | Should       |

## **6.2 Module B — Time Overrun Prediction Model**

| **ID** | **Requirement**                                                                                                                                                                                                                      | **Priority** |
|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|
| FR-B1  | System shall predict probability of missing a clearly defined completion target by more than a configurable threshold (default 6 months), using only information available at the prediction timestamp.                                                   | Must         |
| FR-B2  | System shall estimate expected additional delay in months (regression).                                                                                                                                                              | Should       |
| FR-B3  | Model shall use survival-analysis framing (time-to-delay-event) as an alternative/complement to classification, since "time until overrun" is naturally a survival problem with censored data (ongoing projects haven't failed yet). | Should       |

## **6.3 Module C — Project Risk Scoring Framework**

| **ID** | **Requirement**                                                                                                                                                              | **Priority** |
|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|
| FR-C1  | System shall compute a single Project Risk Score (0–100) combining cost-risk, time-risk, and volatility indicators (e.g., revision frequency).                               | Must         |
| FR-C2  | Score shall map to a 3-band traffic light: Green (0–39), Amber (40–69), Red (70–100), with thresholds configurable.                                                          | Must         |
| FR-C3  | Scoring weights shall be documented and justified (either learned via a meta-model or transparently hand-weighted with rationale) — no unexplained "black box" final number. | Must         |
| FR-C4  | Score history shall be retained so trend (improving/worsening) is visible, not just point-in-time value.                                                                     | Must         |

## **6.4 Module D — Early Warning Alert System**

| **ID** | **Requirement**                                                                                                                                                                                                          | **Priority**   |
|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| FR-D1  | System shall generate an alert when a project's Risk Score crosses into Amber or Red for the first time.                                                                                                                 | Must           |
| FR-D2  | System shall generate an alert on significant month-over-month score deterioration (e.g., +15 points) even if still within the same band.                                                                                | Must           |
| FR-D3  | Each alert shall include a plain-language explanation, e.g., "Flagged Red: expenditure pace has fallen to 40% of the required run-rate to meet the revised completion date, and 2 of the last 3 milestones were missed." | Must           |
| FR-D4  | Alerts shall be viewable in-app (dashboard alert feed) for the MVP; email/SMS digest is a stretch goal (Section 6.9).                                                                                                    | Must / Stretch |
| FR-D5  | Alert list shall be exportable (CSV/PDF) for offline circulation in review meetings.                                                                                                                                     | Should         |

## **6.5 Module E — Benchmarking & Comparative Analytics**

| **ID** | **Requirement**                                                                                                                                                                                        | **Priority** |
|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|
| FR-E1  | System shall let a user compare a project's cost/time performance against the mean/median of its sector, cost-band, and implementing agency peer group.                                                | Must         |
| FR-E2  | System shall present sector-level and ministry-level aggregate overrun trends over time (e.g., "is Transport & Logistics getting better or worse YoY").                                                | Should       |
| FR-E3  | System shall rank implementing agencies by historical on-time/on-budget delivery rate (agency scorecard), with a minimum-sample-size guard to avoid unfair ranking of agencies with very few projects. | Should       |

## **6.6 Module F — Cost Escalation Driver Analysis**

| **ID** | **Requirement**                                                                                                                                                                                                                                      | **Priority** |
|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|
| FR-F1  | System shall classify free-text delay/escalation reasons into standard categories (land acquisition, statutory clearance, funding delay, contractor default, litigation, design change, force majeure, other) using an NLP text-classification step. | Must         |
| FR-F2  | System shall present portfolio-wide and sector-wide breakdowns of which driver categories are most prevalent and most cost-impactful.                                                                                                                | Must         |
| FR-F3  | System shall surface driver-category prevalence as an input feature to the cost/time models (not just a reporting output).                                                                                                                           | Should       |

## **6.7 Module G — AI-Powered Monitoring Dashboard**

| **ID** | **Requirement**                                                                                                                                          | **Priority** |
|--------|----------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|
| FR-G1  | Dashboard shall show a portfolio overview: total projects, total value, count/value by risk band, trend sparkline.                                       | Must         |
| FR-G2  | Dashboard shall provide a sortable/filterable project table (by ministry, sector, state, agency, risk band, cost band).                                  | Must         |
| FR-G3  | Dashboard shall provide a project detail view showing timeline, milestone Gantt-style chart, financial trend, risk score history, and explanation panel. | Must         |
| FR-G4  | Dashboard shall provide a map view (state/district) of project locations colour-coded by risk band, where geo-coordinates are available.                 | Should       |
| FR-G5  | Dashboard shall be usable on a standard laptop browser without installation; responsive layout for tablet is a plus, not required.                       | Must         |
| FR-G6  | Dashboard shall load the full portfolio view in under 3 seconds on free-tier hosting for the 1,981-project scale.                                        | Must         |

## **6.8 Module H — LLM-Enabled Project Intelligence Assistant**

| **ID** | **Requirement**                                                                                                                                                                                       | **Priority**         |
|--------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------|
| FR-H1  | System shall provide a natural-language chat interface allowing questions like "Which projects in the Road sector are at Red risk and why?" or "Summarise delay drivers for Ministry X this quarter." | Should               |
| FR-H2  | The assistant shall use Retrieval-Augmented Generation (RAG) grounded strictly in the structured project database and computed risk outputs — it must not invent figures.                             | Must (if H is built) |
| FR-H3  | Every LLM-generated numeric claim shall be traceable to an underlying query result shown alongside the answer (numbers come from SQL/pandas, not from the LLM's free generation).                     | Must (if H is built) |
| FR-H4  | The assistant shall run on a free-tier or self-hosted open-weight LLM (see Section 8) to respect the zero-cost constraint.                                                                            | Must (if H is built) |

## **6.9 Module I — Documentation & Deployment Framework**

| **ID** | **Requirement**                                                                                                                                                                                                                            | **Priority** |
|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|
| FR-I1  | A public GitHub repository shall contain full source code, a README with setup instructions, and a one-command (or single docker-compose) local run path.                                                                                  | Must         |
| FR-I2  | A data dictionary documenting every CUF field used, every engineered feature, and every model input/output shall be included.                                                                                                              | Must         |
| FR-I3  | A model card shall be produced per model: training data description, algorithm, hyperparameters, evaluation metrics, known limitations, and fairness/bias considerations (e.g., does the model systematically over-flag smaller agencies). | Must         |
| FR-I4  | The comparative study (statistical vs AI/ML, Dimension b) and the CUF-attribution study (Dimension c) shall be written up as a short technical report (5–10 pages) included in the repo and referenced in the pitch deck.                  | Must         |
| FR-I5  | A one-click deploy path (e.g., "Deploy to Streamlit Community Cloud" button or equivalent) shall be provided so judges can access a live instance without local setup.                                                                     | Should       |

## **6.10 Research Dimension B — Statistical vs AI/ML Comparison**

This is a required deliverable, not a nice-to-have. The system shall implement and benchmark, on identical train/test splits:

### **Statistical / classical baselines**

- Logistic regression (cost-overrun and time-overrun binary classification)

- Multiple linear regression (continuous overrun % / delay-months prediction)

- Cox proportional hazards model (survival-analysis framing for time-to-delay)

- Simple rule-based / threshold heuristic baseline (e.g., "flag if expenditure pace \< 70% of required run-rate") — this is the honest "what MoSPI could do with Excel today" baseline

### **AI / ML models**

- Gradient-boosted trees — XGBoost and/or LightGBM (primary candidate; strong on tabular data, fast to train, interpretable via SHAP)

- Random Forest (robust baseline ML model, easy to explain via feature importance)

- (Stretch) A small tabular deep-learning model (e.g., TabNet or a simple feed-forward network) purely to test whether deep learning adds value over gradient boosting on this data — hypothesis is likely "no, not at this data scale," and reporting that negative result honestly is itself a valid research finding.

Requirement FR-DIMB-1: The technical report shall present a single comparison table (ROC-AUC, PR-AUC, precision@10%, calibration, and training/inference cost) across all models above, plus a written verdict on whether ML's accuracy gain (if any) justifies its reduced interpretability versus the statistical baselines — directly answering the brief's Dimension (b) question.

## **6.11 Research Dimension C — CUF Field Attribution Study**

Requirement FR-DIMC-1: The system shall run an ablation study with at least three feature sets: (1) raw CUF fields only, (2) CUF fields + engineered/derived features (Section 5.1.2), (3) CUF + engineered + the NLP delay-reason categorical feature. Performance (ROC-AUC / PR-AUC) shall be reported for each set on identical splits.

Requirement FR-DIMC-2: A feature-importance ranking (e.g., SHAP global importance or permutation importance) across the full feature set shall be produced, clearly marking which top features are already in the CUF and which are engineered/absent, to directly inform whether MoSPI should consider adding fields to the CUF (e.g., a structured/coded delay-reason field instead of free text would likely be a high-leverage, low-cost schema change).

# **7. System Architecture**

## **7.1 High-Level Architecture**

The system is organised into five layers, each independently deployable on free-tier infrastructure:

| **Layer**                      | **Responsibility**                                                                                            | **Cadence**                              |
|--------------------------------|---------------------------------------------------------------------------------------------------------------|------------------------------------------|
| 1\. Ingestion                  | Pull/import CUF-format data (bulk CSV/API export), validate schema, land in raw storage                       | Monthly (matches PAIMANA update cycle)   |
| 2\. Processing & Feature Store | Clean, deduplicate, engineer features (Section 5.1.2), write to an analytics-ready table                      | Monthly, triggered after ingestion       |
| 3\. Modelling                  | Train/retrain statistical + ML models using leakage-safe temporal training windows, score ongoing projects at a defined prediction timestamp, compute Risk Scores, run SHAP explanations, and store validation metadata | Monthly (retrain), on-demand for scoring |
| 4\. Serving / API              | Expose predictions, explanations, and aggregates via a lightweight API layer                                  | Always-on (free tier)                    |
| 5\. Presentation               | Dashboard (web app) + optional LLM assistant chat interface                                                   | Always-on (free tier)                    |

## **7.2 Architecture Diagram (Textual)**

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>Data Flow</strong></p>
<p>PAIMANA/OCMS Export (CSV/API) → Ingestion Script (Python) → Raw Store (Parquet/Postgres) →</p>
<p>Feature Engineering (pandas/Polars) → Feature Table → Model Training (scikit-learn/XGBoost, offline, in CI or notebook) →</p>
<p>Trained Model Artifacts (.pkl/.json, versioned in repo or free object storage) → Scoring Job (monthly batch) →</p>
<p>Predictions + SHAP Explanations Table → FastAPI Backend (free-tier host) → Streamlit/React Dashboard (free-tier host) → End User</p>
<p>Optional side-branch: Feature Table + Predictions → Vector Store (for RAG context) → LLM Assistant → User Chat</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## **7.3 Design Principles**

- **Batch-first, not streaming:** PAIMANA updates monthly, so a real-time streaming architecture (Kafka etc.) is unnecessary complexity and unnecessary cost. Monthly batch jobs are simpler, cheaper, and correct for the update cadence.

- **Stateless serving layer:** The API/dashboard layer reads pre-computed predictions rather than scoring on-the-fly, so free-tier compute (which often sleeps/cold-starts) is never on the critical path for a user's page load.

- **File-first storage where possible:** Parquet files in the Git repo or a free object-storage bucket avoid the operational overhead and free-tier row/connection limits of a hosted database for a dataset this size (tens of thousands of rows, not millions).

- **Explainability is architectural, not bolted on:** SHAP values are computed and stored alongside every prediction at scoring time, not recomputed live, keeping the dashboard fast and guaranteeing every Red/Amber alert has a ready explanation (FR-D3).

- **LLM assistant is optional and isolated:** Module H is architected as an add-on that reads only from the already-computed predictions table (RAG grounding, FR-H2/H3) so it can be cut entirely under time pressure without affecting Modules A–G.

# **8. Technology Stack — Free-Tier & Open-Source Constrained**

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>Hard Constraint</strong></p>
<p>Every component below is chosen so the MVP can be built, trained, deployed, and demoed for ₹0 in infrastructure spend. Where a paid tier exists, the free tier's limits are stated explicitly so the team knows exactly when (if ever) an upgrade would be needed — and a like-for-like free alternative is always given.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## **8.1 Data Processing & Modelling (all open-source, run locally / in free CI — no cost regardless of scale)**

| **Component**                           | **Recommended Tool**                                                                                                                 | **License / Cost**             | **Why**                                                                                             |
|-----------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|--------------------------------|-----------------------------------------------------------------------------------------------------|
| Data wrangling                          | pandas / Polars                                                                                                                      | Free, open-source (BSD)        | Standard; Polars is faster for larger CUF-history joins                                             |
| Local analytical DB                     | DuckDB                                                                                                                               | Free, open-source (MIT)        | In-process SQL over Parquet — no server to host, zero cost at any data size in this project's range |
| Classical ML                            | scikit-learn (Logistic/Linear Regression, Random Forest)                                                                             | Free, open-source (BSD)        | Industry standard, fully offline                                                                    |
| Gradient boosting                       | XGBoost or LightGBM                                                                                                                  | Free, open-source (Apache 2.0) | Best-in-class tabular accuracy, fast CPU training — no GPU required at this data scale              |
| Survival analysis                       | lifelines (Python)                                                                                                                   | Free, open-source (MIT)        | Cox PH model for time-to-overrun framing                                                            |
| Explainability                          | SHAP                                                                                                                                 | Free, open-source (MIT)        | Model-agnostic explanations for FR-A4/FR-D3                                                         |
| NLP text classification (delay reasons) | scikit-learn TF-IDF + classifier, or a small open-weight sentence embedding model (e.g., all-MiniLM-L6-v2 via sentence-transformers) | Free, open-source              | Lightweight, runs on CPU, no API cost per call                                                      |

## **8.2 Storage — Free-Tier Comparison**

| **Option**                                  | **Free Tier Limit**                                  | **Best For**                                                         | **Notes**                                                                              |
|---------------------------------------------|------------------------------------------------------|----------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| Flat files in Git repo (Parquet/CSV)        | Effectively unlimited for this project's ~50–300 MB  | Simplicity, full reproducibility, judges can clone and run instantly | Recommended default for the hackathon MVP                                              |
| Supabase (hosted Postgres)                  | 500 MB database + 1 GB file storage, 2 free projects | If a real queryable API/dashboard backend with auth is wanted        | Good if the dashboard needs multi-user, real-time filtering at DB level                |
| Neon (hosted Postgres, serverless)          | 0.5 GB storage, autosuspend when idle                | Same as above, generous compute-second allowance                     | Cold-start latency on first query after idle — acceptable for a monthly-batch use case |
| Google Sheets (as a lightweight "database") | 15 GB (shared Google account quota)                  | Rapid prototyping, judge-friendly transparency                       | Not recommended beyond prototyping — poor for joins/ML feature pulls at scale          |
| MongoDB Atlas free tier (M0)                | 512 MB                                               | If team prefers a document store for semi-structured milestone data  | Optional alternative, not required                                                     |

## **8.3 Backend / API Layer**

| **Component**                         | **Recommended Tool**                                                                        | **Cost**                                                                                                | **Notes**                                                                                                                                             |
|---------------------------------------|---------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| API framework                         | FastAPI (Python)                                                                            | Free, open-source                                                                                       | Lightweight, auto-generates OpenAPI docs, easy to free-host                                                                                           |
| Hosting                               | Render.com free web service tier, or Railway free tier, or Hugging Face Spaces (Docker SDK) | Free tier (sleeps after inactivity; wakes on request)                                                   | Cold-start (10–50s) on first request after idle is an acceptable trade-off for a monitoring tool checked periodically, not a real-time trading system |
| Scheduled monthly retrain/scoring job | GitHub Actions (scheduled workflow / cron)                                                  | Free — 2,000 CI minutes/month on public repos (unlimited on public repos in practice for this workload) | Runs the monthly batch pipeline (Section 7.1, Layers 1–3) without any always-on server                                                                |

## **8.4 Dashboard / Frontend — Two Viable Free Paths**

### **Path 1 (Recommended for hackathon speed): Streamlit or Dash**

- Pure Python, fastest to build a data-heavy dashboard (tables, filters, charts, map) with FR-G1–G6.

- Deploys free and with zero DevOps effort on Streamlit Community Cloud (unlimited public apps, generous resource limits for this data scale) or Hugging Face Spaces.

- Trade-off: less visual polish/customisation than a bespoke React app, but for a hackathon judged on substance and working demo, this is the right speed/cost trade-off.

### **Path 2 (If more frontend polish is desired / time permits): React + a charting library**

- React + Vite frontend, Recharts or Chart.js for visuals, Tailwind for styling — matches this environment's own available tooling.

- Free hosting via Vercel, Netlify, GitHub Pages, or Cloudflare Pages (all have generous free tiers well beyond this project's traffic).

- Trade-off: more development time for equivalent functionality; only recommended if a team member has strong existing React familiarity or the timeline (Section 12) has slack.

Recommendation: Build Path 1 (Streamlit) as the core deliverable to guarantee a working, judge-accessible demo; treat Path 2 as a stretch/parallel track only if time allows, since a live, working, slightly-less-polished dashboard beats an unfinished polished one.

## **8.5 LLM / RAG Assistant (Module H) — Free-Tier Options, Ranked**

| **Option**                                                                       | **Cost Model**                                                                     | **Pros**                                                                                                     | **Cons**                                                                                 |
|----------------------------------------------------------------------------------|------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| Groq API (open-weight models e.g. Llama 3.1/3.3, served fast)                    | Free tier with generous requests/day for developer accounts                        | Extremely fast inference, no local GPU needed, good free quota for demo-scale traffic                        | Free tier limits (requests/min) — fine for a demo, would need review for real deployment |
| Google Gemini API free tier                                                      | Free tier (rate-limited requests/day)                                              | Strong quality, generous free daily quota, easy integration                                                  | Rate limits mean it's demo-appropriate, not production-heavy-traffic-appropriate         |
| Self-hosted open-weight model via Ollama (e.g., Llama 3.1 8B, Mistral 7B, Phi-3) | ₹0 (runs on a laptop with 16GB+ RAM, or free Colab/Kaggle GPU session for testing) | Zero API dependency, fully offline-capable, no rate limits, best for judge demos with unreliable venue Wi-Fi | Requires reasonably capable local hardware; slower than hosted APIs on modest laptops    |
| Hugging Face Inference API (free tier)                                           | Free tier with rate limits                                                         | Wide model choice, easy prototyping                                                                          | Free tier can be slow/queued under load                                                  |

Recommendation: Use Groq's free API as the primary path for demo reliability and speed, with an Ollama-served open-weight model as an offline fallback so the demo never depends on live internet/API-quota availability during judging.

## **8.6 Vector Store for RAG (if Module H is built)**

| **Option**                  | **Cost**                                       | **Notes**                                                                       |
|-----------------------------|------------------------------------------------|---------------------------------------------------------------------------------|
| ChromaDB (embedded/local)   | Free, open-source, runs in-process — no server | Simplest option; fine for this project's document/row count                     |
| FAISS (Meta, local)         | Free, open-source                              | Even lighter-weight than Chroma for pure vector search                          |
| Qdrant free managed cluster | Free tier (1 GB cluster)                       | Only needed if a hosted, persistent vector DB with a UI is preferred over local |

Given the data scale here, an embedded local vector store (Chroma or FAISS) is sufficient and removes an entire hosted dependency — recommended default.

## **8.7 Development, Version Control & CI**

| **Component**                                  | **Tool**                                                                           | **Cost**                                                                       |
|------------------------------------------------|------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| Version control / repo host                    | GitHub (public repo)                                                               | Free                                                                           |
| CI/CD (tests, scheduled retrain, deploy)       | GitHub Actions                                                                     | Free (public repo — 2,000+ min/month; effectively unlimited for this workload) |
| Experiment tracking (optional but recommended) | MLflow (self-hosted/local, or free-tier Databricks Community Edition if preferred) | Free, open-source                                                              |
| Notebook environment                           | Jupyter (local) or Google Colab (free GPU/CPU tier)                                | Free                                                                           |
| Code quality                                   | ruff / black (Python linting & formatting)                                         | Free, open-source                                                              |

## **8.8 Consolidated Free-Tier Cost Summary**

| **Layer**                | **Monthly Cost at Hackathon/Demo Scale**          | **Monthly Cost If Scaled to Full Production (indicative)**                          |
|--------------------------|---------------------------------------------------|-------------------------------------------------------------------------------------|
| Data storage             | ₹0 (flat files) / ₹0 (Supabase or Neon free tier) | ₹0–₹2,000 (Supabase Pro if row/connection limits exceeded)                          |
| Modelling & training     | ₹0 (local/CI compute)                             | ₹0 (retraining a gradient-boosted model on ~40k rows needs no GPU cluster)          |
| Backend API hosting      | ₹0 (Render/Railway/HF Spaces free tier)           | ₹0–₹600 (Render starter tier if always-on/no-cold-start is required)                |
| Dashboard hosting        | ₹0 (Streamlit Community Cloud / HF Spaces)        | ₹0–₹1,500 (if custom domain + higher resource tier wanted)                          |
| LLM assistant (optional) | ₹0 (Groq/Gemini free tier or self-hosted Ollama)  | ₹0–₹5,000 (only if traffic exceeds free-tier daily quotas at real deployment scale) |
| TOTAL — Hackathon MVP    | ₹0                                                | —                                                                                   |

### 3.3.1 Current Model Results (Implementation, not aspirational targets)

The current implementation has produced the following **5-fold GroupKFold out-of-fold results**. These are useful evidence of model discrimination and ranking quality, but they are **not a replacement for the required strict temporal holdout evaluation or prospective early-warning validation**.

| **Target / Metric** | **Current Result** | **Baseline** |
|---|---:|---:|
| Time slippage — ROC-AUC | **0.857** | 0.594 |
| Time slippage — PR-AUC | **0.878** | 0.614 |
| Time slippage — Precision@Top-10% | **95.2%** | 76.5% |
| Time slippage — MAE | **7.02 months** | 9.07 months |
| Cost overrun — ROC-AUC | **0.838** | 0.612 |
| Cost overrun — PR-AUC | **0.678** | 0.354 |
| Cost overrun — Precision@Top-10% | **79.6%** | 29.0% |
| Cost escalation — P50 coverage | **0.58** | 0.50 target |
| Cost escalation — P90 coverage | **0.81** | 0.90 target |

These results indicate a strong improvement over the reported baseline, especially in top-decile precision. They should be described as **cross-validated model performance**, not as proof that the system predicts six months ahead. A temporal holdout, calibration assessment, sector robustness analysis, and lead-time evaluation are required for the stronger claim.

Even the illustrative "scaled to production" column stays low because the workload is fundamentally batch/monthly and the data volume (thousands, not millions, of rows) never requires enterprise-tier infrastructure — the free tier is not just a hackathon hack here, it is close to the right-sized solution for this problem's actual scale.

# **9. Data Science Methodology**

## **9.1 Problem Framing**

| **Task**                    | **Framing**                                          | **Target Variable**                                                                                                                                                            |
|-----------------------------|------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Cost overrun prediction     | Binary classification (+ optional regression)        | 1 if (revised/final cost − approved cost)/approved cost \> 20% (threshold configurable), else 0. Regression target: overrun %.                                                 |
| Time overrun prediction     | Binary classification (+ optional survival analysis) | Primary target: 1 if the project misses the latest valid anticipated completion date by more than 6 months (threshold configurable), else 0. Any original-schedule-based target is a separate sensitivity analysis. Survival target: time from prediction timestamp to the defined adverse event, with ongoing projects as right-censored observations. |
| Risk scoring                | Weighted composite / meta-model                      | 0–100 score combining calibrated probabilities from the above plus volatility features.                                                                                        |
| Delay-reason classification | Multi-class text classification                      | One of 8 standard driver categories (Section 6.6).                                                                                                                             |

## **9.2 Train / Validation / Test Split Strategy**

- **Primary evaluation must be chronological:** train on an earlier period, validate on a later period, and evaluate once on the most recent eligible period. The final test set must be strictly later in time than the training data. GroupKFold may be used as a secondary robustness check for grouped observations, but it must not be presented as a substitute for temporal holdout validation.

- **Cross-validation:** use expanding-window / rolling-origin cross-validation inside the training period for hyperparameter tuning. If GroupKFold is also used to control project/group dependence, report it separately and explain what dependency it removes.

- **Strict temporal holdout:** reserve the most recent eligible completed cohort, or the most recent fixed time window, as an untouched final test set. Do not tune thresholds, features, or hyperparameters against this set. Record the cutoff date and the number of projects/events in every split.

## **9.3 Handling Data Realities**

- **Class imbalance:** If overrun incidence is (as is typical) the majority rather than a rare minority, standard classification metrics suffice; if it is a minority class in some sector, use class weighting or threshold tuning rather than naive oversampling, and always report Precision/Recall/PR-AUC alongside ROC-AUC since ROC-AUC alone can be misleading under imbalance.

- **Missing data:** CUF submissions will have missing fields for some projects/periods. Use documented imputation (median/mode for numeric/categorical, or a "missing" indicator category) and explicitly report missingness rates per field in the data dictionary (FR-I2) — a high missingness rate on a field is itself a finding relevant to Dimension (c).

- **Leakage prevention:** Every feature must be constructed strictly from information available at the project prediction timestamp. Agency/sector historical performance features must be computed using only projects whose outcomes were already observable before that timestamp and must exclude the project being scored. Revised costs, revised completion dates, current status, delay reasons, milestone outcomes, or other fields must not encode information that became available only after the prediction timestamp or as a consequence of the target event.

- **Outliers:** Mega-projects (₹10,000+ crore) can dominate loss functions; consider log-transforming cost-scale features and/or reporting metrics separately for cost-bands so a few giant projects don't mask model performance on the more typical ₹150 cr – ₹1,000 cr project.

- **Calibration:** Since outputs feed a human-facing Risk Score (not just a ranking), calibrate probabilities (e.g., Platt scaling / isotonic regression) using validation data only, then report calibration error/Brier score and reliability plots on the untouched temporal test set. The 0–100 score must not be interpreted as a literal probability unless calibration supports that interpretation.

## **9.4 Model Selection Process**

1. Establish the rule-based heuristic baseline first (Section 6.10) — using a genuinely competitive information-available-at-time-T rule such as expenditure pace, progress-vs-time gap, or overdue status. Do not use a baseline that is trivially weaker than the feature set being offered to the ML model.
2. Fit statistical baselines (logistic/linear regression, Cox PH) with full interpretability.
3. Fit ML models (Random Forest, then XGBoost/LightGBM) with the same feature set and identical temporal splits.
4. Tune the best-performing model on training/validation data only.
5. Run the CUF-attribution ablation (Section 6.11).
6. Evaluate all models on the untouched temporal test set exactly once.
7. Conduct threshold analysis for realistic review capacity (e.g., top 5%, 10%, and 20%).
8. Conduct lead-time analysis: for every alert tied to a later adverse event, measure the time between first qualifying alert and event.
9. Conduct sector/ministry robustness analysis and report uncertainty intervals.
10. Select the deployed model based on discrimination, precision/recall, calibration, lead time, robustness, and explainability — not accuracy alone.


## **9.5 Evaluation Metrics — Full Set to Report**

| **Metric**                                     | **Why It Matters Here**                                                                                                                        |
|------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| ROC-AUC                                        | Overall discriminative ability, threshold-independent                                                                                          |
| PR-AUC (Precision-Recall AUC)                  | More informative than ROC-AUC if overrun/on-time classes are imbalanced                                                                        |
| Precision @ Top-K% (K=5,10,20)                 | Directly answers "if IPMD can only deep-review the top N projects this month, how many are truly at risk?" — the operationally relevant metric |
| Recall @ fixed false-positive budget           | Answers "how many real problem projects would we miss if we cap review capacity?"                                                              |
| Brier score / calibration curve                | Are the probabilities trustworthy as probabilities, not just as a ranking?                                                                     |
| MAE / RMSE (for regression variants)           | Error magnitude in ₹ crore or months, directly interpretable by non-technical stakeholders                                                     |
| Concordance index (for the Cox survival model) | Standard survival-analysis discrimination metric                                                                                               |
| **Lead time to adverse event**                    | Measures whether alerts arrive sufficiently before deterioration to enable intervention                                                      |
| **Alert precision by horizon**                    | Precision when requiring the adverse event to occur within a defined future window (e.g., 90/180 days)                                   |
| **Recall @ intervention capacity**                | Measures how many true adverse projects can be found when officers can review only the top 5%, 10%, or 20%                               |
| **Calibration error / Brier score**               | Tests whether predicted probabilities correspond to observed event frequencies                                                           |
| **Per-sector / per-ministry performance**         | Detects whether strong aggregate metrics hide weak performance in individual sectors or ministries                                       |
| **Confidence intervals**                           | Quantifies uncertainty in reported metrics rather than treating point estimates as exact                                                  |


# **10. External Validation & Prospective Evaluation**

The current model metrics establish predictive discrimination on historical data. They do **not** by themselves establish real-world early-warning value. Because the deployed system scores current PAIMANA projects, external validation shall be conducted on the projects actually flagged by the system and on an appropriately selected comparison sample of unflagged projects.

## **10.1 July 2026 Alert Validation Set**

The July 2026 alert output contains **133 active alerts**: 47 Rapidly Deteriorating, 31 Newly at Risk, and 55 Stalled and Overdue. These alerts shall be treated as a validation cohort, not as proof of accuracy by themselves.

Each project shall be independently adjudicated using evidence available outside the model output, prioritising: official MoSPI/PAIMANA records, Parliamentary questions/answers, ministry/implementing-agency releases, procurement/tender records, audit or committee documents, and credible news reporting as corroboration.

## **10.2 Adjudication Categories**

Each prediction shall receive one of four primary outcomes:

| Outcome | Definition |
|---|---|
| **Confirmed** | Independent evidence clearly demonstrates the predicted adverse condition or a subsequent adverse event consistent with the alert. |
| **Supported** | Evidence indicates deterioration or elevated risk, but the outcome is not yet sufficiently established to call confirmed. |
| **Contradicted** | Reliable evidence indicates materially healthy/on-track performance inconsistent with the alert. |
| **Unverified** | Insufficient independent evidence is publicly available to adjudicate the prediction. |

**Unverified must not be counted as false positive.** Likewise, finding evidence only after the model's alert date must be checked for temporal order before being credited as early-warning success.

## **10.3 Lead-Time Test**

For every project with a subsequently observed adverse event, record:

- prediction timestamp;
- first qualifying alert timestamp;
- event timestamp;
- lead time in days/months;
- whether the event was already observable at the prediction timestamp.

Report median lead time and the distribution of lead time. The product shall not claim a fixed six-month warning horizon unless a predefined proportion of true positives are shown to receive qualifying alerts at least six months before the adverse event.

## **10.4 Comparison Sample and Selection Bias**

Validating only the 133 flagged projects cannot produce an unbiased estimate of precision or accuracy for the full portfolio. A representative comparison sample of unflagged projects shall also be adjudicated using the same evidence and time window. Where resources permit, evaluate the complete portfolio; otherwise use a pre-registered stratified sample by risk band, ministry, and sector.

## **10.5 External Validation Reporting**

The final validation report shall contain:

1. a row-level evidence table for the 133 alerts;
2. an independently sampled unflagged comparison cohort;
3. confirmed/support/contradicted/unverified counts;
4. Precision, Recall, and Precision@Top-K with class prevalence;
5. lead-time statistics;
6. evidence-source type and publication/record date;
7. sector/ministry breakdowns;
8. a list of borderline cases and adjudication rationale.

The external study is intended to answer a different question from offline ML evaluation: **whether the deployed risk ranking generates actionable early warnings before adverse project outcomes become obvious.**

# **11. Model Limitations & Claims Discipline**

The system shall explicitly distinguish between:

- **Risk ranking:** strong evidence that higher-scored projects are more likely to experience the defined adverse outcome;
- **Probability estimation:** requires calibration evidence before a numerical score can be interpreted probabilistically;
- **Early warning:** requires a future event and measurable lead time;
- **Causal explanation:** SHAP or feature importance explains model contribution, not necessarily causal responsibility for project failure.

The system shall avoid claims that are unsupported by evaluation design, including a blanket statement that the model is "X% accurate" or that a risk score of 88.9 means an 88.9% probability of failure.
