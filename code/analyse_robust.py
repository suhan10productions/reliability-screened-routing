"""Exploratory comparison of the screened procedures with budgeted-robust VRPTW plans.

Reads results/robust_dev (robust plans validated on each instance's 5000-scenario
validation bank), results/v7 (OR-Tools configurations on the same banks) and
results/hgs_dev (HGS configurations on the same banks). A configuration
without a plan scores 0. Intervals are paired bootstrap intervals over
instances (20,000 resamples, seed 20260930), as in the confirmatory analyses.

Usage: PYTHONPATH=code python code/analyse_robust.py [--json results/robust_dev_summary.json]
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESAMPLES, BOOT_SEED = 20_000, 20260930


def boot(diffs, level=0.95):
    x = np.asarray(diffs, dtype=float)
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(x), size=(RESAMPLES, len(x)))
    means = x[idx].mean(axis=1)
    a = (1 - level) / 2
    return [float(x.mean()), float(np.quantile(means, a)), float(np.quantile(means, 1 - a))]


def load(directory):
    out = {}
    for f in sorted(glob.glob(str(ROOT / directory / "instance_*.json"))):
        r = json.loads(Path(f).read_text())
        out[r["instance_seed"]] = r
    return out


def service(entry):
    return 0.0 if entry is None or entry.get("validation") is None else 100 * entry["validation"]["service_level_success"]


def distance(entry):
    return None if entry is None or entry.get("plan") is None else entry["plan"]["metrics"]["distance"]


def screened_robust(settings):
    """Smallest-distance setting admitted on the screening bank; else the best-screening plan."""
    cands = [(k, v) for k, v in settings.items() if v["status"] == "ok"]
    passing = [(v["plan"]["metrics"]["distance"], k) for k, v in cands if v["screening"]["service_level_lcb"] >= 0.95]
    if passing:
        return settings[min(passing)[1]], True
    if not cands:
        return None, False
    best = max(cands, key=lambda kv: (kv[1]["screening"]["service_level_success"], -kv[1]["plan"]["metrics"]["distance"]))
    return best[1], False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path)
    ap.add_argument("--ref", default="ort:capped", choices=["ort:capped", "hgs:capped_cons"])
    a = ap.parse_args()
    rob, ort, hgs = load("results/robust_dev"), load("results/v7"), load("results/hgs_dev")
    cap = load("results/robust_capped_dev")
    seeds = sorted(rob)
    if cap:
        seeds = [s for s in seeds if s in cap]
    sizes = sorted({rob[s]["customers"] for s in seeds})
    keys = rob[seeds[0]]["grid"]
    ckeys = cap[seeds[0]]["grid"] if cap else []
    rows = {}
    for s in seeds:
        r, o = rob[s], ort[s]
        h = hgs.get(s)
        cfg = o["configurations"]
        sr, admitted = screened_robust(r["settings"])
        csr, cadmitted = screened_robust(cap[s]["settings"]) if cap else (None, False)
        rows[s] = {
            "n": r["customers"],
            **{f"rob:{k}": r["settings"][k] for k in keys},
            **({f"cap:{k}": cap[s]["settings"][k] for k in ckeys} if cap else {}),
            "screened_capped_robust": csr, "screened_capped_robust_admitted": cadmitted,
            "ort:nominal": cfg["nominal"], "ort:conservative": cfg["conservative"],
            "ort:procedure": cfg["procedure"], "ort:capped": cfg["capped_procedure"],
            "hgs:capped_cons": None if h is None else h["configurations"]["hgs_capped_cons"],
            "hgs:conservative": None if h is None else h["configurations"]["hgs_conservative"],
            "screened_robust": sr, "screened_robust_admitted": admitted,
        }
    configs = ["ort:nominal", "ort:conservative", "ort:procedure", "ort:capped", "hgs:conservative",
               "hgs:capped_cons", "screened_robust"] + (["screened_capped_robust"] if cap else []) \
        + [f"rob:{k}" for k in keys] + [f"cap:{k}" for k in ckeys]
    summary = {"instances": len(seeds), "sizes": sizes, "by_size": {}, "pooled": {}}
    for group, members in [(str(n), [s for s in seeds if rows[s]["n"] == n]) for n in sizes] + [("all", seeds)]:
        g = {}
        base = {s: distance(rows[s]["rob:G0_d0"]) for s in members}
        for c in configs:
            serv = [service(rows[s][c]) for s in members]
            plans = [s for s in members if distance(rows[s][c]) is not None]
            dpct = [100 * (distance(rows[s][c]) / base[s] - 1) for s in plans if base[s]]
            g[c] = {"instances": len(members), "with_plan": len(plans), "service": float(np.mean(serv)),
                    "distance_vs_nominal_pct": float(np.mean(dpct)) if dpct else None}
        if group == "all" or True:
            for ref in ("ort:capped", "hgs:capped_cons"):
                for c in configs:
                    if c == ref or c.startswith("ort:nominal"):
                        continue
                    diffs = [service(rows[s][ref]) - service(rows[s][c]) for s in members]
                    both = [s for s in members if distance(rows[s][ref]) is not None and distance(rows[s][c]) is not None]
                    dd = [100 * (distance(rows[s][ref]) / distance(rows[s][c]) - 1) for s in both]
                    cond = [service(rows[s][ref]) - service(rows[s][c]) for s in both]
                    g.setdefault("vs", {}).setdefault(ref, {})[c] = {
                        "service_diff": boot(diffs), "distance_diff_pct": boot(dd) if len(dd) > 1 else None,
                        "service_diff_where_both_plan": boot(cond) if len(cond) > 1 else None,
                        "paired_instances_distance": len(both)}
        g["screened_robust_admitted"] = sum(rows[s]["screened_robust_admitted"] for s in members)
        g["screened_capped_robust_admitted"] = sum(rows[s]["screened_capped_robust_admitted"] for s in members)
        summary["by_size" if group != "all" else "pooled"][group] = g
    if a.json:
        a.json.write_text(json.dumps(summary, indent=1))
    # ---- printed overview ----
    for group in [str(n) for n in sizes] + ["all"]:
        g = summary["by_size"][group] if group != "all" else summary["pooled"]["all"]
        print(f"\n== n={group}  (screened robust admitted on {g['screened_robust_admitted']})")
        print(f"{'config':22s} {'plans':>7s} {'service%':>9s} {'dist vs nominal%':>17s} {'ref-minus-this [95%]':>28s} {'refDist vs this%':>20s} {'same, where both plan':>26s}")
        for c in configs:
            x = g[c]
            v = g["vs"][a.ref].get(c)
            sd = "" if v is None else "{:+.1f} [{:+.1f},{:+.1f}]".format(*v["service_diff"])
            dd = "" if v is None or v["distance_diff_pct"] is None else "{:+.1f}".format(v["distance_diff_pct"][0])
            dist = "" if x["distance_vs_nominal_pct"] is None else f"{x['distance_vs_nominal_pct']:+.1f}"
            cd = "" if v is None or v["service_diff_where_both_plan"] is None else "{:+.1f} [{:+.1f},{:+.1f}]".format(*v["service_diff_where_both_plan"])
            print(f"{c:22s} {x['with_plan']:>3d}/{x['instances']:<3d} {x['service']:9.1f} {dist:>17s} {sd:>28s} {dd:>20s} {cd:>26s}")


if __name__ == "__main__":
    main()
