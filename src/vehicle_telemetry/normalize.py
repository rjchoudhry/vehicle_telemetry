from __future__ import annotations

import re

import numpy as np
import pandas as pd

CANONICAL_COLUMNS = [
    "time_s",
    "rpm",
    "speed_kph",
    "throttle_pct",
    "maf_gps",
    "map_kpa",
    "coolant_c",
    "iat_c",
    "stft_pct",
    "ltft_pct",
    "ign_deg",
    "dam",
    "fbk",
    "fkl",
    "boost_target_kpa",
    "boost_error_kpa",
    "wgdc_pct",
]

PSI_TO_KPA = 6.8947572932
MPH_TO_KPH = 1.609344


def _norm_name(text: str) -> str:
    txt = text.lower().strip()
    txt = txt.replace("%", " pct ")
    txt = txt.replace("#1", "1")
    txt = re.sub(r"[^a-z0-9]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _f_to_c(series: pd.Series) -> pd.Series:
    return (series - 32.0) * (5.0 / 9.0)


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def _build_map(df: pd.DataFrame, mapping: dict[str, list[str]]) -> dict[str, str]:
    cols = {_norm_name(c): c for c in df.columns}
    selected: dict[str, str] = {}
    for canonical, aliases in mapping.items():
        for alias in aliases:
            key = _norm_name(alias)
            if key in cols:
                selected[canonical] = cols[key]
                break
    return selected


def _obd_mapping() -> dict[str, list[str]]:
    return {
        "time_s": ["Time sec"],
        "rpm": ["Engine RPM RPM"],
        "speed_kph": ["Vehicle speed km h"],
        "throttle_pct": ["Absolute throttle position pct"],
        "maf_gps": ["Mass air flow rate g s"],
        "map_kpa": ["Intake manifold absolute pressure kPa"],
        "coolant_c": ["Engine coolant temperature C"],
        "iat_c": ["Intake air temperature bank 1 sensor 1 C", "Intake air temperature bank 1 sensor 2 C"],
        "stft_pct": ["Short term fuel pct trim Bank 1 pct"],
        "ltft_pct": ["Long term fuel pct trim Bank 1 pct"],
        "ign_deg": ["Ignition timing advance for 1 cylinder deg"],
    }


def _cobb_mapping() -> dict[str, list[str]]:
    return {
        "time_s": ["Time sec"],
        "rpm": ["RPM RPM"],
        "speed_kph": ["Vehicle Speed mph"],
        "throttle_pct": ["Throttle Pos pct", "Accel Position pct"],
        "maf_gps": ["MAF Corr Final g s"],
        "map_kpa": ["Man Abs Press psi"],
        "coolant_c": ["Coolant Temp F"],
        "iat_c": ["Intake Temp F", "Intake Temp Manifold F"],
        "stft_pct": ["AF Correction 1 pct"],
        "ltft_pct": ["AF Learning 1 pct"],
        "ign_deg": ["Ignition Timing"],
        "dam": ["Dyn Adv Mult DAM"],
        "fbk": ["Feedback Knock"],
        "fkl": ["Fine Knock Learn"],
        "boost_target_kpa": ["Target Boost Final Rel Ext psi"],
        "boost_error_kpa": ["TD Boost Error Ext psi"],
        "wgdc_pct": ["Wastegate Duty pct"],
    }


def normalize_log(df: pd.DataFrame, log_type: str) -> pd.DataFrame:
    """Map source columns into one canonical telemetry schema."""
    if log_type == "obd_fusion":
        selected = _build_map(df, _obd_mapping())
    elif log_type == "cobb_accessport":
        selected = _build_map(df, _cobb_mapping())
    else:
        selected = {}

    out = pd.DataFrame(index=df.index)
    for col in CANONICAL_COLUMNS:
        out[col] = _num(df, selected[col]) if col in selected else np.nan

    if log_type == "cobb_accessport":
        if "speed_kph" in selected:
            out["speed_kph"] = out["speed_kph"] * MPH_TO_KPH
        if "map_kpa" in selected:
            out["map_kpa"] = out["map_kpa"] * PSI_TO_KPA
        if "boost_target_kpa" in selected:
            out["boost_target_kpa"] = out["boost_target_kpa"] * PSI_TO_KPA
        if "boost_error_kpa" in selected:
            out["boost_error_kpa"] = out["boost_error_kpa"] * PSI_TO_KPA
        if "coolant_c" in selected:
            out["coolant_c"] = _f_to_c(out["coolant_c"])
        if "iat_c" in selected:
            out["iat_c"] = _f_to_c(out["iat_c"])

    if out["time_s"].isna().all():
        out["time_s"] = np.arange(len(out), dtype=float)

    return out
