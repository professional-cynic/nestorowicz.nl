#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: 2026 Toni Nestorowicz
# SPDX-License-Identifier: AGPL-3.0-or-later
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pandas", "matplotlib", "scipy"]
# ///
"""Every stretch of ten years or more in the De Bilt temperature record, as one tile.

Averages KNMI's homogenised daily mean temperature (version 2) per complete year,
fits a least-squares trend to every stretch of at least ten years, prints the
numbers quoted on nestorowicz.nl and draws each trend as a tile above the years
it spans.
"""
import argparse
import re
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import to_rgb
from matplotlib.patches import Polygon
from scipy import stats

MIN = 10    # shortest stretch, in years
INK, MUTED = "#152029", "#5A6672"
# [°C per decade, colour]: grey at no change, stronger colour for faster change (the website's light theme)
WARM = [(0, "#D6DDE3"), (.08, "#F1D98C"), (.18, "#EFA55A"), (.3, "#DE6338"), (.45, "#C8322C"), (.7, "#7A1B1F")]
COOL = [(0, "#D6DDE3"), (.08, "#B4D0EA"), (.2, "#72A2D8"), (.35, "#2F6DB5"), (.7, "#1A3667")]


def annual(path: Path, last: int = 2025) -> pd.Series:
    """Mean of version 2 per complete calendar year, rounded as on the website."""
    d = pd.read_csv(path, parse_dates=["date"])
    d = d[d.date.dt.year <= last]
    y = d.groupby(d.date.dt.year).version2
    return y.mean()[y.count() >= 365].round(2)


def trends(t: np.ndarray) -> dict[int, np.ndarray]:
    """B[L][s]: least-squares trend of the L years starting at index s, °C per decade."""
    B = {}
    for L in range(MIN, len(t) + 1):
        x = np.arange(L) - (L - 1) / 2
        w = np.lib.stride_tricks.sliding_window_view(t, L)
        B[L] = 10 * (w - w.mean(axis=1, keepdims=True)) @ x / (x @ x)
    return B


def persistence(t: np.ndarray) -> float:
    """Lag-1 autocorrelation of the year-to-year noise, measured around a cubic fit to the whole record."""
    x = np.arange(t.size)
    r = t - np.polyval(np.polyfit(x, t, 3), x)
    return float(np.corrcoef(r[:-1], r[1:])[0, 1])


def bands(t: np.ndarray, r1: float) -> dict[int, np.ndarray]:
    """H[L][s]: half-width of the 95% interval of each trend, °C per decade, using the
    effective sample size L(1 - r1)/(1 + r1) of Santer et al. (2008)."""
    H = {}
    for L in range(MIN, len(t) + 1):
        x = np.arange(L) - (L - 1) / 2
        w = np.lib.stride_tricks.sliding_window_view(t, L)
        d = w - w.mean(axis=1, keepdims=True)
        b = d @ x / (x @ x)
        rss = (d ** 2).sum(axis=1) - b ** 2 * (x @ x)
        ne = L * (1 - r1) / (1 + r1)
        H[L] = 10 * stats.t.ppf(0.975, ne - 2) * np.sqrt(rss / (x @ x) / (ne - 2))
    return H


def summary(B: dict[int, np.ndarray], y0: int) -> int:
    """Print the figures the website quotes; return the length from which no stretch cools."""
    n = max(B)
    def span(s: int, L: int) -> str:
        return f"{y0 + s}–{y0 + s + L - 1}"

    longest = max(L for L, b in B.items() if (b < 0).any())
    safe = longest + 1
    c, w = int(np.argmin(B[longest])), int(np.argmin(B[safe]))
    print(f"{n} complete years, {y0}–{y0 + n - 1}: {sum(b.size for b in B.values()):,} stretches of {MIN} years or more")
    print(f"{MIN}-year stretches: {(B[MIN] > 0).sum()} warmed, {(B[MIN] < 0).sum()} cooled")
    print(f"longest cooling stretch: {longest} years, {span(c, longest)} at {B[longest][c]:+.4f} °C per decade")
    print(f"weakest {safe}-year stretch: {span(w, safe)} at {B[safe][w]:+.4f} °C per decade")
    print(f"whole record: {B[n][0]:+.3f} °C per decade")
    early, late = B[safe][1960 - y0 - safe + 1], B[safe][-1]
    print(f"{safe} years to 1960: {early:+.3f}, {safe} years to {y0 + n - 1}: {late:+.3f} °C per decade ({late / early:.1f} times as fast)")
    return safe


def tone(b: np.ndarray) -> np.ndarray:
    """Interpolate each trend along the warm or cool scale, capped at its last stop."""
    out = np.empty((b.size, 3))
    for ramp, m in ((WARM, b >= 0), (COOL, b < 0)):
        stops = [v for v, _ in ramp]
        rgb = np.array([to_rgb(c) for _, c in ramp])
        v = np.minimum(np.abs(b[m]), stops[-1])
        out[m] = np.column_stack([np.interp(v, stops, rgb[:, j]) for j in range(3)])
    return out


def draw(t: np.ndarray, B: dict[int, np.ndarray], y0: int, safe: int, out: Path, clear: dict[int, np.ndarray] | None = None) -> None:
    """Draw the figure; with `clear`, tiles whose interval includes zero are faded towards the background."""
    n = len(t)
    fig, (top, bot) = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True, gridspec_kw={"height_ratios": [5, 1.1], "hspace": 0.12})
    fig.patch.set_facecolor("white")

    # tile (s, L) is centred above the middle of its years (x) at its length (y); the outermost reach the straight edge
    polys, cols = [], []
    for L, b in B.items():
        for s in range(b.size):
            left = 1 if s == 0 else 0          # the outermost tiles reach the straight edge
            right = 1 if s + L == n else 0
            x0, x1 = s + L / 2 - 0.5 - left, s + L / 2 + 0.5 + right
            polys.append([(x0, L - 0.5), (x1, L - 0.5), (x1, L + 0.5), (x0, L + 0.5)])
        c = tone(b)
        if clear is not None:
            c[~clear[L]] += (1 - c[~clear[L]]) * 0.68
        cols.append(c)
    edge = Polygon([((MIN - 0.5) / 2 - 0.5, MIN - 0.5), (n - (MIN - 0.5) / 2 + 0.5, MIN - 0.5),
                    (n / 2 + 0.25, n + 0.5), (n / 2 - 0.25, n + 0.5)], transform=top.transData)
    tiles = PolyCollection(polys, facecolors=np.vstack(cols), edgecolors="none", antialiased=False)
    tiles.set_clip_path(edge)
    top.add_collection(tiles)

    top.axhline(safe - 0.5, color=INK, lw=0.9, ls=(0, (4, 3)))
    top.text(n + 0.5, safe + 1, "No stretch above\nthis line cooled", ha="right", va="bottom", color=INK, fontsize=10, linespacing=1.3)
    top.set_ylim(MIN - 0.5, n + 0.5)
    top.set_yticks([MIN, safe - 0.5, n], [f"{MIN} years", f"{safe} years", f"{n} years"])
    top.get_yticklabels()[1].set_color(INK)
    key = top.inset_axes([0.8, 0.95, 0.2, 0.025])   # the colour scale, top right where the tiles leave room
    key.imshow(tone(np.linspace(-0.7, 0.7, 280))[None], aspect="auto", extent=(-0.7, 0.7, 0, 1))
    key.set_yticks([])
    key.set_xticks([-0.5, 0, 0.5], ["−0.5", "0", "+0.5"])
    key.set_title("°C per decade", fontsize=9, color=MUTED, loc="right", pad=3)
    key.tick_params(length=0, colors=MUTED, labelsize=9, pad=2)
    for side in key.spines.values():
        side.set_visible(False)

    # each year against the average
    a = t - t.mean()
    bot.bar(np.arange(n) + 0.5, a, width=0.55, color=MUTED, alpha=0.6)
    bot.axhline(0, color=MUTED, lw=0.6)
    bot.set_yticks([0], ["Each year\nvs average"])
    ticks = [1901, 1925, 1950, 1975, 2000, 2025]
    bot.set_xticks([y - y0 + 0.5 for y in ticks], [str(y) for y in ticks])
    bot.set_xlim(0, n)

    for ax in (top, bot):
        for side in ax.spines.values():
            side.set_visible(False)
        ax.tick_params(length=0, colors=MUTED, labelsize=10)
    fig.text(0.125, 0.955, "The longer you look, the clearer it gets", fontsize=17, color=INK, family="serif")
    fig.text(0.125, 0.9, f"Every stretch of ten years or more in the De Bilt temperature record, {y0}–{y0 + n - 1}, as one tile\n"
             "above the years it spans: warm colours if it warmed, blue if it cooled.", fontsize=10, color=MUTED, linespacing=1.4)
    fig.text(0.125, 0.03, "Data: KNMI, homogenised daily mean temperature, version 2 (CC BY 4.0). Interactive version: nestorowicz.nl",
             fontsize=8.5, color=MUTED)
    fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.25)
    print(f"figure written to {out}")


def main() -> None:
    here = Path(__file__).parent
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("csv", nargs="?", type=Path, default=here / "DeBilt-TG-allversions.csv", help="KNMI's De Bilt file (default: next to this script)")
    p.add_argument("--out", type=Path, default=here / "triangle.png", help="figure file; the extension sets the format (png, svg, pdf)")
    p.add_argument("--trends", type=Path, help="also write every stretch, its trend and its 95%% interval to this CSV")
    p.add_argument("--fade", action="store_true", help="fade stretches whose 95%% interval includes zero, as the website's switch does")
    p.add_argument("--embed", type=Path, help="write the annual means into this page (index.html), replacing its `const T = [...]`")
    args = p.parse_args()

    t = annual(args.csv)
    y0 = int(t.index[0])
    B = trends(t.to_numpy())
    safe = summary(B, y0)
    r1 = persistence(t.to_numpy())
    H = bands(t.to_numpy(), r1)
    def unclear(L: int) -> np.ndarray:
        return np.abs(B[L]) <= H[L]

    short = np.concatenate([unclear(L) for L in range(MIN, 20)])
    print(f"lag-1 autocorrelation of the noise: {r1:.4f}")
    print(f"{MIN}-year stretches clear of zero: {(~unclear(MIN)).sum()} of {B[MIN].size}; stretches under 20 years whose interval includes zero: {short.mean():.0%}")
    if args.embed:
        page = args.embed.read_text(encoding="utf-8")
        page, n = re.subn(r"const T = \[[^\]]*\];", "const T = [" + ",".join(f"{v:g}" for v in t) + "];", page)
        if n != 1:
            raise SystemExit(f"{args.embed}: expected one `const T = [...];`, found {n}")
        args.embed.write_text(page, encoding="utf-8")
        print(f"{len(t)} annual means written into {args.embed}")
    if args.trends:
        rows = [(y0 + s, y0 + s + L - 1, L, round(float(v), 4), round(float(H[L][s]), 4)) for L, b in B.items() for s, v in enumerate(b)]
        pd.DataFrame(rows, columns=["start", "end", "years", "trend_per_decade", "ci95_half_width"]).to_csv(args.trends, index=False)
        print(f"{len(rows):,} trends written to {args.trends}")
    draw(t.to_numpy(), B, y0, safe, args.out, {L: np.abs(B[L]) > H[L] for L in B} if args.fade else None)


if __name__ == "__main__":
    main()
