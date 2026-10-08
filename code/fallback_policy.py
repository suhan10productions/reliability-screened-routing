"""Fallback rules compared on the stored records (exploratory, post hoc).

When screening admits no candidate, the procedures return a fallback plan: the
uncontracted slack-aware plan (the OR-Tools procedures as prespecified) or the
conservative-speed plan (the HGS procedure; G2 and G3 of the second study). This
script asks whether a rule that uses the screening evidence already computed
does better. On every instance where nothing was admitted, it compares:

  stored        the fallback each procedure actually returned
  conservative  the conservative-speed plan (if it exists; else the stored one)
  best_screen   the candidate of the procedure's own family with the highest
                screening success (ties: lower normalized score, then smaller
                buffer)
  best_any      best_screen extended to the conservative-speed plan, which is
                scored on the same screening bank

No rule changes an admitted instance, and no rule uses the validation bank:
each rule picks a plan from screening evidence alone, and the chosen plan is
then validated once on the instance's fresh bank (seed 400000 + instance seed).
The rules were written after the results of all three studies were known, so
the comparison is exploratory.

Usage: PYTHONPATH=code python code/fallback_policy.py --output results/fallback_policy.json
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np

from analyse_robust import boot
from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance, normalized_score
from relscreen_v7 import evaluate, plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
STUDIES = {
    "development": ("results", "results/v7", "results/hgs_dev"),
    "confirmatory 1": ("results/confirm", "results/confirm/v7", None),
    "confirmatory 2": ("results/confirm2", "results/confirm2/v7", "results/confirm2/hgs"),
}
RULES = ("stored", "conservative", "best_screen", "best_any")


def load(directory):
    return {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
            for f in sorted(glob.glob(str(ROOT / directory / "instance_*.json")))}


def best(cands, ranges, params):
    ok = [c for c in cands if c.get("plan") is not None and c.get("screening") is not None]
    if not ok:
        return None
    key = lambda c: (-c["screening"]["service_level_success"],
                     normalized_score(plan_from_dict(c["plan"]), ranges, params), c.get("beta", 0))
    return min(ok, key=key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    params, profile = ModelParams(), SpeedProfile()
    out = {"rules": RULES, "studies": {}}
    for study, (s1dir, v7dir, hgsdir) in STUDIES.items():
        stage1 = {}
        for f in sorted(glob.glob(str(ROOT / s1dir / "study_v6_n*.json"))):
            for r in json.loads(Path(f).read_text())["records"]:
                stage1[r["instance_seed"]] = r
        v7 = load(v7dir)
        hgs = load(hgsdir) if hgsdir else {}
        res = {}
        for proc in ("original", "capped") + (("hgs_capped",) if hgs else ()):
            rows = []
            for seed in sorted(v7):
                s1, r7 = stage1[seed], v7[seed]
                n = s1["customers"]
                if proc == "hgs_capped":
                    h = hgs[seed]
                    rr, cands = h["reference_ranges"], h["families"].get("capped", [])
                    admitted = bool(h["selected"].get("capped"))
                    stored = h["configurations"]["hgs_capped_cons"]
                    cons = h["configurations"]["hgs_conservative"]
                else:
                    rr = s1["reference_ranges"]
                    if proc == "original":
                        cands, admitted = s1["screened"]["candidates"], s1["screened"]["selected_plan"] is not None
                        stored = r7["configurations"]["procedure"]
                    else:
                        cands = r7["capped_procedure"]["candidates"]
                        admitted = r7["capped_procedure"]["selected_plan"] is not None
                        stored = r7["configurations"]["capped_procedure"]
                    cons = r7["configurations"]["conservative"]
                sv = lambda e: 0.0 if e is None or e.get("validation") is None else 100 * e["validation"]["service_level_success"]
                row = {"seed": seed, "n": n, "admitted": admitted, "service": {r: sv(stored) for r in RULES}}
                if not admitted and rr is not None:
                    ranges = (rr["lower"], rr["upper"])
                    data = make_synthetic_instance(n, s1["vehicles_available"], seed)
                    valid = ScenarioBank(5000, 400_000 + seed, params)
                    val = lambda plan: 100 * evaluate(plan_from_dict(plan), data, params, profile, valid)["service_level_success"]
                    row["service"]["conservative"] = sv(cons) if cons is not None else sv(stored)
                    b = best(cands, ranges, params)
                    row["service"]["best_screen"] = val(b["plan"]) if b else sv(stored)
                    choice = b
                    if cons is not None and cons.get("plan") is not None:
                        cscreen = evaluate(plan_from_dict(cons["plan"]), data, params, profile,
                                           ScenarioBank(1000, 100_000 + seed, params))
                        if b is None or cscreen["service_level_success"] > b["screening"]["service_level_success"]:
                            choice = {"plan": cons["plan"], "screening": cscreen, "is_conservative": True}
                    if choice is None:
                        row["service"]["best_any"] = sv(stored)
                    elif choice.get("is_conservative"):
                        row["service"]["best_any"] = sv(cons)
                    else:
                        row["service"]["best_any"] = row["service"]["best_screen"]
                    row["best_any_is_conservative"] = bool(choice and choice.get("is_conservative"))
                rows.append(row)
            fb = [r for r in rows if not r["admitted"]]
            summary = {"instances": len(rows), "fallback_instances": len(fb),
                       "pooled": {r: float(np.mean([x["service"][r] for x in rows])) for r in RULES},
                       "fallback_mean": {r: (float(np.mean([x["service"][r] for x in fb])) if fb else None) for r in RULES},
                       "minus_stored": {r: boot([x["service"][r] - x["service"]["stored"] for x in rows])
                                        for r in RULES if r != "stored"},
                       "best_any_conservative": sum(x.get("best_any_is_conservative", False) for x in fb)}
            res[proc] = {"summary": summary, "rows": rows}
            print(study, proc, json.dumps({k: v for k, v in summary.items() if k != "minus_stored"}),
                  {k: [round(x, 1) for x in v] for k, v in summary["minus_stored"].items()}, flush=True)
        out["studies"][study] = res
    a.output.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
