"""Retained experiment driver, version 6.

Every reported record contains the instance seed, scenario-bank seeds, solver
budget, environment metadata, raw plan metrics and untouched validation
outcomes. The validation bank is never consulted during candidate selection.
"""

from __future__ import annotations

import argparse
import json
import traceback
import time
from pathlib import Path

from relscreen_v6 import (
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


def solve_with_retries(factory, objective, seconds, *, initial_routes=None):
    started = time.perf_counter()
    plan = None
    attempts = 0
    for attempts in range(1, 4):
        plan = factory().solve(
            objective, seconds, initial_routes=initial_routes
        )
        if plan is not None:
            break
    return plan, time.perf_counter() - started, attempts


def diagnose_screening(candidates, beta_values):
    feasible = [item for item in candidates if item.screening is not None]
    if not feasible:
        return {
            "best_beta": None,
            "best_service_lcb": None,
            "feasible_candidates": 0,
            "first_infeasible_beta": min(beta_values),
            "failure_mode": "no feasible candidate solve",
        }
    best = max(feasible, key=lambda item: item.screening.service_level_lcb)
    passing = [item for item in feasible if item.screening.service_level_lcb >= 0.95]
    infeasible = [item.beta for item in candidates if not item.feasible]
    ceiling = max(beta_values)
    if passing:
        failure_mode = "screen-selected"
    elif any(item.beta == ceiling for item in feasible):
        failure_mode = "grid ceiling reached without passing"
    else:
        failure_mode = "contracted solves infeasible before grid ceiling"
    return {
        "best_beta": best.beta,
        "best_service_lcb": best.screening.service_level_lcb,
        "best_service_probability": best.screening.service_level_success,
        "feasible_candidates": len(feasible),
        "first_infeasible_beta": min(infeasible) if infeasible else None,
        "max_feasible_beta": max(item.beta for item in feasible),
        "failure_mode": failure_mode,
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
    peak_planning_speed = params.nominal_speed_kmh / 1.2
    data = make_synthetic_instance(customers, vehicles, seed, params.shift_length)
    screening_seed = 100_000 + seed
    validation_seed = 200_000 + seed
    screening_bank = ScenarioBank(screen_scenarios, screening_seed, params)
    validation_bank = ScenarioBank(validation_scenarios, validation_seed, params)

    # Failure policy (CONFIRMATORY_PROTOCOL.md). Each configuration is recorded
    # separately. "no_plan" means the solver returned no plan after its permitted
    # attempts; "not_attempted" means a prerequisite configuration had no plan.
    # Successful configurations are always kept. Any other exception is a
    # software error and propagates to the caller.
    status = {}
    started = time.perf_counter()
    try:
        ranges, anchors = empirical_reference_ranges(data, params, anchor_seconds)
        status["anchors"] = "ok"
    except RuntimeError as exc:
        if not str(exc).startswith("anchor solve failed"):
            raise
        ranges, anchors = None, {}
        status["anchors"] = f"no_plan: {exc}"
    anchor_elapsed_seconds = time.perf_counter() - started

    static, static_seconds, static_attempts = solve_with_retries(
        lambda: RoutingSolver(data, params), "distance", solve_seconds
    )
    status["static"] = "ok" if static is not None else "no_plan: nominal distance solve"

    peak_aware, peak_seconds, peak_attempts = solve_with_retries(
        lambda: RoutingSolver(
            data, params, planning_speed_kmh=peak_planning_speed
        ),
        "distance",
        solve_seconds,
    )
    if peak_aware is not None:
        peak_aware.objective = "peak-aware distance"
    status["peak_aware_distance"] = (
        "ok" if peak_aware is not None else "no_plan: conservative-speed distance solve")

    weighted, weighted_seconds, weighted_attempts = None, 0.0, 0
    if ranges is None:
        status["weighted_objective_only"] = "not_attempted: anchors returned no plan"
    else:
        weighted, weighted_seconds, weighted_attempts = solve_with_retries(
            lambda: RoutingSolver(data, params, ranges), "weighted", solve_seconds
        )
        status["weighted_objective_only"] = (
            "ok" if weighted is not None else "no_plan: slack-aware solve")

    fleet_target = None
    fleet_matched, fleet_matched_seconds, fleet_matched_attempts = None, 0.0, 0
    if weighted is None:
        status["fleet_matched_distance"] = "not_attempted: slack-aware plan absent"
    else:
        weighted_used = [route for route in weighted.routes if len(route) > 2]
        fleet_target = int(weighted.metrics["fleet"])
        fleet_matched, fleet_matched_seconds, fleet_matched_attempts = solve_with_retries(
            lambda: RoutingSolver(data, params, exact_fleet=fleet_target),
            "distance",
            solve_seconds,
            initial_routes=weighted_used,
        )
        if fleet_matched is not None:
            fleet_matched.objective = "fleet-matched distance"
        status["fleet_matched_distance"] = (
            "ok" if fleet_matched is not None else "no_plan: fleet-matched distance solve")

    static_validation = None
    if static is not None:
        static_validation = evaluate_reliability(
            static, data, params, profile, validation_bank
        )
    peak_validation = None
    if peak_aware is not None:
        peak_validation = evaluate_reliability(
            peak_aware, data, params, profile, validation_bank
        )
    weighted_validation = None
    if weighted is not None:
        weighted_validation = evaluate_reliability(
            weighted, data, params, profile, validation_bank
        )
    fleet_matched_validation = None
    if fleet_matched is not None:
        fleet_matched_validation = evaluate_reliability(
            fleet_matched, data, params, profile, validation_bank
        )

    selected, candidates, screening_diagnostic = None, [], None
    if ranges is None:
        status["screened"] = "not_attempted: anchors returned no plan"
    else:
        selected, candidates = screen_with_internal_buffers(
            data,
            params,
            profile,
            ranges,
            beta_values,
            screening_bank,
            solve_seconds,
        )
        screening_diagnostic = diagnose_screening(candidates, list(beta_values))
        status["screened"] = "ok"
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
        "peak_planning_speed_kmh": peak_planning_speed,
        "anchor_solve_seconds": anchor_seconds,
        "feasibility_attempt_limit": 3,
        "screen_scenarios": screen_scenarios,
        "validation_scenarios": validation_scenarios,
        "beta_values": list(beta_values),
        "configuration_status": status,
        "reference_ranges": None if ranges is None else {"lower": ranges[0], "upper": ranges[1]},
        "anchor_elapsed_seconds": anchor_elapsed_seconds,
        "anchors": {name: plan.as_dict() for name, plan in anchors.items()},
        "static": {
            "solve_seconds": static_seconds,
            "attempts": static_attempts,
            "plan": None if static is None else static.as_dict(),
            "validation": None if static_validation is None else static_validation.as_dict(),
        },
        "peak_aware_distance": {
            "feasible": peak_aware is not None,
            "solve_seconds": peak_seconds,
            "attempts": peak_attempts,
            "plan": None if peak_aware is None else peak_aware.as_dict(),
            "validation": None if peak_validation is None else peak_validation.as_dict(),
        },
        "weighted_objective_only": {
            "solve_seconds": weighted_seconds,
            "attempts": weighted_attempts,
            "plan": None if weighted is None else weighted.as_dict(),
            "validation": None if weighted_validation is None else weighted_validation.as_dict(),
        },
        "fleet_matched_distance": {
            "target_fleet": fleet_target,
            "solve_seconds": fleet_matched_seconds,
            "attempts": fleet_matched_attempts,
            "plan": None if fleet_matched is None else fleet_matched.as_dict(),
            "validation": (
                None if fleet_matched_validation is None else fleet_matched_validation.as_dict()),
        },
        "screened": {
            "selected_plan": None if selected is None else selected.as_dict(),
            "validation": (
                None if selected_validation is None else selected_validation.as_dict()
            ),
            "diagnostic": screening_diagnostic,
            "candidates": [candidate_to_dict(item) for item in candidates],
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[20, 50, 100, 200])
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--seed-shift", type=int, default=0,
        help="Add to every instance seed. 0 reruns the development design; "
             "wall-clock solver limits can produce different routes, so exact "
             "reported tables come from the archived records. The confirmatory "
             "study uses 60000 (see CONFIRMATORY_PROTOCOL.md).")
    parser.add_argument("--solve-seconds", type=float, default=5.0)
    parser.add_argument("--anchor-seconds", type=float, default=2.0)
    parser.add_argument("--screen-scenarios", type=int, default=1000)
    parser.add_argument("--validation-scenarios", type=int, default=5000)
    parser.add_argument("--beta-max", type=int, default=60)
    parser.add_argument("--beta-step", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("results/study_v6.json"))
    args = parser.parse_args()

    if args.output.exists():
        result = json.loads(args.output.read_text(encoding="utf-8"))
        if result.get("schema") != "routeops-v6-study-1":
            raise ValueError("existing output has an incompatible schema")
    else:
        result = {
            "schema": "routeops-v6-study-1",
            "environment": environment_metadata(),
            "records": [],
        }
    result.setdefault("software_errors", [])
    completed = {
        (int(record["customers"]), int(record["instance_seed"]))
        for record in result["records"] + result["software_errors"]
    }
    for customers in args.sizes:
        vehicles, instances, first_seed = SPEC[customers]
        if args.limit is not None:
            instances = min(instances, args.limit)
        for offset in range(instances):
            seed = first_seed + args.seed_shift + offset
            if (customers, seed) in completed:
                continue
            try:
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
            except Exception as exc:  # noqa: BLE001 - recorded, never scored
                # A solver returning no plan is handled per configuration inside
                # run_instance. Anything reaching here is a software error: it is
                # recorded with its traceback and never scored as routing
                # performance. Confirmatory analysis refuses to run while one exists.
                result["software_errors"].append(
                    {"customers": customers, "instance_seed": seed, "stage": 1,
                     "error": f"{type(exc).__name__}: {exc}",
                     "traceback": traceback.format_exc()})
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
                print(f"n={customers} seed={seed} SOFTWARE ERROR in stage 1: {exc}", flush=True)
                continue
            result["records"].append(record)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
            selected = record["screened"]["selected_plan"]
            bad = {k: v for k, v in record["configuration_status"].items() if v != "ok"}
            print(
                f"n={customers} seed={seed} "
                f"selected_beta={None if selected is None else selected['beta']} "
                f"non_ok={bad or 'none'}",
                flush=True,
            )


if __name__ == "__main__":
    main()
