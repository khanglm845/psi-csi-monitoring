"""
=============================================================
Credit Risk Dataset Generator
Company: NovaPay (fictional fintech)
Architecture: Python → Google BigQuery → Power BI
=============================================================
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

np.random.seed(42)

# ── Output directory: same folder as this script ──────────
OUTPUT_DIR = Path(__file__).parent

COMPANY_NAME = "NovaPay"
N_BASELINE = 50000
N_MONTHLY = 5000
MONTHS = 12

COMPANY_CONFIG = {
    "avg_score": 632,
    "std_score": 82,
    "default_rate": 0.065,
    "market": "Vietnam",
    "currency": "VND",
}

def generate_customers(n, drift_factor=0.0, snapshot_month="2023-01"):
    cfg = COMPANY_CONFIG
    age = np.clip(np.random.normal(33 + drift_factor * 1.5, 9, n), 18, 70).astype(int)
    monthly_income = np.clip(
        np.random.lognormal(np.log(13_500_000) + drift_factor * 0.08, 0.58, n),
        3_000_000, 200_000_000
    ).astype(int)
    monthly_income = (monthly_income // 100_000) * 100_000

    loan_amount = np.clip(
        np.random.lognormal(np.log(9_000_000) + drift_factor * 0.12, 0.68, n),
        500_000, 100_000_000
    ).astype(int)
    loan_amount = (loan_amount // 100_000) * 100_000

    dti = np.clip(loan_amount / (monthly_income * 12) + np.random.normal(0, 0.04, n), 0.01, 0.92)
    credit_history_months = np.clip(np.random.normal(38 - drift_factor * 2.5, 17, n), 0, 120).astype(int)
    num_late_payments = np.random.poisson(0.7 + drift_factor * 0.25, n)
    num_active_loans = np.clip(np.random.poisson(1.4 + drift_factor * 0.18, n), 0, 8).astype(int)
    app_usage_days = np.clip(np.random.normal(285 + drift_factor * 8, 58, n), 1, 365).astype(int)
    monthly_txn_count = np.clip(np.random.poisson(42 + drift_factor * 6, n), 0, 300).astype(int)
    avg_txn_amount = np.clip(
        np.random.lognormal(np.log(380_000) + drift_factor * 0.04, 0.48, n),
        10_000, 10_000_000
    ).astype(int)
    savings_balance = np.clip(
        np.random.lognormal(np.log(5_500_000), 1.15, n), 0, 500_000_000
    ).astype(int)
    has_insurance = np.random.binomial(1, 0.36 + drift_factor * 0.015, n)

    employment_probs = np.clip(
        [0.44 - drift_factor*0.025, 0.26, 0.15, 0.10 + drift_factor*0.018, 0.05 + drift_factor*0.007],
        0.01, None
    )
    employment_probs = employment_probs / employment_probs.sum()
    employment_type = np.random.choice(
        ["Salaried", "Self-employed", "Business_owner", "Freelancer", "Student"],
        n, p=employment_probs
    )
    education_level = np.random.choice(
        ["University", "College", "High_school", "Postgraduate"],
        n, p=[0.42, 0.28, 0.22, 0.08]
    )
    city_tier = np.random.choice(
        ["Tier1_HCMC", "Tier1_Hanoi", "Tier2", "Tier3"],
        n, p=[0.28, 0.22, 0.30, 0.20]
    )
    risk_segment = np.random.choice(
        ["Prime", "Near_prime", "Subprime", "Super_prime"],
        n, p=[0.35, 0.30, 0.22, 0.13]
    )
    acquisition_channel = np.random.choice(
        ["Organic_app", "Referral", "Partner_bank", "Social_ads", "Agent"],
        n, p=[0.38, 0.22, 0.18, 0.14, 0.08]
    )

    score_raw = (
        cfg["avg_score"] - 300 +
        (age - 18) / 52 * 55 +
        np.log1p(monthly_income) / np.log1p(200_000_000) * 95 +
        (1 - dti) * 75 +
        credit_history_months / 120 * 65 +
        (1 - num_late_payments / 10) * 55 +
        (1 - num_active_loans / 8) * 38 +
        app_usage_days / 365 * 28 +
        monthly_txn_count / 300 * 27 +
        np.log1p(savings_balance) / np.log1p(500_000_000) * 48 +
        np.random.normal(0, cfg["std_score"] * 0.38, n)
    )
    credit_score = np.clip(score_raw, 300, 850).astype(int)

    default_prob = 1 / (1 + np.exp((credit_score - 570) / 85)) * cfg["default_rate"] * 4.2
    default_flag = np.random.binomial(1, np.clip(default_prob, 0.005, 0.65), n)

    return pd.DataFrame({
        "customer_id":             [f"NP-{snapshot_month}-{i:06d}" for i in range(n)],
        "snapshot_month":          snapshot_month,
        "age":                     age,
        "monthly_income_vnd":      monthly_income,
        "loan_amount_vnd":         loan_amount,
        "debt_to_income_ratio":    np.round(dti, 4),
        "credit_history_months":   credit_history_months,
        "num_late_payments_12m":   num_late_payments,
        "num_active_loans":        num_active_loans,
        "app_usage_days_12m":      app_usage_days,
        "monthly_txn_count":       monthly_txn_count,
        "avg_txn_amount_vnd":      avg_txn_amount,
        "savings_balance_vnd":     savings_balance,
        "has_insurance":           has_insurance,
        "employment_type":         employment_type,
        "education_level":         education_level,
        "city_tier":               city_tier,
        "risk_segment":            risk_segment,
        "acquisition_channel":     acquisition_channel,
        "credit_score":            credit_score,
        "default_flag":            default_flag,
    })


# ── Baseline ──────────────────────────────────────────
baseline_df = generate_customers(N_BASELINE, drift_factor=0.0, snapshot_month="2023-01")
baseline_df.to_csv(OUTPUT_DIR / "novapay_baseline.csv", index=False)

# ── Monthly actual (with increasing drift) ──────────────
monthly_dfs = []
for i in range(MONTHS):
    month_str = (datetime(2023, 2, 1) + timedelta(days=30 * i)).strftime("%Y-%m")
    drift = i * 0.075
    df = generate_customers(N_MONTHLY, drift_factor=drift, snapshot_month=month_str)
    monthly_dfs.append(df)

actual_df = pd.concat(monthly_dfs, ignore_index=True)
actual_df.to_csv(OUTPUT_DIR / "novapay_actual_monthly.csv", index=False)

print(f"Baseline  : {len(baseline_df):,} records  →  {OUTPUT_DIR / 'novapay_baseline.csv'}")
print(f"Actual    : {len(actual_df):,} records   →  {OUTPUT_DIR / 'novapay_actual_monthly.csv'}")
print(f"Company   : {COMPANY_NAME}")
print(f"Features  : {len(baseline_df.columns)} columns")
print(f"\nColumn list: {list(baseline_df.columns)}")
