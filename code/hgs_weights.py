"""The capped HGS procedure under other objective weights (exploratory).

The weight-sensitivity runs in the appendix used the original OR-Tools procedure. This script
reruns the capped HGS procedure (configuration hgs_capped_cons of code/study_hgs.py) on the 53
development instances with the two vectors that hurt the original procedure most: equal
weights, and the original vector with the driver-time weight raised to 0.25. Everything else
is unchanged: candidates are generated with the weighted objective (fuel, driver duration and
fleet terms, as in hgs_generator), screened on the same 1000 days with the Wilson rule,
selected by the score of eq. (4) with the same weights, falling back to 20% padding, and
validated on the same 5000 days. Scaling ranges are the stored ones (they do not depend on the
weights). The frozen study code is imported, not edited.

Usage (from the package root):
  PYTHONPATH=code python code/hgs_weights.py --workers 2
  PYTHONPATH=code python code/hgs_weights.py --summarise
"""
from __future__ import annotations

import argparse
import glob
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import numpy as np

from certify import TARGET, cp_lower, successes
from hgs_generator import DEFAULT_ITERATIONS, HGSSolver
from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance, normalized_score
from relscreen_v7 import certificate, contracted_data, evaluate, plan_from_dict
from study_hgs import BETAS, SCREEN_N, VALID_N
from weight_bracketing import WEIGHTS as WB

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "hgs_weights"
VECTORS = {"equal": (0.25, 0.25, 0.25, 0.25), "duration_up": WB["duration_up"]}


def run_one(name, path):
    rec = json.loads(Path(path).read_text())
    seed = rec["instance_seed"]
    out = OUT / f"{name}_{seed}.json"
    if out.exists():
        return f"{name} {seed} exists"
    res = {"weights_name": name, "weights": VECTORS[name], "instance_seed": seed, "customers": rec["customers"]}
    if rec["reference_ranges"] is None:
        res["capped"] = None
    else:
        params, profile = replace(ModelParams(), weights=VECTORS[name]), SpeedProfile()
        data = make_synthetic_instance(rec["customers"], rec["vehicles_available"], seed)
        rg = (rec["reference_ranges"]["lower"], rec["reference_ranges"]["upper"])
        screen = ScenarioBank(SCREEN_N, 100_000 + seed, params)
        passing = []
        for beta in BETAS:
            cd = contracted_data(data, params, beta, capped=True)
            if certificate(data, params, beta, None, True):
                continue
            plan = HGSSolver(data, params, rg, iterations=DEFAULT_ITERATIONS, seed=seed).solve("weighted", beta=beta, data=cd)
            if plan is None:
                continue
            plan.beta = beta
            rep = evaluate(plan, data, params, profile, screen)
            if rep["service_level_lcb"] >= params.alpha:
                passing.append(((normalized_score(plan, rg, params), beta), plan))
        valid = ScenarioBank(VALID_N, 400_000 + seed, params)
        if passing:
            plan = min(passing, key=lambda x: x[0])[1]
            v = evaluate(plan, data, params, profile, valid)
            met, sel = plan.metrics, True
        else:
            cons = rec["configurations"].get("hgs_conservative")
            v, met, sel = (None, None, False) if cons is None else (cons["validation"], cons["plan"]["metrics"], False)
        if v is None:
            res["capped"] = None
        else:
            k, n = successes(v)
            res["capped"] = {"service": 100 * k / n, "certified": cp_lower(k, n) >= TARGET, "fleet": met["fleet"],
                             "distance": met["distance"], "selected": sel}
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res))
    return f"{name} {seed} {None if res['capped'] is None else round(res['capped']['service'], 1)}"


def boot(x, seed=20261027, n=20000):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def summarise():
    base = {}
    for f in glob.glob(str(ROOT / "results" / "hgs_dev" / "instance_*.json")):
        r = json.loads(Path(f).read_text())
        c, p = r["configurations"].get("hgs_capped_cons"), r["configurations"].get("hgs_conservative")
        val = lambda x: None if x is None else 100 * successes(x["validation"])[0] / successes(x["validation"])[1]  # noqa: E731
        base[r["instance_seed"]] = {"capped": val(c), "padding": val(p),
                                    "fleet": None if c is None else c["plan"]["metrics"]["fleet"]}
    out = {"vectors": {}}
    for name in VECTORS:
        R = {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
             for f in glob.glob(str(OUT / f"{name}_*.json"))}
        common = [s for s in R if R[s]["capped"] and base[s]["capped"] is not None and base[s]["padding"] is not None]
        out["vectors"][name] = {
            "weights": VECTORS[name], "instances": len(R), "common": len(common),
            "selected": sum(R[s]["capped"]["selected"] for s in common),
            "pooled": boot([R[s]["capped"]["service"] for s in common]),
            "minus_padding": boot([R[s]["capped"]["service"] - base[s]["padding"] for s in common]),
            "minus_original_weights": boot([R[s]["capped"]["service"] - base[s]["capped"] for s in common]),
            "fleet_minus_original_weights": boot([R[s]["capped"]["fleet"] - base[s]["fleet"] for s in common]),
            "original_minus_padding": boot([base[s]["capped"] - base[s]["padding"] for s in common]),
            "certified": sum(R[s]["capped"]["certified"] for s in common)}
    (ROOT / "results" / "hgs_weights_summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        return summarise()
    files = sorted(glob.glob(str(ROOT / "results" / "hgs_dev" / "instance_*.json")),
                   key=lambda f: -json.loads(Path(f).read_text())["customers"])
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_one, nm, f): (nm, f) for f in files for nm in VECTORS}
        for fu in as_completed(futs):
            try:
                print(fu.result(), flush=True)
            except Exception as exc:  # recorded, the run continues
                print(f"ERROR {futs[fu]}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
