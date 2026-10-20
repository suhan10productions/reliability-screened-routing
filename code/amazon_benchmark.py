"""Exploratory check on real delivery routes: Amazon Last Mile Routing Research Challenge.

Data: the training set of the 2021 Amazon Last Mile Routing Research Challenge
(CC BY-NC 4.0), sampled by data/amazon/extract_amazon_sample.py into
data/amazon/amazon_sample.json.gz (60 routes scored "High" by Amazon, at most
five per station, fixed seed). Each Amazon route is the work of one van: a
station, about 150 stops, Amazon's travel time between every pair of stops,
the planned service time of every package and the sequence the driver actually
drove.

What is real and what is assumed
  real:    stop locations, travel times between stops, service times, package
           volumes, van capacity, departure time, the driver's actual order;
  assumed: the two-hour delivery windows, the delay model and the time-of-day
           congestion profile (both as in the main study), the fleet of three vans.

Building an instance from a route
  1. Stops are taken in the driver's actual order. A run of consecutive stops in
     the same Amazon zone becomes one customer (a zone visited twice gives two
     customers). The frozen solver rounds each trip up to a whole minute, which
     would add more than an hour to a route of 150 stops less than a minute
     apart; at zone level the trips are several minutes long.
  2. A customer's service time is the time from arriving at its first stop to
     leaving its last stop: the stops' planned service times plus the real
     travel between them. The frozen code has one service time for all
     customers, so each customer's service time is added to the trips leaving it
     (service_minutes = 0); service therefore receives the same random delays as
     driving.
  3. Travel from customer i to customer j is Amazon's time from the last stop of
     i to the first stop of j. Times are converted to distances at the nominal
     40 km/h, so that a nominal plan reproduces Amazon's times.
  4. Driving the actual order at these times from the departure gives an arrival
     time at every customer. Each customer is offered a two-hour window that
     contains that arrival, placed uniformly at random around it (fixed seed),
     as a grocery or parcel service offering two-hour slots would.
  5. The shift starts at the route's real local departure time, so the morning
     and evening congestion periods fall at their real clock times. The shift
     lasts 1.3 times the actual route duration. Three vans of the real capacity
     are available; demand is package volume.

The unchanged OR-Tools pipeline (study_v6.run_instance, then study_v7.run) is
run on each instance, exactly as for the Solomon check. The first 40 sampled
routes are used; the other 20 are spares and were not run.

Delay model (--delay)
  assumed     the study's model (default; results/amazon, results/amazon_summary.json);
  nyc_days    calibrated on New York taxi trips (code/nyc_calibration.py): the measured
              time-of-day profile, sigma from the between-day variation of a fixed
              zone pair and rho relative to it;
  nyc_total   the same profile, sigma from all trip-to-trip variation and rho relative
              to it.
  Results go to results/amazon_<delay> and results/amazon_summary_<delay>.json.

Usage (from the package root):
  PYTHONPATH=code python code/amazon_benchmark.py --workers 4 [--delay nyc_days]
  PYTHONPATH=code python code/amazon_benchmark.py --summarise [--delay nyc_days]
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np

import relscreen_v6
import study_v6
import study_v7
from relscreen_v6 import InstanceData

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "amazon" / "amazon_sample.json.gz"
OUT = ROOT / "results" / "amazon"
DELAY = "assumed"


def set_delay(name: str):
    global OUT, DELAY
    DELAY = name
    OUT = ROOT / "results" / ("amazon" if name == "assumed" else f"amazon_{name}")


def delay_settings(name: str):
    """(params overrides, profile multipliers or None) for a delay model."""
    if name == "assumed":
        return {}, None
    cal = json.loads((ROOT / "results" / "nyc_calibration.json").read_text())
    mult = tuple(round(p["multiplier"], 4) for p in cal["profile"])
    if name == "nyc_days":
        return {"sigma": round(cal["sigma_between_days"], 4), "rho_log": round(cal["rho_between_days"], 4)}, mult
    if name == "nyc_total":
        return {"sigma": round(cal["sigma_total"], 4), "rho_log": round(cal["rho_total"], 4)}, mult
    raise ValueError(name)
N_USED = 40
SEED_BASE = 95_000            # pseudo-seeds 95001 ... outside every other study's range
WINDOW = 120                  # minutes
FLEET = 3
SHIFT_FACTOR = 1.3
KMH = 40.0
# UTC offsets in July and August 2018 (daylight saving time)
UTC_OFFSET = {"DLA": -7, "DSE": -7, "DCH": -5, "DAU": -5, "DBO": -4}


@lru_cache(maxsize=1)
def sample():
    return json.loads(gzip.open(DATA).read())


def route_ids():
    return sorted(sample()["routes"])[:N_USED]


def build(rid: str, seed: int):
    r = sample()["routes"][rid]
    S, T, P = r["route"]["stops"], r["travel_seconds"], r["stops"]
    order = sorted(r["actual_sequence"], key=r["actual_sequence"].get)
    station = order[0]
    assert S[station]["type"] == "Station"
    blocks = []
    for s in order[1:]:
        z = S[s]["zone_id"]
        z = ("?" + s) if not isinstance(z, str) else z
        if blocks and blocks[-1][0] == z:
            blocks[-1][1].append(s)
        else:
            blocks.append((z, [s]))
    first = [station] + [b[1][0] for b in blocks]
    last = [station] + [b[1][-1] for b in blocks]
    service = [0.0] + [sum(P[s]["service_seconds"] for s in b[1]) + sum(T[a][c] for a, c in zip(b[1], b[1][1:]))
                       for b in blocks]
    n = len(first)
    minutes = [[0.0 if i == j else (service[i] + T[last[i]][first[j]]) / 60.0 for j in range(n)] for i in range(n)]
    distance = tuple(tuple(round(m * KMH / 60.0, 3) for m in row) for row in minutes)
    # arrival times along the driver's actual order at the nominal times
    arrival, now = [0.0], 0.0
    for k in range(1, n):
        now += minutes[k - 1][k]
        arrival.append(now)
    duration = now + minutes[n - 1][0]
    shift = int(math.ceil(SHIFT_FACTOR * duration))
    rng = np.random.default_rng(seed)
    windows = [(0, shift)]
    for k in range(1, n):
        lo = int(math.floor(arrival[k] - rng.uniform(0, WINDOW)))
        lo = min(max(0, lo), shift - WINDOW)
        windows.append((lo, lo + WINDOW))
    demands = tuple([0] + [int(math.ceil(sum(P[s]["volume_cm3"] for s in b[1]) / 1000.0)) for b in blocks])
    capacity = int(r["route"]["executor_capacity_cm3"] // 1000)
    lat0, lng0 = S[station]["lat"], S[station]["lng"]
    coords = tuple((int(round((S[f]["lng"] - lng0) * 92.0)), int(round((S[f]["lat"] - lat0) * 111.0))) for f in first)
    dep = datetime.fromisoformat(r["route"]["date_YYYY_MM_DD"] + " " + r["route"]["departure_time_utc"])
    local_minute = (dep.hour * 60 + dep.minute + 60 * UTC_OFFSET[r["route"]["station_code"][:3]]) % 1440
    data = InstanceData(coords, demands, tuple(windows), distance, FLEET)
    overrides = {"capacity": capacity, "service_minutes": 0, "shift_length": shift,
                 "shift_start_minute": int(local_minute)}
    info = {"route_id": rid, "station": r["route"]["station_code"], "date": r["route"]["date_YYYY_MM_DD"],
            "stops": len(order) - 1, "customers": n - 1, "actual_duration_minutes": duration,
            "local_departure": f"{local_minute // 60:02d}:{local_minute % 60:02d}"}
    return data, overrides, info


def _patched_params_factory(overrides):
    base = relscreen_v6.ModelParams
    return lambda: replace(base(), **overrides)


def install(rid: str, seed: int):
    data, overrides, info = build(rid, seed)
    extra, mult = delay_settings(DELAY)
    overrides = {**overrides, **extra}
    loader = lambda customers, vehicles, s, *a, **k: data  # noqa: E731
    for mod in (study_v6, study_v7):
        mod.make_synthetic_instance = loader
        mod.ModelParams = _patched_params_factory(overrides)
        if mult is not None:
            mod.SpeedProfile = lambda m=mult: relscreen_v6.SpeedProfile(congestion_multiplier=m)
    info = {**info, "delay_model": DELAY, "profile_multipliers": mult}
    return data, overrides, info


def run_one(k: int, seconds: float, anchor_seconds: float, screen: int, validation: int,
            delay: str = "assumed") -> str:
    set_delay(delay)
    rid = route_ids()[k]
    seed = SEED_BASE + k + 1
    data, overrides, info = install(rid, seed)
    OUT.mkdir(parents=True, exist_ok=True)
    s1 = OUT / f"stage1_{seed}.json"
    if not s1.exists():
        record = study_v6.run_instance(data.num_customers, data.num_vehicles, seed, seconds, anchor_seconds,
                                       screen, validation, range(0, 61, 5))
        record["amazon"] = info
        record["amazon_overrides"] = overrides
        s1.write_text(json.dumps({"schema": "routeops-v6-study-1",
                                  "environment": relscreen_v6.environment_metadata(),
                                  "records": [record], "software_errors": []}, indent=2))
    record = json.loads(s1.read_text())["records"][0]
    study_v7.run(record, str(OUT / "v7"), seconds)
    return rid


def boot(x, seed=20261019, n=20000):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return [float(x.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def summarise():
    rows = []
    for k, rid in enumerate(route_ids()):
        seed = SEED_BASE + k + 1
        f = OUT / "v7" / f"instance_{seed}.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text())
        info = json.loads((OUT / f"stage1_{seed}.json").read_text())["records"][0]["amazon"]
        c = r["configurations"]
        v = lambda name: 0.0 if c.get(name) is None else 100 * c[name]["validation"]["service_level_success"]  # noqa: E731
        rows.append({"seed": seed, **info, "nominal": v("nominal"), "conservative": v("conservative"),
                     "procedure": v("procedure"), "capped": v("capped_procedure"),
                     "screened_conservative": v("screened_conservative"),
                     "screened_conservative_selected": r["screened_conservative"]["selected_plan"] is not None,
                     "has_nominal": c.get("nominal") is not None,
                     "has_conservative": c.get("conservative") is not None,
                     # vans used (the distance metric also contains the folded-in service time, so it is not reported)
                     "fleet_conservative": None if c.get("conservative") is None else c["conservative"]["plan"]["metrics"]["fleet"],
                     "fleet_capped": None if c.get("capped_procedure") is None else c["capped_procedure"]["plan"]["metrics"]["fleet"],
                     "capped_selected": r["capped_procedure"]["selected_plan"] is not None,
                     "status": {k2: s for k2, s in r["configuration_status"].items() if s != "ok"}})
    out = {"instances": len(rows), "rows": rows}
    if rows:
        out["pooled"] = {m: boot([x[m] for x in rows]) for m in ("nominal", "conservative", "procedure", "capped", "screened_conservative")}
        out["plans"] = {"nominal": sum(x["has_nominal"] for x in rows), "conservative": sum(x["has_conservative"] for x in rows)}
        out["screened_conservative_minus_conservative"] = boot([x["screened_conservative"] - x["conservative"] for x in rows])
        out["screened_conservative_admitted"] = sum(x["screened_conservative_selected"] for x in rows)
        adm = [x for x in rows if x["capped_selected"]]
        out["capped_admitted_at_least_95"] = sum(x["capped"] >= 95 for x in adm)
        out["capped_on_admitted"] = float(np.mean([x["capped"] for x in adm])) if adm else None
        rest = [x for x in rows if not x["capped_selected"] and x["has_nominal"]]
        out["fallback_instances"] = len(rest)
        out["capped_on_fallback"] = float(np.mean([x["capped"] for x in rest])) if rest else None
        out["conservative_on_fallback"] = float(np.mean([x["conservative"] for x in rest])) if rest else None
        sca = [x for x in rows if x["screened_conservative_selected"]]
        out["screened_conservative_on_admitted"] = float(np.mean([x["screened_conservative"] for x in sca])) if sca else None
        out["capped_minus_conservative"] = boot([x["capped"] - x["conservative"] for x in rows])
        both = [x for x in rows if x["has_conservative"]]
        out["capped_minus_conservative_where_planned"] = boot([x["capped"] - x["conservative"] for x in both]) if both else None
        out["where_planned"] = len(both)
        fl = [x for x in both if x["fleet_capped"] is not None]
        out["fleet_capped_minus_conservative"] = boot([x["fleet_capped"] - x["fleet_conservative"] for x in fl]) if fl else None
        out["by_station_city"] = {}
        for city in sorted({x["station"][:3] for x in rows}):
            sub = [x for x in rows if x["station"][:3] == city]
            out["by_station_city"][city] = {"instances": len(sub), "capped": float(np.mean([x["capped"] for x in sub])),
                                            "conservative": float(np.mean([x["conservative"] for x in sub]))}
        out["admitted"] = sum(x["capped_selected"] for x in rows)
    # Amazon's own delivery windows on the routes used (why two-hour windows were assumed)
    widths, windowed, total = [], 0, 0
    for rid in route_ids():
        for stop in sample()["routes"][rid]["stops"].values():
            total += 1
            tws = [(datetime.fromisoformat(a), datetime.fromisoformat(b)) for a, b in stop["time_windows"]]
            if tws:
                windowed += 1
                widths.append((min(t[1] for t in tws) - max(t[0] for t in tws)).total_seconds() / 3600)
    out["amazon_windows"] = {"stops": total, "stops_with_window": windowed,
                             "width_hours_quartiles": [float(q) for q in np.quantile(widths, [0.25, 0.5, 0.75])]}
    nop = [x["customers"] for x in rows if not x["has_nominal"]]
    out["no_plan_customers"] = [min(nop), max(nop)] if nop else None
    out["cities"] = len({x["station"][:3] for x in rows})
    out["delay_model"] = DELAY
    (ROOT / "results" / ("amazon_summary.json" if DELAY == "assumed" else f"amazon_summary_{DELAY}.json")).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--only", type=int, nargs="*")
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--anchor-seconds", type=float, default=2.0)
    ap.add_argument("--screen-scenarios", type=int, default=1000)
    ap.add_argument("--validation-scenarios", type=int, default=5000)
    ap.add_argument("--summarise", action="store_true")
    ap.add_argument("--delay", choices=("assumed", "nyc_days", "nyc_total"), default="assumed")
    a = ap.parse_args()
    set_delay(a.delay)
    if a.summarise:
        return summarise()
    ks = a.only if a.only is not None else list(range(N_USED))
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_one, k, a.seconds, a.anchor_seconds, a.screen_scenarios,
                            a.validation_scenarios, a.delay): k for k in ks}
        for f in as_completed(futs):
            k = futs[f]
            try:
                print(f"done {k} {f.result()}", flush=True)
            except Exception as exc:  # recorded, the run continues
                print(f"ERROR {k}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
