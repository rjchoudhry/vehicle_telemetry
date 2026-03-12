from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import html
import re
from typing import Any

import numpy as np
import pandas as pd

from .features import add_derived_features
from .io import ENCODING_FALLBACKS, read_log_csv
from .normalize import normalize_log

MAJOR_EVENT_TYPES = {"mod", "tune", "reset"}
SUPPORTED_EVENT_TYPES = {"mod", "maintenance", "tune", "reset", "fuel", "driving"}
BUCKETS = [("cobb", "cruising"), ("cobb", "racing"), ("obd", "cruising"), ("obd", "racing")]

COBB_METRICS = [
    "duration_s",
    "min_dam",
    "final_dam",
    "min_fbk",
    "min_fkl",
    "meaningful_fbk_count",
    "meaningful_fkl_count",
    "max_load_proxy",
    "p95_load_proxy",
    "max_maf",
    "p95_maf",
    "max_map_kpa",
    "total_air_mass_g",
    "max_iat_c",
    "max_coolant_c",
    "mean_ltft_pct",
    "mean_stft_pct",
    "high_load_time_s",
    "high_load_pct",
]

OBD_METRICS = [
    "duration_s",
    "max_load_proxy",
    "p95_load_proxy",
    "max_maf",
    "p95_maf",
    "max_map_kpa",
    "total_air_mass_g",
    "max_iat_c",
    "max_coolant_c",
    "mean_ltft_pct",
    "mean_stft_pct",
    "high_load_time_s",
    "high_load_pct",
]


@dataclass
class LogResult:
    summary: dict[str, Any]
    frame: pd.DataFrame


def _safe_float(value: Any) -> float:
    try:
        if value is None:
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def _read_first_lines_with_fallback(path: Path, n: int = 3) -> list[str]:
    for enc in ENCODING_FALLBACKS:
        try:
            with path.open("r", encoding=enc) as f:
                return [f.readline().strip() for _ in range(n)]
        except UnicodeDecodeError:
            continue
    with path.open("r", encoding="latin-1", errors="ignore") as f:
        return [f.readline().strip() for _ in range(n)]


def _parse_obd_start_time(line: str) -> datetime | None:
    m = re.search(r"StartTime\s*=\s*(.+)$", line)
    if not m:
        return None
    raw = m.group(1).strip()
    for fmt in ["%m/%d/%Y %I:%M:%S.%f %p", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S"]:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _parse_datetime_from_filename(name: str) -> datetime | None:
    patterns = [
        (r"(20\d{2})(\d{2})(\d{2})[_-]?(\d{2})(\d{2})(\d{2})", "%Y%m%d%H%M%S"),
        (r"(20\d{2})[-_](\d{2})[-_](\d{2})[-_ ](\d{2})[-_](\d{2})[-_](\d{2})", "%Y%m%d%H%M%S"),
    ]
    for pattern, fmt in patterns:
        m = re.search(pattern, name)
        if m:
            raw = "".join(m.groups())
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                pass

    m = re.search(r"(\d{1,2})[ _-](\d{1,2})[ _-](\d{2,4})", name)
    if m:
        mm, dd, yy = m.groups()
        year = int(yy)
        if year < 100:
            year += 2000
        try:
            return datetime(year, int(mm), int(dd), 12, 0, 0)
        except ValueError:
            return None
    return None


def canonical_log_datetime(path: Path, log_type: str) -> tuple[datetime, str]:
    lines = _read_first_lines_with_fallback(path, n=2)
    if log_type == "obd_fusion" and lines:
        dt = _parse_obd_start_time(lines[0])
        if dt is not None:
            return dt, "content"

    dt_name = _parse_datetime_from_filename(path.name)
    if dt_name is not None:
        return dt_name, "filename"

    return datetime.fromtimestamp(path.stat().st_mtime), "mtime"


def load_events(events_path: str | Path) -> pd.DataFrame:
    path = Path(events_path)
    if not path.exists():
        return pd.DataFrame(columns=["date", "event_type", "event", "notes"])

    df = pd.read_csv(path)
    for col in ["date", "event_type", "event", "notes"]:
        if col not in df.columns:
            df[col] = np.nan

    df = df[["date", "event_type", "event", "notes"]].copy()
    df["event_type"] = df["event_type"].astype(str).str.strip().str.lower()
    df = df[df["event_type"].isin(SUPPORTED_EVENT_TYPES)].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def discover_logs(raw_dir: str | Path) -> list[Path]:
    path = Path(raw_dir)
    if not path.exists():
        return []
    return sorted(path.glob("*.csv"))


def _duration_seconds(frame: pd.DataFrame) -> float:
    t = pd.to_numeric(frame.get("time_s", np.nan), errors="coerce")
    t = t.dropna()
    if t.empty:
        dt = pd.to_numeric(frame.get("dt_s", np.nan), errors="coerce").fillna(0.0)
        return float(dt.sum())
    return float(t.max() - t.min())


def _count_true_runs(mask: pd.Series) -> int:
    vals = mask.fillna(False).astype(bool).to_numpy()
    count = 0
    prev = False
    for v in vals:
        if v and not prev:
            count += 1
        prev = bool(v)
    return count


def classify_session(frame: pd.DataFrame) -> str:
    load = pd.to_numeric(frame.get("load_proxy", np.nan), errors="coerce")
    max_load = _safe_float(load.max())
    p95 = _safe_float(load.quantile(0.95)) if load.notna().any() else np.nan
    high = load > p95 if np.isfinite(p95) else pd.Series(False, index=frame.index)
    high_pct = _safe_float(high.mean() * 100.0) if len(high) else 0.0
    repeated = _count_true_runs(high)

    # Keep session tagging conservative so ordinary spirited driving does not become "racing".
    if np.isfinite(max_load) and max_load >= 90.0:
        return "racing"
    if np.isfinite(high_pct) and high_pct >= 20.0 and np.isfinite(max_load) and max_load >= 60.0:
        return "racing"
    if repeated >= 6 and np.isfinite(max_load) and max_load >= 50.0:
        return "racing"
    return "cruising"


def _recent_event_context(events: pd.DataFrame, dt: datetime, days: int = 30, max_items: int = 3) -> str:
    if events.empty:
        return ""
    start = dt - timedelta(days=days)
    recent = events[(events["date"] <= dt) & (events["date"] >= start)].tail(max_items)
    if recent.empty:
        return ""
    parts = []
    for _, row in recent.iterrows():
        d = row["date"].strftime("%Y-%m-%d")
        parts.append(f"{d}:{row['event_type']}:{row['event']}")
    return " | ".join(parts)


def summarize_log(path: Path, events: pd.DataFrame) -> LogResult:
    raw_df, raw_type = read_log_csv(path)
    log_type = "cobb" if raw_type == "cobb_accessport" else "obd"
    norm = normalize_log(raw_df, raw_type)
    feat = add_derived_features(norm)

    dt_s = pd.to_numeric(feat.get("dt_s", np.nan), errors="coerce").fillna(0.0)
    load = pd.to_numeric(feat.get("load_proxy", np.nan), errors="coerce")
    maf = pd.to_numeric(feat.get("maf_gps", np.nan), errors="coerce")
    map_kpa = pd.to_numeric(feat.get("map_kpa", np.nan), errors="coerce")
    iat = pd.to_numeric(feat.get("iat_c", np.nan), errors="coerce")
    coolant = pd.to_numeric(feat.get("coolant_c", np.nan), errors="coerce")
    stft = pd.to_numeric(feat.get("stft_pct", np.nan), errors="coerce")
    ltft = pd.to_numeric(feat.get("ltft_pct", np.nan), errors="coerce")

    p95_load = _safe_float(load.quantile(0.95)) if load.notna().any() else np.nan
    high_load = load > p95_load if np.isfinite(p95_load) else pd.Series(False, index=feat.index)
    high_load_time_s = float(dt_s.where(high_load, 0.0).sum())
    total_time_s = float(dt_s.sum())

    dt_canonical, dt_source = canonical_log_datetime(path, raw_type)

    summary: dict[str, Any] = {
        "log_id": f"{path.stem}_{dt_canonical.strftime('%Y%m%d%H%M%S')}",
        "filename": path.name,
        "log_datetime": dt_canonical,
        "log_datetime_source": dt_source,
        "log_type": log_type,
        "session_type": classify_session(feat),
        "duration_s": _duration_seconds(feat),
        "max_load_proxy": _safe_float(load.max()),
        "p95_load_proxy": p95_load,
        "max_maf": _safe_float(maf.max()),
        "p95_maf": _safe_float(maf.quantile(0.95)) if maf.notna().any() else np.nan,
        "max_map_kpa": _safe_float(map_kpa.max()),
        "total_air_mass_g": _safe_float((maf * dt_s).sum()),
        "max_iat_c": _safe_float(iat.max()),
        "max_coolant_c": _safe_float(coolant.max()),
        "mean_ltft_pct": _safe_float(ltft.mean()),
        "mean_stft_pct": _safe_float(stft.mean()),
        "high_load_time_s": high_load_time_s,
        "high_load_pct": _safe_float(high_load_time_s / total_time_s * 100.0) if total_time_s > 0 else np.nan,
        "recent_event_context": _recent_event_context(events, dt_canonical),
    }

    if log_type == "cobb":
        dam = pd.to_numeric(feat.get("dam", np.nan), errors="coerce")
        fbk = pd.to_numeric(feat.get("fbk", np.nan), errors="coerce")
        fkl = pd.to_numeric(feat.get("fkl", np.nan), errors="coerce")
        summary.update(
            {
                "min_dam": _safe_float(dam.min()),
                "final_dam": _safe_float(dam.dropna().iloc[-1]) if dam.dropna().any() else np.nan,
                "min_fbk": _safe_float(fbk.min()),
                "min_fkl": _safe_float(fkl.min()),
                "meaningful_fbk_count": int((fbk <= -2.0).sum()),
                "meaningful_fkl_count": int((fkl <= -1.4).sum()),
            }
        )

    return LogResult(summary=summary, frame=feat)


def summarize_all_logs(raw_dir: str | Path, events: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for path in discover_logs(raw_dir):
        result = summarize_log(path, events)
        rows.append(result.summary)
        frames[result.summary["log_id"]] = result.frame

    if not rows:
        return pd.DataFrame(), {}

    summary = pd.DataFrame(rows).sort_values("log_datetime").reset_index(drop=True)
    summary = assign_eras(summary, events)
    return summary, frames


def assign_eras(summary: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    out = summary.copy()
    major = events[events["event_type"].isin(MAJOR_EVENT_TYPES)].copy()
    major_dates = list(major["date"].sort_values())

    era_ids = []
    for dt in out["log_datetime"]:
        count = sum(1 for md in major_dates if md <= dt)
        era_ids.append(f"era_{count}")
    out["era_id"] = era_ids
    return out


def latest_by_bucket(summary: pd.DataFrame) -> dict[tuple[str, str], pd.Series | None]:
    latest: dict[tuple[str, str], pd.Series | None] = {}
    for log_type, session_type in BUCKETS:
        s = summary[(summary["log_type"] == log_type) & (summary["session_type"] == session_type)]
        latest[(log_type, session_type)] = s.sort_values("log_datetime").iloc[-1] if not s.empty else None
    return latest


def select_baseline(summary: pd.DataFrame, latest_row: pd.Series | None) -> pd.DataFrame:
    if latest_row is None:
        return pd.DataFrame()

    cands = summary[
        (summary["log_type"] == latest_row["log_type"])
        & (summary["session_type"] == latest_row["session_type"])
        & (summary["log_datetime"] < latest_row["log_datetime"])
        & (summary["era_id"] == latest_row["era_id"])
    ].copy()

    if cands.empty:
        return cands

    window_start = latest_row["log_datetime"] - timedelta(days=45)
    within_45 = cands[cands["log_datetime"] >= window_start]
    filtered = within_45 if not within_45.empty else cands
    return filtered.sort_values("log_datetime").tail(6)


def baseline_comparison(latest_row: pd.Series | None, baseline: pd.DataFrame) -> pd.DataFrame:
    if latest_row is None:
        return pd.DataFrame(columns=["metric", "latest_value", "baseline_median", "delta"])

    metrics = COBB_METRICS if latest_row["log_type"] == "cobb" else OBD_METRICS
    rows = []
    for metric in metrics:
        latest_val = _safe_float(latest_row.get(metric, np.nan))
        base_med = _safe_float(baseline[metric].median()) if (not baseline.empty and metric in baseline.columns) else np.nan
        delta = latest_val - base_med if np.isfinite(latest_val) and np.isfinite(base_med) else np.nan
        rows.append(
            {
                "metric": metric,
                "latest_value": latest_val,
                "baseline_median": base_med,
                "delta": delta,
            }
        )
    return pd.DataFrame(rows)


def bucket_recent_events(events: pd.DataFrame, latest_row: pd.Series | None) -> pd.DataFrame:
    if latest_row is None or events.empty:
        return pd.DataFrame(columns=events.columns)
    dt = latest_row["log_datetime"]
    start = dt - timedelta(days=60)
    return events[(events["date"] <= dt) & (events["date"] >= start)].sort_values("date").tail(8)


def _fmt_df(df: pd.DataFrame) -> str:
    if df.empty:
        return "(none)"
    return "```\n" + df.to_string(index=False) + "\n```"


def _interpret_bucket(latest_row: pd.Series, comp: pd.DataFrame) -> str:
    pieces = []
    if "high_load_pct" in latest_row and np.isfinite(_safe_float(latest_row.get("high_load_pct"))):
        hl = _safe_float(latest_row["high_load_pct"])
        if hl < 5:
            pieces.append("Drive profile appears light-load.")
        elif hl < 15:
            pieces.append("Drive profile appears moderate-load.")
        else:
            pieces.append("Drive profile includes sustained high-load operation.")

    if latest_row["log_type"] == "cobb":
        min_dam = _safe_float(latest_row.get("min_dam"))
        if np.isfinite(min_dam):
            pieces.append("DAM stayed below 1.0 at points." if min_dam < 1.0 else "DAM remained at full confidence.")

    return " ".join(pieces) if pieces else "No clear interpretation available due to missing data."


def generate_report_markdown(
    summary: pd.DataFrame,
    latest_map: dict[tuple[str, str], pd.Series | None],
    baseline_map: dict[tuple[str, str], pd.DataFrame],
    events: pd.DataFrame,
) -> str:
    lines: list[str] = []
    lines.append("# Vehicle Telemetry Longitudinal Report (v1)")
    lines.append("")
    lines.append("## TLDR Summary")
    lines.append(f"- Total logs analyzed: {len(summary)}")
    if not summary.empty:
        lines.append(f"- Time span: {summary['log_datetime'].min()} -> {summary['log_datetime'].max()}")
    lines.append("- Buckets analyzed independently: cobb/obd x cruising/racing")
    lines.append("")

    lines.append("## A. Cobb Metrics")
    for session in ["cruising", "racing"]:
        bucket = ("cobb", session)
        lines.extend(_bucket_section(bucket, latest_map.get(bucket), baseline_map.get(bucket, pd.DataFrame()), events))

    lines.append("## B. OBD Metrics")
    for session in ["cruising", "racing"]:
        bucket = ("obd", session)
        lines.extend(_bucket_section(bucket, latest_map.get(bucket), baseline_map.get(bucket, pd.DataFrame()), events))

    lines.append("## Historical Trends")
    lines.append("")
    cobb = summary[summary["log_type"] == "cobb"].sort_values("log_datetime")
    if not cobb.empty:
        cols = [c for c in ["log_datetime", "min_dam", "min_fbk", "max_load_proxy", "max_iat_c"] if c in cobb.columns]
        lines.append("### Cobb")
        lines.append(_fmt_df(cobb[cols]))
        lines.append("")

    obd = summary[summary["log_type"] == "obd"].sort_values("log_datetime")
    if not obd.empty:
        cols = [c for c in ["log_datetime", "max_load_proxy", "max_iat_c", "mean_ltft_pct"] if c in obd.columns]
        lines.append("### OBD")
        lines.append(_fmt_df(obd[cols]))
        lines.append("")

    if not events.empty:
        lines.append("### Event Markers")
        lines.append(_fmt_df(events[["date", "event_type", "event", "notes"]]))
        lines.append("")

    return "\n".join(lines)


def _bucket_section(bucket: tuple[str, str], latest_row: pd.Series | None, baseline: pd.DataFrame, events: pd.DataFrame) -> list[str]:
    log_type, session = bucket
    lines: list[str] = []
    lines.append(f"### {log_type.upper()} / {session}")

    if latest_row is None:
        lines.append("- No logs available for this bucket.")
        lines.append("")
        return lines

    lines.append(f"- Latest log: `{latest_row['filename']}` ({latest_row['log_datetime']})")
    lines.append(f"- Era: `{latest_row['era_id']}`")
    lines.append("")

    recent_events = bucket_recent_events(events, latest_row)
    lines.append("Recent relevant events:")
    lines.append(_fmt_df(recent_events[["date", "event_type", "event", "notes"]]) if not recent_events.empty else "(none)")
    lines.append("")

    metric_cols = COBB_METRICS if log_type == "cobb" else OBD_METRICS
    row_df = pd.DataFrame([latest_row])[ [c for c in ["filename", "log_datetime", "session_type", *metric_cols] if c in latest_row.index] ]
    lines.append("Summary metrics:")
    lines.append(_fmt_df(row_df))
    lines.append("")

    comp = baseline_comparison(latest_row, baseline)
    lines.append("Baseline comparison:")
    lines.append(_fmt_df(comp))
    lines.append("")

    lines.append("Interpretation:")
    lines.append(_interpret_bucket(latest_row, comp))
    lines.append("")

    if len(baseline) < 3:
        lines.append("Baseline confidence: **limited** (fewer than 3 baseline logs).")
    else:
        lines.append("Baseline confidence: normal.")
    lines.append("")

    if log_type == "cobb":
        lines.append("Single-log focus: DAM, FBK, FKL, engine stress, knock context, thermal/trims.")
    else:
        lines.append("Single-log focus: engine stress, thermal, trims.")
    lines.append("")
    return lines


def write_outputs(summary: pd.DataFrame, report_md: str, output_dir: str | Path) -> dict[str, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_path = out_dir / "log_summary.csv"
    report_md_path = out_dir / "latest_report.md"
    report_html_path = out_dir / "latest_report.html"

    summary_out = summary.copy()
    if not summary_out.empty and pd.api.types.is_datetime64_any_dtype(summary_out["log_datetime"]):
        summary_out["log_datetime"] = summary_out["log_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
    summary_out.to_csv(summary_path, index=False)

    report_md_path.write_text(report_md, encoding="utf-8")
    report_html = f"<html><body><pre>{html.escape(report_md)}</pre></body></html>"
    report_html_path.write_text(report_html, encoding="utf-8")

    return {
        "log_summary_csv": summary_path,
        "latest_report_md": report_md_path,
        "latest_report_html": report_html_path,
    }
