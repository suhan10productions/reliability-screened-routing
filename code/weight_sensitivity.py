"""Exploratory AHP weight-sensitivity analysis on the development instances.

For each instance and weight vector, the original screened procedure is rerun
with that weight vector: the slack-aware candidate family is regenerated over
the same buffer grid, screened on the same 1000-scenario bank, and the
selected plan (or the uncontracted slack-aware fallback) is validated on the
same fresh 5000-scenario bank used in the study. Conservative-speed planning
does not use the weights, so its archived validated outcome is reused for the
paired comparison P - C.

"baseline_rerun" repeats the original weights. Because OR-Tools runs under a
wall-clock limit, reruns can return different routes; this row measures that
run-to-run variation, against which the other weight vectors are judged.

Usage (from the package root):
  PYTHONPATH=code python code/weight_sensitivity.py --workers 6
  PYTHONPATH=code python code/weight_sensitivity.py --summarise
"""
from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import numpy as np

from relscreen_v6 import (ModelParams, RoutingSolver, ScenarioBank, SpeedProfile,
                          make_synthetic_instance, screen_with_internal_buffers)
from relscreen_v7 import evaluate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "weight_sensitivity"
WEIGHTS = {
    "baseline_rerun": (0.5693, 0.2643, 0.1055, 0.0609),
    "equal": (0.25, 0.25, 0.25, 0.25),
    "slack_first": (0.2643, 0.5693, 0.1055, 0.0609),
    "distance_heavy": (0.80, 0.10, 0.05, 0.05),
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
    selected, _ = screen_with_internal_buffers(
        data, params, profile, ranges, record["beta_values"], screen, seconds)
    fallback = None
    for _ in range(3):
        fallback = RoutingSolver(data, params, ranges).solve("weighted", seconds)
        if fallback is not None:
            break
    plan = selected.plan if selected is not None else fallback
    bank = ScenarioBank(5000, 400_000 + seed, params)
    result = {
        "weights_name": name, "weights": WEIGHTS[name], "instance_seed": seed,
        "customers": n, "selected": selected is not None,
        "selected_beta": None if selected is None else selected.beta,
        "procedure_service": None if plan is None
        else evaluate(plan, data, params, profile, bank)["service_level_success"],
        "candidate_seconds": seconds, "elapsed_seconds": time.perf_counter() - started,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    return result


def boot(d, b=20000, seed=20260930):
    d = np.asarray(d, float)
    m = d[np.random.default_rng(seed).integers(0, len(d), (b, len(d)))].mean(1)
    return 100 * d.mean(), 100 * np.percentile(m, 2.5), 100 * np.percentile(m, 97.5)


def summarise():
    archived = {json.loads(f.read_text())["instance_seed"]: json.loads(f.read_text())
                for f in (ROOT / "results/v7").glob("instance_*.json")}
    rows = {}
    for name in WEIGHTS:
        res = [json.loads(f.read_text()) for f in OUT.glob(f"{name}_*.json")]
        if not res:
            continue
        common = [r for r in res if archived[r["instance_seed"]]["configurations"]["conservative"]]
        diff = [(r["procedure_service"] or 0.0)
                - archived[r["instance_seed"]]["configurations"]["conservative"]["validation"]["service_level_success"]
                for r in common]
        pooled = 100 * np.mean([r["procedure_service"] or 0.0 for r in res])
        mean, lo, hi = boot(diff) if diff else (math.nan,) * 3
        rows[name] = {"instances": len(res), "selected": sum(r["selected"] for r in res),
                      "pooled_P_pp": round(pooled, 1), "P_minus_C_common": len(common),
                      "P_minus_C_pp": [round(mean, 1), round(lo, 1), round(hi, 1)]}
    print(json.dumps(rows, indent=2))
    (ROOT / "results/weight_sensitivity_summary.json").write_text(json.dumps(rows, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--weights", nargs="*", default=list(WEIGHTS))
    ap.add_argument("--seeds", nargs="*", type=int)
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        return summarise()
    recs = stage1_records()
    seeds = a.seeds or sorted(recs)
    tasks = [(recs[s], w) for s in seeds for w in a.weights if recs[s]["reference_ranges"]]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_task, r, w, a.seconds): (r["instance_seed"], w) for r, w in tasks}
        for f in as_completed(futs):
            r = f.result()
            print(f"{r['weights_name']:15s} seed={r['instance_seed']} selected={r['selected']} "
                  f"P={r['procedure_service']}", flush=True)


if __name__ == "__main__":
    main()
