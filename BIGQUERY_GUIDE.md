# 🚀 Hướng dẫn đẩy dữ liệu lên Google BigQuery

> **Dự án**: NovaPay Credit Model Monitoring  
> **Stack**: Python → `pandas_gbq` → Google BigQuery → Power BI  
> **File pipeline**: [`pipeline_to_bigquery.py`](./pipeline_to_bigquery.py)

---

## Mục lục

1. [Chuẩn bị môi trường](#1-chuẩn-bị-môi-trường)
2. [Tạo Google Cloud Project & BigQuery Dataset](#2-tạo-google-cloud-project--bigquery-dataset)
3. [Cấu hình xác thực (Authentication)](#3-cấu-hình-xác-thực-authentication)
4. [Cài đặt thư viện](#4-cài-đặt-thư-viện)
5. [Sinh dữ liệu mẫu](#5-sinh-dữ-liệu-mẫu)
6. [Chạy pipeline đẩy lên BigQuery](#6-chạy-pipeline-đẩy-lên-bigquery)
7. [Kiểm tra dữ liệu trên BigQuery](#7-kiểm-tra-dữ-liệu-trên-bigquery)
8. [Kết nối Power BI](#8-kết-nối-power-bi)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Chuẩn bị môi trường

### Yêu cầu hệ thống
- Python **3.9+**
- Tài khoản **Google Cloud** (miễn phí $300 credit cho người mới)
- **Google Cloud SDK** (CLI `gcloud`)

### Cài đặt Google Cloud SDK (Windows)

Tải về tại: https://cloud.google.com/sdk/docs/install

Sau khi cài xong, chạy trong terminal:

```powershell
gcloud init
```

---

## 2. Tạo Google Cloud Project & BigQuery Dataset

### Bước 2.1 — Tạo Project

Vào [Google Cloud Console](https://console.cloud.google.com) → **New Project**

| Trường | Giá trị gợi ý |
|--------|--------------|
| Project name | `novapay-risk` |
| Project ID | `novapay-risk-prod` *(ghi lại ID này)* |

Hoặc dùng CLI:

```powershell
gcloud projects create novapay-risk-prod --name="NovaPay Risk"
gcloud config set project novapay-risk-prod
```

### Bước 2.2 — Bật BigQuery API

```powershell
gcloud services enable bigquery.googleapis.com
```

### Bước 2.3 — Tạo Dataset

Vào [BigQuery Console](https://console.cloud.google.com/bigquery) → chọn project → **Create dataset**

| Trường | Giá trị |
|--------|---------|
| Dataset ID | `novapay_risk` |
| Location | `asia-southeast1` *(Singapore — gần Việt Nam nhất)* |

Hoặc dùng CLI:

```powershell
bq mk --location=asia-southeast1 novapay-risk-prod:novapay_risk
```

---

## 3. Cấu hình xác thực (Authentication)

> ⚠️ **Đây là bước quan trọng nhất.** Có 2 cách xác thực:

### Cách A — Application Default Credentials *(Phát triển cục bộ — Đơn giản nhất)*

```powershell
gcloud auth application-default login
```

Lệnh này sẽ mở trình duyệt, đăng nhập tài khoản Google → credentials được lưu tự động.  
`pandas_gbq` sẽ tự phát hiện credentials này mà **không cần cấu hình thêm**.

### Cách B — Service Account Key *(Production / CI-CD)*

**Bước 1**: Tạo Service Account

```powershell
gcloud iam service-accounts create novapay-bq-writer `
  --display-name="NovaPay BigQuery Writer"
```

**Bước 2**: Cấp quyền BigQuery

```powershell
gcloud projects add-iam-policy-binding novapay-risk-prod `
  --member="serviceAccount:novapay-bq-writer@novapay-risk-prod.iam.gserviceaccount.com" `
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding novapay-risk-prod `
  --member="serviceAccount:novapay-bq-writer@novapay-risk-prod.iam.gserviceaccount.com" `
  --role="roles/bigquery.jobUser"
```

**Bước 3**: Tải file key JSON

```powershell
gcloud iam service-accounts keys create credentials.json `
  --iam-account=novapay-bq-writer@novapay-risk-prod.iam.gserviceaccount.com
```

> 🔒 **Bảo mật**: Thêm `credentials.json` vào `.gitignore`, **không** commit lên GitHub!

**Bước 4**: Set biến môi trường

```powershell
# Windows PowerShell (tạm thời cho session hiện tại)
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\DELL\OneDrive\Antigravity\psi\credentials.json"

# Hoặc set vĩnh viễn
[System.Environment]::SetEnvironmentVariable(
  "GOOGLE_APPLICATION_CREDENTIALS",
  "C:\Users\DELL\OneDrive\Antigravity\psi\credentials.json",
  "User"
)
```

---

## 4. Cài đặt thư viện

```powershell
pip install -r requirements.txt
```

Hoặc cài riêng `pandas_gbq`:

```powershell
pip install pandas-gbq
```

**Kiểm tra cài đặt:**

```python
import pandas_gbq
print(pandas_gbq.__version__)
```

---

## 5. Sinh dữ liệu mẫu

Chạy script tạo dữ liệu — file CSV sẽ được lưu vào thư mục dự án:

```powershell
python generate_dataset.py
```

Kết quả mong đợi:

```
Baseline  : 50,000 records  →  ...\psi\novapay_baseline.csv
Actual    : 60,000 records  →  ...\psi\novapay_actual_monthly.csv
Company   : NovaPay
Features  : 21 columns
```

---

## 6. Chạy pipeline đẩy lên BigQuery

### 6.1 — Cấu hình `PROJECT_ID` và `DATASET_ID`

Mở [`pipeline_to_bigquery.py`](./pipeline_to_bigquery.py) và chỉnh 2 dòng config ở đầu file:

```python
PROJECT_ID = "novapay-risk-prod"   # ← ID project GCP của bạn
DATASET_ID = "novapay_risk"         # ← Dataset đã tạo ở Bước 2
```

Đảm bảo file `gcp-key.json` nằm cùng thư mục với script (xem [Bước 3 - Cách B](#3-cấu-hình-xác-thực-authentication)).

### 6.2 — Chạy pipeline

```powershell
python pipeline_to_bigquery.py
```

Kết quả mong đợi:

```
==============================================================
  NovaPay — Credit Model Monthly Monitoring
==============================================================

  Processing: 2023-02
    PSI = 0.00312  [Stable]
  ...

Start pushing tables to BigQuery...
Push tables to BigQuery successfully!

  Tables updated:
    novapay_risk.baseline_scores
    novapay_risk.actual_scores_monthly
    novapay_risk.psi_results
    novapay_risk.csi_results
    novapay_risk.monitoring_summary
```

### 6.3 — Cấu trúc upload trong code

Pipeline theo đúng pattern chuẩn — thẳng, dễ đọc, dễ chỉnh:

```python
import os, pandas_gbq
from pathlib import Path

BASE_DIR   = Path(__file__).parent
PROJECT_ID = "novapay-risk-prod"
DATASET_ID = "novapay_risk"

# 1. Đặt credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(BASE_DIR / "gcp-key.json")

# 2. Fix datetime precision (BigQuery/PyArrow cần microsecond, pandas mặc định nanosecond)
for df in [baseline, actual, psi_df, csi_df, summary_df]:
    for col in df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns:
        df[col] = df[col].astype("datetime64[us]")

# 3. Push lên BigQuery
print("Start pushing tables to BigQuery...")
pandas_gbq.to_gbq(baseline,   f"{DATASET_ID}.baseline_scores",      project_id=PROJECT_ID, if_exists="replace")
pandas_gbq.to_gbq(actual,     f"{DATASET_ID}.actual_scores_monthly", project_id=PROJECT_ID, if_exists="replace")
pandas_gbq.to_gbq(psi_df,     f"{DATASET_ID}.psi_results",           project_id=PROJECT_ID, if_exists="replace")
pandas_gbq.to_gbq(csi_df,     f"{DATASET_ID}.csi_results",           project_id=PROJECT_ID, if_exists="replace")
pandas_gbq.to_gbq(summary_df, f"{DATASET_ID}.monitoring_summary",    project_id=PROJECT_ID, if_exists="replace")
print("Push tables to BigQuery successfully!")
```

**Đọc dữ liệu từ BigQuery về:**

```python
df = pandas_gbq.read_gbq(
    "SELECT * FROM `novapay-risk-prod.novapay_risk.monitoring_summary`",
    project_id="novapay-risk-prod",
)
print(df.head())
```

---

## 7. Kiểm tra dữ liệu trên BigQuery

Vào [BigQuery Console](https://console.cloud.google.com/bigquery) → chọn project `novapay-risk-prod` → dataset `novapay_risk`

### Bảng được tạo tự động

| Bảng | Mô tả | Số dòng dự kiến |
|------|--------|----------------|
| `baseline_scores` | Dữ liệu baseline 2023-01 | 50,000 |
| `actual_scores_monthly` | Dữ liệu thực tế 12 tháng | 60,000 |
| `psi_results` | PSI theo tháng | 12 |
| `csi_results` | CSI theo feature × tháng | 204 |
| `monitoring_summary` | Dashboard tổng hợp | 12 |

### Query kiểm tra nhanh

```sql
-- Kiểm tra PSI theo tháng
SELECT snapshot_month, score AS psi_score, status
FROM `novapay-risk-prod.novapay_risk.psi_results`
ORDER BY snapshot_month;

-- Các feature bị drift cao
SELECT snapshot_month, feature_name, score AS csi_score, status
FROM `novapay-risk-prod.novapay_risk.csi_results`
WHERE status = 'High_Drift'
ORDER BY snapshot_month, score DESC;

-- Tổng quan dashboard
SELECT *
FROM `novapay-risk-prod.novapay_risk.monitoring_summary`
ORDER BY snapshot_month;
```

---

## 8. Kết nối Power BI

1. Mở **Power BI Desktop** → **Get Data** → tìm **Google BigQuery**
2. Nhập **Project ID**: `novapay-risk-prod`
3. Đăng nhập tài khoản Google khi được yêu cầu
4. Chọn dataset `novapay_risk` → chọn các bảng cần dùng
5. **Load** → xây dựng dashboard

> 💡 Dùng file [`powerbi_queries.sql`](./powerbi_queries.sql) làm template cho các DAX/Power Query measures.

---

## 9. Troubleshooting

### ❌ `DefaultCredentialsError`
```
google.auth.exceptions.DefaultCredentialsError: Could not automatically determine credentials
```
**Giải pháp**: Chạy `gcloud auth application-default login` hoặc kiểm tra biến môi trường `GOOGLE_APPLICATION_CREDENTIALS`.

---

### ❌ `403 Access Denied`
```
google.api_core.exceptions.Forbidden: 403 Access Denied
```
**Giải pháp**: Service account chưa có quyền. Chạy lại lệnh grant quyền ở [Bước 3](#3-cấu-hình-xác-thực-authentication) → roles `bigquery.dataEditor` + `bigquery.jobUser`.

---

### ❌ `pandas_gbq not found`
```
ModuleNotFoundError: No module named 'pandas_gbq'
```
**Giải pháp**: 
```powershell
pip install pandas-gbq
```

---

### ❌ `Project not found`
```
google.api_core.exceptions.NotFound: 404 Project not found
```
**Giải pháp**: Kiểm tra lại `project_id` trong `BigQueryClient`. Project ID ≠ Project Name. Xem tại [Cloud Console](https://console.cloud.google.com) → cột **ID**.

---

### ❌ Upload chậm với bảng lớn

`pandas_gbq` mặc định dùng HTTP upload. Để tăng tốc với bảng lớn (>100k dòng), cài thêm:

```powershell
pip install db-dtypes google-cloud-bigquery-storage
```

---

## Tóm tắt luồng hoạt động

```
generate_dataset.py          pipeline_to_bigquery.py         Google BigQuery
      │                              │                              │
      ├─ novapay_baseline.csv ──────►│                              │
      └─ novapay_actual_monthly.csv ►│                              │
                                     ├─ calculate PSI/CSI           │
                                     ├─ pandas_gbq.to_gbq() ───────►│ baseline_scores
                                     ├─ pandas_gbq.to_gbq() ───────►│ actual_scores_monthly
                                     ├─ pandas_gbq.to_gbq() ───────►│ psi_results
                                     ├─ pandas_gbq.to_gbq() ───────►│ csi_results
                                     └─ pandas_gbq.to_gbq() ───────►│ monitoring_summary
                                                                     │
                                                              Power BI Dashboard
```
