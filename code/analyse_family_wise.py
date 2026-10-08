"""Family-wise screening: re-screen every stored candidate family with a Bonferroni bound.

The admission rule uses a one-sided 95% Wilson lower bound for each candidate,
which is not a simultaneous guarantee across the 13 buffer levels searched per
instance. This exploratory analysis repeats the selection with the bound at
eta / 13, which is a family-wise one-sided 95% bound over the grid, using the
screening success counts stored for every candidate (1000 scenarios each). The
selection rule is otherwise unchanged (smallest normalized score among admitted
candidates, ties by buffer), and so is the fallback. A selected plan that differs
from the stored one is validated on the instance's original 5000-scenario
validation bank (seed 400000 + instance seed).

The script first re-selects with the original bound and stops unless it
reproduces every stored selection.

Usage: PYTHONPATH=code python code/analyse_family_wise.py --output results/family_wise_summary.json
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np

from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance, normalized_score
from relscreen_v7 import evaluate, plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
ETA, GRID_SIZE = 0.05, 13
ETA_FW = ETA / GRID_SIZE
STUDIES = {
    "development": ("results", "results/v7", "results/hgs_dev"),
    "confirmatory 1": ("results/confirm", "results/confirm/v7", None),
    "confirmatory 2": ("results/confirm2", "results/confirm2/v7", "results/confirm2/hgs"),
}


def wilson(p_hat: float, n: int, eta: float) -> float:
    z = NormalDist().inv_cdf(1 - eta)
    den = 1 + z * z / n
    centre = p_hat + z * z / (2 * n)
    spread = z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return (centre - spread) / den


def same(a, b) -> bool:
    return a is not None and b is not None and a["routes"] == b["routes"] and a["departures"] == b["departures"]


def select(cands, ranges, params, eta):
    passing = []
    for c in cands:
        if c["plan"] is None or c["screening"] is None:
            continue
        sc = c["screening"]
        if wilson(sc["service_level_success"], sc["scenarios"], eta) >= params.alpha:
            plan = plan_from_dict(c["plan"])
            passing.append(((normalized_score(plan, ranges, params), c["beta"]), c["plan"]))
    passing.sort(key=lambda x: x[0])
    return passing[0][1] if passing else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    params, profile = ModelParams(), SpeedProfile()
    assert abs(wilson(0.97, 1000, ETA) - __import__("relscreen_v6").wilson_lower_bound(0.97, 1000, ETA)) < 1e-6
    out = {"eta": ETA, "eta_family_wise": ETA_FW, "grid_size": GRID_SIZE, "studies": {}}
    for study, (s1dir, v7dir, hgsdir) in STUDIES.items():
        stage1 = {}
        for f in sorted(glob.glob(str(ROOT / s1dir / "study_v6_n*.json"))):
            for r in json.loads(Path(f).read_text())["records"]:
                stage1[r["instance_seed"]] = r
        v7 = {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
              for f in sorted(glob.glob(str(ROOT / v7dir / "instance_*.json")))}
        hgs = {} if hgsdir is None else {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
                                         for f in sorted(glob.glob(str(ROOT / hgsdir / "instance_*.json")))}
        assert sorted(stage1) == sorted(v7)
        res = {}
        for proc in ("original", "capped", "hgs_capped_cons"):
            if proc == "hgs_capped_cons" and not hgs:
                continue
            rows = []
            for seed in sorted(v7):
                s1, r7 = stage1[seed], v7[seed]
                if proc == "hgs_capped_cons":
                    h = hgs[seed]
                    rr = h["reference_ranges"]
                    stored_cfg = h["configurations"]["hgs_capped_cons"]
                    if rr is None:
                        rows.append({"seed": seed, "orig_admitted": False, "fw_admitted": False,
                                     "orig_service": 0.0, "fw_service": 0.0, "fw_lcb_ok": None})
                        continue
                    ranges = (rr["lower"], rr["upper"])
                    cands = h["families"]["capped"]
                    cons = h["configurations"]["hgs_conservative"]
                    beta0 = next(c for c in h["families"]["uncapped"] if c["beta"] == 0)
                    fallback = cons["plan"] if cons is not None else beta0["plan"]
                    stored_selected = stored_cfg["plan"] if h["selected"]["capped"] else None
                else:
                    rr = s1["reference_ranges"]
                    key = "procedure" if proc == "original" else "capped_procedure"
                    stored_cfg = r7["configurations"][key]
                    if rr is None:
                        rows.append({"seed": seed, "orig_admitted": False, "fw_admitted": False,
                                     "orig_service": 0.0, "fw_service": 0.0, "fw_lcb_ok": None})
                        continue
                    ranges = (rr["lower"], rr["upper"])
                    cands = s1["screened"]["candidates"] if proc == "original" else r7["capped_procedure"]["candidates"]
                    fallback = s1["weighted_objective_only"]["plan"]
                    stored_selected = (s1["screened"]["selected_plan"] if proc == "original"
                                       else r7["capped_procedure"]["selected_plan"])
                orig = select(cands, ranges, params, ETA)
                assert (orig is None and stored_selected is None) or same(orig, stored_selected), (study, proc, seed)
                fw = select(cands, ranges, params, ETA_FW)
                orig_plan = orig if orig is not None else fallback
                fw_plan = fw if fw is not None else fallback
                orig_service = 0.0 if stored_cfg is None else stored_cfg["validation"]["service_level_success"]
                if fw_plan is None:
                    fw_val = None
                elif same(fw_plan, orig_plan):
                    fw_val = stored_cfg["validation"]
                else:
                    n, k = s1["customers"], s1["vehicles_available"]
                    data = make_synthetic_instance(n, k, seed)
                    fw_val = evaluate(plan_from_dict(fw_plan), data, params, profile,
                                      ScenarioBank(5000, 400_000 + seed, params))
                rows.append({"seed": seed, "n": s1["customers"], "orig_admitted": orig is not None,
                             "fw_admitted": fw is not None, "changed": not same(fw_plan, orig_plan),
                             "orig_service": 100 * orig_service,
                             "fw_service": 0.0 if fw_val is None else 100 * fw_val["service_level_success"],
                             "fw_lcb_ok": None if fw is None else fw_val["service_level_lcb"] >= params.alpha})
            adm_fw = [r for r in rows if r["fw_admitted"]]
            res[proc] = {
                "instances": len(rows),
                "admitted_original": sum(r["orig_admitted"] for r in rows),
                "admitted_family_wise": len(adm_fw),
                "changed_plans": sum(r.get("changed", False) for r in rows),
                "pooled_original": float(np.mean([r["orig_service"] for r in rows])),
                "pooled_family_wise": float(np.mean([r["fw_service"] for r in rows])),
                "family_wise_admitted_mean_service": float(np.mean([r["fw_service"] for r in adm_fw])) if adm_fw else None,
                "family_wise_admitted_retained": sum(bool(r["fw_lcb_ok"]) for r in adm_fw),
                "rows": rows,
            }
            print(study, proc, {k: v for k, v in res[proc].items() if k != "rows"})
        out["studies"][study] = res
    a.output.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
