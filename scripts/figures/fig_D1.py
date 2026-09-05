#!/usr/bin/env python3
"""Regenerate Figure D.1: criteria assessment outcome distribution per variant.

Derived directly from results/criteria_catalog.csv so the figure cannot drift from the catalog.
One slice per criterion, n = 88, no double counting. Run from the repo root:

    python3 scripts/figures/fig_D1.py

No baked-in title: the caption lives in the thesis document, not in the image.
"""
import csv, math, os
from collections import Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV = os.path.join(REPO, "results", "criteria_catalog.csv")
OUT = os.path.join(REPO, "results", "fig_D1.png")

ORDER = ["Satisfied", "Partial", "Not satisfied", "N/A", "Not verified", "Other"]
HATCH = {"Satisfied": "", "Partial": "//", "Not satisfied": "xx", "N/A": "..",
         "Not verified": "||", "Other": "\\\\"}
FACE  = {"Satisfied": "#f7f7f7", "Partial": "#d9d9d9", "Not satisfied": "#8c8c8c",
         "N/A": "#efefef", "Not verified": "#ffffff", "Other": "#c0c0c0"}


def bucket(raw):
    s = raw.strip().lower()
    if s.startswith("satisfied"):
        return "Satisfied"
    if s.startswith("partial"):
        return "Partial"
    if s.startswith("not satisfied"):
        return "Not satisfied"
    if s.startswith("n/a") or s.startswith("not applicable"):
        return "N/A"
    if "not verified" in s or "not assessed" in s or "not testable" in s:
        return "Not verified"
    return "Other"          # the four effort/cost rows carry descriptive values, not scores


def main():
    rows = list(csv.DictReader(open(CSV)))
    counts = {v: Counter(bucket(r[f"{v}_score"]) for r in rows)
              for v in ("supabase", "django")}

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.5})
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 5.2))

    for ax, (var, label) in zip(axes, [("supabase", "Supabase"),
                                       ("django", "Django/PostgreSQL")]):
        c = counts[var]
        keys = [k for k in ORDER if c[k]]
        vals = [c[k] for k in keys]
        total = sum(vals)
        # Label big slices inside the wedge; small ones would collide there, so they get an
        # outside label with a leader line instead. Every slice is labelled either way.
        wedges, _, autotexts = ax.pie(
            vals, startangle=90, counterclock=False,
            colors=[FACE[k] for k in keys],
            autopct=lambda p: f"{p:.0f}%" if p >= 8 else "",
            pctdistance=0.66,
            wedgeprops={"edgecolor": "#111111", "linewidth": 1.1},
            textprops={"fontsize": 11.5, "fontweight": "bold"},
        )
        for w, k in zip(wedges, keys):
            w.set_hatch(HATCH[k])
        for t in autotexts:
            t.set_bbox(dict(facecolor="white", edgecolor="none", alpha=0.8, pad=1.6))

        for w, v in zip(wedges, vals):
            pct = 100.0 * v / total
            if pct >= 8:
                continue
            ang = math.radians((w.theta1 + w.theta2) / 2.0)
            x, y = math.cos(ang), math.sin(ang)
            ax.annotate(
                f"{pct:.0f}%", xy=(0.92 * x, 0.92 * y), xytext=(1.30 * x, 1.30 * y),
                ha="left" if x >= 0 else "right", va="center",
                fontsize=11, fontweight="bold",
                arrowprops=dict(arrowstyle="-", lw=0.9, color="#333333",
                                shrinkA=0, shrinkB=2),
            )
        ax.set_title(f"{label}\n(n = {sum(vals)} criteria)", fontsize=12.5,
                     fontweight="bold", pad=14)

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=FACE[k], edgecolor="#111111",
                             hatch=HATCH[k], linewidth=1.0) for k in ORDER]
    fig.legend(handles, ORDER, loc="lower center", ncol=6, frameon=False,
               fontsize=10.5, bbox_to_anchor=(0.5, 0.005))
    fig.subplots_adjust(left=0.06, right=0.94, top=0.85, bottom=0.14, wspace=0.16)
    fig.savefig(OUT, dpi=200, facecolor="white")

    print(f"wrote {OUT}")
    for v in ("supabase", "django"):
        tot = sum(counts[v].values())
        line = ", ".join(f"{k} {counts[v][k]}" for k in ORDER if counts[v][k])
        print(f"  {v:<9} n={tot}: {line}")


if __name__ == "__main__":
    main()
