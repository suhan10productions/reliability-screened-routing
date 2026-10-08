"""Prespecified analysis of confirmatory protocol 3 (robust comparison).

Modes
  confirmatory  checks the frozen manifest and every record, then tests R1-R4 on
                the confirmatory instances and prints CONFIRMED / NOT CONFIRMED.
  descriptive   computes the same quantities on the development instances
                (results/robust_capped_dev, results/v7, results/hgs_dev); no
                decisions are printed. This mode was run before the freeze to
                check the code against the exploratory results.

Quantities (validated kappa = 0.95 service-event probability on the fresh bank,
5000 scenarios at seed 400000 + instance seed; a configuration without a plan
scores 0):
  screened_relief  screened robust with relief: among the 15 relieved settings,
                   the shortest plan whose screening lower bound reaches 0.95,
                   otherwise the plan with the highest screening success
                   (analyse_robust.screened_robust, unchanged)
  ort_capped       OR-Tools capped procedure (stored, studies 1 and 2)
  hgs_capped_cons  HGS capped procedure with conservative fallback (stored, study 2)
  relief_box_0.6   relieved robust, box uncertainty, theta = 0.6

Hypotheses (see CONFIRMATORY_PROTOCOL_3.md)
  R1 primary    screened_relief - ort_capped > 0, all 90 instances, 97.5% interval
  R2 primary    screened_relief - hgs_capped_cons > 0, 45 study-2 instances, 97.5%
  R3 secondary  vehicles: screened_relief - hgs_capped_cons > 0, study-2 instances
                where both have a plan, 95%
  R4 secondary  distance: 100 (d_screened / d_box - 1) < 0, instances where both
                have a plan, 95%
Paired bootstrap: 20,000 resamples, seed 20260930, percentile intervals.

Usage (from the package root):
  PYTHONPATH=code python code/confirm_analysis_robust.py confirmatory
  PYTHONPATH=code python code/confirm_analysis_robust.py descriptive
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from analyse_robust import screened_robust
from study_robust import DESIGN, GRID, ITERATIONS, SCHEMA, key

ROOT = Path(__file__).resolve().parents[1]
B, BOOT_SEED = 20_000, 20260930
MANIFEST_FILES = [
    "CONFIRMATORY_PROTOCOL_3.md", "requirements.txt",
    "code/relscreen_v6.py", "code/relscreen_v7.py", "code/robust_generator.py",
    "code/study_robust.py", "code/analyse_robust.py", "code/confirm_analysis_robust.py",
]
SIZES = (20, 50, 100)
CAPPED_GRID = [key(g, d) for g, d in GRID if g != 0]
STUDIES = {  # name -> (seed shift, robust dir, OR-Tools stage-2 dir, HGS dir or None)
    "confirmatory 1": (60_000, "results/confirm/robust_capped", "results/confirm/v7", None),
    "confirmatory 2": (80_000, "results/confirm2/robust_capped", "results/confirm2/v7", "results/confirm2/hgs"),
}
DEV = {"development": (0, "results/robust_capped_dev", "results/v7", "results/hgs_dev")}


def fail(msg):
    print(f"VALIDATION FAILED: {msg}")
    sys.exit(2)


def boot(d, level):
    d = np.asarray(d, float)
    m = d[np.random.default_rng(BOOT_SEED).integers(0, len(d), (B, len(d)))].mean(1)
    a = (1 - level) / 2 * 100
    return {"k": len(d), "mean": float(d.mean()), "lo": float(np.percentile(m, a)),
            "hi": float(np.percentile(m, 100 - a)), "level": level}


def expected_seeds(shift):
    return {DESIGN[n][2] + shift + i: n for n in SIZES for i in range(DESIGN[n][1])}


def check_manifest(path):
    if not path.exists():
        fail(f"manifest {path} missing")
    manifest = json.loads(path.read_text())
    if sorted(manifest) != sorted(MANIFEST_FILES):
        fail("manifest file list differs from MANIFEST_FILES")
    for rel, digest in manifest.items():
        if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest:
            fail(f"{rel} differs from the frozen manifest")


def load_dir(directory):
    out = {}
    for f in sorted(glob.glob(str(ROOT / directory / "instance_*.json"))):
        r = json.loads(Path(f).read_text())
        if Path(f).name != f"instance_{r['instance_seed']}.json":
            fail(f"{f} is not named for its seed")
        out[r["instance_seed"]] = r
    return out


def validate_robust(directory, shift):
    d = ROOT / directory
    extra = [p.name for p in d.iterdir() if not p.name.startswith("instance_")] if d.exists() else []
    if extra:
        fail(f"{directory}: unexpected files {extra} (software errors block the analysis)")
    recs = load_dir(directory)
    want = expected_seeds(shift)
    if sorted(recs) != sorted(want):
        fail(f"{directory}: seed set differs (missing {sorted(set(want) - set(recs))}, "
             f"unexpected {sorted(set(recs) - set(want))})")
    for s, r in recs.items():
        n = want[s]
        checks = {"schema": SCHEMA, "customers": n, "vehicles_available": DESIGN[n][0],
                  "screening_seed": 100_000 + s, "validation_seed": 400_000 + s, "screen_scenarios": 1000,
                  "validation_scenarios": 5000, "iterations": ITERATIONS[n], "search_seed": s,
                  "capped": True, "grid": CAPPED_GRID}
        for k, v in checks.items():
            if r.get(k) != v:
                fail(f"{directory} seed {s}: {k} = {r.get(k)!r}, expected {v!r}")
        if sorted(r["settings"]) != sorted(CAPPED_GRID):
            fail(f"seed {s}: settings differ from the grid")
        for k, e in r["settings"].items():
            ok = e["status"] == "ok"
            if ok != (e["plan"] is not None) or ok != (e["validation"] is not None) or ok != (e["screening"] is not None):
                fail(f"seed {s} {k}: status disagrees with plan, screening or validation")
            if not (ok or e["status"].startswith("no_plan")):
                fail(f"seed {s} {k}: status {e['status']!r}")
            if ok:
                visits = sorted(c for route in e["plan"]["routes"] for c in route if c)
                if visits != list(range(1, n + 1)):
                    fail(f"seed {s} {k}: plan does not visit every customer exactly once")
                if e["validation"]["scenarios"] != 5000 or e["screening"]["scenarios"] != 1000:
                    fail(f"seed {s} {k}: scenario counts")
    return recs


def service(entry):
    return 0.0 if entry is None or entry.get("validation") is None else 100 * entry["validation"]["service_level_success"]


def metric(entry, name):
    return None if entry is None or entry.get("plan") is None else entry["plan"]["metrics"][name]


def units_for(studies, confirmatory):
    units = []
    for study, (shift, rdir, odir, hdir) in studies.items():
        rob = validate_robust(rdir, shift) if confirmatory else load_dir(rdir)
        ort, hgs = load_dir(odir), (load_dir(hdir) if hdir else {})
        for s in sorted(rob):
            if s not in ort or (hdir and s not in hgs):
                fail(f"{study} seed {s}: stored OR-Tools or HGS record missing")
            if ort[s]["vehicles_available"] != rob[s]["vehicles_available"]:
                fail(f"{study} seed {s}: fleet sizes differ between records")
            sr, admitted = screened_robust(rob[s]["settings"])
            units.append({"study": study, "seed": s, "n": rob[s]["customers"],
                          "screened_relief": sr, "screened_admitted": admitted,
                          "relief_box_0.6": rob[s]["settings"]["box_d0.6"],
                          "settings": rob[s]["settings"],
                          "ort_capped": ort[s]["configurations"]["capped_procedure"],
                          "hgs_capped_cons": hgs[s]["configurations"]["hgs_capped_cons"] if hdir else None,
                          "has_hgs": bool(hdir)})
    return units


def analyse(units, confirmatory):
    out = {"instances": len(units)}
    hg = [u for u in units if u["has_hgs"]]
    r = {
        "R1": ("primary", boot([service(u["screened_relief"]) - service(u["ort_capped"]) for u in units], 0.975), ">"),
        "R2": ("primary", boot([service(u["screened_relief"]) - service(u["hgs_capped_cons"]) for u in hg], 0.975), ">"),
    }
    both = [u for u in hg if metric(u["screened_relief"], "fleet") is not None and metric(u["hgs_capped_cons"], "fleet") is not None]
    r["R3"] = ("secondary", boot([metric(u["screened_relief"], "fleet") - metric(u["hgs_capped_cons"], "fleet") for u in both], 0.95), ">")
    both = [u for u in units if metric(u["screened_relief"], "distance") and metric(u["relief_box_0.6"], "distance")]
    r["R4"] = ("secondary", boot([100 * (metric(u["screened_relief"], "distance") / metric(u["relief_box_0.6"], "distance") - 1)
                                  for u in both], 0.95), "<")
    for h, (role, res, direction) in r.items():
        if not confirmatory:
            verdict = "descriptive only"
        elif direction == ">":
            verdict = "CONFIRMED" if res["lo"] > 0 else "NOT CONFIRMED"
        else:
            verdict = "CONFIRMED" if res["hi"] < 0 else "NOT CONFIRMED"
        out[h] = {"role": role, **res, "verdict": verdict}
    # descriptive quantities (no decisions)
    out["service_box_0.6_minus_screened"] = boot(
        [service(u["relief_box_0.6"]) - service(u["screened_relief"]) for u in units], 0.95)
    out["screened_admitted"] = sum(u["screened_admitted"] for u in units)
    out["pooled"] = {c: float(np.mean([service(u[c]) for u in units])) for c in ("screened_relief", "ort_capped", "relief_box_0.6")}
    out["pooled"]["hgs_capped_cons (study 2)"] = float(np.mean([service(u["hgs_capped_cons"]) for u in hg])) if hg else None
    out["pooled_settings"] = {k: float(np.mean([service(u["settings"][k]) for u in units])) for k in CAPPED_GRID}
    out["by_size"] = {str(n): {"instances": sum(u["n"] == n for u in units),
                               "screened_admitted": sum(u["screened_admitted"] for u in units if u["n"] == n),
                               "screened_relief": float(np.mean([service(u["screened_relief"]) for u in units if u["n"] == n])),
                               "ort_capped": float(np.mean([service(u["ort_capped"]) for u in units if u["n"] == n]))}
                      for n in SIZES}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("confirmatory", "descriptive"))
    ap.add_argument("--manifest", type=Path, default=ROOT / "FROZEN_MANIFEST_3.json")
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()
    if a.mode == "confirmatory":
        check_manifest(a.manifest)
        units = units_for(STUDIES, True)
    else:
        units = units_for(DEV, False)
    out = {"mode": a.mode, **analyse(units, a.mode == "confirmatory")}
    text = json.dumps(out, indent=1)
    print(text)
    if a.output:
        a.output.write_text(text + "\n")


if __name__ == "__main__":
    main()
