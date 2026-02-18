#!/usr/bin/env python3
import io
import math
from pathlib import Path

import pandas as pd
import requests

CSV_URL = "https://github.com/PatLittle/GC-News-Nouvelles-GC/raw/refs/heads/main/combined_news.csv"
OUT = Path("docs/type_axes_quarter_curves.md")

TOP_TYPES = 10  # keep readable


def esc(s: str) -> str:
    return '"' + str(s).replace('"', '\\"') + '"'


def nice_max(n: int) -> int:
    if n <= 1:
        return 1
    k = 10 ** int(math.floor(math.log10(n)))
    for m in (1, 2, 5, 10):
        if m * k >= n:
            return m * k
    return 10 * k


# --- Load data ---
r = requests.get(CSV_URL, timeout=60)
r.raise_for_status()
df = pd.read_csv(io.BytesIO(r.content))

df["PUBDATE"] = pd.to_datetime(df["PUBDATE"], errors="coerce", utc=True)
df = df[df["PUBDATE"].notna()].copy()
df["_dt"] = df["PUBDATE"].dt.tz_convert(None)
df["_type"] = df["TYPE_EN"].astype(str).str.strip()

# --- Last 12 complete months ---
max_dt = df["_dt"].max()
last_complete_month = (max_dt.to_period("M") - 1)
window_end = (last_complete_month + 1).start_time
window_start = (last_complete_month - 11).start_time

df = df[(df["_dt"] >= window_start) & (df["_dt"] < window_end)].copy()

# Quarter labels
df["_quarter"] = df["_dt"].dt.to_period("Q").astype(str)

# Last 4 quarters
quarters = sorted(df["_quarter"].unique())[-4:]
df = df[df["_quarter"].isin(quarters)]

# Top TYPE_EN across window
top_types = (
    df["_type"]
    .value_counts()
    .head(TOP_TYPES)
    .index
    .tolist()
)

# Pivot: rows = quarter, columns = type
pivot = (
    df[df["_type"].isin(top_types)]
    .groupby(["_quarter", "_type"])
    .size()
    .unstack("_type", fill_value=0)
    .reindex(index=quarters, columns=top_types, fill_value=0)
)

vmax = nice_max(int(pivot.values.max()) if not pivot.empty else 1)

# --- Build Markdown with Mermaid ---
lines = []
lines.append("## TYPE_EN by Quarter (last 12 complete months)")
lines.append("")
lines.append("```mermaid")
lines.append("radar-beta")
lines.append('  title "GC News — TYPE_EN by quarter (last 12 complete months)"')

# Axes = TYPE_EN
axis_parts = [f"t{i+1}[{esc(t)}]" for i, t in enumerate(top_types)]
lines.append("  axis " + ", ".join(axis_parts))
lines.append("")

# Curves = quarters
for i, q in enumerate(quarters, start=1):
    vals = pivot.loc[q].tolist()
    lines.append(f"  curve q{i}[{esc(q)}]" + "{" + ", ".join(map(str, vals)) + "}")

lines.append("")
lines.append("  graticule polygon")
lines.append(f"  max {vmax}")
lines.append("```")
lines.append("")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")

print("Wrote", OUT)

import io
from pathlib import Path
from datetime import timedelta

import pandas as pd
import requests
import plotly.graph_objects as go

CSV_URL = "https://github.com/PatLittle/GC-News-Nouvelles-GC/raw/refs/heads/main/combined_news.csv"

OUT = Path("docs/type_heatmap_180d.svg")
DAYS = 180
TOP_TYPES = 12  # keep readable


# --- Load data ---
r = requests.get(CSV_URL, timeout=60)
r.raise_for_status()
df = pd.read_csv(io.BytesIO(r.content))

# Parse datetime
df["PUBDATE"] = pd.to_datetime(df["PUBDATE"], errors="coerce", utc=True)
df = df[df["PUBDATE"].notna()].copy()
df["_dt"] = df["PUBDATE"].dt.tz_convert(None)
df["_date"] = df["_dt"].dt.date
df["_type"] = df["TYPE_EN"].astype(str).str.strip()

# --- Last 180 days relative to newest record ---
max_date = df["_date"].max()
start_date = max_date - timedelta(days=DAYS - 1)

df = df[df["_date"] >= start_date].copy()

# --- Top TYPE_EN across window ---
top_types = (
    df["_type"]
    .value_counts()
    .head(TOP_TYPES)
    .index
    .tolist()
)

df = df[df["_type"].isin(top_types)]

# --- Pivot: rows = type, columns = date ---
pivot = (
    df.groupby(["_type", "_date"])
      .size()
      .unstack("_date", fill_value=0)
)

# Ensure continuous date axis
all_dates = pd.date_range(start=start_date, end=max_date, freq="D")
pivot = pivot.reindex(columns=all_dates.date, fill_value=0)

# Sort types by total volume
pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]

# --- Plotly Heatmap ---
fig = go.Figure(
    data=go.Heatmap(
        z=pivot.values,
        x=all_dates,
        y=pivot.index.tolist(),
        colorscale="Viridis",
        colorbar=dict(title="Count"),
    )
)

fig.update_layout(
    title=f"GC News — TYPE_EN counts per day (last {DAYS} days ending {max_date})",
    xaxis_title="Date",
    yaxis_title="TYPE_EN",
    xaxis_nticks=36,
    height=500,
    margin=dict(l=160, r=40, t=80, b=60),
)

# --- Save SVG ---
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.write_image(str(OUT))

print("Saved:", OUT)
