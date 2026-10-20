"""The cost of reliability: buffer candidates versus fixed padding (exploratory).

For every development instance, two families of plans:
  buffers   the 13 capped buffer candidates of the screening procedure
            (beta = 0, 5, ..., 60 minutes; results/v7), each evaluated here on the
            instance's validation bank (5000 days, seed 400000 + instance seed);
  padding   plans for distance at padding levels 0, 10, ..., 50% (code/padding_sweep.py),
            already evaluated on the same validation bank.
Both families are judged on the same simulated days, so the comparison is paired.

For each reliability level q, the cheapest plan of a family whose validated
success probability is at least q gives the cost of reaching q with that
family: distance relative to the 0% padding plan (the plain shortest-distance
plan), and vehicles. "Certified" uses the exact Clopper-Pearson one-sided 95%
lower bound of the validated success probability instead of its estimate.

Usage (from the package root):
  PYTHONPATH=code python code/frontier.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np

from certify import cp_lower, successes
from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance
from relscreen_v7 import evaluate, plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
LEVELS = (0, 10, 20, 30, 40, 50)
QS = (0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 0.99)


def boot(x, seed=20261020, n=20000):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def main():
    params, profile = ModelParams(), SpeedProfile()
    stage1 = {}
    for f in sorted(glob.glob(str(ROOT / "results" / "study_v6_n*.json"))):
        for r in json.loads(Path(f).read_text())["records"]:
            stage1[r["instance_seed"]] = r
    inst = []
    for f in sorted(glob.glob(str(ROOT / "results" / "v7" / "instance_*.json"))):
        r = json.loads(Path(f).read_text())
        seed = r["instance_seed"]
        s1 = stage1[seed]
        data = make_synthetic_instance(s1["customers"], s1["vehicles_available"], seed)
        bank = ScenarioBank(5000, 400_000 + seed, params)
        buffers = []
        for c in r["capped_procedure"]["candidates"]:
            if c["plan"] is None:
                continue
            v = evaluate(plan_from_dict(c["plan"]), data, params, profile, bank)
            k, n = successes(v)
            buffers.append({"beta": c["beta"], "distance": c["plan"]["metrics"]["distance"],
                            "fleet": c["plan"]["metrics"]["fleet"], "success": k / n, "cp_lower": cp_lower(k, n)})
        padding = []
        for lv in LEVELS:
            p = json.loads((ROOT / "results" / "padding_sweep" / f"pad{lv:02d}_{seed}.json").read_text())
            if not p["has_plan"]:
                continue
            k, n = successes(p["validation"])
            padding.append({"padding": lv, "distance": p["metrics"]["distance"], "fleet": p["metrics"]["fleet"],
                            "success": k / n, "cp_lower": cp_lower(k, n)})
        ref = json.loads((ROOT / "results" / "padding_sweep" / f"pad00_{seed}.json").read_text())
        assert ref["has_plan"]
        inst.append({"seed": seed, "n": s1["customers"], "ref_distance": ref["metrics"]["distance"],
                     "ref_fleet": ref["metrics"]["fleet"], "buffers": buffers, "padding": padding})
    N = len(inst)

    def cheapest(plans, q, key):
        ok = [p for p in plans if p[key] >= q]
        return min(ok, key=lambda p: (p["distance"], p["fleet"])) if ok else None

    out = {"instances": N, "levels": {}}
    for key, qs in (("success", QS), ("cp_lower", (0.95,))):
        for q in qs:
            name = f"{q:.2f}" + ("_certified" if key == "cp_lower" else "")
            rows = []
            for i in inst:
                b, p = cheapest(i["buffers"], q, key), cheapest(i["padding"], q, key)
                rows.append({"seed": i["seed"], "n": i["n"],
                             "buffers": None if b is None else {"distance_pct": 100 * (b["distance"] / i["ref_distance"] - 1),
                                                               "fleet": b["fleet"] - i["ref_fleet"], "beta": b["beta"]},
                             "padding": None if p is None else {"distance_pct": 100 * (p["distance"] / i["ref_distance"] - 1),
                                                               "fleet": p["fleet"] - i["ref_fleet"], "level": p["padding"]}})
            both = [r for r in rows if r["buffers"] and r["padding"]]
            out["levels"][name] = {
                "q": q, "certified": key == "cp_lower",
                "reach_buffers": sum(r["buffers"] is not None for r in rows),
                "reach_padding": sum(r["padding"] is not None for r in rows),
                "reach_buffers_only": sum(r["buffers"] is not None and r["padding"] is None for r in rows),
                "reach_padding_only": sum(r["padding"] is not None and r["buffers"] is None for r in rows),
                "both": len(both),
                "distance_pct_buffers": boot([r["buffers"]["distance_pct"] for r in both]) if both else None,
                "distance_pct_padding": boot([r["padding"]["distance_pct"] for r in both]) if both else None,
                "distance_pct_diff": boot([r["buffers"]["distance_pct"] - r["padding"]["distance_pct"] for r in both]) if both else None,
                "fleet_diff": boot([r["buffers"]["fleet"] - r["padding"]["fleet"] for r in both]) if both else None,
                "rows": rows}
            v = out["levels"][name]
            print(name, v["reach_buffers"], v["reach_padding"], v["both"],
                  None if not both else [round(x, 2) for x in v["distance_pct_diff"]],
                  None if not both else [round(x, 2) for x in v["fleet_diff"]], flush=True)
    out["instances_detail"] = inst
    (ROOT / "results" / "frontier_summary.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
