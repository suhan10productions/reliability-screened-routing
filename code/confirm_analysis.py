"""Prespecified analysis for CONFIRMATORY_PROTOCOL.md.

Two modes.

  confirmatory  Validates the complete prescribed study before computing
                anything: exact fresh seed set, size allocation, run
                parameters, scenario counts, seed derivation, provenance
                hashes, and the frozen protocol/code manifest. Any violation
                aborts. Only this mode prints CONFIRMED / NOT CONFIRMED.
  descriptive   Computes the same quantities on any records (for example the
                exploratory development set) and labels them descriptive.
                It never prints a confirmation verdict.

Usage:
  python code/confirm_analysis.py confirmatory --stage1 results/confirm/study_v6_n*.json \
         --stage2 results/confirm/v7 --manifest FROZEN_MANIFEST.json
  python code/confirm_analysis.py descriptive --stage2 results/v7
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

B = 20_000
SEED = 20260930
Z = 1.6448536269514722
N_FRESH = 5000

# Frozen confirmatory design (must match CONFIRMATORY_PROTOCOL.md).
SEED_SHIFT = 60000
DESIGN = {20: (20, 7200), 50: (15, 7500), 100: (10, 8000), 200: (8, 9000)}
EXPECTED = {n: set(range(first + SEED_SHIFT, first + SEED_SHIFT + k)) for n, (k, first) in DESIGN.items()}
STAGE1_PARAMS = {"solve_seconds": 5.0, "anchor_solve_seconds": 2.0,
                 "feasibility_attempt_limit": 3, "screen_scenarios": 1000,
                 "validation_scenarios": 5000, "beta_values": list(range(0, 61, 5))}
CONFIGS = ("nominal", "conservative", "slack", "fleet_matched", "procedure",
           "screened_conservative", "capped_procedure", "clock_aware")
SWEEP_CELLS = {f"{s:.2f},{r:.1f}" for s in (0.1, 0.2, 0.3) for r in (0.0, 0.5, 0.9)}
STAGE1_PLAN_KEYS = {"static": "static", "peak_aware_distance": "peak_aware_distance",
                    "weighted_objective_only": "weighted_objective_only",
                    "fleet_matched_distance": "fleet_matched_distance"}
MANIFEST_FILES = ("CONFIRMATORY_PROTOCOL.md", "requirements.txt",
                  "code/relscreen_v6.py", "code/relscreen_v7.py", "code/study_v6.py",
                  "code/study_v7.py", "code/confirm_analysis.py")


class ProtocolViolation(SystemExit):
    pass


def fail(msg: str):
    raise ProtocolViolation(f"PROTOCOL VIOLATION: {msg}")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson_lb(p: float, n: int) -> float:
    a = p + Z * Z / (2 * n)
    b = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return (a - b) / (1 + Z * Z / n)


# ---------------------------------------------------------------- validation
def validate(stage1_paths, stage2_dir: Path, manifest_path: Path, root: Path):
    man = json.loads(manifest_path.read_text())
    for rel in MANIFEST_FILES:
        if man.get(rel) != sha(root / rel):
            fail(f"{rel} differs from the frozen manifest")

    # ---- stage 1: every prescribed instance exactly once, no software errors
    s1 = []
    for p in stage1_paths:
        d = json.loads(Path(p).read_text())
        if d.get("software_errors"):
            e = d["software_errors"][0]
            fail(f"stage-1 software error on seed {e['instance_seed']}: {e['error']} "
                 "(fix, re-freeze and report as a labelled deviation)")
        s1 += d["records"]
    seeds1 = [r["instance_seed"] for r in s1]
    if len(seeds1) != len(set(seeds1)):
        fail("duplicate stage-1 records")
    expected_seeds = set().union(*EXPECTED.values())
    if set(seeds1) != expected_seeds:
        fail("stage-1 global seed set differs from the prescribed set "
             f"(missing {sorted(expected_seeds - set(seeds1))[:5]}, "
             f"unexpected {sorted(set(seeds1) - expected_seeds)[:5]})")
    if any(r["customers"] not in EXPECTED for r in s1):
        fail("stage-1 record has an unsupported customer size")
    for n, seeds in EXPECTED.items():
        have = {r["instance_seed"] for r in s1 if r["customers"] == n}
        if have != seeds:
            fail(f"n={n}: stage-1 seeds differ from the prescribed set "
                 f"(missing {sorted(seeds - have)[:5]}, unexpected {sorted(have - seeds)[:5]})")
    for r in s1:
        seed = r["instance_seed"]
        for k, v in STAGE1_PARAMS.items():
            if r.get(k) != v:
                fail(f"seed {seed}: {k}={r.get(k)!r}, expected {v!r}")
        for key, off in (("screening_seed", 100_000), ("validation_seed", 200_000)):
            if r[key] != off + seed:
                fail(f"seed {seed}: stage-1 {key} not derived as prescribed")
        st = r.get("configuration_status")
        if not st:
            fail(f"seed {seed}: stage-1 configuration status missing")
        for key in STAGE1_PLAN_KEYS:
            if (st.get(key) == "ok") != (r[key]["plan"] is not None):
                fail(f"seed {seed}: stage-1 {key} status disagrees with its plan")
        if (st.get("anchors") == "ok") != (r["reference_ranges"] is not None):
            fail(f"seed {seed}: anchor status disagrees with the scaling ranges")
        if (st.get("screened") == "ok") != bool(r["screened"]["candidates"]):
            fail(f"seed {seed}: screening status disagrees with its candidates")

    # ---- stage 2: one record per instance, no software errors, nothing else
    errors = sorted(glob.glob(str(stage2_dir / "software_error_*.json")))
    if errors:
        e = json.loads(Path(errors[0]).read_text())
        fail(f"stage-2 software error on seed {e['instance_seed']}: {e['error']} "
             "(fix, re-freeze and report as a labelled deviation)")
    unexpected = [f for f in glob.glob(str(stage2_dir / "*.json"))
                  if not Path(f).name.startswith("instance_")]
    if unexpected:
        fail(f"unexpected stage-2 files: {[Path(f).name for f in unexpected][:3]}")
    s2 = {}
    for f in sorted(glob.glob(str(stage2_dir / "instance_*.json"))):
        r = json.loads(Path(f).read_text())
        seed = r["instance_seed"]
        if Path(f).name != f"instance_{seed}.json":
            fail(f"{Path(f).name} contains seed {seed}")
        if seed in s2:
            fail(f"duplicate stage-2 record for seed {seed}")
        s2[seed] = r
    by_seed = {r["instance_seed"]: r for r in s1}
    if set(s2) != set(by_seed):
        fail(f"stage-2 records do not match stage 1 (missing {sorted(set(by_seed) - set(s2))[:5]}, "
             f"unexpected {sorted(set(s2) - set(by_seed))[:5]})")

    for seed, r in s2.items():
        src = hashlib.sha256(json.dumps(by_seed[seed], sort_keys=True).encode()).hexdigest()
        if r["customers"] != by_seed[seed]["customers"]:
            fail(f"seed {seed}: stage-2 size {r['customers']} differs from "
                 f"stage-1 size {by_seed[seed]['customers']}")
        if r["source_record_sha256"] != src:
            fail(f"seed {seed}: stage-2 record does not derive from its stage-1 record")
        if r["candidate_seconds"] != 5.0:
            fail(f"seed {seed}: candidate budget {r['candidate_seconds']}")
        for key, off in (("screening_seed", 100_000), ("validation_seed", 400_000),
                         ("sensitivity_seed", 500_000)):
            if r[key] != off + seed:
                fail(f"seed {seed}: {key} not derived as prescribed")
        st = r.get("configuration_status") or {}
        for c in CONFIGS:
            if c not in r["configurations"] or c not in st:
                fail(f"seed {seed}: configuration {c} or its status is absent")
            x = r["configurations"][c]
            if (st[c] == "ok") != (x is not None):
                fail(f"seed {seed}: {c} status {st[c]!r} disagrees with its plan")
            if x is None:
                continue
            if x["validation"]["scenarios"] != N_FRESH:
                fail(f"seed {seed}: {c} validated on {x['validation']['scenarios']} scenarios")
            if set(x.get("sensitivity", {})) != SWEEP_CELLS:
                fail(f"seed {seed}: {c} sweep cells {sorted(set(x.get('sensitivity', {})) ^ SWEEP_CELLS)} "
                     "missing or unexpected")
            for cell in x["sensitivity"].values():
                if cell["scenarios"] != 1000:
                    fail(f"seed {seed}: {c} sweep cell has {cell['scenarios']} scenarios")
    return s2, len(by_seed)


# ------------------------------------------------------------------- analysis
def val(r, c):
    """Validated service probability. Failure policy: a missing plan scores 0."""
    if r is None:
        return 0.0
    x = r["configurations"].get(c)
    return 0.0 if x is None else x["validation"]["service_level_success"]


def has(r, c):
    return r is not None and r["configurations"].get(c) is not None


def sweep(r, c, cell):
    """Sweep outcome. Failure policy: a missing plan scores 0 in every cell."""
    x = r["configurations"].get(c)
    return 0.0 if x is None else x["sensitivity"][cell]["service_level_success"]


def selected(r, proc):
    if r is None:
        return False
    if proc == "procedure":
        return bool(r["old_failure_audit"]["selected"])
    return r[proc]["selected_plan"] is not None


def boot(d, level):
    d = np.asarray(d, dtype=float)
    if len(d) == 0:
        return {"k": 0, "mean_pp": None, "lo_pp": None, "hi_pp": None, "level": level}
    rng = np.random.default_rng(SEED)
    means = d[rng.integers(0, len(d), (B, len(d)))].mean(axis=1)
    lo, hi = np.percentile(means, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    # Unrounded values drive every decision; rounding happens only for display.
    return {"k": len(d), "mean_pp": 100 * float(d.mean()), "lo_pp": 100 * float(lo),
            "hi_pp": 100 * float(hi), "level": level}


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def analyse(units, confirmatory):
    """units: list of (instance_seed, customers, record-or-None)."""
    recs = [r for _, _, r in units]
    common = [r for r in recs if has(r, "conservative")]
    out = {"instances": len(units), "common_subset": len(common)}

    h1 = boot([val(r, "procedure") - val(r, "conservative") for r in common], 0.975)
    h2 = boot([val(r, "capped_procedure") - val(r, "procedure") for r in recs], 0.975)
    kb = sum(selected(r, "capped_procedure") and not selected(r, "procedure") for r in recs)
    pb = sum(selected(r, "procedure") and not selected(r, "capped_procedure") for r in recs)
    h3 = {"K_selected": sum(selected(r, "capped_procedure") for r in recs),
          "P_selected": sum(selected(r, "procedure") for r in recs),
          "K_only": kb, "P_only": pb, "exact_p": mcnemar_exact(kb, pb)}
    sw = common          # H4 uses exactly H1's subset, as the protocol defines
    h4 = boot([(sweep(r, "procedure", "0.30,0.0") - sweep(r, "conservative", "0.30,0.0"))
               - (sweep(r, "procedure", "0.10,0.0") - sweep(r, "conservative", "0.10,0.0"))
               for r in sw], 0.95)

    def verdict(x):
        if not confirmatory:
            return "descriptive only"
        if x["k"] == 0:
            return "NO DATA"
        return "CONFIRMED" if x["lo_pp"] > 0 else "NOT CONFIRMED"

    out["H1_P_minus_C"] = {**h1, "verdict": verdict(h1)}
    out["H2_K_minus_P"] = {**h2, "verdict": verdict(h2)}
    out["H3_admission"] = {**h3, "verdict": ("descriptive only" if not confirmatory else
                           "CONFIRMED" if (kb > pb and h3["exact_p"] < 0.05) else "NOT CONFIRMED")}
    out["H4_noise_growth"] = {**h4, "verdict": verdict(h4)}
    # Display rounding, applied after every verdict has been decided.
    for key in ("H1_P_minus_C", "H2_K_minus_P", "H4_noise_growth"):
        for f in ("mean_pp", "lo_pp", "hi_pp"):
            if out[key][f] is not None:
                out[key][f] = round(out[key][f], 2)
    out["H3_admission"]["exact_p"] = round(out["H3_admission"]["exact_p"], 5)

    desc = {}
    for n in (20, 50, 100, 200):
        s = [r for _, c, r in units if c == n]
        if not s:
            continue
        row = {"instances": len(s)}
        for proc in ("procedure", "screened_conservative", "capped_procedure"):
            sel = [r for r in s if selected(r, proc)]
            ret = [r for r in sel if wilson_lb(val(r, proc), N_FRESH) >= 0.95]
            row[proc] = {"selected": len(sel), "retained": len(ret),
                         "mean_pp": round(100 * float(np.mean([val(r, proc) for r in s])), 2)}
        desc[str(n)] = row
    out["descriptive_by_size"] = desc
    out["pooled_mean_pp"] = {p: round(100 * float(np.mean([val(r, p) for r in recs])), 2)
                             for p in ("procedure", "screened_conservative", "capped_procedure")}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("confirmatory", "descriptive"))
    ap.add_argument("--stage1", nargs="*", default=[])
    ap.add_argument("--stage2", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=Path("FROZEN_MANIFEST.json"))
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[1]

    if a.mode == "confirmatory":
        if not a.stage1:
            fail("confirmatory mode requires the four stage-1 files")
        s2, total = validate(a.stage1, a.stage2, a.manifest, root)
        units = [(seed, n, s2[seed]) for n, seeds in EXPECTED.items() for seed in sorted(seeds)]
        no_plan = {seed: {c: st for c, st in s2[seed]["configuration_status"].items() if st != "ok"}
                   for seed in sorted(s2)}
        out = {"mode": "CONFIRMATORY (validated against the frozen protocol)",
               "configurations_without_plan": {k: v for k, v in no_plan.items() if v},
               **analyse(units, confirmatory=True)}
    else:
        recs = [json.loads(Path(f).read_text()) for f in sorted(glob.glob(str(a.stage2 / "instance_*.json")))]
        if not recs:
            sys.exit(f"no instance records in {a.stage2}")
        units = [(r["instance_seed"], r["customers"], r) for r in recs]
        out = {"mode": "DESCRIPTIVE - not a confirmatory result",
               **analyse(units, confirmatory=False)}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
