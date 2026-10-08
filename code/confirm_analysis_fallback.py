"""Prespecified analysis of confirmatory protocol 3, part B (fallback rule).

Part B runs the frozen OR-Tools pipeline (study_v6, study_v7) and the frozen
HGS pipeline (study_hgs) on 53 new instances (development seeds + 120000) and
tests a fallback rule that uses the screening evidence already computed:

  best-screened fallback: when screening admits no candidate of a procedure's
  family, return the family's candidate with the highest screening success
  (ties: lower normalized score with the record's scaling ranges, then the
  smaller buffer). If no candidate has a plan, the procedure's own stored
  fallback is kept. The chosen plan is validated once on the instance's fresh
  bank (5000 scenarios, seed 400000 + instance seed). Admitted instances are
  unchanged.

Quantities (validated kappa = 0.95 service-event probability; no plan scores 0)
  ort_capped        OR-Tools capped procedure as specified (slack-aware fallback)
  ort_capped_best   the same selections with the best-screened fallback
  hgs_capped_cons   HGS capped procedure with conservative fallback (protocol 2)
  hgs_capped_best   the same selections with the best-screened fallback

Hypotheses (see CONFIRMATORY_PROTOCOL_3.md)
  F1 primary   ort_capped_best - ort_capped > 0, all 53 instances, 97.5% interval
  F2 primary   hgs_capped_best - hgs_capped_cons > 0, all 53 instances, 97.5%
  F3 estimate  pooled ort_capped_best with a 95% interval
  F4 estimate  pooled hgs_capped_best with a 95% interval
Paired bootstrap: 20,000 resamples, seed 20260930, percentile intervals.

Modes
  confirmatory  validates both halves with the frozen validators of protocol 2,
                pointed at seeds + 120000, checks FROZEN_MANIFEST_3.json, then
                tests F1-F4 and prints CONFIRMED / NOT CONFIRMED.
  descriptive   the same quantities on the development and second confirmatory
                records; no decisions. Run before the freeze as a check.

Usage (from the package root):
  PYTHONPATH=code python code/confirm_analysis_fallback.py confirmatory \
      --output results/confirm3_fallback_analysis_output.json
  PYTHONPATH=code python code/confirm_analysis_fallback.py descriptive
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np

import confirm_analysis_hgs as cah
from confirm_analysis_robust import check_manifest
from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance, normalized_score
from relscreen_v7 import evaluate, plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
B, BOOT_SEED = 20_000, 20260930
SEED_SHIFT = 120_000
PART_B = {"stage1": [f"results/confirm3/study_v6_n{n}.json" for n in (20, 50, 100, 200)],
          "stage2": "results/confirm3/v7", "hgs": "results/confirm3/hgs"}
DESCRIPTIVE = {"development": ("results", "results/v7", "results/hgs_dev"),
               "confirmatory 2": ("results/confirm2", "results/confirm2/v7", "results/confirm2/hgs")}


def boot(values, level):
    d = np.asarray(values, float)
    m = d[np.random.default_rng(BOOT_SEED).integers(0, len(d), (B, len(d)))].mean(1)
    a = (1 - level) / 2 * 100
    return {"k": len(d), "mean": float(d.mean()), "lo": float(np.percentile(m, a)),
            "hi": float(np.percentile(m, 100 - a)), "level": level}


def best_screened(cands, ranges, params):
    ok = [c for c in cands if c.get("plan") is not None and c.get("screening") is not None]
    if not ok:
        return None
    return min(ok, key=lambda c: (-c["screening"]["service_level_success"],
                                  normalized_score(plan_from_dict(c["plan"]), ranges, params), c["beta"]))


def service(cfg):
    return 0.0 if cfg is None or cfg.get("validation") is None else 100 * cfg["validation"]["service_level_success"]


def load(directory):
    return {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
            for f in sorted(glob.glob(str(ROOT / directory / "instance_*.json")))}


def stage1_records(paths):
    out = {}
    for p in paths:
        for r in json.loads(Path(p).read_text())["records"]:
            out[r["instance_seed"]] = r
    return out


def units_for(stage1, v7, hgs):
    params, profile = ModelParams(), SpeedProfile()
    units = []
    for seed in sorted(v7):
        s1, o, h = stage1[seed], v7[seed], hgs[seed]
        n = s1["customers"]
        data, bank = None, None

        def validate_plan(plan):
            nonlocal data, bank
            if data is None:
                data = make_synthetic_instance(n, s1["vehicles_available"], seed)
                bank = ScenarioBank(5000, 400_000 + seed, params)
            return 100 * evaluate(plan_from_dict(plan), data, params, profile, bank)["service_level_success"]

        u = {"seed": seed, "n": n}
        # OR-Tools capped procedure
        stored = o["configurations"]["capped_procedure"]
        u["ort_capped"] = service(stored)
        u["ort_admitted"] = o["capped_procedure"]["selected_plan"] is not None
        u["ort_capped_best"] = u["ort_capped"]
        rr = s1["reference_ranges"]
        if not u["ort_admitted"] and rr is not None:
            b = best_screened(o["capped_procedure"]["candidates"], (rr["lower"], rr["upper"]), params)
            if b is not None:
                u["ort_capped_best"] = validate_plan(b["plan"])
        # HGS capped procedure
        u["hgs_capped_cons"] = service(h["configurations"]["hgs_capped_cons"])
        u["hgs_admitted"] = bool(h["selected"].get("capped"))
        u["hgs_capped_best"] = u["hgs_capped_cons"]
        rr = h["reference_ranges"]
        if not u["hgs_admitted"] and rr is not None:
            b = best_screened(h["families"].get("capped", []), (rr["lower"], rr["upper"]), params)
            if b is not None:
                u["hgs_capped_best"] = validate_plan(b["plan"])
        units.append(u)
    return units


def analyse(units, confirmatory):
    out = {"instances": len(units)}
    tests = {
        "F1": ("primary", boot([u["ort_capped_best"] - u["ort_capped"] for u in units], 0.975)),
        "F2": ("primary", boot([u["hgs_capped_best"] - u["hgs_capped_cons"] for u in units], 0.975)),
    }
    for h, (role, res) in tests.items():
        verdict = ("CONFIRMED" if res["lo"] > 0 else "NOT CONFIRMED") if confirmatory else "descriptive only"
        out[h] = {"role": role, **res, "verdict": verdict}
    out["F3"] = {"role": "estimate", **boot([u["ort_capped_best"] for u in units], 0.95)}
    out["F4"] = {"role": "estimate", **boot([u["hgs_capped_best"] for u in units], 0.95)}
    out["pooled"] = {k: float(np.mean([u[k] for u in units]))
                     for k in ("ort_capped", "ort_capped_best", "hgs_capped_cons", "hgs_capped_best")}
    out["fallback_instances"] = {"ort": sum(not u["ort_admitted"] for u in units),
                                 "hgs": sum(not u["hgs_admitted"] for u in units)}
    out["by_size"] = {str(n): {k: float(np.mean([u[k] for u in units if u["n"] == n]))
                               for k in ("ort_capped", "ort_capped_best", "hgs_capped_cons", "hgs_capped_best")}
                      for n in sorted({u["n"] for u in units})}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("confirmatory", "descriptive"))
    ap.add_argument("--manifest", type=Path, default=ROOT / "FROZEN_MANIFEST_3.json")
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()
    if a.mode == "confirmatory":
        check_manifest(a.manifest)
        # Point the frozen validators of protocol 2 at part B without editing them.
        cah.EXPECTED = {seed: n for n, (_, k, first) in cah.DESIGN.items()
                        for seed in range(first + SEED_SHIFT, first + SEED_SHIFT + k)}
        stage1 = [ROOT / p for p in PART_B["stage1"]]
        ort, hgs = cah.validate(stage1, ROOT / PART_B["stage2"], ROOT / PART_B["hgs"],
                                ROOT / "FROZEN_MANIFEST_2.json", ROOT)
        units = units_for(stage1_records(stage1), load(PART_B["stage2"]), load(PART_B["hgs"]))
        out = {"mode": "confirmatory", **analyse(units, True)}
    else:
        out = {"mode": "descriptive"}
        for study, (s1dir, v7dir, hgsdir) in DESCRIPTIVE.items():
            stage1 = stage1_records(sorted(glob.glob(str(ROOT / s1dir / "study_v6_n*.json"))))
            out[study] = analyse(units_for(stage1, load(v7dir), load(hgsdir)), False)
    text = json.dumps(out, indent=1)
    print(text)
    if a.output:
        a.output.write_text(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
