# Vehicle Telemetry

Python project for normalizing Subaru FA20DIT telemetry logs and generating a longitudinal engine health report.

## What It Does

- Reads raw CSV logs from `data/raw/`
- Detects `Cobb Accessport` and `OBD Fusion` log formats
- Normalizes both formats into a shared schema
- Computes derived features such as `dt_s`, `load_proxy`, `air_mass_g`, and drive state
- Classifies each session as `cruising` or `racing`
- Buckets logs by:
  - `cobb / cruising`
  - `cobb / racing`
  - `obd / cruising`
  - `obd / racing`
- Builds a baseline-aware report for the latest log in each bucket
- Writes report artifacts to `outputs/`

## Repo Layout

```text
src/vehicle_telemetry/     Core parsing, normalization, features, plotting, and reporting modules
notebooks/                 Interactive notebooks, including the main telemetry report
scripts/                   Small runners for executing notebooks and report generation
data/raw/                  Drop raw CSV logs here (git-ignored)
data/events.csv            Optional event log used for tune/mod/maintenance context
outputs/                   Generated report artifacts (git-ignored)
```

## Supported Inputs

### Cobb Accessport
Primary full-detail mode. Supports DAM, FBK, FKL, boost, trims, and thermal metrics when present.

### OBD Fusion
Reduced-detail mode. Supports airflow, MAP, trims, speed, and thermal metrics when present. It does not fabricate DAM/FBK/FKL analysis.

## Quick Start

### 1. Create an environment and install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

### 2. Add logs

Drop raw `.csv` files into:

```text
data/raw/
```

Optional: add timeline events to:

```text
data/events.csv
```

Expected columns:

```text
date,event_type,event,notes
```

Supported `event_type` values:
- `mod`
- `maintenance`
- `tune`
- `reset`
- `fuel`
- `driving`

### 3. Run the report notebook

Open and run:

```text
notebooks/FA20DIT_Engine_Health_Analysis.ipynb
```

Or execute the saved report runner:

```powershell
python scripts/run_telemetry_report.py
```

## Outputs

Running the telemetry report produces:

- `outputs/log_summary.csv`
- `outputs/latest_report.md`
- `outputs/latest_report.html`
- `outputs/latest_report.ipynb`

## Current Report Design

The report is organized around four main views:

1. `Summary`
2. `Cobb Data`
3. `OBD Data`
4. `Metadata`

The summary is anomaly-first and is designed to float up things worth investigating rather than simply labeling high-load driving as dangerous.

## Longitudinal Baselines

For the latest log in each bucket, the baseline is selected from:

- prior logs only
- same `log_type`
- same `session_type`
- same era after the latest major boundary event (`mod`, `tune`, `reset`)
- within the last 45 days when possible
- up to the 6 most recent matching prior logs

If fewer than 3 baseline logs are available, the report marks baseline confidence as limited.

## Notes On Timestamps

Canonical log datetime is chosen using this priority:

1. in-file timestamp when available
2. filename timestamp when available
3. file modified time fallback

That means OBD logs can usually use embedded session timestamps, while some Cobb logs may fall back to filename or filesystem metadata.

## Development Notes

- Keep code simple, explicit, and easy to inspect
- Missing columns should degrade gracefully
- Most report logic lives in `src/vehicle_telemetry/longitudinal.py` and `notebooks/FA20DIT_Engine_Health_Analysis.ipynb`

## Next Steps

This repo is at a solid v1. Likely future improvements would be:

- configurable manual overrides for session classification and timestamps
- baseline-aware narrative interpretations
- additional FA20DIT-specific calibration as more logs accumulate
- packaging the notebook flow into a small CLI
