"""Screen-then-certify: an exact, solver-independent reliability certificate (exploratory).

The screening procedure chooses a plan with 1000 simulated days. Any plan,
however it was produced and chosen, can then be certified on days that played
no part in producing or choosing it:

  certified  <=>  the one-sided exact (Clopper-Pearson) 95% lower confidence
                  bound on the plan's success probability, computed from its
                  successes on the independent validation bank (5000 days),
                  is at least the target 0.95.

Theorem (in the manuscript). If the validation days are independent of
everything used to produce and choose the plan, then P(plan certified and its
true success probability < 0.95) <= 0.05, whatever the solver, the candidate
family and the selection rule.

This script applies the certificate to every stored configuration of every study
and then tests it on a third, fresh bank of 5000 days (seed 1_100_000 + instance
seed, unused by any other script), where a plan "fails its certificate" when
the exact one-sided 95% upper bound on its fresh success probability is below
0.95. The theorem allows such failures on at most about 5% of certified plans.

Studies: development (OR-Tools records results/v7, HGS records results/hgs_dev),
confirmatory 1 and 2, and the 40 Amazon routes under the three delay models.

Usage (from the package root):
  PYTHONPATH=code python code/certify.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
from scipy.stats import beta as beta_dist

import amazon_benchmark as amz
from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance
from relscreen_v7 import evaluate, plan_from_dict

ROOT = Path(__file__).resolve().parents[1]
ALPHA, TARGET, TEST_SEED = 0.05, 0.95, 1_100_000
OR_CONFIGS = {"nominal": "Nominal plan", "conservative": "20% padding", "procedure": "Original procedure",
              "capped_procedure": "Capped procedure", "screened_conservative": "Screened conservative"}
HGS_CONFIGS = {"hgs_nominal": "HGS nominal plan", "hgs_conservative": "HGS 20% padding",
               "hgs_capped_cons": "HGS capped procedure"}


def cp_lower(k: int, n: int, a: float = ALPHA) -> float:
    return 0.0 if k == 0 else float(beta_dist.ppf(a, k, n - k + 1))


def cp_upper(k: int, n: int, a: float = ALPHA) -> float:
    return 1.0 if k == n else float(beta_dist.ppf(1 - a, k + 1, n - k))


def successes(validation: dict) -> tuple[int, int]:
    n = int(validation["scenarios"])
    k = int(round(validation["service_level_success"] * n))
    assert abs(k / n - validation["service_level_success"]) < 1e-9
    return k, n


def synthetic_loader(customers, vehicles, seed):
    data = make_synthetic_instance(customers, vehicles, seed)
    return data, ModelParams(), SpeedProfile()


def amazon_loader(delay):
    def load(k_index):
        amz.set_delay(delay)
        rid = amz.route_ids()[k_index]
        data, overrides, _ = amz.build(rid, amz.SEED_BASE + k_index + 1)
        extra, mult = amz.delay_settings(delay)
        from dataclasses import replace
        params = replace(ModelParams(), **{**overrides, **extra})
        profile = SpeedProfile() if mult is None else SpeedProfile(congestion_multiplier=mult)
        return data, params, profile
    return load


def certify_rows(items, configs, get_cfg, load):
    """items: (seed, loader-args); returns per-configuration summaries."""
    out = {}
    for key, label in configs.items():
        rows = []
        for seed, args, record in items:
            cfg = get_cfg(record, key)
            if cfg is None:
                rows.append({"seed": seed, "plan": False, "certified": False})
                continue
            k, n = successes(cfg["validation"])
            lo = cp_lower(k, n)
            row = {"seed": seed, "plan": True, "validation_success": k / n, "cp_lower": lo, "certified": lo >= TARGET}
            if row["certified"]:
                data, params, profile = load(*args)
                test = evaluate(plan_from_dict(cfg["plan"]), data, params, profile,
                                ScenarioBank(5000, TEST_SEED + seed, params))
                kt, nt = successes(test)
                row.update({"test_success": kt / nt, "test_cp_upper": cp_upper(kt, nt),
                            "fails_certificate": cp_upper(kt, nt) < TARGET})
            rows.append(row)
        cert = [r for r in rows if r["certified"]]
        out[key] = {"label": label, "instances": len(rows), "with_plan": sum(r["plan"] for r in rows),
                    "certified": len(cert),
                    "test_mean_success_certified": float(np.mean([r["test_success"] for r in cert])) if cert else None,
                    "test_below_target": sum(r["test_success"] < TARGET for r in cert),
                    "fails_certificate": sum(r["fails_certificate"] for r in cert), "rows": rows}
    return out


def main():
    out = {"alpha": ALPHA, "target": TARGET, "test_seed_offset": TEST_SEED, "studies": {}}
    # synthetic studies
    for study, (s1dir, v7dir, hgsdir) in {"development": ("results", "results/v7", "results/hgs_dev"),
                                          "confirmatory 1": ("results/confirm", "results/confirm/v7", None),
                                          "confirmatory 2": ("results/confirm2", "results/confirm2/v7", "results/confirm2/hgs")}.items():
        stage1 = {}
        for f in sorted(glob.glob(str(ROOT / s1dir / "study_v6_n*.json"))):
            for r in json.loads(Path(f).read_text())["records"]:
                stage1[r["instance_seed"]] = r
        v7 = {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
              for f in sorted(glob.glob(str(ROOT / v7dir / "instance_*.json")))}
        items = [(s, (stage1[s]["customers"], stage1[s]["vehicles_available"], s), v7[s]) for s in sorted(v7)]
        res = certify_rows(items, OR_CONFIGS, lambda r, k: r["configurations"].get(k), synthetic_loader)
        if hgsdir:
            hg = {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
                  for f in sorted(glob.glob(str(ROOT / hgsdir / "instance_*.json")))}
            items_h = [(s, (hg[s]["customers"], hg[s]["vehicles_available"], s), hg[s]) for s in sorted(hg)]
            res.update(certify_rows(items_h, HGS_CONFIGS, lambda r, k: r["configurations"].get(k), synthetic_loader))
        out["studies"][study] = res
        print(study, {k: (v["with_plan"], v["certified"], v["fails_certificate"]) for k, v in res.items()}, flush=True)
    # Amazon routes
    for delay, sub in (("assumed", "amazon"), ("nyc_days", "amazon_nyc_days"), ("nyc_total", "amazon_nyc_total")):
        items = []
        for k_index in range(amz.N_USED):
            seed = amz.SEED_BASE + k_index + 1
            items.append((seed, (k_index,), json.loads((ROOT / "results" / sub / "v7" / f"instance_{seed}.json").read_text())))
        res = certify_rows(items, OR_CONFIGS, lambda r, k: r["configurations"].get(k), amazon_loader(delay))
        out["studies"][f"amazon {delay}"] = res
        print("amazon", delay, {k: (v["with_plan"], v["certified"], v["fails_certificate"]) for k, v in res.items()}, flush=True)
    tot = [v for s in out["studies"].values() for v in s.values()]
    out["all_certified"] = sum(v["certified"] for v in tot)
    out["all_fails_certificate"] = sum(v["fails_certificate"] for v in tot)
    out["all_test_below_target"] = sum(v["test_below_target"] for v in tot)
    (ROOT / "results" / "certify_summary.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != "studies"})


if __name__ == "__main__":
    main()
