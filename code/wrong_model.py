"""What happens when the delay model used for screening is wrong? (exploratory)

On the 40 Amazon routes, a company screens with a delay model it assumed (the
study's model), but the real delays behave like those fitted to New York taxi
trips (code/nyc_calibration.py), which, among other differences, have no
morning slowdown. This script takes the plans stored in results/amazon (chosen
under the assumed model) and judges them under each fitted model on a fresh bank
of 5000 days (seed 1_200_000 + instance seed). For comparison, the plans chosen
when the screen used the fitted model itself (results/amazon_<model>) are judged
on the same days. Nothing is re-planned.

Also reported: of the plans certified under the assumed model (code/certify.py),
how many keep their certificate under the fitted model, i.e. whose exact
one-sided 95% upper bound on the fresh success probability is not below 0.95.

Usage (from the package root):
  PYTHONPATH=code python code/wrong_model.py
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

import amazon_benchmark as amz
from certify import TARGET, cp_lower, cp_upper, successes
from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile
from relscreen_v7 import evaluate, plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
SEED = 1_200_000
CONFIGS = ("nominal", "conservative", "capped_procedure", "screened_conservative")


def boot(x, seed=20261020, n=20000):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def main():
    out = {"routes": amz.N_USED, "models": {}}
    for true_model in ("nyc_days", "nyc_total"):
        extra, mult = amz.delay_settings(true_model)
        rows = []
        for k in range(amz.N_USED):
            seed = amz.SEED_BASE + k + 1
            data, overrides, _ = amz.build(amz.route_ids()[k], seed)
            params = replace(ModelParams(), **{**overrides, **extra})
            profile = SpeedProfile(congestion_multiplier=mult)
            bank = ScenarioBank(5000, SEED + seed, params)
            row = {"seed": seed}
            for source, sub in (("assumed", "amazon"), ("fitted", f"amazon_{true_model}")):
                rec = json.loads((ROOT / "results" / sub / "v7" / f"instance_{seed}.json").read_text())
                for c in CONFIGS:
                    cfg = rec["configurations"].get(c)
                    if cfg is None:
                        row[f"{source}:{c}"] = None
                        continue
                    v = evaluate(plan_from_dict(cfg["plan"]), data, params, profile, bank)
                    kk, nn = successes(v)
                    ks, ns = successes(cfg["validation"])
                    row[f"{source}:{c}"] = {"success": kk / nn, "cp_upper": cp_upper(kk, nn),
                                            "certified_when_chosen": cp_lower(ks, ns) >= TARGET}
            rows.append(row)
        res = {}
        for source in ("assumed", "fitted"):
            for c in CONFIGS:
                vals = [0.0 if r[f"{source}:{c}"] is None else 100 * r[f"{source}:{c}"]["success"] for r in rows]
                cert = [r[f"{source}:{c}"] for r in rows if r[f"{source}:{c}"] and r[f"{source}:{c}"]["certified_when_chosen"]]
                res[f"{source}:{c}"] = {"pooled": boot(vals), "certified_when_chosen": len(cert),
                                        "certificate_kept": sum(x["cp_upper"] >= TARGET for x in cert),
                                        "mean_success_certified": float(np.mean([100 * x["success"] for x in cert])) if cert else None}
        d = lambda a, b: boot([(0 if r[a] is None else 100 * r[a]["success"]) - (0 if r[b] is None else 100 * r[b]["success"]) for r in rows])  # noqa: E731
        res["assumed_capped_minus_assumed_padding"] = d("assumed:capped_procedure", "assumed:conservative")
        res["assumed_screened_cons_minus_assumed_padding"] = d("assumed:screened_conservative", "assumed:conservative")
        res["fitted_capped_minus_assumed_capped"] = d("fitted:capped_procedure", "assumed:capped_procedure")
        out["models"][true_model] = {"summary": res, "rows": rows,
                                     "sigma": extra["sigma"], "rho": extra["rho_log"], "profile": mult}
        print(true_model, json.dumps({k: (v if isinstance(v, list) else {kk: (round(x, 1) if isinstance(x, float) else x) if not isinstance(x, list) else [round(y, 1) for y in x] for kk, x in v.items()}) for k, v in res.items()}, indent=0), flush=True)
    # The other direction: real delays harsher than assumed (stored results of code/misspecification.py,
    # 5000 fresh days per plan and model). Do plans certified under the assumed model keep their certificate?
    mis = json.loads((ROOT / "results" / "misspecification.json").read_text())
    cert = json.loads((ROOT / "results" / "certify_summary.json").read_text())
    pairs = {"ort_capped": "capped_procedure", "hgs_capped_cons": "hgs_capped_cons", "ort_conservative": "conservative"}
    syn = {}
    for study in ("development", "confirmatory 1", "confirmatory 2"):
        crows = cert["studies"][study]
        for mkey, ckey in pairs.items():
            if ckey not in crows:
                continue
            certified = {r["seed"] for r in crows[ckey]["rows"] if r["certified"]}
            for model in mis["models"]:
                kept = total = 0
                vals = []
                for r in mis["studies"][study]["rows"]:
                    if r["seed"] in certified and mkey in r["service"][model]:
                        k = int(round(r["service"][model][mkey] / 100 * 5000))
                        total += 1
                        kept += cp_upper(k, 5000) >= TARGET
                        vals.append(r["service"][model][mkey])
                e = syn.setdefault(model, {}).setdefault(ckey, {"certified": 0, "kept": 0, "service": []})
                e["certified"] += total
                e["kept"] += kept
                e["service"] += vals
    for model, v in syn.items():
        for ckey, e in v.items():
            e["mean_service"] = float(np.mean(e["service"])) if e["service"] else None
            del e["service"]
    out["synthetic_misspecification"] = {"models": mis["models"], "certificates": syn}
    print(json.dumps(syn, indent=0))
    (ROOT / "results" / "wrong_model_summary.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
