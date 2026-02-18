#!/usr/bin/env python3
from __future__ import annotations

import io
import math
from pathlib import Path

import pandas as pd
import requests

CSV_URL = "https://github.com/PatLittle/GC-News-Nouvelles-GC/raw/refs/heads/main/combined_news.csv"

OUT_MMD = "docs/type_by_quarter_last12_complete_months_radar.mmd"
TOP_TYPES = 8  # keep readable; tweak as desired


def esc_label(s: str) -> str:
    s = str(s).replace('"', '\\"')
    # Mermaid radar labels often work best quoted when they contain spaces/punct
    return f'"{s}"'


def nice_max(n: int) -> int:
    """Round up to a nice axis max (1, 2, 5 * 10^k)."""
    if n <= 1:
        return 1
    k = 10 ** int(math.floor(math.log10(n)))
    for m in (1, 2, 5, 10):
        if m * k >= n:
            return m * k
    return 10 * k


def main() -> None:
    r = requests.get(CSV_URL, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.BytesIO(r.content))

    if "PUBDATE" not in df.columns or "TYPE_EN" not in df.columns:
        raise SystemExit(f"Expected PUBDATE and TYPE_EN. Columns: {list(df.columns)}")

    # Parse datetime
    dt = pd.to_datetime(df["PUBDATE"], errors="coerce", utc=True)
    df = df.loc[dt.notna()].copy()
    df["_dt"] = dt.loc[dt.notna()].dt.tz_convert(None)  # naive local-ish
    df["_type"] = df["TYPE_EN"].astype(str).str.strip()

    # Last 12 COMPLETE months: exclude current partial month
    last_complete_month_end = (df["_dt"].max().to_period("M").start_time)  # first day of max month
    # If max month is partial, we exclude it by treating "last complete month" as previous month end
    # We want the last *complete* month relative to latest timestamp in file:
    # take the month containing max_dt, then step back 1 month.
    last_complete_month = (df["_dt"].max().to_period("M") - 1)  # previous month (complete)
    window_end_exclusive = (last_complete_month + 1).start_time  # first day after last complete month
    window_start = (last_complete_month - 11).start_time         # 12 months back inclusive

    df = df[(df["_dt"] >= window_start) & (df["_dt"] < window_end_exclusive)].copy()

    if df.empty:
        mer = "\n".join([
            "```mermaid",
            "radar-beta",
            '  title "TYPE_EN by quarter (last 12 complete months) — no data"',
            '  axis q1["No data"]',
            '  curve t1["No data"]{0}',
            "  graticule polygon",
            "  max 1",
            "```",
            ""
        ])
        Path(OUT_MMD).parent.mkdir(parents=True, exist_ok=True)
        Path(OUT_MMD).write_text(mer, encoding="utf-8")
        print(f"Wrote {OUT_MMD}")
        return

    # Quarter bucket
    df["_q"] = df["_dt"].dt.to_period("Q").astype(str)  # e.g., 2025Q4

    # Determine the 4 quarters covered by those 12 complete months (should be 4 complete quarters)
    quarters = sorted(df["_q"].unique().tolist())
    # If for any reason we got >4 (due to boundaries), keep the last 4 complete quarters
    quarters = quarters[-4:]

    # Keep only those quarters
    df = df[df["_q"].isin(quarters)].copy()

    # Top types across the window
    top_types = (
        df["_type"].value_counts()
        .head(TOP_TYPES)
        .index
        .tolist()
    )

    # Pivot: rows = TYPE, cols = quarter
    pivot = (
        df[df["_type"].isin(top_types)]
        .groupby(["_type", "_q"])
        .size()
        .unstack("_q", fill_value=0)
        .reindex(columns=quarters, fill_value=0)
    )

    vmax = int(pivot.to_numpy().max()) if not pivot.empty else 1
    vmax = nice_max(max(1, vmax))

    # Build Mermaid radar-beta
    # Axes: quarters
    axis_parts = []
    for i, q in enumerate(quarters, start=1):
        axis_parts.append(f'q{i}[{esc_label(q)}]')
    axis_line = "  axis " + ", ".join(axis_parts)

    lines = []
    lines.append("```mermaid")
    lines.append("radar-beta")
    lines.append(f'  title "GC News — TYPE_EN counts by quarter (last 12 complete months)"')
    lines.append(axis_line)
    lines.append("")  # spacing

    # Curves: each TYPE_EN, values aligned to quarters
    for idx, t in enumerate(pivot.index.tolist(), start=1):
        vals = [int(pivot.loc[t, q]) for q in quarters]
        lines.append(f'  curve t{idx}[{esc_label(t)}]' + "{" + ", ".join(map(str, vals)) + "}")

    lines.append("")
    lines.append("  graticule polygon")
    lines.append(f"  max {vmax}")
    lines.append("```")
    lines.append("")

    Path(OUT_MMD).parent.mkdir(parents=True, exist_ok=True)
    Path(OUT_MMD).write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MMD}")


if __name__ == "__main__":
    main()
