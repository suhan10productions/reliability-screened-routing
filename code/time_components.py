"""Run time of the two procedure components on this machine (exploratory).

For every development instance: the time to screen one candidate on the
1000-scenario screening bank (the stored capped-procedure plan), and the time
of one HGS weighted solve (10,000 iterations, beta = 0, the instance's stored
scaling ranges). OR-Tools candidates use a fixed five-second budget, so they
need no measurement. Output: results/timing_components.json.
"""
from __future__ import annotations

import glob
import json
import platform
import time
from pathlib import Path

import numpy as np

from hgs_generator import HGSSolver
from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance
from relscreen_v7 import evaluate, plan_from_dict

ROOT = Path(__file__).resolve().parents[1]


def main():
    params, profile = ModelParams(), SpeedProfile()
    rows = []
    for f in sorted(glob.glob(str(ROOT / "results/v7/instance_*.json"))):
        r = json.loads(Path(f).read_text())
        seed, n, k = r["instance_seed"], r["customers"], r["vehicles_available"]
        data = make_synthetic_instance(n, k, seed)
        plan = plan_from_dict(r["configurations"]["capped_procedure"]["plan"])
        bank = ScenarioBank(1000, 100_000 + seed, params)
        t0 = time.perf_counter(); evaluate(plan, data, params, profile, bank); screen = time.perf_counter() - t0
        h = json.loads((ROOT / f"results/hgs_dev/instance_{seed}.json").read_text())
        rr = h["reference_ranges"]
        hgs_t = None
        if rr is not None:
            t0 = time.perf_counter()
            HGSSolver(data, params, (rr["lower"], rr["upper"]), seed=seed).solve("weighted", beta=0)
            hgs_t = time.perf_counter() - t0
        rows.append({"seed": seed, "n": n, "screen_seconds": screen, "hgs_seconds": hgs_t})
        print(seed, n, round(screen, 3), hgs_t and round(hgs_t, 2), flush=True)
    summary = {}
    for n in (20, 50, 100, 200):
        rs = [x for x in rows if x["n"] == n]
        summary[str(n)] = {"screen_median": float(np.median([x["screen_seconds"] for x in rs])),
                           "hgs_median": float(np.median([x["hgs_seconds"] for x in rs if x["hgs_seconds"] is not None]))}
    (ROOT / "results/timing_components.json").write_text(json.dumps(
        {"machine": platform.platform(), "processor": platform.processor() or "not reported",
         "rows": rows, "median_by_size": summary}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
