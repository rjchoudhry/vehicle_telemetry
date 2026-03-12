from __future__ import annotations

import numpy as np
import pandas as pd

KPH_TO_MPH = 0.621371192237334


def _safe_stat(series: pd.Series, fn, default=np.nan):
    clean = pd.to_numeric(series, errors="coerce") if series is not None else pd.Series(dtype=float)
    clean = clean.dropna()
    if clean.empty:
        return default
    return float(fn(clean))


def _max_consecutive_true(mask: pd.Series) -> int:
    arr = pd.Series(mask).fillna(False).astype(bool).to_numpy()
    best = 0
    run = 0
    for v in arr:
        if v:
            run += 1
            if run > best:
                best = run
        else:
            run = 0
    return int(best)


def build_summary(df: pd.DataFrame) -> dict[str, float]:
    speed_mph = df.get("speed_mph")
    if speed_mph is None:
        speed_kph = pd.to_numeric(df.get("speed_kph", np.nan), errors="coerce")
        speed_mph = speed_kph * KPH_TO_MPH

    throttle = pd.to_numeric(df.get("throttle_pct", np.nan), errors="coerce")
    rpm = pd.to_numeric(df.get("rpm", np.nan), errors="coerce")
    state = df.get("state")
    accel = pd.Series(False, index=df.index) if state is None else state.astype(str).str.lower().eq("accel")

    high_load_boost = (throttle > 60.0) & (rpm > 2500.0)
    boost_error_hl = pd.to_numeric(df.get("boost_error_kpa", np.nan), errors="coerce").where(high_load_boost)

    knock_eval_load = ((throttle > 25.0) & (rpm > 2000.0)) | accel
    fbk = pd.to_numeric(df.get("fbk", np.nan), errors="coerce")
    fkl = pd.to_numeric(df.get("fkl", np.nan), errors="coerce")
    meaningful_knock = knock_eval_load & ((fbk <= -2.0) | (fkl <= -2.0))

    summary = {
        "duration_s": _safe_stat(df.get("time_s"), lambda s: s.max() - s.min(), 0.0),
        "avg_rpm": _safe_stat(df.get("rpm"), np.mean),
        "avg_speed_mph": _safe_stat(speed_mph, np.mean),
        "avg_load_proxy": _safe_stat(df.get("load_proxy"), np.mean),
        "stft_mean_pct": _safe_stat(df.get("stft_pct"), np.mean),
        "ltft_mean_pct": _safe_stat(df.get("ltft_pct"), np.mean),
        "coolant_max_c": _safe_stat(df.get("coolant_c"), np.max),
        "iat_max_c": _safe_stat(df.get("iat_c"), np.max),
        "dam_min": _safe_stat(df.get("dam"), np.min),
        "fbk_min": _safe_stat(df.get("fbk"), np.min),
        "fkl_min": _safe_stat(df.get("fkl"), np.min),
        "meaningful_knock_samples_under_load": float(pd.Series(meaningful_knock).fillna(False).sum()),
        "meaningful_knock_max_consecutive_under_load": float(_max_consecutive_true(meaningful_knock)),
        "boost_error_abs_p95_kpa_high_load": _safe_stat(boost_error_hl, lambda s: np.percentile(np.abs(s), 95)),
    }
    return summary


def build_flags(summary: dict[str, float]) -> dict[str, bool]:
    def has(v: float) -> bool:
        return np.isfinite(v)

    stft = summary.get("stft_mean_pct", np.nan)
    ltft = summary.get("ltft_mean_pct", np.nan)
    knock_count = summary.get("meaningful_knock_samples_under_load", np.nan)
    knock_run = summary.get("meaningful_knock_max_consecutive_under_load", np.nan)

    flags = {
        "fuel_trim_bias": (has(stft) and abs(stft) > 10.0) or (has(ltft) and abs(ltft) > 8.0),
        "active_knock": (has(knock_count) and knock_count > 1.0) or (has(knock_run) and knock_run > 1.0),
        "historical_knock": has(summary.get("dam_min", np.nan)) and summary["dam_min"] < 1.0,
        "high_coolant": has(summary.get("coolant_max_c", np.nan)) and summary["coolant_max_c"] > 105.0,
        "high_iat": has(summary.get("iat_max_c", np.nan)) and summary["iat_max_c"] > 55.0,
        "boost_control_variance": has(summary.get("boost_error_abs_p95_kpa_high_load", np.nan))
        and summary["boost_error_abs_p95_kpa_high_load"] > 20.0,
    }
    return flags
