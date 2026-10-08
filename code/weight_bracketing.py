"""Exploratory weight bracketing on the development instances.

The weight-sensitivity analysis (code/weight_sensitivity.py) found that the
advantage over conservative speed is not distinguishable from zero under equal
weights. Equal weights change two things at once against the original vector:
the fleet-use weight rises from 0.0609 to 0.25 and the driver-duration weight
from 0.1055 to 0.25. This run separates the two. The vectors were fixed before
the run:

  original_here   the original vector, rerun on this machine
  equal_here      equal weights, rerun on this machine
  fleet_up        original vector with the fleet-use weight raised to 0.25 and
                  the other three scaled to sum to 0.75
  duration_up     original vector with the driver-duration weight raised to 0.25
                  and the other three scaled to sum to 0.75

The procedure is the one of code/weight_sensitivity.py (original screened
procedure, same buffer grid, screening bank, fallback and validation bank), so
the two runs differ only in the machine and the stored detail: this script also
stores the returned plan, every candidate's planned metrics and screening result,
and the validation report, so the reason for a lower admission rate can be read
from the records. OR-Tools stops at a wall-clock limit, so the two vectors rerun
here are compared with each other and with the new vectors on the same machine.

Usage (from the package root):
  PYTHONPATH=code python code/weight_bracketing.py --workers 2
  PYTHONPATH=code python code/weight_bracketing.py --summarise
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

from relscreen_v6 import (ModelParams, RoutingSolver, ScenarioBank, SpeedProfile,
                          make_synthetic_instance, screen_with_internal_buffers)
from relscreen_v7 import evaluate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "weight_bracketing"
ORIGINAL = (0.5693, 0.2643, 0.1055, 0.0609)   # distance, slack deficit, driver duration, fleet use


def raised(index: int, value: float = 0.25):
    rest = sum(w for k, w in enumerate(ORIGINAL) if k != index)
    w = [value if k == index else round(ORIGINAL[k] * (1 - value) / rest, 4) for k in range(4)]
    w[0] = round(1 - sum(w[1:]), 4)               # absorb rounding in the distance weight
    return tuple(w)


WEIGHTS = {
    "original_here": ORIGINAL,
    "equal_here": (0.25, 0.25, 0.25, 0.25),
    "fleet_up": raised(3),
    "duration_up": raised(2),
}


def stage1_records():
    recs = {}
    for n in (20, 50, 100, 200):
        for r in json.loads((ROOT / f"results/study_v6_n{n}.json").read_text())["records"]:
            recs[r["instance_seed"]] = r
    return recs


def run_task(record: dict, name: str, seconds: float) -> dict:
    seed, n = record["instance_seed"], record["customers"]
    path = OUT / f"{name}_{seed}.json"
    if path.exists():
        return json.loads(path.read_text())
    started = time.perf_counter()
    params = replace(ModelParams(), weights=WEIGHTS[name])
    profile = SpeedProfile()
    data = make_synthetic_instance(n, record["vehicles_available"], seed)
    rr = record["reference_ranges"]
    ranges = (rr["lower"], rr["upper"])
    screen = ScenarioBank(1000, 100_000 + seed, params)
    selected, cands = screen_with_internal_buffers(
        data, params, profile, ranges, record["beta_values"], screen, seconds)
    fallback = None
    for _ in range(3):
        fallback = RoutingSolver(data, params, ranges).solve("weighted", seconds)
        if fallback is not None:
            break
    plan = selected if selected is not None else fallback
    bank = ScenarioBank(5000, 400_000 + seed, params)
    validation = None if plan is None else evaluate(plan, data, params, profile, bank)
    result = {
        "schema": "relscreen-weight-bracketing-1",
        "weights_name": name, "weights": WEIGHTS[name], "instance_seed": seed, "customers": n,
        "selected": selected is not None,
        "selected_beta": None if selected is None else selected.beta,
        "procedure_service": None if validation is None else validation["service_level_success"],
        "plan": None if plan is None else plan.as_dict(),
        "validation": validation,
        "candidates": [{"beta": c.beta, "has_plan": c.feasible,
                        "metrics": None if c.plan is None else c.plan.metrics,
                        "screening_success": None if c.screening is None else c.screening.service_level_success,
                        "screening_lcb": None if c.screening is None else c.screening.service_level_lcb}
                       for c in cands],
        "candidate_seconds": seconds, "elapsed_seconds": time.perf_counter() - started,
        "machine": platform.platform(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--weights", nargs="*", default=list(WEIGHTS))
    a = ap.parse_args()
    recs = stage1_records()
    tasks = [(recs[s], w) for w in a.weights for s in sorted(recs) if recs[s]["reference_ranges"]]
    print("vectors:", {w: WEIGHTS[w] for w in a.weights}, flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_task, r, w, a.seconds): (r["instance_seed"], w) for r, w in tasks}
        failed = []
        for f in as_completed(futs):
            seed, name = futs[f]
            try:
                r = f.result()
            except Exception as exc:
                failed.append((seed, name, f"{type(exc).__name__}: {exc}"))
                print(f"ERROR {name} seed={seed}: {type(exc).__name__}: {exc}", flush=True)
                continue
            print(f"{r['weights_name']:14s} seed={r['instance_seed']} selected={r['selected']} "
                  f"P={r['procedure_service']}", flush=True)
    if failed:
        print(f"{len(failed)} task(s) failed; rerun the same command to resume.")


if __name__ == "__main__":
    main()
