"""Equal-budget OR-Tools versus PyVRP/HGS deterministic-core benchmark."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from pyvrp import Model
from pyvrp.stop import MaxRuntime

from relscreen_v5 import ModelParams, RoutingSolver, make_synthetic_instance
from study_v5 import SPEC


def solve_pyvrp(data, params, seconds, seed=1):
    model = Model()
    locations = [
        model.add_location(x=float(x), y=float(y)) for x, y in data.coords
    ]
    depot = model.add_depot(
        location=locations[data.depot], tw_early=0, tw_late=params.shift_length
    )
    model.add_vehicle_type(
        num_available=data.num_vehicles,
        capacity=[params.capacity],
        start_depot=depot,
        end_depot=depot,
        shift_duration=params.shift_length,
        tw_early=0,
        tw_late=params.shift_length,
    )
    for customer in range(1, len(data.demands)):
        lower, upper = data.offered_windows[customer]
        model.add_client(
            location=locations[customer],
            delivery=[int(data.demands[customer])],
            service_duration=params.service_minutes,
            tw_early=int(lower),
            tw_late=int(upper),
        )
    speed = params.nominal_speed_kmh / 60.0
    for origin in range(len(data.demands)):
        for destination in range(len(data.demands)):
            if origin == destination:
                continue
            model.add_edge(
                locations[origin],
                locations[destination],
                distance=int(data.distance[origin][destination]),
                duration=int(np.ceil(data.distance[origin][destination] / speed)),
            )
    started = time.perf_counter()
    result = model.solve(stop=MaxRuntime(seconds), seed=seed, display=False)
    elapsed = time.perf_counter() - started
    if not result.is_feasible():
        return None, elapsed
    return {
        "distance": float(result.best.distance()),
        "fleet": int(result.best.num_routes()),
    }, elapsed


def solve_ortools(data, params, seconds):
    started = time.perf_counter()
    plan = RoutingSolver(data, params).solve("distance", seconds)
    elapsed = time.perf_counter() - started
    if plan is None:
        return None, elapsed
    return {
        "distance": float(plan.metrics["distance"]),
        "fleet": int(plan.metrics["fleet"]),
    }, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[20, 50, 100, 200])
    parser.add_argument("--budgets", type=float, nargs="+", default=[1.0, 5.0])
    parser.add_argument("--output", type=Path, default=Path("results/benchmark_v5.json"))
    args = parser.parse_args()
    params = ModelParams()
    result = {
        "schema": "routeops-v5-benchmark-1",
        "solver": {"hgs": "PyVRP 0.14.0", "ortools": "OR-Tools 9.15.6755"},
        "records": [],
    }
    for customers in args.sizes:
        vehicles, instances, first_seed = SPEC[customers]
        for offset in range(instances):
            seed = first_seed + offset
            data = make_synthetic_instance(customers, vehicles, seed, params.shift_length)
            for budget in args.budgets:
                hgs, hgs_elapsed = solve_pyvrp(data, params, budget, seed=1)
                ortools, ortools_elapsed = solve_ortools(data, params, budget)
                gap = None
                if hgs is not None and ortools is not None:
                    gap = 100.0 * (
                        ortools["distance"] - hgs["distance"]
                    ) / hgs["distance"]
                row = {
                    "customers": customers,
                    "instance_seed": seed,
                    "budget_seconds": budget,
                    "hgs": hgs,
                    "hgs_elapsed": hgs_elapsed,
                    "ortools": ortools,
                    "ortools_elapsed": ortools_elapsed,
                    "ortools_excess_distance_percent": gap,
                }
                result["records"].append(row)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
                print(
                    f"n={customers} seed={seed} budget={budget:g} gap={gap}",
                    flush=True,
                )


if __name__ == "__main__":
    main()
