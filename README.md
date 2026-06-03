# NovaPay — Automated Credit Model Monitoring Dashboard
## Credit Risk Analyst · Internal Project

### Company context
NovaPay is a fictional fintech company. This project was built by the
Credit Risk Analytics team to automate monthly scorecard health checks.

---

### System architecture
```
Python (generate + compute)
    │
    ├── generate_dataset.py         → novapay_baseline.csv (50K records, Jan 2023)
    │                               → novapay_actual_monthly.csv (60K records, Feb–Dec 2023)
    │
    └── pipeline_to_bigquery.py     → BigQuery: novapay-risk-prod.novapay_risk
            │                             baseline_scores
            │                             actual_scores_monthly
            │                             psi_results
            │                             csi_results
            │                             monitoring_summary
            │
            └── Power BI (DirectQuery / Import)
                    powerbi_queries.sql  ← SQL views used in Power BI
```

Trigger: GCP Cloud Scheduler runs `pipeline_to_bigquery.py` on the 1st of each month.

---

### Feature set (17 input features + 1 target)

| Feature | Type | Description |
|---|---|---|
| age | Continuous | Customer age |
| monthly_income_vnd | Continuous | Monthly income (VND) |
| loan_amount_vnd | Continuous | Requested loan amount |
| debt_to_income_ratio | Continuous | DTI ratio |
| credit_history_months | Continuous | Length of credit history |
| num_late_payments_12m | Continuous | Late payments in last 12 months |
| num_active_loans | Continuous | Active loan count |
| app_usage_days_12m | Continuous | Days app was used in 12 months |
| monthly_txn_count | Continuous | Monthly transaction count |
| avg_txn_amount_vnd | Continuous | Average transaction amount |
| savings_balance_vnd | Continuous | Savings account balance |
| employment_type | Categorical | Salaried / Self-employed / Business_owner / Freelancer / Student |
| education_level | Categorical | University / College / High_school / Postgraduate |
| city_tier | Categorical | Tier1_HCMC / Tier1_Hanoi / Tier2 / Tier3 |
| risk_segment | Categorical | Prime / Near_prime / Subprime / Super_prime |
| acquisition_channel | Categorical | Organic_app / Referral / Partner_bank / Social_ads / Agent |
| has_insurance | Categorical | Binary: 0 / 1 |
| **credit_score** | **Target** | **300–850 (scorecard output)** |
| **default_flag** | **Target** | **Binary: 1 = defaulted within 12M** |

---

### Monitoring thresholds

| Index | Stable | Monitor | Action required |
|---|---|---|---|
| PSI | < 0.10 | 0.10 – 0.25 | > 0.25 → Retrain model |
| CSI | < 0.10 | 0.10 – 0.25 | > 0.25 → Recalibrate feature |

---

### Running the pipeline

```bash
# Install dependencies
pip install -r requirements.txt

# Step 1 — generate dataset (run once, or to refresh)
python generate_dataset.py

# Step 2 — run monthly monitoring + upload to BigQuery
#   Set use_mock=False and configure GCP credentials for production
python pipeline_to_bigquery.py

# Step 3 — connect Power BI to BigQuery
#   File → Get Data → Google BigQuery
#   Use queries from powerbi_queries.sql
```

---

### Key findings (2023 monitoring cycle)

<img width="959" height="533" alt="psi" src="https://github.com/user-attachments/assets/9e56c413-13ac-4de0-a117-6cae4ed24b97" />

- PSI remains stable throughout all 12 months (max: 0.0035)
- `monthly_txn_count` shows progressive High Drift from Sep 2023 (CSI: 0.52 in Dec)
- Recommendation: recalibrate scorecard weight for `monthly_txn_count` before Q1 2024
