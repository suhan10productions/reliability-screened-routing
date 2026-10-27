"""Fixed-order certification: certify the cheapest plan of the family, with the same guarantee (exploratory).

The screen chooses one plan on the screening days and the certificate then tests
that plan alone. A firm would rather certify the cheapest plan that is good
enough. Choosing it on the validation days themselves would break Theorem 1,
because many plans would be tested on the same days. Fixed-order testing avoids
that without any correction for multiplicity:

  order the candidates by a rule fixed before the validation days are used
  (here: buffer from largest to smallest, the order of decreasing protection);
  test them in that order on the validation bank, certifying a candidate when
  its exact one-sided Clopper-Pearson bound reaches tau;
  stop at the first candidate that is not certified;
  return the cheapest certified candidate (smallest score of the procedure).

Proposition (in the manuscript). P(some candidate is certified although its
success probability is below tau) <= alpha. Proof: let k* be the first
candidate in the order whose probability is below tau. A candidate after k* is
reached only if k* was certified, and candidates before k* are not below tau,
so the event implies that candidate k* was certified, which has probability at
most alpha by Theorem 1 (the order is fixed before the validation days, so
conditioning on it changes nothing). The chosen plan is one of the certified
candidates, so it inherits the guarantee whatever the selection rule.

Each certified plan chosen this way is tested on the fresh bank of
code/certify.py (5000 days, seed 1_100_000 + instance seed).

Studies: OR-Tools capped family (development results/v7, confirmatory 1
results/confirm/v7, confirmatory 2 results/confirm2/v7) and HGS capped family
(results/hgs_dev, results/confirm2/hgs). Compared with the capped procedure of
each study (configurations capped_procedure and hgs_capped_cons).

Usage (from the package root):
  PYTHONPATH=code python code/fixed_order.py --workers 2
  PYTHONPATH=code python code/fixed_order.py --summarise
"""
from __future__ import annotations

import argparse
import glob
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from certify import TARGET, cp_lower, cp_upper, successes
from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance, normalized_score
from relscreen_v7 import evaluate, plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "fixed_order"
VALID, TEST = 400_000, 1_100_000
STUDIES = {
    ("development", "ortools"): ("results/v7", "results/study_v6_n*.json"),
    ("confirmatory 1", "ortools"): ("results/confirm/v7", "results/confirm/study_v6_n*.json"),
    ("confirmatory 2", "ortools"): ("results/confirm2/v7", "results/confirm2/study_v6_n*.json"),
    ("development", "hgs"): ("results/hgs_dev", None),
    ("confirmatory 2", "hgs"): ("results/confirm2/hgs", None),
}


def tasks():
    for (study, solver), (rec_dir, _) in STUDIES.items():
        for f in sorted(glob.glob(str(ROOT / rec_dir / "instance_*.json"))):
            yield study, solver, f


def stage1(pattern):
    out = {}
    for f in glob.glob(str(ROOT / pattern)):
        for r in json.loads(Path(f).read_text())["records"]:
            out[r["instance_seed"]] = r
    return out


def run_one(study, solver, path):
    rec = json.loads(Path(path).read_text())
    seed = rec["instance_seed"]
    out = OUT / f"{solver}_{seed}.json"
    if out.exists():
        return f"{solver} {seed} exists"
    params, profile = ModelParams(), SpeedProfile()
    if solver == "ortools":
        s1 = stage1(STUDIES[(study, solver)][1])[seed]
        data = make_synthetic_instance(s1["customers"], s1["vehicles_available"], seed)
        ranges = s1["reference_ranges"]
        cands = rec["capped_procedure"]["candidates"]
        proc = rec["configurations"].get("capped_procedure")
    else:
        data = make_synthetic_instance(rec["customers"], rec["vehicles_available"], seed)
        ranges = rec["reference_ranges"]
        cands = (rec["families"] or {}).get("capped", [])
        proc = rec["configurations"].get("hgs_capped_cons")
    res = {"study": study, "solver": solver, "seed": seed, "customers": rec["customers"]}
    k, n = (successes(proc["validation"]) if proc else (0, 1))
    res["procedure"] = None if proc is None else {
        "certified": cp_lower(k, n) >= TARGET, "fleet": proc["plan"]["metrics"]["fleet"],
        "distance": proc["plan"]["metrics"]["distance"], "beta": proc["plan"].get("beta")}
    if ranges is None or not cands:
        res["fixed_order"] = None
        res["note"] = "no candidate family (anchor solves failed)"
    else:
        rg = (ranges["lower"], ranges["upper"]) if isinstance(ranges, dict) else ranges
        valid = ScenarioBank(5000, VALID + seed, params)
        tested, certified = [], []
        for c in sorted([c for c in cands if c.get("plan")], key=lambda c: -c["beta"]):
            plan = plan_from_dict(c["plan"])
            kk, nn = successes(evaluate(plan, data, params, profile, valid))
            lb = cp_lower(kk, nn)
            tested.append({"beta": c["beta"], "success": kk / nn, "cp_lower": lb})
            if lb < TARGET:
                break
            certified.append((normalized_score(plan, rg, params), c["beta"], c["plan"]))
        res["tested"] = tested
        if certified:
            score, beta, pd_ = min(certified, key=lambda x: (x[0], x[1]))
            kt, nt = successes(evaluate(plan_from_dict(pd_), data, params, profile, ScenarioBank(5000, TEST + seed, params)))
            res["fixed_order"] = {"beta": beta, "fleet": pd_["metrics"]["fleet"], "distance": pd_["metrics"]["distance"],
                                  "certified_count": len(certified), "fresh_success": kt / nt,
                                  "fails_certificate": cp_upper(kt, nt) < TARGET}
        else:
            res["fixed_order"] = None
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res))
    fo = res["fixed_order"]
    return f"{solver} {seed} fixed={None if fo is None else fo['beta']} proc_cert={res['procedure'] and res['procedure']['certified']}"


def boot(x, seed=20261027, n=20000):
    x = np.asarray(x, float)
    if len(x) == 0:
        return None
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def summarise():
    rows = [json.loads(Path(f).read_text()) for f in sorted(glob.glob(str(OUT / "*.json")))]
    out = {"groups": {}}
    for (study, solver) in STUDIES:
        R = [r for r in rows if r["study"] == study and r["solver"] == solver]
        pc = [r for r in R if r["procedure"] and r["procedure"]["certified"]]
        fo = [r for r in R if r["fixed_order"]]
        both = [r for r in R if r["fixed_order"] and r["procedure"] and r["procedure"]["certified"]]
        out["groups"][f"{study}|{solver}"] = {
            "instances": len(R), "procedure_certified": len(pc), "fixed_order_certified": len(fo),
            "both": len(both),
            "fixed_only": sum(1 for r in fo if not (r["procedure"] and r["procedure"]["certified"])),
            "procedure_only": sum(1 for r in pc if not r["fixed_order"]),
            "fleet_fixed_minus_procedure": boot([r["fixed_order"]["fleet"] - r["procedure"]["fleet"] for r in both]),
            "distance_pct_fixed_minus_procedure": boot([100 * (r["fixed_order"]["distance"] / r["procedure"]["distance"] - 1) for r in both]),
            "fresh_fails": sum(r["fixed_order"]["fails_certificate"] for r in fo),
            "fresh_below_target": sum(r["fixed_order"]["fresh_success"] < TARGET for r in fo),
        }
    tot = lambda k: sum(g[k] for g in out["groups"].values())  # noqa: E731
    out["total"] = {k: tot(k) for k in ("instances", "procedure_certified", "fixed_order_certified", "fixed_only",
                                         "procedure_only", "fresh_fails", "fresh_below_target", "both")}
    allboth = [r for r in rows if r["fixed_order"] and r["procedure"] and r["procedure"]["certified"]]
    out["total"]["fleet_fixed_minus_procedure"] = boot([r["fixed_order"]["fleet"] - r["procedure"]["fleet"] for r in allboth])
    out["total"]["distance_pct_fixed_minus_procedure"] = boot(
        [100 * (r["fixed_order"]["distance"] / r["procedure"]["distance"] - 1) for r in allboth])
    (ROOT / "results" / "fixed_order_summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        return summarise()
    T = list(tasks())
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_one, *t): t for t in T}
        for f in as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception as exc:  # recorded, the run continues
                print(f"ERROR {futs[f][2]}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
