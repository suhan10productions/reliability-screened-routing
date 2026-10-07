"""Exploratory external benchmark on Solomon VRPTW instances.

Runs the unchanged two-stage pipeline (study_v6.run_instance, then
study_v7.run) on eight 100-customer Solomon instances (R101, R102, R103, R112,
RC104, RC105, RC106, RC108) with the paper's time-dependent profile and
disturbance model overlaid. The C1 instances are excluded: their horizon
(1236 time units) does not fit a single working shift.

Mapping (instance-level quantities come from Solomon; travel, disturbance and
statistical parameters stay as in the manuscript's Table 2):
  - coordinates are read as km; distances use the study's rounded Euclidean
    convention; the nominal planning speed stays 40 km/h;
  - one Solomon time unit = 1.5 minutes, so that Solomon's unit-speed travel
    time matches 40 km/h; ready and due times are scaled and floored;
  - service time 10 units -> 15 minutes; capacity 200 and 25 vehicles kept;
  - shift = scaled depot due time (345 min for R1, 360 min for RC1), starting
    at 06:00, so every route meets the 07:00-09:00 peak.
The frozen driver code is not modified: this script substitutes the instance
loader and the parameter constructor inside each worker process.

Solomon (1987); files from the ML4VRP 2024 competition repository
(github.com/ML4VRP/ML4VRP2024, Instances/cvrptw/txt).

Usage (from the package root):
  PYTHONPATH=code python code/solomon_benchmark.py --workers 6
  PYTHONPATH=code python code/solomon_benchmark.py --summarise
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
import study_v6
import study_v7
from relscreen_v6 import InstanceData

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "solomon"
OUT = ROOT / "results" / "solomon"
SCALE = 1.5
INSTANCES = {  # name -> pseudo-seed (outside every development and confirmatory range)
    "R101": 91101, "R102": 91102, "R103": 91103, "R112": 91112,
    "RC104": 92104, "RC105": 92105, "RC106": 92106, "RC108": 92108,
}
SEED_TO_NAME = {v: k for k, v in INSTANCES.items()}


def parse(name: str):
    rows = [l.split() for l in (DATA / f"{name}.txt").read_text(encoding="utf-8").replace("\r", "").split("\n")]
    vehicles, capacity = [int(x) for x in next(r for r in rows if len(r) == 2 and r[0].isdigit())]
    nodes = [list(map(int, r)) for r in rows if len(r) == 7 and r[0].isdigit()]
    return vehicles, capacity, nodes


def load(name: str):
    vehicles, capacity, nodes = parse(name)
    coords = tuple((x, y) for _, x, y, *_ in nodes)
    demands = tuple(n[3] for n in nodes)
    shift = int(math.floor(nodes[0][5] * SCALE))
    windows = [(0, shift)] + [(int(math.floor(n[4] * SCALE)), int(math.floor(n[5] * SCALE)))
                              for n in nodes[1:]]
    m = len(coords)
    distance = tuple(tuple(int(round(math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])))
                           for j in range(m)) for i in range(m))
    service = int(round(nodes[1][6] * SCALE))
    data = InstanceData(coords, demands, tuple(windows), distance, vehicles)
    return data, {"capacity": capacity, "service_minutes": service, "shift_length": shift}


def _patched_params_factory(overrides):
    base = relscreen_v6.ModelParams
    return lambda: replace(base(), **overrides)


def install(name: str):
    """Make the unchanged drivers build this Solomon instance and its parameters."""
    data, overrides = load(name)
    loader = lambda customers, vehicles, seed, *a, **k: data  # noqa: E731
    for mod in (study_v6, study_v7):
        mod.make_synthetic_instance = loader
        mod.ModelParams = _patched_params_factory(overrides)
    return data, overrides


def run_one(name: str, seconds: float, anchor_seconds: float,
            screen: int, validation: int) -> str:
    install(name)
    seed = INSTANCES[name]
    OUT.mkdir(parents=True, exist_ok=True)
    s1 = OUT / f"stage1_{name}.json"
    if not s1.exists():
        data, _ = load(name)
        record = study_v6.run_instance(100, data.num_vehicles, seed, seconds, anchor_seconds,
                                       screen, validation, range(0, 61, 5))
        record["solomon_instance"] = name
        s1.write_text(json.dumps({"schema": "routeops-v6-study-1",
                                  "environment": relscreen_v6.environment_metadata(),
                                  "records": [record], "software_errors": []}, indent=2))
    record = json.loads(s1.read_text())["records"][0]
    study_v7.run(record, str(OUT / "v7"), seconds)
    return name


def summarise():
    rows = {}
    for name, seed in INSTANCES.items():
        f = OUT / "v7" / f"instance_{seed}.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text())
        v = lambda c: (None if r["configurations"][c] is None
                       else round(100 * r["configurations"][c]["validation"]["service_level_success"], 1))
        rows[name] = {"nominal": v("nominal"), "conservative": v("conservative"), "slack": v("slack"),
                      "procedure": v("procedure"), "capped": v("capped_procedure"),
                      "procedure_selected": bool(r["old_failure_audit"]["selected"]),
                      "capped_selected": r["capped_procedure"]["selected_plan"] is not None,
                      "status": {k: s for k, s in r["configuration_status"].items() if s != "ok"}}
    print(json.dumps(rows, indent=2))
    (ROOT / "results" / "solomon_summary.json").write_text(json.dumps(rows, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--instances", nargs="*", default=list(INSTANCES))
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--anchor-seconds", type=float, default=2.0)
    ap.add_argument("--screen-scenarios", type=int, default=1000)
    ap.add_argument("--validation-scenarios", type=int, default=5000)
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        return summarise()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = [pool.submit(run_one, n, a.seconds, a.anchor_seconds, a.screen_scenarios,
                            a.validation_scenarios) for n in a.instances]
        for f in as_completed(futs):
            try:
                print("done:", f.result(), flush=True)
            except Exception as exc:  # reported at once, never silent
                print(f"ERROR: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
