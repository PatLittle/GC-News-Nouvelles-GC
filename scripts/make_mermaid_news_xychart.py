#!/usr/bin/env python3
from __future__ import annotations

import io
from datetime import timedelta
import pandas as pd
import requests
from pathlib import Path

CSV_URL = "https://github.com/PatLittle/GC-News-Nouvelles-GC/raw/refs/heads/main/combined_news.csv"

def mermaid_escape_label(s: str) -> str:
    s = str(s).replace('"', '\\"')
    if any(ch.isspace() for ch in s) or any(ch in s for ch in [",", "[", "]"]):
        return f'"{s}"'
    return s

def main(days: int = 30, out_path: str = "docs/news_type_30d.mmd", max_series: int = 12, simulate_stacked: bool = True):
    r = requests.get(CSV_URL, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.BytesIO(r.content))

    if "PUBDATE" not in df.columns or "TYPE_EN" not in df.columns:
        raise SystemExit(f"Expected PUBDATE and TYPE_EN. Columns: {list(df.columns)}")

    dt = pd.to_datetime(df["PUBDATE"], errors="coerce", utc=True)
    df = df.loc[dt.notna()].copy()
    df["_date"] = dt.loc[dt.notna()].dt.tz_convert(None).dt.date
    df["_type"] = df["TYPE_EN"].astype(str).str.strip()

    max_date = pd.to_datetime(df["_date"]).max().date()
    start_date = (pd.to_datetime(max_date) - timedelta(days=days - 1)).date()
    df = df[df["_date"] >= start_date].copy()

    g = (
        df.groupby(["_date", "_type"], as_index=False)
          .size()
          .rename(columns={"size": "count"})
    )

    top_types = (
        g.groupby("_type")["count"].sum()
         .sort_values(ascending=False)
         .head(max_series)
         .index
         .tolist()
    )
    g = g[g["_type"].isin(top_types)].copy()

    pivot = (
        g.pivot_table(index="_date", columns="_type", values="count", aggfunc="sum", fill_value=0)
         .sort_index()
    )

    all_days = pd.date_range(start=start_date, end=max_date, freq="D").date
    pivot = pivot.reindex(all_days, fill_value=0)

    x_labels = [d.strftime("%Y-%m-%d") for d in pd.to_datetime(pivot.index)]
    ymax = int(pivot.sum(axis=1).max()) if len(pivot) else 0
    ymax = max(1, ymax)

    lines = []
    lines.append("```mermaid")
    lines.append("xychart-beta")
    lines.append(f'  title "GC News — count by TYPE_EN per day (last {days} days)"')
    lines.append("  x-axis [" + ", ".join(mermaid_escape_label(x) for x in x_labels) + "]")
    lines.append(f'  y-axis "Count" 0 --> {ymax}')

    if simulate_stacked:
        running = pd.Series([0] * len(pivot), index=pivot.index)
        for t in pivot.columns:
            running = running + pivot[t]
            vals = ", ".join(str(int(v)) for v in running.tolist())
            lines.append(f"  bar {mermaid_escape_label(t)} [{vals}]")
    else:
        for t in pivot.columns:
            vals = ", ".join(str(int(v)) for v in pivot[t].tolist())
            lines.append(f"  bar {mermaid_escape_label(t)} [{vals}]")

    lines.append("```")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
