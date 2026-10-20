"""Calibrate the delay model on real New York City taxi trips (exploratory).

Data: NYC Taxi & Limousine Commission yellow-taxi trip records, January to March
2024 (data/nyc/yellow_tripdata_2024-0{1,2,3}.parquet), public data from
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

The study's delay model (relscreen_v6) has three parts that were assumed:
  1. a time-of-day profile: travel times are multiplied by 0.9 before 07:00,
     1.2 from 07:00 to 09:00, 1.0 from 09:00 to 17:00, 1.3 from 17:00 to 19:00
     and 0.9 after 19:00;
  2. a log-normal factor exp(eps) on every trip with standard deviation sigma = 0.2;
  3. a share rho = 0.5 of the variance of eps that is common to every trip on the
     same day.
This script estimates each part from taxi trips.

Method
  - Weekday trips with valid zones, different pickup and drop-off zones, 0.5 to
    30 miles, 1 to 120 minutes and 1 to 60 mph. The time per mile ("pace") is
    used instead of the duration, so that trips of different length inside the
    same pair of zones are comparable.
  - A trip's period is the study's period containing its pickup time.
  - Profile: for every zone pair with at least 20 trips in both the period and
    the 09:00-17:00 reference, the difference of mean log pace; the multiplier is
    exp of the trip-weighted mean difference.
  - Residual: log pace minus the mean log pace of its zone pair and period (cells
    with at least 20 trips).
  - sigma: standard deviation of the residuals. Part of it is variation between
    addresses inside the same pair of zones, so a second, lower estimate keeps
    only the variation between days: the variance of zone-pair-and-day means,
    minus the part explained by the number of trips averaged.
  - rho: the variance of the day means of the residuals (all trips on a day)
    divided by the residual variance.

Usage (from the package root):
  python code/nyc_calibration.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "nyc"
MONTHS = ("2024-01", "2024-02", "2024-03")
PERIODS = ((0, 7), (7, 9), (9, 17), (17, 19), (19, 24))       # hours, as SpeedProfile.periods
ASSUMED = (0.9, 1.2, 1.0, 1.3, 0.9)
MIN_CELL = 20


def load() -> pd.DataFrame:
    frames = []
    for m in MONTHS:
        df = pd.read_parquet(DATA / f"yellow_tripdata_{m}.parquet",
                             columns=["tpep_pickup_datetime", "tpep_dropoff_datetime", "trip_distance",
                                      "PULocationID", "DOLocationID"])
        start = pd.Timestamp(m + "-01")
        df = df[(df.tpep_pickup_datetime >= start) & (df.tpep_pickup_datetime < start + pd.offsets.MonthBegin(1))]
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    n_raw = len(df)
    dur = (df.tpep_dropoff_datetime - df.tpep_pickup_datetime).dt.total_seconds() / 60
    mph = df.trip_distance / (dur / 60)
    keep = ((df.tpep_pickup_datetime.dt.dayofweek < 5) & df.PULocationID.between(1, 263) &
            df.DOLocationID.between(1, 263) & (df.PULocationID != df.DOLocationID) &
            df.trip_distance.between(0.5, 30) & dur.between(1, 120) & mph.between(1, 60))
    df = df[keep].copy()
    df["lp"] = np.log(dur[keep] / df.trip_distance)
    hour = df.tpep_pickup_datetime.dt.hour
    df["period"] = np.select([hour.between(a, b - 1) for a, b in PERIODS], range(len(PERIODS)))
    df["od"] = df.PULocationID.astype(np.int32) * 1000 + df.DOLocationID.astype(np.int32)
    df["day"] = df.tpep_pickup_datetime.dt.normalize()
    df.attrs["n_raw"] = n_raw
    return df[["od", "period", "day", "lp"]]


def main():
    df = load()
    out = {"source": "NYC TLC yellow taxi trip records, " + ", ".join(MONTHS), "trips_raw": int(df.attrs["n_raw"]),
           "trips_used": int(len(df)), "weekdays": int(df.day.nunique())}
    cell = df.groupby(["od", "period"]).lp.agg(["mean", "count"])
    # 1. profile, relative to 09:00-17:00
    ref = cell.xs(2, level="period")
    mult = []
    for p in range(len(PERIODS)):
        if p == 2:
            mult.append({"multiplier": 1.0, "zone_pairs": int((ref["count"] >= MIN_CELL).sum())})
            continue
        c = cell.xs(p, level="period").join(ref, lsuffix="_p", rsuffix="_r", how="inner")
        c = c[(c.count_p >= MIN_CELL) & (c.count_r >= MIN_CELL)]
        w = np.minimum(c.count_p, c.count_r)
        diff = float(np.average(c.mean_p - c.mean_r, weights=w))
        mult.append({"multiplier": float(np.exp(diff)), "zone_pairs": int(len(c))})
    out["profile"] = [{"from_hour": a, "to_hour": b, "assumed": ASSUMED[i], **mult[i]}
                      for i, (a, b) in enumerate(PERIODS)]
    # 2. residuals within well-populated cells
    good = cell[cell["count"] >= MIN_CELL]
    d = df.join(good["mean"].rename("cell_mean"), on=["od", "period"], how="inner")
    d["r"] = d.lp - d.cell_mean
    var_r = float(d.r.var())
    out["residual_trips"] = int(len(d))
    out["sigma_total"] = float(np.sqrt(var_r))
    # between-day variation of a fixed zone pair (removes address and trip-to-trip noise)
    g = d.groupby(["od", "period", "day"]).r.agg(["mean", "var", "count"])
    g = g[g["count"] >= 5]
    var_between = float(g["mean"].var() - np.mean(g["var"] / g["count"]))
    out["sigma_between_days"] = float(np.sqrt(max(var_between, 0.0)))
    # 3. day-common share
    day_means = d.groupby("day").r.agg(["mean", "count"])
    var_day = float(day_means["mean"].var() - var_r / day_means["count"].mean())
    out["day_effect_sd"] = float(np.sqrt(max(var_day, 0.0)))
    out["rho_total"] = var_day / var_r
    out["rho_between_days"] = var_day / var_between if var_between > 0 else None
    out["assumed"] = {"sigma": 0.20, "rho": 0.50}
    (ROOT / "results" / "nyc_calibration.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
