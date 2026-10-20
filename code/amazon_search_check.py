"""Were the missing Amazon plans search failures or infeasible problems? (exploratory)

On every Amazon route where the nominal plan (40 km/h) or the 20% padded plan
(40/1.2 km/h) was missing with the study's budget (5 s per attempt, up to three
attempts), OR-Tools is run again for distance with 60 s per attempt, up to three
attempts. A plan found now shows that the earlier failure was a limit of the
search, not of the problem. A plan still missing is not a proof of
infeasibility. Every padded plan found is validated on the route's validation
bank (5000 days, seed 400000 + route seed) under each delay model, so that 20%
padding can be re-scored with the longer search. Plans already found with 5 s are
kept unchanged.

Usage (from the package root):
  PYTHONPATH=code python code/amazon_search_check.py
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import amazon_benchmark as amz
from relscreen_v6 import ModelParams, RoutingSolver, ScenarioBank, SpeedProfile
from relscreen_v7 import evaluate
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SECONDS = 60.0


def main():
    rows = []
    for k in range(amz.N_USED):
        seed = amz.SEED_BASE + k + 1
        rec = json.loads((ROOT / "results" / "amazon" / "v7" / f"instance_{seed}.json").read_text())
        data, overrides, info = amz.build(amz.route_ids()[k], seed)
        params = replace(ModelParams(), **overrides)
        for name, speed in (("nominal", None), ("conservative", params.nominal_speed_kmh / 1.2)):
            if rec["configurations"].get(name) is not None:
                continue
            plan, attempts = None, 0
            for attempts in range(1, 4):
                plan = RoutingSolver(data, params, planning_speed_kmh=speed).solve("distance", SECONDS)
                if plan is not None:
                    break
            row = {"seed": seed, "customers": info["customers"], "configuration": name,
                   "found": plan is not None, "attempts": attempts,
                   "fleet": None if plan is None else plan.metrics["fleet"],
                   "plan": None if plan is None else plan.as_dict(), "validation": {}}
            if plan is not None:
                for delay in ("assumed", "nyc_days", "nyc_total"):
                    extra, mult = amz.delay_settings(delay)
                    p2 = replace(params, **extra)
                    prof = SpeedProfile() if mult is None else SpeedProfile(congestion_multiplier=mult)
                    v = evaluate(plan, data, p2, prof, ScenarioBank(5000, 400_000 + seed, p2))
                    row["validation"][delay] = v["service_level_success"]
            rows.append(row)
            print({k: v for k, v in rows[-1].items() if k != "plan"}, flush=True)
    out = {"seconds_per_attempt": SECONDS, "rows": rows,
           "nominal_missing": sum(r["configuration"] == "nominal" for r in rows),
           "nominal_found": sum(r["configuration"] == "nominal" and r["found"] for r in rows),
           "conservative_missing": sum(r["configuration"] == "conservative" for r in rows),
           "conservative_found": sum(r["configuration"] == "conservative" and r["found"] for r in rows)}
    # 20% padding re-scored: 5 s plans where they existed, 60 s plans where found now, zero otherwise
    for delay, sub in (("assumed", "amazon"), ("nyc_days", "amazon_nyc_days"), ("nyc_total", "amazon_nyc_total")):
        pad, cap = [], []
        for k in range(amz.N_USED):
            seed = amz.SEED_BASE + k + 1
            rec = json.loads((ROOT / "results" / sub / "v7" / f"instance_{seed}.json").read_text())
            c = rec["configurations"]
            if c.get("conservative") is not None:
                pad.append(100 * c["conservative"]["validation"]["service_level_success"])
            else:
                r = next((r for r in rows if r["seed"] == seed and r["configuration"] == "conservative"), None)
                pad.append(0.0 if r is None or not r["found"] else 100 * r["validation"][delay])
            cap.append(0.0 if c.get("capped_procedure") is None else 100 * c["capped_procedure"]["validation"]["service_level_success"])
        x = np.asarray(cap) - np.asarray(pad)
        rng = np.random.default_rng(20261020)
        mb = x[rng.integers(0, len(x), size=(20000, len(x)))].mean(axis=1)
        out[f"padding_rescored_{delay}"] = {"padding_pooled": float(np.mean(pad)), "capped_pooled": float(np.mean(cap)),
                                            "capped_minus_padding": [float(x.mean()), float(np.quantile(mb, 0.025)),
                                                                     float(np.quantile(mb, 0.975))]}
    (ROOT / "results" / "amazon_search_check.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != "rows"})


if __name__ == "__main__":
    main()
