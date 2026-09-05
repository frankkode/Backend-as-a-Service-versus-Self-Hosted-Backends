#!/usr/bin/env python3
"""
Aggregate measured operational-task durations into a monthly effort figure per variant
(thesis Section 3.5 / 5.3).

Reads : results/ops_effort_log.csv   (produced by scripts/measure_ops_effort.sh)
Writes: results/ops_effort_summary.csv

Method
------
monthly_minutes(task) = mean(measured durations for that task) x assumed monthly frequency

Durations are MEASURED. Frequencies are ASSUMED, and each assumption is stated with its
justification below so the thesis can cite exactly which half of the calculation is
empirical and which is not. Change FREQUENCIES if your deployment cadence differs --
do not change them to make a result come out.

Usage:
  python3 scripts/aggregate_ops_effort.py
  python3 scripts/aggregate_ops_effort.py --rate-eur-per-hour 68.75
"""

import argparse
import csv
import os
import statistics
from collections import defaultdict

LOG = "results/ops_effort_log.csv"
OUT = "results/ops_effort_summary.csv"

# task_id -> (times per month, justification for that cadence)
FREQUENCIES = {
    "os_patching": (
        1.0,
        "Monthly patch window. Ubuntu LTS ships security updates continuously; a monthly "
        "supervised window is the common small-operator practice.",
    ),
    "image_update": (
        1.0,
        "Monthly. Tracks the base-image release cadence for postgres/nginx/python official images.",
    ),
    "backup_run": (
        4.33,
        "Weekly (52/12). Nightly automated dumps are unattended; the weekly figure counts the "
        "supervised run only.",
    ),
    "backup_verify": (
        1.0,
        "Monthly restore test. An unverified backup is not a backup; monthly is the usual "
        "minimum recommended cadence.",
    ),
    "health_check": (
        4.33,
        "Weekly (52/12). Routine service/disk/log inspection.",
    ),
    "dependency_triage": (
        1.0,
        "Monthly. Reviewing outdated packages and advisories.",
    ),
    "tls_renewal": (
        0.33,
        "Every 3 months. Let's Encrypt certificates last 90 days; renewal is automated but "
        "supervised/verified quarterly.",
    ),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--rate-eur-per-hour",
        type=float,
        default=68.75,
        help="Hourly rate for costing (default 68.75 = EUR550/day over an 8h day, Section 3.5).",
    )
    args = ap.parse_args()

    if not os.path.exists(LOG):
        raise SystemExit(f"No measurement log at {LOG}. Run scripts/measure_ops_effort.sh first.")

    runs = defaultdict(list)  # (variant, task) -> [minutes]
    with open(LOG) as f:
        for row in csv.DictReader(f):
            try:
                runs[(row["variant"], row["task_id"])].append(float(row["duration_minutes"]))
            except (KeyError, ValueError):
                continue

    if not runs:
        raise SystemExit(f"{LOG} has no usable rows yet.")

    variants = sorted({v for v, _ in runs})
    rows_out = []
    totals = {}

    for variant in variants:
        total_min = 0.0
        print(f"\n=== {variant} ===")
        print(f"{'task':<20}{'n':>3}{'mean min':>10}{'sd':>8}{'freq/mo':>9}{'min/mo':>9}")
        for task, (freq, _just) in FREQUENCIES.items():
            durations = runs.get((variant, task), [])
            if not durations:
                continue
            mean = statistics.mean(durations)
            sd = statistics.stdev(durations) if len(durations) > 1 else 0.0
            monthly = mean * freq
            total_min += monthly
            print(f"{task:<20}{len(durations):>3}{mean:>10.2f}{sd:>8.2f}{freq:>9.2f}{monthly:>9.1f}")
            rows_out.append(
                {
                    "variant": variant,
                    "task_id": task,
                    "n_measurements": len(durations),
                    "mean_minutes": round(mean, 2),
                    "sd_minutes": round(sd, 2),
                    "assumed_freq_per_month": freq,
                    "monthly_minutes": round(monthly, 1),
                }
            )
        hrs = total_min / 60.0
        totals[variant] = hrs
        print(f"{'TOTAL':<20}{'':>3}{'':>10}{'':>8}{'':>9}{total_min:>9.1f}  = {hrs:.2f} h/month"
              f"  = EUR{hrs * args.rate_eur_per_hour:,.0f}/month")

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "variant",
                "task_id",
                "n_measurements",
                "mean_minutes",
                "sd_minutes",
                "assumed_freq_per_month",
                "monthly_minutes",
            ],
        )
        w.writeheader()
        w.writerows(rows_out)

    print(f"\nWrote {OUT}")

    if len(totals) == 2 and "django" in totals and "supabase" in totals:
        d, s = totals["django"], totals["supabase"]
        print(
            f"\nMeasured operational effort: Django {d:.2f} h/month vs Supabase {s:.2f} h/month "
            f"(difference {d - s:+.2f} h/month, "
            f"EUR{(d - s) * args.rate_eur_per_hour:,.0f}/month at the stated rate)."
        )
        print(
            "Compare against the estimates currently in Section 3.5 (Django ~4-8 h/month, "
            "Supabase ~1 h/month) and report the measured figures instead, noting any divergence."
        )

    print(
        "\nFrequency assumptions used (durations are measured; these cadences are not):"
    )
    for task, (freq, just) in FREQUENCIES.items():
        print(f"  - {task}: {freq}/month. {just}")


if __name__ == "__main__":
    main()
