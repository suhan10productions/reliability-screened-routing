"""Reliability screening with a PyVRP/HGS candidate generator.

Per instance, everything except the generator matches the OR-Tools study:
instance generator and seeds, planning matrices, buffer grid, capped windows,
reachability certificates, scenario banks (screening 1000 at 100000+seed,
validation 5000 at 400000+seed), the Wilson admission rule and the selection
score. Scaling ranges come from the unchanged OR-Tools anchor solves.

Configurations (validated on the same fresh bank)
  hgs_nominal        HGS distance, 40 km/h planning matrix
  hgs_conservative   HGS distance, 33.3 km/h planning matrix
  hgs_procedure_slack   uncapped screened family; fallback = beta 0 plan
  hgs_procedure_cons    same family; fallback = hgs_conservative
  hgs_capped_slack      capped screened family; fallback = beta 0 plan
  hgs_capped_cons       same family; fallback = hgs_conservative
When hgs_conservative has no plan, the conservative fallback uses the beta 0
plan. Each configuration's status is ok, no_plan or not_attempted; any other
exception is a software error, recorded and never scored.

Usage:
  PYTHONPATH=code python code/study_hgs.py --output results/hgs_dev --workers 6
  PYTHONPATH=code python code/study_hgs.py --seed-shift 80000 --output results/confirm2/hgs --workers 6
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from importlib.metadata import version
from pathlib import Path

from relscreen_v6 import (ModelParams, ScenarioBank, SpeedProfile, empirical_reference_ranges,
                          environment_metadata, make_synthetic_instance, normalized_score)
from relscreen_v7 import certificate, contracted_data, evaluate
from hgs_generator import DEFAULT_ITERATIONS, HGSSolver

SCHEMA = "relscreen-hgs-1"
DESIGN = {20: (6, 20, 7200), 50: (14, 15, 7500), 100: (26, 10, 8000), 200: (40, 8, 9000)}
BETAS = list(range(0, 61, 5))
SCREEN_N, VALID_N, ANCHOR_SECONDS = 1000, 5000, 2.0


def family(data, params, profile, ranges, bank, *, capped, iterations, seed, reuse=None):
    cands, passing, by_beta = [], [], {}
    for beta in BETAS:
        t0 = time.perf_counter()
        cd = contracted_data(data, params, beta, capped=capped)
        proof = certificate(data, params, beta, None, capped)
        plan, source = None, "new solve"
        if reuse is not None and cd.offered_windows == data.contracted(beta).offered_windows:
            plan, source = reuse.get(beta), "reused identical uncapped model"
        elif proof:
            source = "reachability certificate; solve skipped"
        else:
            plan = HGSSolver(data, params, ranges, iterations=iterations, seed=seed).solve(
                "weighted", beta=beta, data=cd)
            if plan is not None:
                plan.beta = beta
        by_beta[beta] = plan
        rep = None if plan is None else evaluate(plan, data, params, profile, bank)
        cands.append({"beta": beta, "source": source, "certificate": proof,
                      "solve_seconds": time.perf_counter() - t0,
                      "plan": None if plan is None else plan.as_dict(), "screening": rep})
        if rep and rep["service_level_lcb"] >= params.alpha:
            passing.append(((normalized_score(plan, ranges, params), beta), plan))
    passing.sort(key=lambda x: x[0])
    return cands, (passing[0][1] if passing else None), by_beta


def run_instance(n, seed, iterations):
    started = time.perf_counter()
    params, profile = ModelParams(), SpeedProfile()
    vehicles = DESIGN[n][0]
    data = make_synthetic_instance(n, vehicles, seed)
    status, plans = {}, {}
    hgs = lambda speed=None: HGSSolver(data, params, None, planning_speed_kmh=speed,
                                       iterations=iterations, seed=seed)
    plans["hgs_nominal"] = hgs().solve("distance")
    plans["hgs_conservative"] = hgs(params.nominal_speed_kmh / 1.2).solve("distance")
    for k in ("hgs_nominal", "hgs_conservative"):
        status[k] = "ok" if plans[k] is not None else f"no_plan: {k} solve"
    try:
        ranges, _ = empirical_reference_ranges(data, params, ANCHOR_SECONDS)
        status["anchors"] = "ok"
    except RuntimeError as exc:
        if not str(exc).startswith("anchor solve failed"):
            raise
        ranges, status["anchors"] = None, f"no_plan: {exc}"
    screen = ScenarioBank(SCREEN_N, 100_000 + seed, params)
    fam, chosen, base = {}, {}, None
    if ranges is not None:
        cu, chosen["uncapped"], uncapped_plans = family(
            data, params, profile, ranges, screen, capped=False, iterations=iterations, seed=seed)
        cc, chosen["capped"], _ = family(
            data, params, profile, ranges, screen, capped=True, iterations=iterations, seed=seed,
            reuse=uncapped_plans)
        fam = {"uncapped": cu, "capped": cc}
        base = uncapped_plans.get(0)          # slack-aware analogue: uncontracted weighted plan
    cons = plans["hgs_conservative"]
    for tag, key in (("procedure", "uncapped"), ("capped", "capped")):
        for fb in ("slack", "cons"):
            name = f"hgs_{tag}_{fb}"
            if ranges is None:
                plans[name], status[name] = None, "not_attempted: anchors returned no plan"
                continue
            sel = chosen[key]
            fallback = base if fb == "slack" or cons is None else cons
            plans[name] = sel if sel is not None else fallback
            status[name] = "ok" if plans[name] is not None else "no_plan: no selection and no fallback"
    valid = ScenarioBank(VALID_N, 400_000 + seed, params)
    configs = {k: (None if v is None else {"plan": v.as_dict(),
                                           "validation": evaluate(v, data, params, profile, valid)})
               for k, v in plans.items()}
    return {
        "schema": SCHEMA, "customers": n, "vehicles_available": vehicles, "instance_seed": seed,
        "screening_seed": 100_000 + seed, "validation_seed": 400_000 + seed,
        "screen_scenarios": SCREEN_N, "validation_scenarios": VALID_N, "beta_values": BETAS,
        "hgs_iterations": iterations, "hgs_seed": seed, "anchor_seconds": ANCHOR_SECONDS,
        "reference_ranges": None if ranges is None else {"lower": list(ranges[0]), "upper": list(ranges[1])},
        "selected": {k: v is not None for k, v in chosen.items()},
        "selected_beta": {k: (None if v is None else v.beta) for k, v in chosen.items()},
        "configuration_status": status, "configurations": configs, "families": fam,
        "environment": {**environment_metadata(), "pyvrp": version("pyvrp")},
        "elapsed_seconds": time.perf_counter() - started,
    }


def _task(n, seed, iterations, out):
    path = Path(out) / f"instance_{seed}.json"
    if path.exists():
        return seed, "exists"
    rec = run_instance(n, seed, iterations)
    path.write_text(json.dumps(rec))
    return seed, {"n": n, "selected": rec["selected"], "elapsed": round(rec["elapsed_seconds"], 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", nargs="*", type=int, default=[20, 50, 100, 200])
    ap.add_argument("--seed-shift", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    tasks = []
    for n in a.sizes:
        _, count, first = DESIGN[n]
        count = count if a.limit is None else min(count, a.limit)
        tasks += [(n, first + a.seed_shift + i) for i in range(count)]
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(_task, n, s, a.iterations, str(a.output)): (n, s) for n, s in tasks}
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
