"""Quality check of the robust search at gamma = 0 (nominal VRPTW) against PyVRP/HGS.

For every development instance with 20, 50 and 100 customers, the distance
objective is solved by HGS (10,000 iterations, instance seed) and by
RobustSolver with gamma = 0 at several iteration counts (instance seed). Both
searches are deterministic. The manuscript reports the counts used in
study_robust.ITERATIONS (6000 at 20 and 50 customers, 3000 at 100).

Usage: PYTHONPATH=code python code/benchmark_robust.py --output results/robust_benchmark.json --workers 2
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from hgs_generator import HGSSolver
from relscreen_v6 import ModelParams, make_synthetic_instance
from robust_generator import RobustSolver

DESIGN = {20: (6, 20, 7200), 50: (14, 15, 7500), 100: (26, 10, 8000)}
ITERATION_GRID = {20: [1000, 3000, 6000], 50: [1000, 3000, 6000], 100: [1000, 3000]}


def job(task):
    n, vehicles, seed, iterations = task
    p = ModelParams()
    d = make_synthetic_instance(n, vehicles, seed)
    h = HGSSolver(d, p, None, seed=seed).solve("distance")
    out = {"n": n, "seed": seed, "hgs": h and h.metrics["distance"]}
    for it in iterations:
        t = time.time()
        r = RobustSolver(d, p, 0, 0.0, iterations=it, seed=seed).solve()
        out[f"r{it}"] = r and r.metrics["distance"]
        out[f"t{it}"] = round(time.time() - t, 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    tasks = [(n, k, first + i, ITERATION_GRID[n]) for n, (k, count, first) in DESIGN.items() for i in range(count)]
    with ProcessPoolExecutor(a.workers) as ex:
        res = list(ex.map(job, tasks))
    a.output.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
