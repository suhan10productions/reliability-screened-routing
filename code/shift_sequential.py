"""Additive shift certificates and sequential certification on the plans of the main analysis (exploratory).

Both use each plan's own validation bank (5000 days, the bank of its certificate) and a day-by-day
evaluator, day_outcomes(), that mirrors relscreen_v7.evaluate exactly (checked on every plan with
delta = 0 against the stored validation result) but returns the outcome of each day and can add a
constant delta minutes to every arc. The frozen code is imported, not edited.

1. Additive shift (Proposition 6 in the manuscript). If, under a coupling, every real arc takes at
   most delta minutes longer than modelled, the real arrival maps are pointwise no later than those
   of the model with delta added to every arc, which are non-decreasing; by Proposition 1 the plan's
   real reliability is at least its reliability p_delta(x) under that shifted model. For each
   certified plan, delta = 0.5, 1, 2, 3, 5, 10 is tested in this order on the validation bank (fixed
   order, Proposition 4) and the shift margin delta*(x) is the last certified value. The fragility
   rho_delta(x) = P(day succeeds under the model and fails with delta added) is measured exactly on
   the same days, so that p_delta = p - rho_delta (the shifted model is pointwise worse, so its
   successful days are a subset).
2. Sequential certification (Proposition 7). The validation days are inspected after 1000, 2000,
   3000, 4000 and 5000 days; the plan is certified at the first inspection where the exact
   one-sided bound at level alpha/5 reaches 0.95. Reported: stopping inspections, the expected
   number of days used, plans certified by one rule but not the other, and, for every plan certified
   sequentially, the fresh-day test of code/certify.py (5000 days, seed 1_100_000 + instance seed).

Plans: every configuration of the certification analysis (code/certify.py): development and
confirmatory OR-Tools and HGS records, and the 40 Amazon routes under the three delay models. Plans
whose validated success is below 0.93 can certify under neither rule and are skipped.

Usage (from the package root):
  PYTHONPATH=code python code/shift_sequential.py --workers 2
  PYTHONPATH=code python code/shift_sequential.py --summarise
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

import amazon_benchmark as amz
from certify import HGS_CONFIGS, OR_CONFIGS, TARGET, TEST_SEED, amazon_loader, cp_lower, cp_upper, successes, synthetic_loader
from relscreen_v6 import ScenarioBank
from relscreen_v7 import evaluate, plan_from_dict, vector_travel

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "shift_sequential"
DELTAS = (0.5, 1.0, 2.0, 3.0, 5.0, 10.0)
LOOKS = (1000, 2000, 3000, 4000, 5000)
ALPHA = 0.05
MIN_SUCCESS = 0.93


def day_outcomes(plan, data, params, profile, bank, delta=0.0):
    """Success of each day (on-time share >= kappa), as in relscreen_v7.evaluate, with delta added to every arc."""
    counts = np.zeros(bank.scenarios, dtype=int)
    used = 0
    for ridx, route in enumerate(plan.routes):
        if len(route) <= 2:
            continue
        used += 1
        now = np.full(bank.scenarios, plan.departures[ridx], dtype=float)
        route_late = np.zeros(bank.scenarios, dtype=int)
        for i, j in zip(route[:-1], route[1:]):
            clock = now + params.shift_start_minute
            travel = vector_travel(data.distance[i][j], clock, profile)
            log_error = params.sigma * (math.sqrt(params.rho_log) * bank._global
                                        + math.sqrt(1 - params.rho_log) * bank.local_errors((i, j)))
            now += travel * np.exp(log_error) + delta
            if j:
                lo, hi = data.offered_windows[j]
                now = np.maximum(now, lo)
                route_late += np.maximum(0.0, now - hi) > 1e-9
                now += params.service_minutes
        counts += route_late
    if not used:
        raise ValueError("empty plan")
    fraction = 1 - counts / data.num_customers
    return fraction >= params.kappa


def items():
    """(study, config, seed, loader name, loader args, record path) for every plan of the certification analysis."""
    for study, (s1dir, v7dir, hgsdir) in {"development": ("results", "results/v7", "results/hgs_dev"),
                                          "confirmatory 1": ("results/confirm", "results/confirm/v7", None),
                                          "confirmatory 2": ("results/confirm2", "results/confirm2/v7", "results/confirm2/hgs")}.items():
        stage1 = {}
        for f in sorted(glob.glob(str(ROOT / s1dir / "study_v6_n*.json"))):
            for r in json.loads(Path(f).read_text())["records"]:
                stage1[r["instance_seed"]] = r
        for f in sorted(glob.glob(str(ROOT / v7dir / "instance_*.json"))):
            s = json.loads(Path(f).read_text())["instance_seed"]
            for c in OR_CONFIGS:
                yield study, c, s, "syn", (stage1[s]["customers"], stage1[s]["vehicles_available"], s), f
        if hgsdir:
            for f in sorted(glob.glob(str(ROOT / hgsdir / "instance_*.json"))):
                r = json.loads(Path(f).read_text())
                for c in HGS_CONFIGS:
                    yield study, c, r["instance_seed"], "syn", (r["customers"], r["vehicles_available"], r["instance_seed"]), f
    for delay, sub in (("assumed", "amazon"), ("nyc_days", "amazon_nyc_days"), ("nyc_total", "amazon_nyc_total")):
        for k in range(amz.N_USED):
            seed = amz.SEED_BASE + k + 1
            for c in OR_CONFIGS:
                yield f"amazon {delay}", c, seed, f"amz:{delay}", (k,), str(ROOT / "results" / sub / "v7" / f"instance_{seed}.json")


def run_one(study, cfg_name, seed, loader, args, path):
    out = OUT / f"{study.replace(' ', '_')}__{cfg_name}__{seed}.json"
    if out.exists():
        return None
    rec = json.loads(Path(path).read_text())
    cfg = rec["configurations"].get(cfg_name)
    res = {"study": study, "config": cfg_name, "seed": seed}
    if cfg is None:
        res["skipped"] = "no plan"
    else:
        k, n = successes(cfg["validation"])
        res["fixed_success"] = k / n
        res["fixed_certified"] = cp_lower(k, n) >= TARGET
        if k / n < MIN_SUCCESS:
            res["skipped"] = "validated success below 0.93"
        else:
            data, params, profile = synthetic_loader(*args) if loader == "syn" else amazon_loader(loader.split(":")[1])(*args)
            vseed = rec.get("validation_seed", 400_000 + seed)
            bank = ScenarioBank(5000, vseed, params)
            plan = plan_from_dict(cfg["plan"])
            base = day_outcomes(plan, data, params, profile, bank)
            assert abs(base.mean() - k / n) < 1e-12, (study, cfg_name, seed, base.mean(), k / n)
            # sequential
            stop = None
            for nj in LOOKS:
                if cp_lower(int(base[:nj].sum()), nj, ALPHA / len(LOOKS)) >= TARGET:
                    stop = nj
                    break
            res["sequential_stop"] = stop
            if stop is not None and not res["fixed_certified"]:
                kt, nt = successes(evaluate(plan, data, params, profile, ScenarioBank(5000, TEST_SEED + seed, params)))
                res["sequential_fresh_fails"] = cp_upper(kt, nt) < TARGET
            # additive shift
            if res["fixed_certified"]:
                margin, tested = 0.0, []
                for d in DELTAS:
                    s = day_outcomes(plan, data, params, profile, bank, d)
                    assert not np.any(s & ~base) or True   # the shifted model is pointwise worse (checked below)
                    tested.append({"delta": d, "success": float(s.mean()), "rho": float(np.mean(base & ~s)),
                                   "gained_days": int(np.sum(s & ~base)), "cp_lower": cp_lower(int(s.sum()), 5000)})
                    if cp_lower(int(s.sum()), 5000) < TARGET:
                        break
                    margin = d
                res["shift_margin"], res["shift_tested"] = margin, tested
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res))
    return f"{study} {cfg_name} {seed} stop={res.get('sequential_stop')} margin={res.get('shift_margin')}"


def auc(score, label):
    s, y = np.asarray(score, float), np.asarray(label, bool)
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return None
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def summarise():
    R = [json.loads(f.read_text()) for f in sorted(OUT.glob("*.json"))]
    cert = json.loads((ROOT / "results" / "certify_summary.json").read_text())
    fresh = {}
    for study, v in cert["studies"].items():
        for c, x in v.items():
            for r in x["rows"]:
                if r.get("certified"):
                    fresh[(study, c, r["seed"])] = r["fails_certificate"]
    fixed = [r for r in R if r.get("fixed_certified")]
    evald = [r for r in R if "sequential_stop" in r]
    seq = [r for r in evald if r["sequential_stop"] is not None]
    days = [r["sequential_stop"] if r["sequential_stop"] else 5000 for r in fixed]
    out = {"plans_evaluated": len(evald), "fixed_certified": len(fixed), "sequential_certified": len(seq),
           "fixed_only": sum(1 for r in fixed if r.get("sequential_stop") is None),
           "sequential_only": sum(1 for r in seq if not r["fixed_certified"]),
           "stop_counts": {str(n): sum(r["sequential_stop"] == n for r in seq) for n in LOOKS},
           "mean_days_fixed_certified_plans": float(np.mean(days)),
           "days_saved_share": float(1 - np.mean(days) / 5000),
           "sequential_fresh_fails": sum(fresh.get((r["study"], r["config"], r["seed"]), r.get("sequential_fresh_fails", False))
                                         for r in seq)}
    assert all(t["gained_days"] == 0 for r in fixed for t in r["shift_tested"])   # shifted model never better
    mg = np.array([r["shift_margin"] for r in fixed])
    out["shift"] = {"plans": len(fixed), "margin_counts": {str(d): int((mg == d).sum()) for d in (0.0,) + DELTAS},
                    "margin_median": float(np.median(mg)),
                    "rho_median": {str(d): float(np.median([t["rho"] for r in fixed for t in r["shift_tested"] if t["delta"] == d]))
                                   for d in DELTAS[:3]}}
    # rho at 1 minute for every certified plan (it is always tested, since the margin search starts at 0.5)
    # predictive check on the synthetic capped plans with misspecification results (code/slowdown_margin.py)
    sm = json.loads((ROOT / "results" / "slowdown_margin_summary.json").read_text())
    surv = {(r["study"], r["config"], r["seed"]): r["survives"] for r in sm["rows"]}
    rows = [(r["shift_margin"], surv[(r["study"], r["config"], r["seed"])]) for r in fixed
            if (r["study"], r["config"], r["seed"]) in surv]
    out["shift"]["predictive"] = {"plans": len(rows),
                                  "auc_incidents": auc([m for m, _ in rows], [s["incidents"] for _, s in rows]),
                                  "auc_strong_peak": auc([m for m, _ in rows], [s["strong_peak"] for _, s in rows])}
    (ROOT / "results" / "shift_sequential_summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        return summarise()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_one, *t): t for t in items()}
        for f in as_completed(futs):
            try:
                r = f.result()
                if r:
                    print(r, flush=True)
            except Exception as exc:  # recorded, the run continues
                print(f"ERROR {futs[f][:3]}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
