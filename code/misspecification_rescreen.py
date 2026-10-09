"""Re-screening under the alternative delay models (exploratory).

code/misspecification.py evaluates the stored plans, fixed, under four other
delay models. This script asks what the procedure itself would do under each
model: every stored candidate of the capped family is screened again on 1000
scenarios drawn from that model (seed 100000 + instance seed, the screening
seed of the studies), the selection rule is applied unchanged (smallest
normalized score among candidates whose Wilson lower bound reaches 0.95, ties
by buffer), and the selected plan is validated on the 5000 scenarios of that
model used by code/misspecification.py (seed 700000 + instance seed). The
candidate families are not regenerated: they were built for the paper's model.

Two fallbacks are reported when nothing is admitted: the procedure's stored
fallback (OR-Tools: the slack-aware beta-0 plan; HGS: the conservative-speed
plan) and the best-screened candidate under the same model.

Under the paper's model ("baseline") the screening bank equals the studies'
screening bank, so the selections must reproduce the stored ones; the script
checks this before using any other model.

Usage: PYTHONPATH=code python code/misspecification_rescreen.py --output results/misspecification_rescreen.json
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np

from analyse_robust import boot
from misspecification import MODELS, SCENARIOS, SEED_OFFSET, AltBank, evaluate_alt
from relscreen_v6 import ModelParams, make_synthetic_instance, normalized_score, wilson_lower_bound
from relscreen_v7 import plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
STUDIES = {
    "development": ("results", "results/v7", "results/hgs_dev"),
    "confirmatory 1": ("results/confirm", "results/confirm/v7", None),
    "confirmatory 2": ("results/confirm2", "results/confirm2/v7", "results/confirm2/hgs"),
}


def load(directory):
    return {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
            for f in sorted(glob.glob(str(ROOT / directory / "instance_*.json")))}


def same(a, b):
    return a is not None and b is not None and a["routes"] == b["routes"] and a["departures"] == b["departures"]


def rescreen(cands, ranges, params, data, bank):
    scored = []
    for c in cands:
        if c.get("plan") is None:
            continue
        p = evaluate_alt(plan_from_dict(c["plan"]), data, params, bank) / 100
        scored.append((c, p, wilson_lower_bound(p, bank.n, params.eta)))
    passing = [(normalized_score(plan_from_dict(c["plan"]), ranges, params), c["beta"], c) for c, p, lcb in scored
               if lcb >= params.alpha]
    selected = min(passing, key=lambda x: (x[0], x[1]))[2] if passing else None
    best = (min(scored, key=lambda x: (-x[1], normalized_score(plan_from_dict(x[0]["plan"]), ranges, params),
                                       x[0]["beta"]))[0] if scored else None)
    return selected, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    params = ModelParams()
    fixed = json.loads((ROOT / "results/misspecification.json").read_text())
    out = {"models": MODELS, "studies": {}}
    for study, (s1dir, v7dir, hgsdir) in STUDIES.items():
        stage1 = {}
        for f in sorted(glob.glob(str(ROOT / s1dir / "study_v6_n*.json"))):
            for r in json.loads(Path(f).read_text())["records"]:
                stage1[r["instance_seed"]] = r
        v7, hgs = load(v7dir), (load(hgsdir) if hgsdir else {})
        fixed_rows = {r["seed"]: r for r in fixed["studies"][study]["rows"]}
        rows = []
        for seed in sorted(v7):
            s1, o = stage1[seed], v7[seed]
            n = s1["customers"]
            data = make_synthetic_instance(n, s1["vehicles_available"], seed)
            procs = {}
            if s1["reference_ranges"] is not None:
                rr = s1["reference_ranges"]
                procs["ort"] = (o["capped_procedure"]["candidates"], (rr["lower"], rr["upper"]),
                                o["capped_procedure"]["selected_plan"], s1["weighted_objective_only"]["plan"])
            if hgs and hgs[seed]["reference_ranges"] is not None:
                h = hgs[seed]
                rr = h["reference_ranges"]
                cons = h["configurations"]["hgs_conservative"]
                beta0 = next((c for c in h["families"]["uncapped"] if c["beta"] == 0), None)
                fb = cons["plan"] if cons is not None else (beta0 or {}).get("plan")
                stored_sel = h["configurations"]["hgs_capped_cons"]["plan"] if h["selected"]["capped"] else None
                procs["hgs"] = (h["families"]["capped"], (rr["lower"], rr["upper"]), stored_sel, fb)
            row = {"seed": seed, "n": n, "service": {}}
            for model in MODELS:
                screen = AltBank(1000, 100_000 + seed, model)
                valid = AltBank(SCENARIOS, SEED_OFFSET + seed, model)
                res = {}
                for tag, (cands, ranges, stored_sel, fallback) in procs.items():
                    sel, best = rescreen(cands, ranges, params, data, screen)
                    if model == "baseline":
                        assert (sel is None and stored_sel is None) or same(sel["plan"] if sel else None, stored_sel), \
                            (study, seed, tag)
                    val = lambda plan: 0.0 if plan is None else evaluate_alt(plan_from_dict(plan), data, params, valid)
                    res[f"{tag}_rescreened"] = val(sel["plan"] if sel else fallback)
                    res[f"{tag}_rescreened_best"] = val(sel["plan"] if sel else (best["plan"] if best else fallback))
                    res[f"{tag}_admitted"] = sel is not None
                for k in ("ort_conservative", "ort_capped", "hgs_conservative", "hgs_capped_cons"):
                    if k in fixed_rows[seed]["service"][model]:
                        res[k] = fixed_rows[seed]["service"][model][k]
                row["service"][model] = res
            rows.append(row)
            print(study, seed, flush=True)
        out["studies"][study] = {"rows": rows}
    # pooled summary over studies
    allrows = [r for s in out["studies"].values() for r in s["rows"]]
    summary = {}
    for model in MODELS:
        g = {}
        for k in ("ort_capped", "ort_rescreened", "ort_rescreened_best", "ort_conservative",
                  "hgs_capped_cons", "hgs_rescreened", "hgs_rescreened_best", "hgs_conservative"):
            vals = [r["service"][model][k] for r in allrows if k in r["service"][model]]
            g[k] = {"instances": len(vals), "mean": float(np.mean(vals))}
        for tag in ("ort", "hgs"):
            rs = [r for r in allrows if f"{tag}_admitted" in r["service"][model]]
            g[f"{tag}_admitted"] = sum(r["service"][model][f"{tag}_admitted"] for r in rs)
            fixed_key = "ort_capped" if tag == "ort" else "hgs_capped_cons"
            cons_key = f"{tag}_conservative"
            for x in ("rescreened", "rescreened_best"):
                pr = [r for r in rs if fixed_key in r["service"][model]]
                g[f"{tag}_{x}_minus_fixed"] = boot([r["service"][model][f"{tag}_{x}"] - r["service"][model][fixed_key] for r in pr])
                pc = [r for r in rs if cons_key in r["service"][model]]
                g[f"{tag}_{x}_minus_conservative"] = boot([r["service"][model][f"{tag}_{x}"] - r["service"][model][cons_key] for r in pc])
        summary[model] = g
    out["summary"] = summary
    a.output.write_text(json.dumps(out, indent=1))
    for model, g in summary.items():
        print(model, {k: (round(v["mean"], 1) if isinstance(v, dict) else (v if not isinstance(v, list) else [round(x, 1) for x in v]))
                      for k, v in g.items()})


if __name__ == "__main__":
    main()
