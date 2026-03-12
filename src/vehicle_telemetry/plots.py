from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _missing(ax, text: str) -> None:
    ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes)
    ax.set_axis_off()


def _valid_xy(df: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
    if x not in df.columns or y not in df.columns:
        return pd.DataFrame()
    return df[[x, y]].replace([np.inf, -np.inf], np.nan).dropna()


def plot_rpm_load_heatmap(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    v = _valid_xy(df, "rpm", "load_proxy")
    if v.empty:
        _missing(ax, "Need rpm and load_proxy")
        return fig
    h = ax.hist2d(v["rpm"], v["load_proxy"], bins=60, cmap="viridis", cmin=1)
    plt.colorbar(h[3], ax=ax, label="count")
    ax.set_xlabel("RPM")
    ax.set_ylabel("Load Proxy")
    ax.set_title("RPM vs Load Proxy")
    return fig


def plot_load_map_over_time(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 4))
    if "time_s" not in df.columns:
        _missing(ax, "Need time_s")
        return fig
    t = df["time_s"]
    has_load = "load_proxy" in df.columns and df["load_proxy"].notna().any()
    has_map = "map_kpa" in df.columns and df["map_kpa"].notna().any()

    if not has_load and not has_map:
        _missing(ax, "Need load_proxy and/or map_kpa")
        return fig

    if has_load:
        ax.plot(t, df["load_proxy"], label="load_proxy", lw=1.2)
        ax.set_ylabel("Load Proxy")
    if has_map:
        ax2 = ax.twinx()
        ax2.plot(t, df["map_kpa"], label="map_kpa", lw=1.0, color="tab:red", alpha=0.7)
        ax2.set_ylabel("MAP (kPa)")
    ax.set_xlabel("Time (s)")
    ax.set_title("Load and MAP over Time")
    return fig


def plot_fuel_trims(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 4))
    if "time_s" not in df.columns:
        _missing(ax, "Need time_s")
        return fig
    t = df["time_s"]
    plotted = False
    if "stft_pct" in df.columns and df["stft_pct"].notna().any():
        ax.plot(t, df["stft_pct"], label="STFT", lw=1.0)
        plotted = True
    if "ltft_pct" in df.columns and df["ltft_pct"].notna().any():
        ax.plot(t, df["ltft_pct"], label="LTFT", lw=1.0)
        plotted = True

    if not plotted:
        _missing(ax, "Need stft_pct and/or ltft_pct")
        return fig

    ax.axhline(0, color="black", lw=0.8, alpha=0.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Fuel Trim (%)")
    ax.set_title("Fuel Trims over Time")
    ax.legend()
    return fig


def plot_temps(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 4))
    if "time_s" not in df.columns:
        _missing(ax, "Need time_s")
        return fig
    t = df["time_s"]
    plotted = False
    if "coolant_c" in df.columns and df["coolant_c"].notna().any():
        ax.plot(t, df["coolant_c"], label="Coolant C", lw=1.2)
        plotted = True
    if "iat_c" in df.columns and df["iat_c"].notna().any():
        ax.plot(t, df["iat_c"], label="IAT C", lw=1.0)
        plotted = True

    if not plotted:
        _missing(ax, "Need coolant_c and/or iat_c")
        return fig

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Temperature (C)")
    ax.set_title("Coolant and IAT over Time")
    ax.legend()
    return fig


def plot_accel_maf_vs_rpm(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 5))
    if "state" not in df.columns:
        _missing(ax, "Need state column")
        return fig
    v = df[df["state"] == "accel"]
    v = _valid_xy(v, "rpm", "maf_gps")
    if v.empty:
        _missing(ax, "Need accel rows with rpm and maf_gps")
        return fig
    ax.scatter(v["rpm"], v["maf_gps"], s=8, alpha=0.45)
    ax.set_xlabel("RPM")
    ax.set_ylabel("MAF (g/s)")
    ax.set_title("Accel-only MAF vs RPM")
    return fig
