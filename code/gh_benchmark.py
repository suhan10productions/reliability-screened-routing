"""Exploratory external check on Gehring–Homberger 200-customer instances.

Runs the unchanged HGS pipeline of the second confirmatory study
(study_hgs.run_instance) on the twenty R1 and RC1 instances with 200 customers
(data/gh200), with the paper's time-dependent profile and disturbance model
added. The C1 and type-2 classes are excluded: their horizons are much longer
than one working shift.

Mapping (instance quantities come from the benchmark; travel, disturbance and
statistical parameters stay as in the manuscript's Table 2):
  - the depot horizon (634 time units) becomes the 600-minute shift starting at
    06:00, so one time unit = 600/634 minutes; ready and due times are scaled
    and floored, and the service time of 10 units becomes 9 minutes;
  - one coordinate unit = (600/634) * (40/60) km, so that the benchmark's
    unit-speed travel corresponds to the nominal planning speed of 40 km/h;
    distances use the study's rounded Euclidean convention (whole km);
  - capacity 200 and the fleet of 50 vehicles are kept.
The frozen driver code is not modified: this script substitutes the instance
loader, the parameter constructor and the fleet size inside each worker
process, as code/solomon_benchmark.py does for the Solomon check.

Pseudo-seeds (outside every other study's range) fix the scenario banks:
93200 + k for R1_2_k and 94200 + k for RC1_2_k. The screening bank uses seed
100000 + pseudo-seed and the validation bank 400000 + pseudo-seed.

Usage (from the package root):
  PYTHONPATH=code python code/gh_benchmark.py --workers 2
  PYTHONPATH=code python code/gh_benchmark.py --summarise
"""
from __future__ import annotations

import argparse
import json
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import numpy as np

import relscreen_v6
import study_hgs
from analyse_robust import boot
from relscreen_v6 import InstanceData

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "gh200"
OUT = ROOT / "results" / "gh200"
SHIFT = 600
INSTANCES = {**{f"R1_2_{k}": 93200 + k for k in range(1, 11)},
             **{f"RC1_2_{k}": 94200 + k for k in range(1, 11)}}


def parse(name: str):
    head, sections, sec = {}, {}, None
    for line in (DATA / f"{name}.vrp").read_text().splitlines():
        line = line.strip()
        if not line or line == "EOF":
            continue
        if line.endswith("SECTION"):
            sec = line
            sections[sec] = []
        elif ":" in line and not line[0].isdigit():
            k, v = line.split(":", 1)
            head[k.strip()] = v.strip()
        else:
            sections[sec].append([int(x) for x in line.split()])
    return head, sections


def load(name: str):
    head, s = parse(name)
    horizon = s["TIME_WINDOW_SECTION"][0][2]
    t = SHIFT / horizon                      # minutes per time unit
    km = t * 40.0 / 60.0                     # km per coordinate unit at 40 km/h
    coords = [(x, y) for _, x, y in s["NODE_COORD_SECTION"]]
    demands = tuple(d for _, d in s["DEMAND_SECTION"])
    windows = tuple((int(math.floor(a * t)), int(math.floor(b * t))) for _, a, b in s["TIME_WINDOW_SECTION"])
    m = len(coords)
    distance = tuple(tuple(int(round(km * math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])))
                           for j in range(m)) for i in range(m))
    km_coords = tuple((round(km * x, 3), round(km * y, 3)) for x, y in coords)
    data = InstanceData(km_coords, demands, windows, distance, int(head["VEHICLES"]))
    overrides = {"capacity": int(head["CAPACITY"]), "service_minutes": int(round(int(head["SERVICE_TIME"]) * t)),
                 "shift_length": SHIFT}
    return data, overrides


def install(name: str):
    data, overrides = load(name)
    study_hgs.make_synthetic_instance = lambda customers, vehicles, seed, *a, **k: data
    base = relscreen_v6.ModelParams
    study_hgs.ModelParams = lambda: replace(base(), **overrides)
    study_hgs.DESIGN = {200: (data.num_vehicles, 1, INSTANCES[name])}
    return data, overrides


def run_one(name: str) -> str:
    path = OUT / f"instance_{INSTANCES[name]}.json"
    if path.exists():
        return f"{name} exists"
    data, overrides = install(name)
    rec = study_hgs.run_instance(200, INSTANCES[name], study_hgs.DEFAULT_ITERATIONS)
    rec.update({"gh_instance": name, "mapping": {"minutes_per_time_unit": SHIFT / 634,
                                                  "km_per_coordinate_unit": SHIFT / 634 * 40 / 60,
                                                  **overrides}})
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec))
    return f"{name} selected={rec['selected']} status={rec['configuration_status']}"


def summarise():
    rows = {}
    for name, seed in INSTANCES.items():
        f = OUT / f"instance_{seed}.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text())
        v = lambda c: (None if r["configurations"][c] is None
                       else 100 * r["configurations"][c]["validation"]["service_level_success"])
        rows[name] = {"anchors": r["configuration_status"]["anchors"], "admitted": r["selected"].get("capped"),
                      **{c: v(c) for c in ("hgs_nominal", "hgs_conservative", "hgs_capped_cons", "hgs_capped_slack")}}
    both = [x for x in rows.values() if x["hgs_conservative"] is not None and x["hgs_capped_cons"] is not None]
    summary = {"instances": len(rows), "anchors_ok": sum(x["anchors"] == "ok" for x in rows.values()),
               "admitted": sum(bool(x["admitted"]) for x in rows.values()),
               "capped_cons_minus_conservative": boot([x["hgs_capped_cons"] - x["hgs_conservative"] for x in both]) if both else None,
               "pooled": {c: float(np.mean([x[c] or 0.0 for x in rows.values()]))
                          for c in ("hgs_nominal", "hgs_conservative", "hgs_capped_cons")},
               "rows": rows}
    (ROOT / "results/gh200_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--names", nargs="*", default=list(INSTANCES))
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        return summarise()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_one, n): n for n in a.names}
        for f in as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception as exc:  # recorded, never scored
                print(f"{futs[f]} SOFTWARE ERROR: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
