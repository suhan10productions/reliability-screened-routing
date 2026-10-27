"""Certified slowdown margin: how much slower than modelled can every trip be? (exploratory)

For a plan x and lambda >= 0, let p_lambda(x) be its reliability when every travel time is
multiplied by (1 + lambda): the speed profile's congestion multipliers are all scaled by
(1 + lambda), and the random delay factors are unchanged. On the same validation bank the
slowed travel times are pointwise no shorter, so with fixed departures every service start is
no earlier (Proposition 1) and p_lambda(x) cannot increase with lambda.

Margin. Test lambda = 0, then LAMBDAS in increasing order, on the plan's validation bank (5000
days, seed 400000 + instance seed, the bank of its certificate), certifying lambda when the
exact one-sided Clopper-Pearson bound reaches 0.95, and stop at the first lambda not certified.
The certified margin lambda*(x) is the last certified value. By fixed-order testing
(Proposition 4) the claims hold simultaneously: P(some certified lambda has p_lambda(x) < 0.95)
<= 0.05. By Proposition 1, the plan is then at least 95% reliable under any delays pointwise no
worse than the model slowed by lambda*.

Test against the harsher delay models of code/misspecification.py (fresh banks, seed 700000 +
instance seed), for the plans certified under the assumed model (code/certify.py):
  strong_peak  the morning multiplier 1.4 instead of 1.2, i.e. morning trips 1/6 slower and
               nothing else: pointwise dominated by a uniform slowdown of 1/6, so every plan
               with lambda* >= 1/6 is guaranteed to keep its certificate (up to the 5% error);
  incidents    3% of trips doubled: not dominated by any uniform slowdown below 100%, so here
               the question is only whether the margin predicts survival.
A certificate survives a model when the exact one-sided 95% upper bound on the plan's success
probability under that model is not below 0.95 (as in code/wrong_model.py).

Usage (from the package root):
  PYTHONPATH=code python code/slowdown_margin.py --workers 2
  PYTHONPATH=code python code/slowdown_margin.py --summarise
"""
from __future__ import annotations

import argparse
import glob
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from certify import TARGET, cp_lower, cp_upper, successes
from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance
from relscreen_v7 import evaluate, plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "slowdown_margin"
LAMBDAS = (0.025, 0.05, 0.075, 0.10, 0.125, 0.15, 1 / 6, 0.20, 0.25, 0.30, 0.40, 0.50)
STRONG_PEAK_SLOWDOWN = 1.4 / 1.2 - 1
SOURCES = {  # (study, config) -> (records, stage-1 pattern or None, misspecification key)
    ("development", "capped_procedure"): ("results/v7", "results/study_v6_n*.json", "ort_capped"),
    ("confirmatory 1", "capped_procedure"): ("results/confirm/v7", "results/confirm/study_v6_n*.json", "ort_capped"),
    ("confirmatory 2", "capped_procedure"): ("results/confirm2/v7", "results/confirm2/study_v6_n*.json", "ort_capped"),
    ("development", "hgs_capped_cons"): ("results/hgs_dev", None, "hgs_capped_cons"),
    ("confirmatory 2", "hgs_capped_cons"): ("results/confirm2/hgs", None, "hgs_capped_cons"),
}


def stage1(pattern):
    out = {}
    for f in glob.glob(str(ROOT / pattern)):
        for r in json.loads(Path(f).read_text())["records"]:
            out[r["instance_seed"]] = r
    return out


def tasks():
    for (study, cfg), (rec_dir, _, _) in SOURCES.items():
        for f in sorted(glob.glob(str(ROOT / rec_dir / "instance_*.json"))):
            yield study, cfg, f


def run_one(study, cfg, path):
    rec = json.loads(Path(path).read_text())
    seed = rec["instance_seed"]
    out = OUT / f"{cfg}_{seed}.json"
    if out.exists():
        return f"{cfg} {seed} exists"
    c = rec["configurations"].get(cfg)
    res = {"study": study, "config": cfg, "seed": seed}
    if c is None:
        res["certified"] = False
    else:
        k, n = successes(c["validation"])
        res["certified"] = cp_lower(k, n) >= TARGET
    if res["certified"]:
        params, base = ModelParams(), SpeedProfile()
        if cfg == "capped_procedure":
            s1 = stage1(SOURCES[(study, cfg)][1])[seed]
            data = make_synthetic_instance(s1["customers"], s1["vehicles_available"], seed)
        else:
            data = make_synthetic_instance(rec["customers"], rec["vehicles_available"], seed)
        plan = plan_from_dict(c["plan"])
        bank = ScenarioBank(5000, 400_000 + seed, params)
        margin, tested = 0.0, []
        for lam in LAMBDAS:
            prof = SpeedProfile(periods=base.periods, free_flow_kmh=base.free_flow_kmh,
                                congestion_multiplier=tuple(m * (1 + lam) for m in base.congestion_multiplier))
            kk, nn = successes(evaluate(plan, data, params, prof, bank))
            lb = cp_lower(kk, nn)
            tested.append({"lambda": lam, "success": kk / nn, "cp_lower": lb})
            if lb < TARGET:
                break
            margin = lam
        res["margin"], res["tested"] = margin, tested
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res))
    return f"{cfg} {seed} certified={res['certified']} margin={res.get('margin')}"


def auc(score, label):
    """Probability that a random surviving plan has a larger margin than a random failing one (ties 1/2)."""
    s, y = np.asarray(score, float), np.asarray(label, bool)
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return None
    gt = (pos[:, None] > neg[None, :]).mean()
    eq = (pos[:, None] == neg[None, :]).mean()
    return float(gt + 0.5 * eq)


def summarise():
    mis = json.loads((ROOT / "results" / "misspecification.json").read_text())
    svc = {}
    for study, v in mis["studies"].items():
        for r in v["rows"]:
            svc[(study, r["seed"])] = r["service"]
    rows = []
    for f in sorted(OUT.glob("*.json")):
        r = json.loads(f.read_text())
        if not r["certified"]:
            continue
        mkey = SOURCES[(r["study"], r["config"])][2]
        s = svc.get((r["study"], r["seed"]))
        if s is None or mkey not in s["incidents"]:
            continue
        surv = {}
        for model in ("incidents", "strong_peak", "peak_noise", "heavy_tails"):
            k = int(round(s[model][mkey] / 100 * 5000))
            surv[model] = bool(cp_upper(k, 5000) >= TARGET)
        rows.append({"study": r["study"], "config": r["config"], "seed": r["seed"], "margin": r["margin"],
                     "validated": r["tested"][0]["success"] if r["tested"] else None, "survives": surv})
    out = {"plans": len(rows), "lambdas": list(LAMBDAS), "strong_peak_slowdown": STRONG_PEAK_SLOWDOWN}
    m = np.array([r["margin"] for r in rows])
    out["margin_quantiles"] = {q: float(np.quantile(m, q)) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}
    out["margin_zero"] = int((m == 0).sum())
    for model in ("incidents", "strong_peak", "peak_noise", "heavy_tails"):
        y = np.array([r["survives"][model] for r in rows])
        cov = m >= STRONG_PEAK_SLOWDOWN - 1e-12
        out[model] = {"survived": int(y.sum()), "auc_margin": auc(m, y),
                      "covered": int(cov.sum()), "covered_survived": int(y[cov].sum()),
                      "uncovered": int((~cov).sum()), "uncovered_survived": int(y[~cov].sum()),
                      "by_margin": {f"{lo:.3f}-{hi:.3f}": [int(((m >= lo) & (m < hi)).sum()), int(y[(m >= lo) & (m < hi)].sum())]
                                    for lo, hi in ((0, 0.05), (0.05, 0.10), (0.10, 1 / 6), (1 / 6, 0.25), (0.25, 9))}}
    # does the margin add anything to the validated success estimate?
    v = np.array([r["validated"] for r in rows])
    for model in ("incidents", "strong_peak"):
        y = np.array([r["survives"][model] for r in rows])
        out[model]["auc_validated"] = auc(v, y)
    out["rows"] = rows
    (ROOT / "results" / "slowdown_margin_summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        return summarise()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(run_one, *t): t for t in tasks()}
        for f in as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception as exc:  # recorded, the run continues
                print(f"ERROR {futs[f][2]}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
