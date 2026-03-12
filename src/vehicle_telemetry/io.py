from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

LogType = Literal["obd_fusion", "cobb_accessport", "unknown"]
ENCODING_FALLBACKS = ("utf-8", "cp1252", "latin-1")


def _read_csv_with_fallback(path: Path, **kwargs) -> pd.DataFrame:
    last_error: UnicodeDecodeError | None = None
    for encoding in ENCODING_FALLBACKS:
        try:
            return pd.read_csv(path, encoding=encoding, **kwargs)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise UnicodeDecodeError("utf-8", b"", 0, 1, "Unable to decode CSV with fallback encodings")


def _read_first_line_with_fallback(path: Path) -> str:
    last_error: UnicodeDecodeError | None = None
    for encoding in ENCODING_FALLBACKS:
        try:
            with path.open("r", encoding=encoding) as f:
                return f.readline().strip().lstrip("\ufeff")
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise UnicodeDecodeError("utf-8", b"", 0, 1, "Unable to decode first line with fallback encodings")


def detect_log_type(csv_path: str | Path) -> LogType:
    """Detect log source from early file lines and header tokens."""
    path = Path(csv_path)
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = [f.readline().strip() for _ in range(3)]

    joined = "\n".join(lines)
    if "AP Info:" in joined or "Dyn Adv Mult" in joined:
        return "cobb_accessport"
    if "# StartTime" in joined or "Calculated load value" in joined:
        return "obd_fusion"

    header = lines[0] if lines else ""
    if "Time (sec)" in header and "Vehicle speed (km/h)" in header:
        return "obd_fusion"
    if "Time (sec)" in header and "Vehicle Speed (mph)" in header:
        return "cobb_accessport"
    return "unknown"


def read_log_csv(csv_path: str | Path, log_type: LogType | None = None) -> tuple[pd.DataFrame, LogType]:
    """Read telemetry CSV while handling OBD Fusion comment preamble lines."""
    path = Path(csv_path)
    resolved_type = log_type or detect_log_type(path)

    if resolved_type == "obd_fusion":
        first = _read_first_line_with_fallback(path)
        skiprows = 1 if first.startswith("#") else 0
        df = _read_csv_with_fallback(path, skiprows=skiprows)
    else:
        df = _read_csv_with_fallback(path)

    return df, resolved_type
