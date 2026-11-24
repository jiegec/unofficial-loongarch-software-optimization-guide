#!/usr/bin/env python3
"""Render the core-to-core latency heatmaps for the guide.

Usage:
    uv run --with matplotlib --with numpy python scripts/plot_core_to_core.py

The input files are the CSV matrices produced by
https://github.com/nviennot/core-to-core-latency. They store the lower
triangle of the matrix, with the diagonal left blank; the script fills in the
symmetric upper half and renders one annotated heatmap per part.
"""

from __future__ import annotations

import argparse
import csv
import os
import tempfile
from pathlib import Path

# Keep matplotlib's cache out of the user's home directory. This also avoids a
# hard failure on systems where ~/.config is read-only.
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "core-to-core-latency-matplotlib"),
)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize

ROOT = Path(__file__).resolve().parents[1]

PARTS = [
    {
        "csv": "core-to-core-3C5000.csv",
        "png": "core-to-core-3c5000.png",
        "title": "3C5000: 16 logical CPUs",
        "figsize": (7.2, 6.2),
        "fontsize": 7.2,
        "tick_step": 1,
        "grid_step": 4,
    },
    {
        "csv": "core-to-core-3C6000S.csv",
        "png": "core-to-core-3c6000s.png",
        "title": "3C6000/S: 32 logical CPUs",
        "figsize": (12.5, 11.5),
        "fontsize": 5.2,
        "tick_step": 4,
        "grid_step": 4,
    },
]


def load_matrix(path: Path) -> np.ndarray:
    """Load a lower-triangular core-to-core CSV and mirror it."""
    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    while rows and not any(cell.strip() for cell in rows[-1]):
        rows.pop()

    n = len(rows)
    matrix = np.full((n, n), np.nan)
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            if cell.strip():
                value = float(cell)
                matrix[i, j] = value
                matrix[j, i] = value
    return matrix


def render(matrix: np.ndarray, out: Path, part: dict) -> None:
    n = len(matrix)
    fig, ax = plt.subplots(figsize=part["figsize"])

    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("#e5e7eb")
    norm = Normalize(vmin=np.nanmin(matrix), vmax=np.nanmax(matrix))
    image = ax.imshow(
        np.ma.masked_invalid(matrix),
        cmap=cmap,
        norm=norm,
        interpolation="nearest",
    )

    ax.set_title(part["title"], fontsize=12, pad=10)
    ax.set_xlabel("logical CPU", fontsize=10)
    ax.set_ylabel("logical CPU", fontsize=10)

    ticks = list(range(0, n, part["tick_step"]))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.tick_params(labelsize=8 if n == 16 else 7.5)

    # Thin grid on every cell, plus a stronger line every grid_step cells.
    ax.set_xticks(np.arange(-0.5, n, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.4, alpha=0.25)
    ax.tick_params(which="minor", length=0)
    for boundary in np.arange(part["grid_step"] - 0.5, n, part["grid_step"]):
        ax.axhline(boundary, color="white", linewidth=0.9, alpha=0.65)
        ax.axvline(boundary, color="white", linewidth=0.9, alpha=0.65)

    for spine in ax.spines.values():
        spine.set_visible(False)

    for i in range(n):
        for j in range(n):
            value = matrix[i, j]
            if np.isnan(value):
                continue
            color = "black" if norm(value) > 0.55 else "white"
            ax.text(
                j,
                i,
                f"{value:.1f}",
                ha="center",
                va="center",
                fontsize=part["fontsize"],
                color=color,
            )

    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.035)
    colorbar.set_label("median latency (ns)", fontsize=9)
    colorbar.ax.tick_params(labelsize=8)

    fig.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "docs" / "microarchitecture",
        help="directory containing the core-to-core CSV files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "docs" / "assets" / "images",
        help="directory for the rendered PNG files",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for part in PARTS:
        source = args.data_dir / part["csv"]
        out = args.output_dir / part["png"]
        render(load_matrix(source), out, part)
        print(f"{source} -> {out}")


if __name__ == "__main__":
    main()
