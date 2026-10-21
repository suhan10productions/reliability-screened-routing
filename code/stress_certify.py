"""Certifying against a set of delay models (exploratory).

A certificate granted under one delay model often failed when real delays were
harsher (code/wrong_model.py). This script tests the remedy proposed in the
manuscript: screen and certify against a set M of delay models at once. The set
is the five models of code/misspecification.py, fixed before that analysis was
run: the paper's model (baseline), heavy-tailed delays, random incidents, more
noise in the peaks, and a stronger morning peak.

  stress screen   a capped candidate passes if its one-sided 95% Wilson bound reaches
                  0.95 on 1000 screening days under every model in M (seed 100000 +
                  instance seed for each model, as in code/misspecification_rescreen.py);
                  the passing candidate with the smallest normalized score is selected;
  stress certify  the selected plan is certified if its exact one-sided 95% lower
                  bound reaches 0.95 on 5000 days under every model in M (seed
                  700000 + instance seed, the banks of code/misspecification.py);
  test            every certified plan is simulated on 5000 fresh days under every
                  model (seed 1_300_000 + instance seed, unused elsewhere); it fails
                  its certificate under a model if the exact one-sided 95% upper bound
                  is below 0.95.

For comparison, the plans selected by the ordinary (single-model) screen are
certified in the same two ways: under the paper's model only, and under all of M.

Configurations: the capped OR-Tools procedure (development and confirmatory
studies 1 and 2) and the capped HGS procedure (development and study 2). When
no candidate passes the stress screen, no plan is certified; the fallback is not
used here.

Usage (from the package root):
  PYTHONPATH=code python code/stress_certify.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np

from certify import TARGET, cp_lower, cp_upper
from misspecification import MODELS, AltBank, evaluate_alt
from relscreen_v6 import ModelParams, make_synthetic_instance, normalized_score, wilson_lower_bound
from relscreen_v7 import plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
SCREEN_N, CERT_N, TEST_N = 1000, 5000, 5000
TEST_SEED = 1_300_000


def load(directory):
    return {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
            for f in sorted(glob.glob(str(ROOT / directory / "instance_*.json")))}


def success_count(plan, data, params, bank):
    return int(round(evaluate_alt(plan, data, params, bank) / 100 * bank.n))


def stage1(directory):
    recs = {}
    for f in sorted(glob.glob(str(ROOT / directory / "study_v6_n*.json"))):
        for r in json.loads(Path(f).read_text())["records"]:
            recs[r["instance_seed"]] = r
    return recs


def main():
    params = ModelParams()
    jobs = []
    for study, (s1dir, v7dir, hgsdir) in {"development": ("results", "results/v7", "results/hgs_dev"),
                                          "confirmatory 1": ("results/confirm", "results/confirm/v7", None),
                                          "confirmatory 2": ("results/confirm2", "results/confirm2/v7", "results/confirm2/hgs")}.items():
        s1, v7 = stage1(s1dir), load(v7dir)
        for seed, r in sorted(v7.items()):
            rr = s1[seed]["reference_ranges"]
            jobs.append((study, "capped_ortools", seed, s1[seed]["customers"], s1[seed]["vehicles_available"],
                         None if rr is None else (rr["lower"], rr["upper"]),
                         r["capped_procedure"]["candidates"], r["capped_procedure"]["selected_plan"]))
        if hgsdir:
            for seed, h in sorted(load(hgsdir).items()):
                rr = h["reference_ranges"]
                sel = h["configurations"]["hgs_capped_cons"]["plan"] if h["selected"].get("capped") else None
                jobs.append((study, "capped_hgs", seed, h["customers"], h["vehicles_available"],
                             None if rr is None else (rr["lower"], rr["upper"]), h["families"].get("capped", []), sel))
    rows = []
    for study, proc, seed, n, k, ranges, cands, single_sel in jobs:
        data = make_synthetic_instance(n, k, seed)
        screen = {m: AltBank(SCREEN_N, 100_000 + seed, m) for m in MODELS}
        cert = {m: AltBank(CERT_N, 700_000 + seed, m) for m in MODELS}
        test = {m: AltBank(TEST_N, TEST_SEED + seed, m) for m in MODELS}
        # stress screen
        passing = []
        for c in cands:
            if c.get("plan") is None or ranges is None:
                continue
            plan = plan_from_dict(c["plan"])
            ok = all(wilson_lower_bound(success_count(plan, data, params, screen[m]) / SCREEN_N, SCREEN_N, params.eta)
                     >= params.alpha for m in MODELS)
            if ok:
                passing.append(((normalized_score(plan, ranges, params), c["beta"]), c["plan"]))
        passing.sort(key=lambda x: x[0])
        stress_sel = passing[0][1] if passing else None

        def certify(plan_dict, models):
            plan = plan_from_dict(plan_dict)
            return all(cp_lower(success_count(plan, data, params, cert[m]), CERT_N) >= TARGET for m in models)

        def tested(plan_dict):
            plan = plan_from_dict(plan_dict)
            res = {}
            for m in MODELS:
                kk = success_count(plan, data, params, test[m])
                res[m] = {"success": kk / TEST_N, "fails": cp_upper(kk, TEST_N) < TARGET}
            return res

        row = {"study": study, "procedure": proc, "seed": seed, "n": n,
               "single_selected": single_sel is not None, "stress_selected": stress_sel is not None}
        for tag, sel in (("single", single_sel), ("stress", stress_sel)):
            if sel is None:
                row[tag] = None
                continue
            entry = {"cert_baseline": certify(sel, ("baseline",)), "cert_all": certify(sel, MODELS),
                     "fleet": sel["metrics"]["fleet"], "distance": sel["metrics"]["distance"], "beta": sel.get("beta")}
            entry["test"] = tested(sel) if (entry["cert_baseline"] or entry["cert_all"]) else None
            row[tag] = entry
        rows.append(row)
    out = {"models": MODELS, "rows": rows, "summary": {}}
    for proc in ("capped_ortools", "capped_hgs"):
        R = [r for r in rows if r["procedure"] == proc]
        s = {"instances": len(R)}
        for tag, key in (("single", "cert_baseline"), ("single", "cert_all"), ("stress", "cert_all")):
            cert = [r for r in R if r[tag] and r[tag][key]]
            name = f"{tag}_{key}"
            s[name] = {"certified": len(cert),
                       "fails_by_model": {m: sum(r[tag]["test"][m]["fails"] for r in cert) for m in MODELS},
                       "mean_test_success": {m: float(np.mean([100 * r[tag]["test"][m]["success"] for r in cert])) if cert else None
                                             for m in MODELS}}
        both = [r for r in R if r["single"] and r["stress"]]
        s["both_selected"] = len(both)
        s["stress_minus_single_fleet"] = float(np.mean([r["stress"]["fleet"] - r["single"]["fleet"] for r in both])) if both else None
        s["stress_minus_single_distance_pct"] = float(np.mean([100 * (r["stress"]["distance"] / r["single"]["distance"] - 1) for r in both])) if both else None
        s["stress_selected"] = sum(r["stress_selected"] for r in R)
        s["single_selected"] = sum(r["single_selected"] for r in R)
        out["summary"][proc] = s
        print(proc, json.dumps(s, indent=0), flush=True)
    (ROOT / "results" / "stress_certify_summary.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
