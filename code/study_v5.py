"""Retained experiment driver, version 5.

Every reported record contains the instance seed, scenario-bank seeds, solver
budget, environment metadata, raw plan metrics and untouched validation
outcomes. The validation bank is never consulted during candidate selection.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from relscreen_v5 import (
    ModelParams,
    RoutingSolver,
    ScenarioBank,
    SpeedProfile,
    empirical_reference_ranges,
    environment_metadata,
    evaluate_reliability,
    make_synthetic_instance,
    screen_with_internal_buffers,
)


SPEC = {
    20: (6, 20, 7200),
    50: (14, 15, 7500),
    100: (26, 10, 8000),
    200: (40, 8, 9000),
}


def candidate_to_dict(record):
    return {
        "beta": record.beta,
        "feasible": record.feasible,
        "solve_seconds": record.solve_seconds,
        "plan": None if record.plan is None else record.plan.as_dict(),
        "screening": (
            None if record.screening is None else record.screening.as_dict()
        ),
    }


def run_instance(
    customers,
    vehicles,
    seed,
    solve_seconds,
    anchor_seconds,
    screen_scenarios,
    validation_scenarios,
    beta_values,
):
    params = ModelParams()
    profile = SpeedProfile()
    data = make_synthetic_instance(customers, vehicles, seed, params.shift_length)
    screening_seed = 100_000 + seed
    validation_seed = 200_000 + seed
    screening_bank = ScenarioBank(screen_scenarios, screening_seed, params)
    validation_bank = ScenarioBank(validation_scenarios, validation_seed, params)

    started = time.perf_counter()
    ranges, anchors = empirical_reference_ranges(data, params, anchor_seconds)
    anchor_elapsed_seconds = time.perf_counter() - started

    started = time.perf_counter()
    static = None
    for _ in range(3):
        static = RoutingSolver(data, params).solve("distance", solve_seconds)
        if static is not None:
            break
    static_seconds = time.perf_counter() - started
    if static is None:
        raise RuntimeError("static solve failed")

    started = time.perf_counter()
    weighted = None
    for _ in range(3):
        weighted = RoutingSolver(data, params, ranges).solve("weighted", solve_seconds)
        if weighted is not None:
            break
    weighted_seconds = time.perf_counter() - started
    if weighted is None:
        raise RuntimeError("weighted solve failed")

    static_validation = evaluate_reliability(
        static, data, params, profile, validation_bank
    )
    weighted_validation = evaluate_reliability(
        weighted, data, params, profile, validation_bank
    )

    selected, candidates = screen_with_internal_buffers(
        data,
        params,
        profile,
        ranges,
        beta_values,
        screening_bank,
        solve_seconds,
    )
    selected_validation = None
    if selected is not None:
        selected_validation = evaluate_reliability(
            selected, data, params, profile, validation_bank
        )

    return {
        "customers": customers,
        "vehicles_available": vehicles,
        "instance_seed": seed,
        "screening_seed": screening_seed,
        "validation_seed": validation_seed,
        "solve_seconds": solve_seconds,
        "anchor_solve_seconds": anchor_seconds,
        "feasibility_attempt_limit": 3,
        "screen_scenarios": screen_scenarios,
        "validation_scenarios": validation_scenarios,
        "beta_values": list(beta_values),
        "reference_ranges": {"lower": ranges[0], "upper": ranges[1]},
        "anchor_elapsed_seconds": anchor_elapsed_seconds,
        "anchors": {name: plan.as_dict() for name, plan in anchors.items()},
        "static": {
            "solve_seconds": static_seconds,
            "plan": static.as_dict(),
            "validation": static_validation.as_dict(),
        },
        "weighted_objective_only": {
            "solve_seconds": weighted_seconds,
            "plan": weighted.as_dict(),
            "validation": weighted_validation.as_dict(),
        },
        "screened": {
            "selected_plan": None if selected is None else selected.as_dict(),
            "validation": (
                None if selected_validation is None else selected_validation.as_dict()
            ),
            "candidates": [candidate_to_dict(item) for item in candidates],
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[20, 50, 100, 200])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--solve-seconds", type=float, default=2.0)
    parser.add_argument("--anchor-seconds", type=float, default=2.0)
    parser.add_argument("--screen-scenarios", type=int, default=1000)
    parser.add_argument("--validation-scenarios", type=int, default=5000)
    parser.add_argument("--beta-max", type=int, default=30)
    parser.add_argument("--beta-step", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("results/study_v5.json"))
    args = parser.parse_args()

    if args.output.exists():
        result = json.loads(args.output.read_text(encoding="utf-8"))
        if result.get("schema") != "routeops-v5-study-1":
            raise ValueError("existing output has an incompatible schema")
    else:
        result = {
            "schema": "routeops-v5-study-1",
            "environment": environment_metadata(),
            "records": [],
        }
    completed = {
        (int(record["customers"]), int(record["instance_seed"]))
        for record in result["records"]
    }
    for customers in args.sizes:
        vehicles, instances, first_seed = SPEC[customers]
        if args.limit is not None:
            instances = min(instances, args.limit)
        for offset in range(instances):
            seed = first_seed + offset
            if (customers, seed) in completed:
                continue
            record = run_instance(
                customers,
                vehicles,
                seed,
                args.solve_seconds,
                args.anchor_seconds,
                args.screen_scenarios,
                args.validation_scenarios,
                range(0, args.beta_max + 1, args.beta_step),
            )
            result["records"].append(record)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
            selected = record["screened"]["selected_plan"]
            print(
                f"n={customers} seed={seed} "
                f"static_service={record['static']['validation']['service_level_success']:.3f} "
                f"weighted_service={record['weighted_objective_only']['validation']['service_level_success']:.3f} "
                f"selected_beta={None if selected is None else selected['beta']}",
                flush=True,
            )


if __name__ == "__main__":
    main()
