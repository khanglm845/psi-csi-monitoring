"""
=============================================================
NovaPay — Credit Model Monitoring Pipeline
Architecture: CSV → BigQuery → (Power BI reads via connector)

BigQuery tables pushed:
  novapay_risk.baseline_scores
  novapay_risk.actual_scores_monthly
  novapay_risk.psi_results
  novapay_risk.csi_results
  novapay_risk.monitoring_summary

Dependencies:
  pip install pandas-gbq
=============================================================
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
# pyrefly: ignore [missing-import]
import pandas_gbq

warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ── BigQuery config ────────────────────────────────────────
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(BASE_DIR / "gcp-key.json")

PROJECT_ID = "affable-tribute-498114-i9"
DATASET_ID = "novapay_risk"

# ─────────────────────────────────────────────────────────
#  PSI  (Population Stability Index)
# ─────────────────────────────────────────────────────────

def calculate_psi(baseline: pd.Series, actual: pd.Series, bins: int = 10) -> dict:
    """
    PSI for the total credit score distribution.
    Thresholds: < 0.10 Stable | 0.10–0.25 Monitor | > 0.25 Retrain
    """
    bp = np.percentile(baseline.dropna(), np.linspace(0, 100, bins + 1))
    bp = np.unique(bp)
    bp[0], bp[-1] = -np.inf, np.inf

    b_pct = np.histogram(baseline.dropna(), bins=bp)[0] / len(baseline.dropna())
    a_pct = np.histogram(actual.dropna(),   bins=bp)[0] / len(actual.dropna())
    b_pct = np.where(b_pct == 0, 1e-4, b_pct)
    a_pct = np.where(a_pct == 0, 1e-4, a_pct)

    psi_total = float(((a_pct - b_pct) * np.log(a_pct / b_pct)).sum())

    return {
        "psi_score": round(psi_total, 5),
        "status":    "Stable" if psi_total < 0.10 else "Monitor" if psi_total < 0.25 else "Retrain",
        "bins":      len(b_pct),
    }


# ─────────────────────────────────────────────────────────
#  CSI  (Characteristic Stability Index)
# ─────────────────────────────────────────────────────────

def calculate_csi(baseline: pd.Series, actual: pd.Series,
                  feature_name: str, feature_type: str,
                  bins: int = 10) -> dict:
    """
    CSI for a single input feature (continuous or categorical).
    Same thresholds as PSI.
    """
    if feature_type == "continuous":
        bp = np.percentile(baseline.dropna(), np.linspace(0, 100, bins + 1))
        bp = np.unique(bp)
        bp[0], bp[-1] = -np.inf, np.inf
        b_pct = np.histogram(baseline.dropna(), bins=bp)[0] / len(baseline.dropna())
        a_pct = np.histogram(actual.dropna(),   bins=bp)[0] / len(actual.dropna())
    else:
        cats  = set(baseline.dropna().unique()) | set(actual.dropna().unique())
        b_pct = baseline.value_counts(normalize=True).reindex(cats, fill_value=1e-4).values
        a_pct = actual.value_counts(normalize=True).reindex(cats,   fill_value=1e-4).values

    b_pct   = np.where(b_pct == 0, 1e-4, b_pct)
    a_pct   = np.where(a_pct == 0, 1e-4, a_pct)
    csi_val = float(((a_pct - b_pct) * np.log(a_pct / b_pct)).sum())

    return {
        "feature_name": feature_name,
        "feature_type": feature_type,
        "csi_score":    round(csi_val, 5),
        "status":       "Stable" if csi_val < 0.10 else "Monitor" if csi_val < 0.25 else "High_Drift",
    }


# ─────────────────────────────────────────────────────────
#  Feature registry
# ─────────────────────────────────────────────────────────

FEATURES = {
    "continuous": [
        "age", "monthly_income_vnd", "loan_amount_vnd", "debt_to_income_ratio",
        "credit_history_months", "num_late_payments_12m", "num_active_loans",
        "app_usage_days_12m", "monthly_txn_count", "avg_txn_amount_vnd", "savings_balance_vnd",
    ],
    "categorical": [
        "has_insurance", "employment_type", "education_level",
        "city_tier", "risk_segment", "acquisition_channel",
    ],
}


# ─────────────────────────────────────────────────────────
#  Helper: fix datetime precision for BigQuery / PyArrow
# ─────────────────────────────────────────────────────────

def fix_datetime_precision(df: pd.DataFrame) -> pd.DataFrame:
    """BigQuery/PyArrow requires microsecond (us) precision.
    pandas defaults to nanoseconds (ns) which causes upload errors."""
    for col in df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns:
        df[col] = df[col].astype("datetime64[us]")
    return df


# ─────────────────────────────────────────────────────────
#  Monthly monitoring run
# ─────────────────────────────────────────────────────────

def run_monthly_monitoring(baseline_path: str, actual_path: str,
                           months_to_run: list = None):
    print("=" * 62)
    print("  NovaPay — Credit Model Monthly Monitoring")
    print("=" * 62)

    baseline = pd.read_csv(baseline_path)
    actual   = pd.read_csv(actual_path)
    months   = sorted(actual["snapshot_month"].unique())
    if months_to_run:
        months = [m for m in months if m in months_to_run]

    all_psi_rows = []
    all_csi_rows = []
    all_summary  = []

    for month in months:
        print(f"\n  Processing: {month}")
        am = actual[actual["snapshot_month"] == month]

        # ── PSI ────────────────────────────────────────────
        psi     = calculate_psi(baseline["credit_score"], am["credit_score"])
        psi_row = {
            "snapshot_month": month,
            "metric":         "PSI",
            "feature_name":   "credit_score",
            "score":          psi["psi_score"],
            "status":         psi["status"],
            "n_baseline":     len(baseline),
            "n_actual":       len(am),
        }
        all_psi_rows.append(psi_row)
        print(f"    PSI = {psi['psi_score']:.5f}  [{psi['status']}]")

        # ── CSI ────────────────────────────────────────────
        csi_scores = []
        for ft, ftype in (
            [(f, "continuous")  for f in FEATURES["continuous"]] +
            [(f, "categorical") for f in FEATURES["categorical"]]
        ):
            if ft not in baseline.columns:
                continue
            csi     = calculate_csi(baseline[ft], am[ft], ft, ftype)
            csi_row = {
                "snapshot_month": month,
                "metric":         "CSI",
                "feature_name":   csi["feature_name"],
                "feature_type":   csi["feature_type"],
                "score":          csi["csi_score"],
                "status":         csi["status"],
            }
            all_csi_rows.append(csi_row)
            csi_scores.append(csi["csi_score"])
            if csi["status"] != "Stable":
                print(f"    CSI [{ft}] = {csi['csi_score']:.5f}  [{csi['status']}]")

        # ── Summary row (for Power BI dashboard) ───────────
        all_summary.append({
            "snapshot_month":        month,
            "psi_score":             psi["psi_score"],
            "psi_status":            psi["status"],
            "max_csi":               round(max(csi_scores), 5),
            "features_in_monitor":   sum(1 for s in all_csi_rows if s["snapshot_month"] == month and s["status"] == "Monitor"),
            "features_in_drift":     sum(1 for s in all_csi_rows if s["snapshot_month"] == month and s["status"] == "High_Drift"),
            "mean_score_actual":     round(am["credit_score"].mean(), 2),
            "mean_score_baseline":   round(baseline["credit_score"].mean(), 2),
            "score_shift_pts":       round(am["credit_score"].mean() - baseline["credit_score"].mean(), 2),
            "default_rate_actual":   round(am["default_flag"].mean(), 5),
            "default_rate_baseline": round(baseline["default_flag"].mean(), 5),
            "n_actual":              len(am),
        })

    return baseline, actual, pd.DataFrame(all_psi_rows), pd.DataFrame(all_csi_rows), pd.DataFrame(all_summary)


# ─────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── 1. Run monitoring calculations ────────────────────
    baseline, actual, psi_df, csi_df, summary_df = run_monthly_monitoring(
        baseline_path=str(BASE_DIR / "novapay_baseline.csv"),
        actual_path=str(BASE_DIR / "novapay_actual_monthly.csv"),
    )

    # ── 2. Fix datetime precision for BigQuery / PyArrow ──
    #    BigQuery/PyArrow requires microsecond (us) precision,
    #    pandas defaults to nanoseconds (ns).
    for df in [baseline, actual, psi_df, csi_df, summary_df]:
        fix_datetime_precision(df)

    # ── 3. Push all tables to BigQuery ────────────────────
    print("\nStart pushing tables to BigQuery...")

    pandas_gbq.to_gbq(baseline,   f"{DATASET_ID}.baseline_scores",       project_id=PROJECT_ID, if_exists="replace")
    pandas_gbq.to_gbq(actual,     f"{DATASET_ID}.actual_scores_monthly",  project_id=PROJECT_ID, if_exists="replace")
    pandas_gbq.to_gbq(psi_df,     f"{DATASET_ID}.psi_results",            project_id=PROJECT_ID, if_exists="replace")
    pandas_gbq.to_gbq(csi_df,     f"{DATASET_ID}.csi_results",            project_id=PROJECT_ID, if_exists="replace")
    pandas_gbq.to_gbq(summary_df, f"{DATASET_ID}.monitoring_summary",     project_id=PROJECT_ID, if_exists="replace")

    print("Push tables to BigQuery successfully!")
    print("\n  Tables updated:")
    print(f"    {DATASET_ID}.baseline_scores")
    print(f"    {DATASET_ID}.actual_scores_monthly")
    print(f"    {DATASET_ID}.psi_results")
    print(f"    {DATASET_ID}.csi_results")
    print(f"    {DATASET_ID}.monitoring_summary")

    # ── 4. Print monthly summary ───────────────────────────
    print("\n  Monthly summary:")
    print(
        summary_df[
            ["snapshot_month", "psi_score", "psi_status", "max_csi",
             "features_in_drift", "mean_score_actual", "default_rate_actual"]
        ].to_string(index=False)
    )
