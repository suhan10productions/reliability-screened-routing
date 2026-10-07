"""Prespecified analysis for CONFIRMATORY_PROTOCOL_2.md.

The second confirmatory study runs two generators on the same 53 fresh
instances (development seeds + 80000): the unchanged, frozen OR-Tools pipeline
(study_v6 then study_v7) and the HGS pipeline (study_hgs).

Modes
  confirmatory  Validates both halves of the complete prescribed study before
                computing anything. The OR-Tools half uses the frozen
                validator in confirm_analysis.py, pointed at the new seed set
                and the protocol-2 manifest; the HGS half is validated here.
                Any violation aborts. Only this mode prints a verdict.
  descriptive   Same quantities on any paired records (for example the
                development runs); labelled descriptive, never a verdict.

Usage
  python code/confirm_analysis_hgs.py confirmatory \
      --stage1 results/confirm2/study_v6_n20.json ... --stage2 results/confirm2/v7 \
      --hgs results/confirm2/hgs --manifest FROZEN_MANIFEST_2.json
  python code/confirm_analysis_hgs.py descriptive --stage2 results/v7 --hgs results/hgs_dev
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path

import numpy as np

B, BOOT_SEED = 20_000, 20260930
SEED_SHIFT = 80000
DESIGN = {20: (6, 20, 7200), 50: (14, 15, 7500), 100: (26, 10, 8000), 200: (40, 8, 9000)}
EXPECTED = {seed: n for n, (_, k, first) in DESIGN.items()
            for seed in range(first + SEED_SHIFT, first + SEED_SHIFT + k)}
CONFIGS = ("hgs_nominal", "hgs_conservative", "hgs_procedure_slack", "hgs_procedure_cons",
           "hgs_capped_slack", "hgs_capped_cons")
RUN = {"schema": "relscreen-hgs-1", "screen_scenarios": 1000, "validation_scenarios": 5000,
       "hgs_iterations": 10_000, "anchor_seconds": 2.0, "beta_values": list(range(0, 61, 5))}
VERSIONS = {"pyvrp": "0.14.0", "ortools": "9.15.6755", "numpy": "2.5.3"}
MANIFEST_FILES = ("CONFIRMATORY_PROTOCOL_2.md", "requirements.txt", "code/relscreen_v6.py",
                  "code/relscreen_v7.py", "code/study_v6.py", "code/study_v7.py",
                  "code/confirm_analysis.py", "code/hgs_generator.py", "code/study_hgs.py",
                  "code/confirm_analysis_hgs.py")

# Quantities are validated kappa = 0.95 service-event probability on the fresh
# bank, per instance; a configuration without a plan scores 0.
#   ort_capped        OR-Tools capped procedure as specified (slack-aware fallback)
#   ort_capped_cons   same selections; fallback = OR-Tools conservative-speed plan
#   ort_procedure / ort_procedure_cons   the same for the uncapped procedure
#   hgs_*             HGS configurations (see study_hgs.py)
# (id, role, treatment, comparator, subset, two-sided interval level, decision)
HYPOTHESES = (
    ("G1", "primary", "hgs_capped_cons", "hgs_conservative", "hgs_common", 0.975, "directional"),
    ("G2", "primary", "ort_capped_cons", "ort_capped", "all", 0.975, "directional"),
    ("G3", "secondary", "ort_procedure_cons", "ort_procedure", "all", 0.95, "directional"),
    ("G4", "secondary", "hgs_capped_cons", "ort_capped_cons", "all", 0.95, "estimate"),
)


class ProtocolViolation(SystemExit):
    pass


def fail(msg):
    raise ProtocolViolation(f"PROTOCOL VIOLATION: {msg}")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def validate_hgs(records_dir: Path):
    files = sorted(glob.glob(str(records_dir / "*.json")))
    errors = [f for f in files if Path(f).name.startswith("software_error_")]
    if errors:
        e = json.loads(Path(errors[0]).read_text())
        fail(f"software error on seed {e['instance_seed']}: {e['error']} "
             "(fix, re-freeze and report as a labelled deviation)")
    other = [Path(f).name for f in files if not Path(f).name.startswith("instance_")]
    if other:
        fail(f"unexpected files: {other[:3]}")
    recs = {}
    for f in files:
        r = json.loads(Path(f).read_text())
        s = r["instance_seed"]
        if Path(f).name != f"instance_{s}.json":
            fail(f"{Path(f).name} contains seed {s}")
        if s in recs:
            fail(f"duplicate record for seed {s}")
        recs[s] = r
    if set(recs) != set(EXPECTED):
        fail(f"seed set differs from the prescribed set (missing {sorted(set(EXPECTED) - set(recs))[:5]}, "
             f"unexpected {sorted(set(recs) - set(EXPECTED))[:5]})")
    for s, r in recs.items():
        n = EXPECTED[s]
        if r["customers"] != n or r["vehicles_available"] != DESIGN[n][0]:
            fail(f"seed {s}: size or fleet differs from the design")
        for k, v in RUN.items():
            if r.get(k) != v:
                fail(f"seed {s}: {k}={r.get(k)!r}, expected {v!r}")
        if r["screening_seed"] != 100_000 + s or r["validation_seed"] != 400_000 + s or r["hgs_seed"] != s:
            fail(f"seed {s}: scenario or HGS seeds not derived as prescribed")
        for pkg, ver in VERSIONS.items():
            if r["environment"].get(pkg) != ver:
                fail(f"seed {s}: {pkg} {r['environment'].get(pkg)} differs from the pinned {ver}")
        st = r["configuration_status"]
        for c in CONFIGS:
            if c not in r["configurations"] or c not in st:
                fail(f"seed {s}: configuration {c} or its status is absent")
            x = r["configurations"][c]
            if (st[c] == "ok") != (x is not None):
                fail(f"seed {s}: {c} status {st[c]!r} disagrees with its plan")
            if x is None:
                continue
            if x["validation"]["scenarios"] != 5000:
                fail(f"seed {s}: {c} validated on {x['validation']['scenarios']} scenarios")
            visits = sorted(v for route in x["plan"]["routes"] for v in route if v)
            if visits != list(range(1, n + 1)):
                fail(f"seed {s}: {c} plan does not visit every customer exactly once")
    return recs


def validate(stage1, stage2_dir: Path, hgs_dir: Path, manifest: Path, root: Path):
    import confirm_analysis as ca
    man = json.loads(manifest.read_text())
    for rel in MANIFEST_FILES:
        if man.get(rel) != sha(root / rel):
            fail(f"{rel} differs from the frozen manifest")
    # Point the frozen OR-Tools validator at protocol 2 without editing it.
    ca.EXPECTED = {n: {s for s, m in EXPECTED.items() if m == n} for n in DESIGN}
    ca.MANIFEST_FILES = MANIFEST_FILES
    ort, _ = ca.validate(stage1, stage2_dir, manifest, root)
    hgs = validate_hgs(hgs_dir)
    if set(ort) != set(hgs):
        fail("OR-Tools and HGS records cover different instances")
    return ort, hgs


def _v(cfg):
    return None if cfg is None else cfg["validation"]["service_level_success"]


def unit(seed, ort, hgs):
    """All quantities for one instance. Failure policy: a missing plan scores 0."""
    c, o = ort["configurations"], {}
    for proc, key, sel in (("procedure", "procedure", bool(ort["old_failure_audit"]["selected"])),
                           ("capped", "capped_procedure", ort["capped_procedure"]["selected_plan"] is not None)):
        base = _v(c[key])
        cons = _v(c["conservative"])
        o[f"ort_{proc}"] = base or 0.0
        o[f"ort_{proc}_cons"] = (base if sel else (cons if cons is not None else base)) or 0.0
        o[f"ort_{proc}_selected"] = sel
    o["ort_conservative_has_plan"] = c["conservative"] is not None
    for k in CONFIGS:
        o[k] = _v(hgs["configurations"][k]) or 0.0
    o["hgs_conservative_has_plan"] = hgs["configurations"]["hgs_conservative"] is not None
    o["hgs_uncapped_selected"] = bool(hgs["selected"].get("uncapped"))
    o["hgs_capped_selected"] = bool(hgs["selected"].get("capped"))
    o["customers"], o["seed"] = hgs["customers"], seed
    return o


def boot(d, level):
    d = np.asarray(d, float)
    if len(d) == 0:
        return {"k": 0, "mean_pp": None, "lo_pp": None, "hi_pp": None, "level": level}
    m = d[np.random.default_rng(BOOT_SEED).integers(0, len(d), (B, len(d)))].mean(1)
    a = (1 - level) / 2 * 100
    return {"k": len(d), "mean_pp": 100 * float(d.mean()), "lo_pp": 100 * float(np.percentile(m, a)),
            "hi_pp": 100 * float(np.percentile(m, 100 - a)), "level": level}


def analyse(units, confirmatory):
    out = {"instances": len(units),
           "hgs_common_subset": sum(u["hgs_conservative_has_plan"] for u in units)}
    for hid, role, t, c, subset, level, kind in HYPOTHESES:
        rs = [u for u in units if u["hgs_conservative_has_plan"]] if subset == "hgs_common" else units
        res = boot([u[t] - u[c] for u in rs], level)
        if not confirmatory:
            verdict = "descriptive only"
        elif kind == "estimate":
            verdict = "estimate only (no directional decision)"
        else:
            verdict = "NO DATA" if res["k"] == 0 else "CONFIRMED" if res["lo_pp"] > 0 else "NOT CONFIRMED"
        out[hid] = {"role": role, "treatment": t, "comparator": c, "subset": subset, **res, "verdict": verdict}
    for hid, *_ in HYPOTHESES:                          # display rounding after decisions
        for f in ("mean_pp", "lo_pp", "hi_pp"):
            if out[hid][f] is not None:
                out[hid][f] = round(out[hid][f], 2)
    keys = ("ort_procedure", "ort_procedure_cons", "ort_capped", "ort_capped_cons") + CONFIGS
    out["pooled_mean_pp"] = {k: round(100 * float(np.mean([u[k] for u in units])), 2) for k in keys}
    desc = {}
    for n in sorted({u["customers"] for u in units}):
        us = [u for u in units if u["customers"] == n]
        row = {"instances": len(us)}
        for flag in ("ort_procedure_selected", "ort_capped_selected", "hgs_uncapped_selected",
                     "hgs_capped_selected"):
            row[flag.replace("_selected", "_admitted")] = sum(u[flag] for u in us)
        for k in keys:
            row[k] = round(100 * float(np.mean([u[k] for u in us])), 2)
        desc[str(n)] = row
    out["descriptive_by_size"] = desc
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("confirmatory", "descriptive"))
    ap.add_argument("--stage1", nargs="*", default=[])
    ap.add_argument("--stage2", type=Path, required=True)
    ap.add_argument("--hgs", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=Path("FROZEN_MANIFEST_2.json"))
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    if a.mode == "confirmatory":
        if len(a.stage1) != 4:
            fail("confirmatory mode requires the four OR-Tools stage-1 files")
        ort, hgs = validate(a.stage1, a.stage2, a.hgs, a.manifest, root)
        units = [unit(s, ort[s], hgs[s]) for s in sorted(hgs)]
        out = {"mode": "CONFIRMATORY (validated against the frozen protocol 2)", **analyse(units, True)}
    else:
        load = lambda d: {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
                          for f in sorted(glob.glob(str(d / "instance_*.json")))}
        ort, hgs = load(a.stage2), load(a.hgs)
        seeds = sorted(set(ort) & set(hgs))
        if not seeds:
            raise SystemExit("no paired records")
        units = [unit(s, ort[s], hgs[s]) for s in seeds]
        out = {"mode": "DESCRIPTIVE - not a confirmatory result", **analyse(units, False)}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
