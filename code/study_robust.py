"""Budgeted-robust VRPTW comparator, evaluated on the pipeline's scenario banks.

For each instance, every robust setting (gamma, delta) in GRID is solved by
RobustSolver and the resulting plan is scored on
  * the screening bank (1000 scenarios, seed 100000 + instance seed), used only
    by the descriptive "screened robust" selection, and
  * the validation bank (5000 scenarios, seed 400000 + instance seed), the same
    bank on which every configuration of the OR-Tools and HGS studies was
    validated, so all comparisons are paired by instance and scenario.
gamma = 0 is the nominal model solved by the same search (a reference point);
gamma = "box" is box uncertainty (every arc at its upper value). With --capped,
every setting except gamma = 0 uses the capped robust model (reachability
relief; see robust_generator.CappedRobustModel).

A setting without a robust feasible plan has status no_plan and scores 0, as
under the failure policy of the confirmatory studies. Any other exception is a
software error: it is recorded and never scored.

Usage:
  PYTHONPATH=code python code/study_robust.py --sizes 20 50 --output results/robust_dev --workers 2
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, environment_metadata, make_synthetic_instance
from relscreen_v7 import evaluate
from robust_generator import RobustSolver

SCHEMA = "relscreen-robust-1"
DESIGN = {20: (6, 20, 7200), 50: (14, 15, 7500), 100: (26, 10, 8000), 200: (40, 8, 9000)}
DELTAS = (0.2, 0.4, 0.6)
GAMMAS = (1, 2, 3, 5, "box")
GRID = [(0, 0.0)] + [(g, d) for d in DELTAS for g in GAMMAS]
ITERATIONS = {20: 6000, 50: 6000, 100: 3000, 200: 2000}
SCREEN_N, VALID_N = 1000, 5000


def key(gamma, delta) -> str:
    return f"{'box' if gamma == 'box' else 'G' + str(gamma)}_d{delta:g}"


def run_instance(n: int, seed: int, capped: bool = False) -> dict:
    started = time.perf_counter()
    params, profile = ModelParams(), SpeedProfile()
    data = make_synthetic_instance(n, DESIGN[n][0], seed)
    screen = ScenarioBank(SCREEN_N, 100_000 + seed, params)
    valid = ScenarioBank(VALID_N, 400_000 + seed, params)
    settings = {}
    grid = [x for x in GRID if not (capped and x[0] == 0)]
    for gamma, delta in grid:
        t0 = time.perf_counter()
        plan = RobustSolver(data, params, None if gamma == "box" else gamma, delta,
                            iterations=ITERATIONS[n], seed=seed, capped=capped).solve()
        entry = {"gamma": gamma, "delta": delta, "solve_seconds": time.perf_counter() - t0,
                 "status": "ok" if plan is not None else "no_plan: no robust feasible plan found",
                 "plan": None, "screening": None, "validation": None}
        if plan is not None:
            entry["plan"] = plan.as_dict()
            entry["screening"] = evaluate(plan, data, params, profile, screen)
            entry["validation"] = evaluate(plan, data, params, profile, valid)
        settings[key(gamma, delta)] = entry
    return {
        "schema": SCHEMA, "customers": n, "vehicles_available": DESIGN[n][0], "instance_seed": seed,
        "screening_seed": 100_000 + seed, "validation_seed": 400_000 + seed,
        "screen_scenarios": SCREEN_N, "validation_scenarios": VALID_N,
        "iterations": ITERATIONS[n], "search_seed": seed, "capped": capped,
        "grid": [key(g, d) for g, d in grid],
        "settings": settings, "environment": environment_metadata(),
        "elapsed_seconds": time.perf_counter() - started,
    }


def _task(n, seed, out, capped):
    path = Path(out) / f"instance_{seed}.json"
    if path.exists():
        return seed, "exists"
    rec = run_instance(n, seed, capped)
    path.write_text(json.dumps(rec))
    ok = sum(v["status"] == "ok" for v in rec["settings"].values())
    return seed, {"n": n, "settings_with_plan": ok, "elapsed": round(rec["elapsed_seconds"], 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", nargs="*", type=int, default=[20, 50])
    ap.add_argument("--seed-shift", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--capped", action="store_true")
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    tasks = []
    for n in a.sizes:
        _, count, first = DESIGN[n]
        count = count if a.limit is None else min(count, a.limit)
        tasks += [(n, first + a.seed_shift + i) for i in range(count)]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(_task, n, s, str(a.output), a.capped): (n, s) for n, s in tasks}
        for f in as_completed(futs):
            n, s = futs[f]
            try:
                print(f.result(), flush=True)
            except Exception as exc:  # noqa: BLE001 - recorded, never scored
                (a.output / f"software_error_{s}.json").write_text(json.dumps(
                    {"customers": n, "instance_seed": s, "error": f"{type(exc).__name__}: {exc}",
                     "traceback": "".join(traceback.format_exception(exc))}, indent=2))
                print(f"seed={s} SOFTWARE ERROR: {exc}", flush=True)


if __name__ == "__main__":
    main()
