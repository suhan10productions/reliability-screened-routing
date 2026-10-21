"""Amazon routes with the HGS pipeline (exploratory).

The OR-Tools check on the Amazon routes (code/amazon_benchmark.py) lost plans to
its 5-second search: on several routes neither the nominal nor the padded planner
found a plan although the driver's own order is feasible. This script runs the
HGS pipeline of the second confirmatory study (study_hgs.run_instance, unchanged)
on the same instances, built exactly as in code/amazon_benchmark.py, on all 60
sampled routes: the first 40 of the OR-Tools check and the 20 spares, which were
not run before. It is repeated under the assumed delay model and the two models
fitted to New York traffic (code/nyc_calibration.py).

Usage (from the package root):
  PYTHONPATH=code python code/amazon_hgs.py --workers 2 --delay assumed
  PYTHONPATH=code python code/amazon_hgs.py --summarise
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import numpy as np

import amazon_benchmark as amz
import relscreen_v6
import study_hgs
from certify import TARGET, cp_lower, cp_upper, successes
from relscreen_v6 import ScenarioBank
from relscreen_v7 import evaluate, plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
N_ROUTES = 60
TEST_SEED = 1_100_000
CONFIGS = ("hgs_nominal", "hgs_conservative", "hgs_capped_cons")


def all_route_ids():
    return sorted(amz.sample()["routes"])[:N_ROUTES]


def out_dir(delay: str) -> Path:
    return ROOT / "results" / f"amazon_hgs_{delay}"


def setup(k: int, delay: str):
    seed = amz.SEED_BASE + k + 1
    data, overrides, info = amz.build(all_route_ids()[k], seed)
    extra, mult = amz.delay_settings(delay)
    params_over = {**overrides, **extra}
    base = relscreen_v6.ModelParams
    profile = relscreen_v6.SpeedProfile() if mult is None else relscreen_v6.SpeedProfile(congestion_multiplier=mult)
    return seed, data, params_over, profile, info, base


def run_one(k: int, delay: str) -> str:
    seed, data, over, profile, info, base = setup(k, delay)
    path = out_dir(delay) / f"instance_{seed}.json"
    if path.exists():
        return f"{k} exists"
    study_hgs.make_synthetic_instance = lambda customers, vehicles, s, *a, **kw: data
    study_hgs.ModelParams = lambda: replace(base(), **over)
    study_hgs.SpeedProfile = lambda: profile
    study_hgs.DESIGN = {data.num_customers: (data.num_vehicles, 1, seed)}
    rec = study_hgs.run_instance(data.num_customers, seed, study_hgs.DEFAULT_ITERATIONS)
    rec.update({"amazon": info, "delay_model": delay, "overrides": over})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec))
    return f"{k} selected={rec['selected']}"


def boot(x, seed=20261021, n=20000):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def summarise():
    out = {"routes": N_ROUTES, "models": {}}
    for delay in ("assumed", "nyc_days", "nyc_total"):
        rows = []
        for k in range(N_ROUTES):
            seed, data, over, profile, info, base = setup(k, delay)
            f = out_dir(delay) / f"instance_{seed}.json"
            if not f.exists():
                continue
            r = json.loads(f.read_text())
            params = replace(base(), **over)
            row = {"seed": seed, "k": k, "spare": k >= amz.N_USED, "customers": info["customers"]}
            for c in CONFIGS:
                cfg = r["configurations"].get(c)
                if cfg is None:
                    row[c] = None
                    continue
                kk, nn = successes(cfg["validation"])
                cert = cp_lower(kk, nn) >= TARGET
                cell = {"service": 100 * kk / nn, "certified": cert, "fleet": cfg["plan"]["metrics"]["fleet"]}
                if cert:
                    t = evaluate(plan_from_dict(cfg["plan"]), data, params, profile, ScenarioBank(5000, TEST_SEED + seed, params))
                    kt, nt = successes(t)
                    cell["fails_certificate"] = cp_upper(kt, nt) < TARGET
                row[c] = cell
            row["admitted"] = bool(r["selected"].get("capped"))
            rows.append(row)
        v = lambda r, c: 0.0 if r[c] is None else r[c]["service"]  # noqa: E731
        both = [r for r in rows if r["hgs_conservative"] is not None and r["hgs_capped_cons"] is not None]
        res = {"routes": len(rows),
               "plans": {c: sum(r[c] is not None for r in rows) for c in CONFIGS},
               "pooled": {c: boot([v(r, c) for r in rows]) for c in CONFIGS},
               "capped_minus_padding": boot([v(r, "hgs_capped_cons") - v(r, "hgs_conservative") for r in rows]),
               "both": len(both),
               "capped_minus_padding_both": boot([r["hgs_capped_cons"]["service"] - r["hgs_conservative"]["service"] for r in both]) if both else None,
               "fleet_capped_minus_padding_both": boot([r["hgs_capped_cons"]["fleet"] - r["hgs_conservative"]["fleet"] for r in both]) if both else None,
               "admitted": sum(r["admitted"] for r in rows),
               "certified": {c: sum(bool(r[c] and r[c]["certified"]) for r in rows) for c in CONFIGS},
               "fails_certificate": sum(bool(r[c] and r[c].get("fails_certificate")) for r in rows for c in CONFIGS),
               "first40_capped_minus_padding": boot([v(r, "hgs_capped_cons") - v(r, "hgs_conservative") for r in rows if not r["spare"]]),
               # where the screen could not run (no scaling ranges), apply the procedure's declared fallback, 20% padding
               "screen_not_run": sum(r["hgs_capped_cons"] is None for r in rows),
               "capped_with_fallback_pooled": boot([v(r, "hgs_capped_cons") if r["hgs_capped_cons"] is not None else v(r, "hgs_conservative") for r in rows]),
               "capped_with_fallback_minus_padding": boot([(v(r, "hgs_capped_cons") if r["hgs_capped_cons"] is not None else v(r, "hgs_conservative")) - v(r, "hgs_conservative") for r in rows]),
               "rows": rows}
        out["models"][delay] = res
        print(delay, json.dumps({k: x for k, x in res.items() if k != "rows"}), flush=True)
    (ROOT / "results" / "amazon_hgs_summary.json").write_text(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--delay", choices=("assumed", "nyc_days", "nyc_total"), default="assumed")
    ap.add_argument("--only", type=int, nargs="*")
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        return summarise()
    ks = a.only if a.only is not None else list(range(N_ROUTES))
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_one, k, a.delay): k for k in ks}
        for f in as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception as exc:  # recorded, the run continues
                print(f"ERROR {futs[f]}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
