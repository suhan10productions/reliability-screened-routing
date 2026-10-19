"""Exploratory padding sweep on the development instances.

The paper compares the screened procedures with one padding level, 20% (planning
at 40/1.2 km/h). A fair comparison asks what padding costs at the reliability the
screened procedure reaches. This script plans every development instance for
distance at padding levels of 0, 10, 20, 30, 40 and 50% (planning speed
40/(1+p) km/h), with the same OR-Tools budget as the conservative-speed
configuration (5 s, up to three attempts), and evaluates each plan on the
instance's 5000-scenario validation bank, the bank every stored configuration
was validated on. No plan is screened; padding is applied as an operator would.
A level that returns no plan scores zero, as in the main studies.

The levels were fixed before the run. Results are exploratory.

Usage (from the package root):
  PYTHONPATH=code python code/padding_sweep.py --workers 2
  PYTHONPATH=code python code/padding_sweep.py --summarise
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from relscreen_v6 import ModelParams, RoutingSolver, ScenarioBank, SpeedProfile, make_synthetic_instance
from relscreen_v7 import evaluate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "padding_sweep"
LEVELS = (0, 10, 20, 30, 40, 50)          # percent padding of every planned trip


def stage1_records():
    recs = {}
    for n in (20, 50, 100, 200):
        for r in json.loads((ROOT / f"results/study_v6_n{n}.json").read_text())["records"]:
            recs[r["instance_seed"]] = r
    return recs


def run_task(record: dict, level: int, seconds: float) -> dict:
    seed, n = record["instance_seed"], record["customers"]
    path = OUT / f"pad{level:02d}_{seed}.json"
    if path.exists():
        return json.loads(path.read_text())
    started = time.perf_counter()
    params, profile = ModelParams(), SpeedProfile()
    data = make_synthetic_instance(n, record["vehicles_available"], seed)
    speed = params.nominal_speed_kmh / (1 + level / 100)
    plan = None
    attempts = 0
    for attempts in range(1, 4):
        plan = RoutingSolver(data, params, planning_speed_kmh=speed).solve("distance", seconds)
        if plan is not None:
            break
    bank = ScenarioBank(5000, 400_000 + seed, params)
    validation = None if plan is None else evaluate(plan, data, params, profile, bank)
    result = {
        "schema": "relscreen-padding-sweep-1", "instance_seed": seed, "customers": n,
        "padding_percent": level, "planning_speed_kmh": speed, "attempts": attempts,
        "has_plan": plan is not None,
        "metrics": None if plan is None else plan.metrics,
        "service": 0.0 if validation is None else validation["service_level_success"],
        "validation": validation, "candidate_seconds": seconds,
        "elapsed_seconds": time.perf_counter() - started, "machine": platform.platform(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1))
    return result


def boot(x, seed=20260930, n=20000):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return [float(x.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def summarise():
    recs = stage1_records()
    seeds = sorted(s for s in recs if recs[s]["reference_ranges"])
    stored = {s: json.loads((ROOT / f"results/v7/instance_{s}.json").read_text()) for s in seeds}
    rows = {}
    for lv in LEVELS:
        rows[lv] = {s: json.loads((OUT / f"pad{lv:02d}_{s}.json").read_text()) for s in seeds}
    cap = {s: stored[s]["configurations"]["capped_procedure"] for s in seeds}
    cap_service = {s: 100 * cap[s]["validation"]["service_level_success"] for s in seeds}
    out = {"instances": len(seeds), "levels": {}, "capped": {}}
    out["capped"] = {"pooled_service": float(np.mean(list(cap_service.values()))),
                     "pooled_service_ci": boot(list(cap_service.values())),
                     "mean_fleet": float(np.mean([cap[s]["plan"]["metrics"]["fleet"] for s in seeds])),
                     "mean_distance": float(np.mean([cap[s]["plan"]["metrics"]["distance"] for s in seeds]))}
    for lv in LEVELS:
        r = rows[lv]
        both = [s for s in seeds if r[s]["has_plan"]]
        out["levels"][lv] = {
            "with_plan": len(both),
            "pooled_service": float(np.mean([100 * r[s]["service"] for s in seeds])),
            "pooled_service_ci": boot([100 * r[s]["service"] for s in seeds]),
            "service_minus_capped": boot([100 * r[s]["service"] - cap_service[s] for s in seeds]),
            # cost on the instances where the padded plan exists (capped has a plan on all)
            "distance_vs_capped_pct": boot([100 * (r[s]["metrics"]["distance"] / cap[s]["plan"]["metrics"]["distance"] - 1)
                                            for s in both]) if both else None,
            "fleet_minus_capped": boot([r[s]["metrics"]["fleet"] - cap[s]["plan"]["metrics"]["fleet"]
                                        for s in both]) if both else None,
            # only the instances where the padded plan exists: no failure is scored as zero
            "service_on_plans": float(np.mean([100 * r[s]["service"] for s in both])) if both else None,
            "capped_on_plans": float(np.mean([cap_service[s] for s in both])) if both else None,
            "service_minus_capped_on_plans": boot([100 * r[s]["service"] - cap_service[s] for s in both]) if both else None,
            "by_size": {n: float(np.mean([100 * r[s]["service"] for s in seeds if recs[s]["customers"] == n]))
                        for n in (20, 50, 100, 200)},
        }
    (ROOT / "results" / "padding_sweep_summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "levels"}, indent=1))
    for lv, v in out["levels"].items():
        print(lv, v["with_plan"], round(v["pooled_service"], 1), [round(x, 1) for x in v["service_minus_capped"]],
              None if v["distance_vs_capped_pct"] is None else [round(x, 1) for x in v["distance_vs_capped_pct"]],
              None if v["fleet_minus_capped"] is None else [round(x, 2) for x in v["fleet_minus_capped"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        summarise()
        return
    recs = stage1_records()
    tasks = [(recs[s], lv) for lv in LEVELS for s in sorted(recs) if recs[s]["reference_ranges"]]
    print(f"{len(tasks)} tasks", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_task, r, lv, a.seconds): (r["instance_seed"], lv) for r, lv in tasks}
        for f in as_completed(futs):
            seed, lv = futs[f]
            try:
                r = f.result()
                print(f"pad={lv} seed={seed} plan={r['has_plan']} service={r['service']:.3f}", flush=True)
            except Exception as exc:
                print(f"ERROR pad={lv} seed={seed}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
