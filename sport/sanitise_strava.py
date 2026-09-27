#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: 2026 Toni Nestorowicz
# SPDX-License-Identifier: AGPL-3.0-or-later
# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas==3.0.2"]
# [tool.uv]
# exclude-newer = "2026-09-27T00:00:00Z"
# ///
"""Reduce a Strava bulk-export activities.csv to exactly the data the sport figure on nestorowicz.nl uses.

Output columns (sessions.csv):
  date          local calendar date (Europe/Amsterdam). Start times are not published.
  sport         ride, indoor_ride, run, walk or strength.
  moving_min    moving time in minutes, one decimal.
  distance_km   only for runs over 1 km and outdoor rides over 5 km, which feed the pace and
                speed findings; blank for every other session.
Rows are sorted by date, sport, moving time and distance, so the order of sessions within a day
is not kept and the output does not depend on the row order of the export.

Gear and titles are read only to classify indoor rides and strength sessions and are never written.
Everything else in the export is dropped: activity IDs, titles, descriptions, notes, gear, file
names, start times, elapsed time, heart rate, power, body weight, weather and Strava's scores.

The dependency versions are pinned (and resolution is frozen with exclude-newer), so the same
activities.csv always gives a byte-identical sessions.csv.

The page carries the same bytes inside it; --embed writes them there, between
<script id="sessions" type="text/csv"> and </script>.

Usage:  ./sanitise_strava.py activities.csv sessions.csv [--embed ../index.html]
"""
import argparse
from pathlib import Path

import pandas as pd

MIN_YEAR = 2018                 # earlier years are too sparse to be representative
TZ = "Europe/Amsterdam"         # Strava export timestamps are UTC; converted to local time here

SPORTS = {                      # export label (Dutch or English) -> published label
    "Fietsrit": "ride", "Ride": "ride",
    "Virtuele fietsrit": "indoor_ride", "Virtual Ride": "indoor_ride",
    "Hardloopsessie": "run", "Run": "run",
    "Wandeling": "walk", "Walk": "walk", "Hiken": "walk", "Hike": "walk",
    "Krachttraining": "strength", "Weight Training": "strength",
}
COLS = {  # canonical -> candidates (Dutch, English)
    "date": ["Datum van activiteit", "Activity Date"],
    "type": ["Activiteitstype", "Activity Type"],
    "moving": ["Beweegtijd", "Moving Time"],
    "metres": ["Afstand.1", "Distance.1"],
    "gear": ["Uitrusting voor activiteit", "Activity Gear"],   # used for classification only, never published
    "name": ["Naam activiteit", "Activity Name"],             # used for classification only, never published
}
# Reclassification rules. Strava files indoor rides without a virtual platform as ordinary rides,
# and some strength sessions as generic "Training".
INDOOR_GEAR = {"Wattbike Pro"}          # bikes that only exist indoors
INDOOR_NAME = r"\bindoor\b"            # ride titles that mark an indoor session
STRENGTH_NAME = r"krachttraining|strength"

# Distance is published only where index.html reads it (pace and speed). Keep in sync with the page.
DISTANCE_OVER_KM = {"run": 1.0, "ride": 5.0}

# Sessions to leave out, keyed by local start time (minute precision) and sport.
# Matched before start times are dropped.
EXCLUDE = {
    ("2018-07-21T21:30", "ride"): "added manually afterwards; the real start time is unknown",
}
NL_MONTHS = dict(zip("jan feb mrt apr mei jun jul aug sep okt nov dec".split(), range(1, 13), strict=True))
OUT_COLS = ["date", "sport", "moving_min", "distance_km"]


def pick(df: pd.DataFrame, key: str) -> pd.Series:
    for c in COLS[key]:
        if c in df.columns:
            return df[c]
    raise KeyError(f"None of {COLS[key]} found in CSV")


def parse_dates(s: pd.Series) -> pd.Series:
    nl = s.str.extract(r"^(\d{1,2}) ([a-z]{3}) (\d{4}), (\d{1,2}:\d{2}:\d{2})$")
    if nl.notna().all(axis=None):
        iso = nl[2] + "-" + nl[1].map(NL_MONTHS).astype(str).str.zfill(2) + "-" + nl[0].str.zfill(2) + " " + nl[3]
        dt = pd.to_datetime(iso, format="%Y-%m-%d %H:%M:%S")
    else:
        dt = pd.to_datetime(s, format="mixed")
    return dt.dt.tz_localize("UTC").dt.tz_convert(TZ).dt.tz_localize(None)


def main(src: str, dst: str, page: Path | None = None) -> None:
    raw = pd.read_csv(src)
    start = parse_dates(pick(raw, "date")).dt.floor("min")
    raw_type = pick(raw, "type")
    gear, name = pick(raw, "gear").fillna(""), pick(raw, "name").fillna("")

    sport = raw_type.map(SPORTS)
    indoor = (sport == "ride") & (gear.isin(INDOOR_GEAR) | name.str.contains(INDOOR_NAME, case=False, regex=True))
    strength = raw_type.isin(["Training", "Workout"]) & name.str.contains(STRENGTH_NAME, case=False, regex=True)
    sport[indoor] = "indoor_ride"
    sport[strength] = "strength"
    print(f"Reclassified {int(indoor.sum())} rides as indoor and {int(strength.sum())} training sessions as strength")

    df = pd.DataFrame({
        "start": start,
        "sport": sport,
        "moving_min": (pick(raw, "moving").astype(float) / 60).round(1),
        # Round once, here, so the published value and the distance threshold below agree
        "km": (pick(raw, "metres").astype(float).fillna(0) / 1000).round(2),
    })
    skipped = raw_type[df["sport"].isna()].value_counts()
    df = df.dropna(subset=["sport"])
    df = df[df["start"].dt.year >= MIN_YEAR]

    key = list(zip(df["start"].dt.strftime("%Y-%m-%dT%H:%M"), df["sport"], strict=True))
    drop = pd.Series([k in EXCLUDE for k in key], index=df.index)
    for k in EXCLUDE:
        if k not in key:
            print(f"Warning: excluded session {k} not found")
    df = df[~drop]

    limit = df["sport"].map(DISTANCE_OVER_KM)
    keep_km = limit.notna() & (df["km"] > limit)
    out = pd.DataFrame({
        "date": df["start"].dt.strftime("%Y-%m-%d"),
        "sport": df["sport"],
        "moving_min": df["moving_min"].map(lambda v: f"{v:.1f}"),
        "distance_km": df["km"].map(lambda v: f"{v:.2f}").where(keep_km, ""),
    })
    # Sort on content only, so the result does not depend on the row order of the export
    out = out.assign(_m=df["moving_min"], _k=df["km"]).sort_values(["date", "sport", "_m", "_k"], kind="stable")[OUT_COLS]
    text = out.to_csv(index=False, lineterminator="\n")
    Path(dst).write_text(text, encoding="utf-8")
    if page:
        html, tag = page.read_text(encoding="utf-8"), '<script id="sessions" type="text/csv">\n'
        a = html.index(tag) + len(tag)
        page.write_text(html[:a] + text + html[html.index("</script>", a):], encoding="utf-8")
        print(f"Embedded the sessions in {page}")

    print(f"Excluded {int(drop.sum())} listed session(s)")
    print(f"Wrote {len(out)} sessions with columns {OUT_COLS} to {dst} (distance kept for {int(keep_km.sum())})")
    if len(skipped):
        print("Skipped sports:\n" + skipped.to_string())


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("src", nargs="?", default="activities.csv", help="Strava bulk-export activities.csv")
    p.add_argument("dst", nargs="?", default="sessions.csv", help="published CSV to write")
    p.add_argument("--embed", type=Path, help="also write the sessions into this page (index.html)")
    a = p.parse_args()
    main(a.src, a.dst, a.embed)
