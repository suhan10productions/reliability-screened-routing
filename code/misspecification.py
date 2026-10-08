"""Stored plans evaluated under delay models other than the one used for screening.

Exploratory. Every plan was chosen under the paper's disturbance model:
lognormal multipliers with sigma = 0.20, latent correlation rho = 0.5 and the
morning peak divisor 1.2. Here the same fixed plans, with no re-screening or
re-optimization, are evaluated on 5000 new scenarios (seed 700000 + instance
seed) under five models, fixed before this script was run:

  baseline     the paper's model, on the new scenarios (reference)
  heavy_tails  log-errors with Student-t(3) common and local components, scaled
               to unit variance, in place of normal ones
  incidents    the paper's model, plus an independent incident on each arc
               traversal with probability 0.03 that doubles its travel time
  peak_noise   uncertainty that depends on the time of day: sigma = 0.30 and
               rho = 0.8 for departures in the peaks (07:00-09:00, 17:00-19:00),
               sigma = 0.15 and rho = 0.3 otherwise
  strong_peak  the predictable morning peak is stronger than planned (divisor
               1.4 instead of 1.2 from 07:00 to 09:00); noise as in the paper

Configurations: OR-Tools conservative speed, original and capped procedures
(development and both confirmatory studies); HGS conservative speed and HGS
capped procedure with conservative fallback (development and confirmatory 2);
relieved robust Gamma = 3, theta = 0.6 and screened robust with relief
(development instances with up to 100 customers). A missing plan scores 0.

Usage: PYTHONPATH=code python code/misspecification.py --output results/misspecification.json
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path

import numpy as np

from analyse_robust import boot, screened_robust
from relscreen_v6 import ModelParams, SpeedProfile, _stable_seed, make_synthetic_instance
from relscreen_v7 import plan_from_dict, vector_travel

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("baseline", "heavy_tails", "incidents", "peak_noise", "strong_peak")
SCENARIOS, SEED_OFFSET = 5000, 700_000
INCIDENT_P, INCIDENT_FACTOR = 0.03, 2.0
PEAKS = ((420, 540), (1020, 1140))


class AltBank:
    def __init__(self, scenarios: int, seed: int, model: str):
        self.n, self.seed, self.model = scenarios, seed, model
        g = np.random.default_rng(_stable_seed(seed, 0)).standard_normal(scenarios)
        if model == "heavy_tails":
            chi = np.random.default_rng(_stable_seed(seed, 2)).chisquare(3, scenarios)
            g = g / np.sqrt(chi / 3) / math.sqrt(3)
        self.g = g
        self._local, self._inc = {}, {}

    def local(self, arc):
        if arc not in self._local:
            z = np.random.default_rng(_stable_seed(self.seed, 1, *arc)).standard_normal(self.n)
            if self.model == "heavy_tails":
                chi = np.random.default_rng(_stable_seed(self.seed, 3, *arc)).chisquare(3, self.n)
                z = z / np.sqrt(chi / 3) / math.sqrt(3)
            self._local[arc] = z
        return self._local[arc]

    def incident(self, arc):
        if arc not in self._inc:
            u = np.random.default_rng(_stable_seed(self.seed, 4, *arc)).random(self.n)
            self._inc[arc] = np.where(u < INCIDENT_P, INCIDENT_FACTOR, 1.0)
        return self._inc[arc]


def evaluate_alt(plan, data, params, bank: AltBank):
    profile = SpeedProfile()
    if bank.model == "strong_peak":
        mult = list(profile.congestion_multiplier)
        mult[1] = 1.4
        profile = SpeedProfile(congestion_multiplier=tuple(mult))
    late = np.zeros(bank.n, dtype=int)
    for ridx, route in enumerate(plan.routes):
        if len(route) <= 2:
            continue
        now = np.full(bank.n, plan.departures[ridx], dtype=float)
        for i, j in zip(route[:-1], route[1:]):
            clock = now + params.shift_start_minute
            travel = vector_travel(data.distance[i][j], clock, profile)
            if bank.model == "peak_noise":
                peak = np.zeros(bank.n, dtype=bool)
                for a, b in PEAKS:
                    peak |= (clock >= a) & (clock < b)
                sigma = np.where(peak, 0.30, 0.15)
                rho = np.where(peak, 0.8, 0.3)
            else:
                sigma, rho = params.sigma, params.rho_log
            eps = sigma * (np.sqrt(rho) * bank.g + np.sqrt(1 - rho) * bank.local((i, j)))
            factor = np.exp(eps)
            if bank.model == "incidents":
                factor = factor * bank.incident((i, j))
            now = now + travel * factor
            if j:
                lo, hi = data.offered_windows[j]
                now = np.maximum(now, lo)
                late += (now - hi) > 1e-9
                now = now + params.service_minutes
    frac = 1 - late / data.num_customers
    return 100 * float(np.mean(frac >= params.kappa))


def load(directory):
    return {json.loads(Path(f).read_text())["instance_seed"]: json.loads(Path(f).read_text())
            for f in sorted(glob.glob(str(ROOT / directory / "instance_*.json")))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    params = ModelParams()
    studies = {
        "development": {"v7": load("results/v7"), "hgs": load("results/hgs_dev"),
                        "rob": load("results/robust_capped_dev")},
        "confirmatory 1": {"v7": load("results/confirm/v7"), "hgs": {}, "rob": {}},
        "confirmatory 2": {"v7": load("results/confirm2/v7"), "hgs": load("results/confirm2/hgs"), "rob": {}},
    }
    out = {"models": MODELS, "scenarios": SCENARIOS, "seed_offset": SEED_OFFSET, "studies": {}}
    for study, src in studies.items():
        rows = []
        for seed, r in sorted(src["v7"].items()):
            data = make_synthetic_instance(r["customers"], r["vehicles_available"], seed)
            cfg = {"ort_conservative": r["configurations"]["conservative"],
                   "ort_original": r["configurations"]["procedure"],
                   "ort_capped": r["configurations"]["capped_procedure"]}
            if src["hgs"]:
                h = src["hgs"][seed]["configurations"]
                cfg["hgs_conservative"] = h["hgs_conservative"]
                cfg["hgs_capped_cons"] = h["hgs_capped_cons"]
            if seed in src["rob"]:
                st = src["rob"][seed]["settings"]
                cfg["relief_G3_t0.6"] = st["G3_d0.6"]
                cfg["screened_relief"] = screened_robust(st)[0]
            row = {"seed": seed, "n": r["customers"], "service": {}}
            for model in MODELS:
                bank = AltBank(SCENARIOS, SEED_OFFSET + seed, model)
                row["service"][model] = {k: (0.0 if (v is None or v.get("plan") is None)
                                             else evaluate_alt(plan_from_dict(v["plan"]), data, params, bank))
                                         for k, v in cfg.items()}
            rows.append(row)
            print(study, seed, flush=True)
        configs = sorted({k for r in rows for k in r["service"]["baseline"]})
        summary = {}
        for model in MODELS:
            summary[model] = {}
            for c in configs:
                vals = [r["service"][model][c] for r in rows if c in r["service"][model]]
                summary[model][c] = {"instances": len(vals), "mean": float(np.mean(vals))}
            pairs = [("ort_capped", "ort_conservative"), ("ort_original", "ort_conservative"),
                     ("hgs_capped_cons", "hgs_conservative"), ("screened_relief", "hgs_capped_cons"),
                     ("relief_G3_t0.6", "hgs_capped_cons")]
            summary[model]["contrasts"] = {}
            for x, y in pairs:
                rs = [r for r in rows if x in r["service"][model] and y in r["service"][model]]
                if rs:
                    summary[model]["contrasts"][f"{x} minus {y}"] = {
                        "instances": len(rs),
                        "diff": boot([r["service"][model][x] - r["service"][model][y] for r in rs])}
        out["studies"][study] = {"summary": summary, "rows": rows}
    a.output.write_text(json.dumps(out, indent=1))
    for study, d in out["studies"].items():
        print("\n==", study)
        for model in MODELS:
            s = d["summary"][model]
            print(f"  {model:12s}", {k: round(v["mean"], 1) for k, v in s.items() if k != "contrasts"})
            for k, v in s["contrasts"].items():
                print(f"      {k:40s} {v['diff'][0]:+.1f} [{v['diff'][1]:+.1f}, {v['diff'][2]:+.1f}] (k={v['instances']})")


if __name__ == "__main__":
    main()
