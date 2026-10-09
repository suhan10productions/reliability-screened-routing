"""Robust plans restricted to the comparator's fleet (exploratory).

The relieved robust plans used more vehicles than the screened procedures, so
part of their extra reliability may come from fleet size. For each development
instance and each comparator (the HGS capped procedure with conservative
fallback, and the OR-Tools capped procedure), this script keeps only the
relieved robust settings whose plan uses no more vehicles than the comparator's
plan and applies the screened-robust rule within them: the shortest plan whose
screening lower bound reaches 0.95, otherwise the plan with the highest
screening success. All plans were validated on the instance's fresh bank when
they were computed, so nothing is re-evaluated.

Usage: PYTHONPATH=code python code/robust_fleet_matched.py --output results/robust_fleet_matched.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from analyse_robust import boot, load, screened_robust

ROOT = Path(__file__).resolve().parents[1]


def service(e):
    return 0.0 if e is None or e.get("validation") is None else 100 * e["validation"]["service_level_success"]


def fleet(e):
    return None if e is None or e.get("plan") is None else e["plan"]["metrics"]["fleet"]


def distance(e):
    return None if e is None or e.get("plan") is None else e["plan"]["metrics"]["distance"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    sets = {
        "development": (load("results/robust_capped_dev"), load("results/v7"), load("results/hgs_dev")),
        # confirmatory instances of part A (exploratory addition, not prespecified)
        "confirmatory": ({**load("results/confirm/robust_capped"), **load("results/confirm2/robust_capped")},
                         {**load("results/confirm/v7"), **load("results/confirm2/v7")}, load("results/confirm2/hgs")),
    }
    result = {}
    for setname, (cap, ort, hgs) in sets.items():
        result[setname] = compare(cap, ort, hgs)
    a.output.write_text(json.dumps(result, indent=1))


def compare(cap, ort, hgs):
    out = {}
    for name, get in (("hgs_capped_cons", lambda s: hgs[s]["configurations"]["hgs_capped_cons"]),
                      ("ort_capped", lambda s: ort[s]["configurations"]["capped_procedure"])):
        rows = []
        for s in sorted(cap):
            if name == "hgs_capped_cons" and s not in hgs:
                continue
            ref = get(s)
            limit = fleet(ref)
            unrestricted, _ = screened_robust(cap[s]["settings"])
            if limit is None:
                rows.append({"seed": s, "eligible": False})
                continue
            subset = {k: v for k, v in cap[s]["settings"].items() if v["status"] == "ok" and fleet(v) <= limit}
            chosen, admitted = screened_robust(subset) if subset else (None, False)
            rows.append({"seed": s, "n": cap[s]["customers"], "eligible": chosen is not None, "admitted": admitted,
                         "ref_service": service(ref), "ref_fleet": limit, "ref_distance": distance(ref),
                         "matched_service": service(chosen), "matched_fleet": fleet(chosen),
                         "matched_distance": distance(chosen),
                         "unrestricted_service": service(unrestricted), "unrestricted_fleet": fleet(unrestricted)})
        el = [r for r in rows if r["eligible"]]
        out[name] = {
            "instances": len(rows), "with_fleet_matched_plan": len(el),
            "admitted_within_fleet": sum(r["admitted"] for r in el),
            "service_matched_minus_ref": boot([r["matched_service"] - r["ref_service"] for r in el]),
            "service_unrestricted_minus_ref": boot([r["unrestricted_service"] - r["ref_service"] for r in el]),
            "fleet_matched_minus_ref": boot([r["matched_fleet"] - r["ref_fleet"] for r in el]),
            "distance_matched_vs_ref_pct": boot([100 * (r["matched_distance"] / r["ref_distance"] - 1) for r in el]),
            "pooled_matched": float(np.mean([r["matched_service"] for r in el])),
            "pooled_ref": float(np.mean([r["ref_service"] for r in el])),
            "rows": rows,
        }
        print(name, {k: (v if not isinstance(v, list) or len(v) != 3 else [round(x, 2) for x in v])
                     for k, v in out[name].items() if k != "rows"})
    return out


if __name__ == "__main__":
    main()
