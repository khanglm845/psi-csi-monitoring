-- ============================================================
-- NovaPay — Power BI DirectQuery SQL snippets
-- Source: BigQuery dataset novapay_risk
-- ============================================================

-- 1. Monthly monitoring summary (main dashboard table)
SELECT
  snapshot_month,
  psi_score,
  psi_status,
  max_csi,
  features_in_monitor,
  features_in_drift,
  mean_score_actual,
  mean_score_baseline,
  score_shift_pts,
  ROUND(default_rate_actual * 100, 2)   AS default_rate_pct,
  ROUND(default_rate_baseline * 100, 2) AS default_rate_baseline_pct,
  n_actual
FROM `novapay-risk-prod.novapay_risk.monitoring_summary`
ORDER BY snapshot_month;

-- 2. CSI per feature per month (heatmap / ranking visual)
SELECT
  snapshot_month,
  feature_name,
  feature_type,
  score                                         AS csi_score,
  status                                        AS csi_status,
  CASE
    WHEN score >= 0.25 THEN 3
    WHEN score >= 0.10 THEN 2
    ELSE 1
  END                                           AS status_rank
FROM `novapay-risk-prod.novapay_risk.csi_results`
ORDER BY snapshot_month, score DESC;

-- 3. Score distribution comparison (Baseline vs latest month)
SELECT
  'Baseline'      AS cohort,
  credit_score,
  NTILE(10) OVER (ORDER BY credit_score) AS score_decile
FROM `novapay-risk-prod.novapay_risk.baseline_scores`
UNION ALL
SELECT
  snapshot_month  AS cohort,
  credit_score,
  NTILE(10) OVER (ORDER BY credit_score) AS score_decile
FROM `novapay-risk-prod.novapay_risk.actual_scores_monthly`
WHERE snapshot_month = (
  SELECT MAX(snapshot_month)
  FROM `novapay-risk-prod.novapay_risk.actual_scores_monthly`
);

-- 4. PSI time series with threshold bands (for conditional formatting)
SELECT
  snapshot_month,
  score                                         AS psi_score,
  status                                        AS psi_status,
  0.10                                          AS threshold_monitor,
  0.25                                          AS threshold_retrain
FROM `novapay-risk-prod.novapay_risk.psi_results`
ORDER BY snapshot_month;

-- 5. Feature drift alert summary (features with High_Drift in latest month)
SELECT
  feature_name,
  feature_type,
  score   AS csi_score,
  status
FROM `novapay-risk-prod.novapay_risk.csi_results`
WHERE snapshot_month = (
  SELECT MAX(snapshot_month) FROM `novapay-risk-prod.novapay_risk.csi_results`
)
AND status = 'High_Drift'
ORDER BY score DESC;
