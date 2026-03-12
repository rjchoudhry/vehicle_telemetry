from __future__ import annotations

import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    notebook_path = root / "notebooks" / "telemetry_report.ipynb"
    output_path = root / "outputs" / "latest_report.ipynb"
    runtime_dir = root / ".jupyter_runtime"

    runtime_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["JUPYTER_RUNTIME_DIR"] = str(runtime_dir)

    with notebook_path.open("r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    client = NotebookClient(nb, timeout=900, kernel_name="python3")
    client.execute()

    with output_path.open("w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    print(output_path)


if __name__ == "__main__":
    main()
