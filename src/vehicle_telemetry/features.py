from __future__ import annotations

import numpy as np
import pandas as pd

KPH_TO_MPH = 0.621371192237334


def compute_dt(df: pd.DataFrame) -> pd.Series:
    """Compute sample period from time_s with robust fill for first/invalid rows."""
    t = pd.to_numeric(df.get("time_s", pd.Series(dtype=float)), errors="coerce")
    dt = t.diff()
    valid = dt[(dt > 0) & dt.notna()]
    fallback = float(valid.median()) if not valid.empty else 0.0
    dt = dt.where(dt > 0, np.nan).fillna(fallback)
    return dt


def compute_load_proxy(df: pd.DataFrame) -> pd.Series:
    """Simple engine load proxy for turbo Subaru logs: MAF/RPM*1000."""
    maf = pd.to_numeric(df.get("maf_gps", np.nan), errors="coerce")
    rpm = pd.to_numeric(df.get("rpm", np.nan), errors="coerce")
    return np.where((rpm > 0) & np.isfinite(rpm), maf / rpm * 1000.0, np.nan)


def segment_state(df: pd.DataFrame) -> pd.Series:
    """Segment drive state into idle, cruise, accel, or decel."""
    rpm = pd.to_numeric(df.get("rpm", np.nan), errors="coerce")
    throttle = pd.to_numeric(df.get("throttle_pct", np.nan), errors="coerce")

    speed_mph = df.get("speed_mph")
    if speed_mph is None:
        speed_mph = pd.to_numeric(df.get("speed_kph", np.nan), errors="coerce") * KPH_TO_MPH
    else:
        speed_mph = pd.to_numeric(speed_mph, errors="coerce")

    ds_mph = speed_mph.diff().fillna(0.0)
    dth = throttle.diff().fillna(0.0)

    idle = ((speed_mph <= 1.0) & (throttle <= 18) & (rpm <= 1500)) | (
        (speed_mph <= 0.5) & (throttle <= 25) & (rpm <= 1800)
    )
    accel = ((dth > 0.6) & (ds_mph > 0.05) & (throttle > 12)) | ((throttle > 40) & (ds_mph > 0.05))
    decel = (throttle < 10) & (ds_mph < -0.15) & (speed_mph > 3.0)

    state = np.full(len(df), "cruise", dtype=object)
    state[idle.fillna(False).to_numpy()] = "idle"
    state[decel.fillna(False).to_numpy()] = "decel"
    state[accel.fillna(False).to_numpy()] = "accel"
    return pd.Series(state, index=df.index, name="state")


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "speed_kph" in out.columns:
        out["speed_mph"] = pd.to_numeric(out["speed_kph"], errors="coerce") * KPH_TO_MPH
    else:
        out["speed_mph"] = np.nan
    out["dt_s"] = compute_dt(out)
    out["load_proxy"] = compute_load_proxy(out)
    if out.get("boost_error_kpa") is None or out["boost_error_kpa"].isna().all():
        if {"boost_target_kpa", "map_kpa"}.issubset(out.columns):
            out["boost_error_kpa"] = out["boost_target_kpa"] - out["map_kpa"]
    out["state"] = segment_state(out)
    return out
