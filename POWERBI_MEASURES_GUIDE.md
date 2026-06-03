# 📊 DAX Measures — Automated Credit Model Monitoring Dashboard

> **Dự án**: NovaPay Credit Model Monitoring  
> **Nguồn dữ liệu**: Google BigQuery → Power BI DirectQuery  
> **Dataset**: `novapay-risk-prod.novapay_risk`  
> **File SQL**: [`powerbi_queries.sql`](./powerbi_queries.sql)

---

## Mục lục

1. [Sơ đồ bảng & quan hệ](#1-sơ-đồ-bảng--quan-hệ)
2. [Bảng hỗ trợ (Helper Tables)](#2-bảng-hỗ-trợ-helper-tables)
3. [Measures — Top Bar](#3-measures--top-bar)
4. [Measures — KPI Row (4 Cards)](#4-measures--kpi-row-4-cards)
5. [Measures — PSI Trend Chart (Left Top)](#5-measures--psi-trend-chart-left-top)
6. [Measures — Combo Chart Default Rate + Mean Score (Left Bottom)](#6-measures--combo-chart-default-rate--mean-score-left-bottom)
7. [Measures — Max CSI Trend Chart (Right Top)](#7-measures--max-csi-trend-chart-right-top)
8. [Measures — CSI Feature Ranking (Right Bottom)](#8-measures--csi-feature-ranking-right-bottom)
9. [Measures — Bottom Alert Banner](#9-measures--bottom-alert-banner)
10. [Conditional Formatting Rules](#10-conditional-formatting-rules)
11. [Hướng dẫn tổ chức Measure Groups](#11-hướng-dẫn-tổ-chức-measure-groups)

---

## 1. Sơ đồ bảng & quan hệ

### Các bảng load từ BigQuery

| Bảng Power BI | Nguồn BigQuery | Mô tả |
|---|---|---|
| `monitoring_summary` | `novapay_risk.monitoring_summary` | 12 dòng — tổng hợp tháng |
| `csi_results` | `novapay_risk.csi_results` | 204 dòng — CSI theo feature × tháng |
| `psi_results` | `novapay_risk.psi_results` | 12 dòng — PSI theo tháng |
| `csi_feature_latest` | Query SQL #5 | Features bị High_Drift tháng mới nhất |

### Quan hệ (Relationships)

```
monitoring_summary[snapshot_month]  ──1:N──  psi_results[snapshot_month]
monitoring_summary[snapshot_month]  ──1:N──  csi_results[snapshot_month]
```

> **Lưu ý**: Đặt `snapshot_month` là kiểu `Date` (format `YYYY-MM-01`) để Power BI nhận diện time intelligence.

---

## 2. Bảng hỗ trợ (Helper Tables)

Tạo trong **Power BI Desktop → Enter Data** hoặc dùng DAX:

### 2.1 Bảng ngưỡng ngưỡng (Threshold)

```
Table: _Thresholds
─────────────────────────────────
Metric         | Amber  | Red
─────────────────────────────────
PSI            | 0.10   | 0.25
CSI            | 0.10   | 0.25
```

> Không cần tạo bảng này nếu đã có cột `threshold_monitor` và `threshold_retrain` trong query SQL #4.

### 2.2 Bảng tháng hiện tại (không bắt buộc)

```dax
_LatestMonth = 
    CALCULATE(
        MAX(monitoring_summary[snapshot_month])
    )
```

---

## 3. Measures — Top Bar

### 3.1 Last Refresh Timestamp

```dax
Last Refresh =
    "Last updated: " & FORMAT(NOW(), "DD/MM/YYYY HH:MM")
```

### 3.2 Overall Status Badge

Logic ưu tiên: nếu có bất kỳ metric nào vi phạm ngưỡng đỏ → **Retrain**, vi phạm ngưỡng vàng → **Monitor**, còn lại → **Stable**.

```dax
Overall Status =
VAR _LatestPSI =
    CALCULATE(
        MAX(psi_results[psi_score]),
        psi_results[snapshot_month] = MAX(psi_results[snapshot_month])
    )
VAR _LatestCSI =
    CALCULATE(
        MAX(csi_results[csi_score]),
        csi_results[snapshot_month] = MAX(csi_results[snapshot_month])
    )
RETURN
    IF(
        _LatestPSI >= 0.25 || _LatestCSI >= 0.25,
        "🔴 Retrain",
        IF(
            _LatestPSI >= 0.10 || _LatestCSI >= 0.10,
            "🟡 Monitor",
            "🟢 Stable"
        )
    )
```

### 3.3 Overall Status (cho Conditional Formatting — trả về số)

```dax
Overall Status Code =
VAR _LatestPSI =
    CALCULATE(
        MAX(psi_results[psi_score]),
        psi_results[snapshot_month] = MAX(psi_results[snapshot_month])
    )
VAR _LatestCSI =
    CALCULATE(
        MAX(csi_results[csi_score]),
        csi_results[snapshot_month] = MAX(csi_results[snapshot_month])
    )
RETURN
    IF(
        _LatestPSI >= 0.25 || _LatestCSI >= 0.25, 3,   -- Red / Retrain
        IF(
            _LatestPSI >= 0.10 || _LatestCSI >= 0.10, 2, -- Amber / Monitor
            1                                              -- Green / Stable
        )
    )
```

> **Dùng measure này** để tô màu pill badge qua Conditional Formatting:  
> `1` → `#1D9E75` · `2` → `#BA7517` · `3` → `#A32D2D`

---

## 4. Measures — KPI Row (4 Cards)

> Mỗi card cần 3 measures: **Giá trị hiện tại**, **Delta so tháng trước**, **Nhãn delta**.

---

### 4.1 PSI Score Card

#### Giá trị hiện tại
```dax
PSI Score (Latest) =
CALCULATE(
    MAX(psi_results[psi_score]),
    psi_results[snapshot_month] = CALCULATE(MAX(psi_results[snapshot_month]))
)
```

#### Tháng trước
```dax
PSI Score (Prior Month) =
VAR _Latest = CALCULATE(MAX(psi_results[snapshot_month]))
VAR _PriorMonth = EDATE(_Latest, -1)
RETURN
    CALCULATE(
        MAX(psi_results[psi_score]),
        psi_results[snapshot_month] = _PriorMonth
    )
```

#### Delta (số)
```dax
PSI Delta =
    [PSI Score (Latest)] - [PSI Score (Prior Month)]
```

#### Delta (nhãn hiển thị)
```dax
PSI Delta Label =
VAR _Delta = [PSI Delta]
RETURN
    IF(
        ISBLANK(_Delta), "N/A",
        IF(_Delta > 0,
            "▲ " & FORMAT(ABS(_Delta), "0.0000"),
            IF(_Delta < 0,
                "▼ " & FORMAT(ABS(_Delta), "0.0000"),
                "— 0.0000"
            )
        )
    )
```

#### Color Code (cho Conditional Formatting)
```dax
PSI Color Code =
VAR _v = [PSI Score (Latest)]
RETURN
    IF(_v >= 0.25, 3, IF(_v >= 0.10, 2, 1))
```

---

### 4.2 Max CSI Card

#### Giá trị hiện tại
```dax
Max CSI (Latest) =
CALCULATE(
    MAX(csi_results[csi_score]),
    csi_results[snapshot_month] = CALCULATE(MAX(csi_results[snapshot_month]))
)
```

#### Tháng trước
```dax
Max CSI (Prior Month) =
VAR _Latest = CALCULATE(MAX(csi_results[snapshot_month]))
VAR _PriorMonth = EDATE(_Latest, -1)
RETURN
    CALCULATE(
        MAX(csi_results[csi_score]),
        csi_results[snapshot_month] = _PriorMonth
    )
```

#### Delta
```dax
CSI Delta =
    [Max CSI (Latest)] - [Max CSI (Prior Month)]
```

#### Delta Label
```dax
CSI Delta Label =
VAR _Delta = [CSI Delta]
RETURN
    IF(
        ISBLANK(_Delta), "N/A",
        IF(_Delta > 0,
            "▲ " & FORMAT(ABS(_Delta), "0.0000"),
            IF(_Delta < 0,
                "▼ " & FORMAT(ABS(_Delta), "0.0000"),
                "— 0.0000"
            )
        )
    )
```

#### Color Code
```dax
CSI Color Code =
VAR _v = [Max CSI (Latest)]
RETURN
    IF(_v >= 0.25, 3, IF(_v >= 0.10, 2, 1))
```

---

### 4.3 Default Rate Card

#### Giá trị hiện tại (%)
```dax
Default Rate (Latest) =
CALCULATE(
    MAX(monitoring_summary[default_rate_pct]),
    monitoring_summary[snapshot_month] = CALCULATE(MAX(monitoring_summary[snapshot_month]))
)
```

> `default_rate_pct` đã được nhân 100 trong SQL query. Measure này trả về %, ví dụ `3.45`.

#### Tháng trước
```dax
Default Rate (Prior Month) =
VAR _Latest = CALCULATE(MAX(monitoring_summary[snapshot_month]))
VAR _PriorMonth = EDATE(_Latest, -1)
RETURN
    CALCULATE(
        MAX(monitoring_summary[default_rate_pct]),
        monitoring_summary[snapshot_month] = _PriorMonth
    )
```

#### Delta
```dax
Default Rate Delta =
    [Default Rate (Latest)] - [Default Rate (Prior Month)]
```

#### Delta Label
```dax
Default Rate Delta Label =
VAR _Delta = [Default Rate Delta]
RETURN
    IF(
        ISBLANK(_Delta), "N/A",
        IF(_Delta > 0,
            "▲ " & FORMAT(ABS(_Delta), "0.00") & " pp",
            IF(_Delta < 0,
                "▼ " & FORMAT(ABS(_Delta), "0.00") & " pp",
                "— 0.00 pp"
            )
        )
    )
```

#### Color Code (tỷ lệ nợ xấu tăng = xấu)
```dax
Default Rate Color Code =
VAR _Delta = [Default Rate Delta]
RETURN
    IF(_Delta > 0.5, 3, IF(_Delta > 0, 2, 1))
```

---

### 4.4 Mean Credit Score Card

#### Giá trị hiện tại
```dax
Mean Credit Score (Latest) =
CALCULATE(
    MAX(monitoring_summary[mean_score_actual]),
    monitoring_summary[snapshot_month] = CALCULATE(MAX(monitoring_summary[snapshot_month]))
)
```

#### Tháng trước
```dax
Mean Credit Score (Prior Month) =
VAR _Latest = CALCULATE(MAX(monitoring_summary[snapshot_month]))
VAR _PriorMonth = EDATE(_Latest, -1)
RETURN
    CALCULATE(
        MAX(monitoring_summary[mean_score_actual]),
        monitoring_summary[snapshot_month] = _PriorMonth
    )
```

#### Delta
```dax
Mean Score Delta =
    [Mean Credit Score (Latest)] - [Mean Credit Score (Prior Month)]
```

#### Delta Label
```dax
Mean Score Delta Label =
VAR _Delta = [Mean Score Delta]
RETURN
    IF(
        ISBLANK(_Delta), "N/A",
        IF(_Delta > 0,
            "▲ " & FORMAT(ABS(_Delta), "0.0") & " pts",
            IF(_Delta < 0,
                "▼ " & FORMAT(ABS(_Delta), "0.0") & " pts",
                "— 0.0 pts"
            )
        )
    )
```

#### Color Code (điểm giảm = xấu)
```dax
Mean Score Color Code =
VAR _Delta = [Mean Score Delta]
RETURN
    IF(_Delta < -5, 3, IF(_Delta < 0, 2, 1))
```

---

## 5. Measures — PSI Trend Chart (Left Top)

> **Visual**: Line Chart — trục X: `snapshot_month` · trục Y: PSI Score  
> Nguồn: bảng `psi_results` (SQL Query #4)

### 5.1 PSI Score (trend line)

Dùng trực tiếp cột `psi_results[psi_score]` làm Values.  
Thêm measure sau để tô màu điểm theo severity:

```dax
PSI Point Color =
VAR _v = MAX(psi_results[psi_score])
RETURN
    IF(_v >= 0.25, "#A32D2D", IF(_v >= 0.10, "#BA7517", "#1D9E75"))
```

### 5.2 Threshold Lines (đường tham chiếu ngang)

Dùng cột `threshold_monitor` và `threshold_retrain` từ SQL Query #4 làm hai dòng riêng.  
Hoặc tạo constant measures:

```dax
PSI Threshold Amber = 0.10
```

```dax
PSI Threshold Red = 0.25
```

> Trong Power BI: Add these as separate series → format dashed line, color `#BA7517` và `#A32D2D`.

### 5.3 PSI Status Label (tooltip)

```dax
PSI Status Label =
VAR _v = MAX(psi_results[psi_score])
RETURN
    IF(_v >= 0.25, "High Drift — Retrain",
        IF(_v >= 0.10, "Moderate Drift — Monitor",
            "Stable"))
```

---

## 6. Measures — Combo Chart Default Rate + Mean Score (Left Bottom)

> **Visual**: Clustered Bar + Line Chart — Dual Y-Axis  
> Trục X: `snapshot_month` · Bar: Default Rate % · Line: Mean Credit Score  
> Nguồn: bảng `monitoring_summary`

### 6.1 Default Rate % (Bar)

Dùng trực tiếp cột `monitoring_summary[default_rate_pct]`.

Hoặc measure tường minh:

```dax
Default Rate % =
    AVERAGE(monitoring_summary[default_rate_pct])
```

### 6.2 Default Rate Baseline (Bar tham chiếu)

```dax
Default Rate Baseline % =
    AVERAGE(monitoring_summary[default_rate_baseline_pct])
```

### 6.3 Mean Score Actual (Line — trục Y phải)

```dax
Mean Score Actual =
    AVERAGE(monitoring_summary[mean_score_actual])
```

### 6.4 Mean Score Baseline (Line tham chiếu)

```dax
Mean Score Baseline =
    AVERAGE(monitoring_summary[mean_score_baseline])
```

### 6.5 Score Shift (tooltip)

```dax
Score Shift =
    AVERAGE(monitoring_summary[score_shift_pts])
```

---

## 7. Measures — Max CSI Trend Chart (Right Top)

> **Visual**: Line Chart — Data points tô màu theo severity  
> Trục X: `snapshot_month` · Trục Y: Max CSI Score  
> Nguồn: bảng `csi_results`

### 7.1 Max CSI per Month (trend line)

```dax
Max CSI per Month =
    CALCULATE(
        MAX(csi_results[csi_score])
    )
```

### 7.2 CSI Threshold Lines

```dax
CSI Threshold Amber = 0.10
```

```dax
CSI Threshold Red = 0.25
```

### 7.3 Max CSI Color (cho data label / tooltip color)

```dax
Max CSI Color =
VAR _v = [Max CSI per Month]
RETURN
    IF(_v >= 0.25, "#A32D2D", IF(_v >= 0.10, "#BA7517", "#1D9E75"))
```

### 7.4 Number of Features in Drift (tooltip phụ)

```dax
Features in Drift (Month) =
    CALCULATE(
        COUNTROWS(csi_results),
        csi_results[csi_status] = "High_Drift"
    )
```

```dax
Features in Monitor (Month) =
    CALCULATE(
        COUNTROWS(csi_results),
        csi_results[csi_status] = "Moderate_Drift"
    )
```

---

## 8. Measures — CSI Feature Ranking (Right Bottom)

> **Visual**: Horizontal Bar Chart — 17 features (hoặc toàn bộ feature có dữ liệu)  
> Lọc theo tháng mới nhất · Sort descending · Màu bar theo threshold  
> Nguồn: bảng `csi_results`

### 8.1 Lọc tháng mới nhất

Áp dụng filter ở **Visual Filters**: `csi_results[snapshot_month]` = `MAX(csi_results[snapshot_month])`  
Hoặc dùng measure:

```dax
CSI Latest Month =
    CALCULATE(
        MAX(csi_results[csi_score]),
        csi_results[snapshot_month] = CALCULATE(MAX(csi_results[snapshot_month]))
    )
```

### 8.2 CSI Feature Score (Value cho Bar Chart)

```dax
CSI Feature Score =
    MAX(csi_results[csi_score])
```

### 8.3 CSI Feature Status (cho color conditional formatting)

```dax
CSI Feature Status Code =
VAR _v = [CSI Feature Score]
RETURN
    IF(_v >= 0.25, 3, IF(_v >= 0.10, 2, 1))
```

### 8.4 CSI Feature Label (hiển thị giá trị + status)

```dax
CSI Feature Label =
VAR _v = [CSI Feature Score]
VAR _status =
    IF(_v >= 0.25, "High Drift",
        IF(_v >= 0.10, "Moderate",
            "Stable"))
RETURN
    FORMAT(_v, "0.0000") & "  (" & _status & ")"
```

### 8.5 Sort: CSI Score Rank

```dax
CSI Feature Rank =
    RANKX(
        ALLSELECTED(csi_results[feature_name]),
        [CSI Feature Score],
        ,
        DESC,
        Dense
    )
```

---

## 9. Measures — Bottom Alert Banner

> **Visual**: Text Card hoặc Custom Visual (ví dụ: HTML Content)  
> Hiển thị có điều kiện khi có breach · Background color theo severity

### 9.1 Alert Visibility Flag

```dax
Alert Is Visible =
VAR _PSI = [PSI Score (Latest)]
VAR _CSI = [Max CSI (Latest)]
RETURN
    IF(_PSI >= 0.10 || _CSI >= 0.10, 1, 0)
```

> Dùng measure này trong **Page-level filter** của banner: `Alert Is Visible = 1`  
> Hoặc dùng Bookmark + Button để toggle.

### 9.2 Alert Severity Level

```dax
Alert Severity =
VAR _PSI = [PSI Score (Latest)]
VAR _CSI = [Max CSI (Latest)]
RETURN
    IF(_PSI >= 0.25 || _CSI >= 0.25, 3,    -- Critical / Red
        IF(_PSI >= 0.10 || _CSI >= 0.10, 2, -- Warning / Amber
            0))                              -- No alert
```

### 9.3 Alert Background Color

```dax
Alert BG Color =
VAR _level = [Alert Severity]
RETURN
    SWITCH(
        _level,
        3, "#A32D2D",
        2, "#BA7517",
        "#1D9E75"
    )
```

### 9.4 Alert Message Text

```dax
Alert Message =
VAR _PSI = [PSI Score (Latest)]
VAR _CSI = [Max CSI (Latest)]
VAR _PSIStatus =
    IF(_PSI >= 0.25, "⚠ PSI = " & FORMAT(_PSI, "0.0000") & " — HIGH DRIFT (≥ 0.25)",
        IF(_PSI >= 0.10, "⚠ PSI = " & FORMAT(_PSI, "0.0000") & " — MODERATE DRIFT (≥ 0.10)", ""))
VAR _CSIStatus =
    IF(_CSI >= 0.25, "⚠ Max CSI = " & FORMAT(_CSI, "0.0000") & " — HIGH DRIFT (≥ 0.25)",
        IF(_CSI >= 0.10, "⚠ Max CSI = " & FORMAT(_CSI, "0.0000") & " — MODERATE DRIFT (≥ 0.10)", ""))
VAR _separator =
    IF(_PSIStatus <> "" && _CSIStatus <> "", "  |  ", "")
RETURN
    IF(
        _PSIStatus = "" && _CSIStatus = "",
        "✅ All metrics within acceptable thresholds",
        _PSIStatus & _separator & _CSIStatus
    )
```

### 9.5 Affected Features List

```dax
Affected Features =
VAR _LatestMonth = CALCULATE(MAX(csi_results[snapshot_month]))
VAR _DriftFeatures =
    CALCULATETABLE(
        VALUES(csi_results[feature_name]),
        csi_results[snapshot_month] = _LatestMonth,
        csi_results[csi_status] IN {"High_Drift", "Moderate_Drift"}
    )
RETURN
    IF(
        COUNTROWS(_DriftFeatures) = 0,
        "No features in drift",
        "Affected features: " &
        CONCATENATEX(
            _DriftFeatures,
            csi_results[feature_name],
            ", "
        )
    )
```

---

## 10. Conditional Formatting Rules

Áp dụng trong **Format → Conditional Formatting → Background color / Font color** của từng visual.

### Bảng quy tắc màu theo Status Code

| Status Code | Màu | Hex | Áp dụng cho |
|---|---|---|---|
| `1` (Stable) | Green | `#1D9E75` | KPI cards, bars, badges |
| `2` (Monitor) | Amber | `#BA7517` | KPI cards, bars, badges |
| `3` (Retrain/Drift) | Red | `#A32D2D` | KPI cards, bars, badges |
| N/A | Navy | `#1B3A6B` | Background mặc định |

### 10.1 Conditional Formatting — KPI Card background

Với mỗi KPI card, vào **Format → Background → Conditional formatting**:
- **Field**: chọn measure `PSI Color Code` / `CSI Color Code` / `Default Rate Color Code` / `Mean Score Color Code`
- **Rules**:
  - `= 1` → `#1D9E75`
  - `= 2` → `#BA7517`
  - `= 3` → `#A32D2D`

### 10.2 Conditional Formatting — CSI Horizontal Bar Chart

Vào **Format → Data colors → Conditional formatting** của bar chart:
- **Field**: `CSI Feature Status Code`
- Rules như trên

### 10.3 Overall Status Badge — Text color

```dax
Status Badge Color =
SWITCH(
    [Overall Status Code],
    1, "#1D9E75",
    2, "#BA7517",
    3, "#A32D2D",
    "#1B3A6B"
)
```

---

## 11. Hướng dẫn tổ chức Measure Groups

Để dễ quản lý trong Power BI, tạo các **Display Folders** (nhóm measure) như sau:

```
📁 _KPI
   ├── PSI Score (Latest)
   ├── PSI Score (Prior Month)
   ├── PSI Delta
   ├── PSI Delta Label
   ├── PSI Color Code
   ├── Max CSI (Latest)
   ├── Max CSI (Prior Month)
   ├── CSI Delta
   ├── CSI Delta Label
   ├── CSI Color Code
   ├── Default Rate (Latest)
   ├── Default Rate (Prior Month)
   ├── Default Rate Delta
   ├── Default Rate Delta Label
   ├── Default Rate Color Code
   ├── Mean Credit Score (Latest)
   ├── Mean Credit Score (Prior Month)
   ├── Mean Score Delta
   ├── Mean Score Delta Label
   └── Mean Score Color Code

📁 _Charts
   ├── PSI Threshold Amber
   ├── PSI Threshold Red
   ├── PSI Status Label
   ├── PSI Point Color
   ├── CSI Threshold Amber
   ├── CSI Threshold Red
   ├── Max CSI per Month
   ├── Max CSI Color
   ├── Features in Drift (Month)
   ├── Features in Monitor (Month)
   ├── Default Rate %
   ├── Default Rate Baseline %
   ├── Mean Score Actual
   ├── Mean Score Baseline
   └── Score Shift

📁 _CSI Ranking
   ├── CSI Latest Month
   ├── CSI Feature Score
   ├── CSI Feature Status Code
   ├── CSI Feature Label
   └── CSI Feature Rank

📁 _Alert
   ├── Alert Is Visible
   ├── Alert Severity
   ├── Alert BG Color
   ├── Alert Message
   └── Affected Features

📁 _TopBar
   ├── Last Refresh
   ├── Overall Status
   ├── Overall Status Code
   └── Status Badge Color
```

---

## Checklist tạo Dashboard

- [ ] Load 4 bảng từ BigQuery DirectQuery
- [ ] Set kiểu `Date` cho cột `snapshot_month` ở cả 3 bảng
- [ ] Tạo quan hệ `monitoring_summary ↔ psi_results` và `monitoring_summary ↔ csi_results` qua `snapshot_month`
- [ ] Tạo toàn bộ measures theo hướng dẫn trên và phân vào Display Folders
- [ ] **Top Bar**: 3 Text Cards — Logo | Title | `[Last Refresh]` + `[Overall Status]`
- [ ] **KPI Row**: 4 Cards — Value = measure `(Latest)`, Secondary = Delta Label, CF = Color Code
- [ ] **PSI Trend**: Line Chart — X: `snapshot_month`, Y: `psi_score` + 2 constant lines
- [ ] **Combo Chart**: Bật Dual Y-Axis — Bar = `[Default Rate %]`, Line = `[Mean Score Actual]`
- [ ] **Max CSI Trend**: Line Chart — Y: `[Max CSI per Month]` + 2 constant lines, CF data points
- [ ] **CSI Feature Ranking**: Horizontal Bar — Values: `[CSI Feature Score]`, Axis: `feature_name`, CF bars
- [ ] **Alert Banner**: Text Card — Value: `[Alert Message]`, Filter: `Alert Is Visible = 1`, BG CF: `Alert BG Color`
- [ ] Set font toàn bộ report: **Inter** hoặc **DM Sans**, size 10–14
- [ ] Set màu nền canvas: `#1B3A6B`, màu card: `#F8F9FA`
- [ ] Kiểm tra toàn bộ Conditional Formatting rules

---

*Tài liệu này được tạo tự động phục vụ dự án NovaPay Credit Model Monitoring.*  
*Cập nhật: 2026-06-02*
