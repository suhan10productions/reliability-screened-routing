"""HGS ablations: which part of the capped HGS procedure produces its gain (exploratory).

The capped HGS procedure (study_hgs, configuration hgs_capped_cons) differs from
20% padding (hgs_conservative) in four ways at once: the weighted objective,
the buffer family, the cap and the screen. This script separates the objective
from the buffers and the screen on the synthetic instances of the development
study (results/hgs_dev) and the second confirmatory study (results/confirm2/hgs):

  hgs_weighted_noscreen  the weighted plan with no buffer and no screen (the
                         beta 0 member of the stored family; no new solve)
  hgs_distance_capped    the distance objective at the nominal planning speed on
                         the same capped buffer family (beta 0..60), screened on
                         the same 1000 screening days with the same Wilson rule,
                         choosing the passing plan with the least distance;
                         fallback 20% padding, as for hgs_capped_cons

Everything else is unchanged: instances, seeds, banks, admission rule and the
5000-day validation bank (400000 + seed). The frozen study code is imported, not
edited. The slack-deficit term of the weighted objective cannot be expressed in
PyVRP and is omitted from HGS generation in every configuration (hgs_generator).

Usage (from the package root):
  PYTHONPATH=code python code/hgs_ablation.py --workers 2
  PYTHONPATH=code python code/hgs_ablation.py --summarise
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from certify import TARGET, cp_lower, successes
from hgs_generator import DEFAULT_ITERATIONS, HGSSolver
from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance
from relscreen_v7 import certificate, contracted_data, evaluate, plan_from_dict
from study_hgs import BETAS, SCREEN_N, VALID_N

ROOT = Path(__file__).resolve().parents[1]
STUDIES = {"development": ROOT / "results" / "hgs_dev", "confirmatory 2": ROOT / "results" / "confirm2" / "hgs"}
OUT = ROOT / "results" / "hgs_ablation"


def records():
    for study, d in STUDIES.items():
        for f in sorted(d.glob("instance_*.json")):
            yield study, f


def run_one(study: str, path: str) -> str:
    rec = json.loads(Path(path).read_text())
    seed, n, vehicles = rec["instance_seed"], rec["customers"], rec["vehicles_available"]
    out = OUT / f"instance_{seed}.json"
    if out.exists():
        return f"{seed} exists"
    params, profile = ModelParams(), SpeedProfile()
    data = make_synthetic_instance(n, vehicles, seed)
    valid = ScenarioBank(VALID_N, 400_000 + seed, params)
    screen = ScenarioBank(SCREEN_N, 100_000 + seed, params)
    res = {"study": study, "instance_seed": seed, "customers": n, "anchors_ok": rec["reference_ranges"] is not None}
    # weighted objective, no buffer, no screen
    base = None
    if rec["families"]:
        c0 = next(c for c in rec["families"]["uncapped"] if c["beta"] == 0)
        base = c0["plan"]
    res["hgs_weighted_noscreen"] = None if base is None else {
        "plan_metrics": base["metrics"], "validation": evaluate(plan_from_dict(base), data, params, profile, valid)}
    # distance objective on the capped buffer family, screened
    cands, passing = [], []
    for beta in BETAS:
        cd = contracted_data(data, params, beta, capped=True)
        if certificate(data, params, beta, None, True):
            cands.append({"beta": beta, "source": "reachability certificate; solve skipped"})
            continue
        plan = HGSSolver(data, params, None, iterations=DEFAULT_ITERATIONS, seed=seed).solve("distance", beta=beta, data=cd)
        if plan is None:
            cands.append({"beta": beta, "source": "no plan"})
            continue
        plan.beta = beta
        rep = evaluate(plan, data, params, profile, screen)
        cands.append({"beta": beta, "source": "new solve", "metrics": plan.metrics,
                      "screen_lcb": rep["service_level_lcb"]})
        if rep["service_level_lcb"] >= params.alpha:
            passing.append(((plan.metrics["distance"], beta), plan))
    passing.sort(key=lambda x: x[0])
    chosen = passing[0][1] if passing else None
    cons = rec["configurations"].get("hgs_conservative")
    if chosen is not None:
        res["hgs_distance_capped"] = {"selected": True, "beta": chosen.beta, "plan_metrics": chosen.metrics,
                                      "validation": evaluate(chosen, data, params, profile, valid)}
    elif cons is not None:
        res["hgs_distance_capped"] = {"selected": False, "beta": None, "plan_metrics": cons["plan"]["metrics"],
                                      "validation": cons["validation"]}
    else:
        res["hgs_distance_capped"] = None
    res["candidates"] = cands
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res))
    return f"{seed} selected={chosen is not None} beta={None if chosen is None else chosen.beta}"


def boot(x, seed=20261026, n=20000):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def summarise():
    rows = []
    for study, f in records():
        rec = json.loads(f.read_text())
        a = OUT / f"instance_{rec['instance_seed']}.json"
        if not a.exists():
            continue
        ab = json.loads(a.read_text())
        row = {"study": study, "seed": rec["instance_seed"], "customers": rec["customers"], "anchors_ok": ab["anchors_ok"]}
        cells = {k: rec["configurations"].get(k) for k in ("hgs_nominal", "hgs_conservative", "hgs_capped_cons")}
        cells["hgs_weighted_noscreen"] = ab["hgs_weighted_noscreen"]
        cells["hgs_distance_capped"] = ab["hgs_distance_capped"]
        for k, v in cells.items():
            if v is None:
                row[k] = None
                continue
            kk, nn = successes(v["validation"])
            met = v.get("plan_metrics") or v["plan"]["metrics"]
            row[k] = {"service": 100 * kk / nn, "certified": cp_lower(kk, nn) >= TARGET,
                      "fleet": met["fleet"], "distance": met["distance"]}
        row["distance_selected"] = bool(ab["hgs_distance_capped"] and ab["hgs_distance_capped"]["selected"])
        rows.append(row)
    keys = ("hgs_conservative", "hgs_weighted_noscreen", "hgs_distance_capped", "hgs_capped_cons")
    # common set: every configuration has a plan (anchors ran, so the full procedure was attempted)
    common = [r for r in rows if all(r[k] is not None for k in keys)]
    out = {"instances": len(rows), "common": len(common), "configs": {}}
    for k in keys:
        out["configs"][k] = {
            "plans": sum(r[k] is not None for r in rows),
            "pooled_common": boot([r[k]["service"] for r in common]),
            "certified_common": sum(r[k]["certified"] for r in common),
            "minus_padding": boot([r[k]["service"] - r["hgs_conservative"]["service"] for r in common]),
            "fleet_minus_padding": boot([r[k]["fleet"] - r["hgs_conservative"]["fleet"] for r in common]),
            "distance_pct_minus_padding": boot([100 * (r[k]["distance"] / r["hgs_conservative"]["distance"] - 1) for r in common]),
        }
    out["full_minus_distance_capped"] = boot([r["hgs_capped_cons"]["service"] - r["hgs_distance_capped"]["service"] for r in common])
    out["full_minus_weighted_noscreen"] = boot([r["hgs_capped_cons"]["service"] - r["hgs_weighted_noscreen"]["service"] for r in common])
    out["distance_selected_common"] = sum(r["distance_selected"] for r in common)
    out["rows"] = rows
    (ROOT / "results" / "hgs_ablation_summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        return summarise()
    tasks = list(records())
    # largest instances first so the run finishes evenly
    tasks.sort(key=lambda t: -json.loads(t[1].read_text())["customers"])
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_one, s, str(f)): f.name for s, f in tasks}
        for fu in as_completed(futs):
            try:
                print(fu.result(), flush=True)
            except Exception as exc:  # recorded, the run continues
                print(f"ERROR {futs[fu]}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
