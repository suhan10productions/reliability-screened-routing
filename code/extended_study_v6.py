"""Post-hoc robustness analyses for retained version-6 plans.

The script evaluates each fixed plan on the same untouched validation bank for
multiple service thresholds. It also removes random disturbances (sigma=0)
while retaining the time-dependent speed profile, isolating deterministic
planner/profile mismatch from stochastic variation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from relscreen_v6 import (
    ModelParams,
    Plan,
    ScenarioBank,
    SpeedProfile,
    _evaluate_route,
    make_synthetic_instance,
)


KAPPAS = (0.90, 0.95, 0.98, 1.00)
SIGMAS = (0.10, 0.20, 0.30)
RHOS = (0.0, 0.5, 0.9)


def plan_from_dict(raw: dict) -> Plan:
    return Plan(
        routes=[[int(node) for node in route] for route in raw["routes"]],
        departures=[float(value) for value in raw["departures"]],
        service_starts={int(key): float(value) for key, value in raw["service_starts"].items()},
        metrics={key: float(value) for key, value in raw["metrics"].items()},
        objective=str(raw["objective"]),
        beta=int(raw.get("beta", 0)),
        solver_objective=raw.get("solver_objective"),
    )


def scenario_late_counts(plan, data, params, profile, bank):
    used = [
        (route, plan.departures[index])
        for index, route in enumerate(plan.routes)
        if len(route) > 2
    ]
    counts = np.zeros(bank.scenarios, dtype=np.int32)
    lateness = np.zeros(bank.scenarios, dtype=float)
    for scenario in range(bank.scenarios):
        for route, departure in used:
            result = _evaluate_route(
                route, departure, data, params, profile, bank, scenario
            )
            counts[scenario] += int(result["late_customers"])
            lateness[scenario] += float(result["total_lateness"])
    return counts, lateness


def summarize_counts(counts, lateness, customers):
    on_time = 1.0 - counts.astype(float) / customers
    return {
        "service_probability_by_kappa": {
            f"{kappa:.2f}": float(np.mean(on_time >= kappa)) for kappa in KAPPAS
        },
        "mean_on_time_fraction": float(np.mean(on_time)),
        "expected_late_customers": float(np.mean(counts)),
        "mean_total_lateness": float(np.mean(lateness)),
    }


def process(path: Path, sensitivity_scenarios: int):
    payload = json.loads(path.read_text(encoding="utf-8"))
    params = ModelParams()
    profile = SpeedProfile()
    deterministic_params = replace(params, sigma=0.0)
    output = {
        "schema": "routeops-v6-extended-1",
        "source": str(path),
        "kappas": list(KAPPAS),
        "sensitivity_grid": {"sigma": list(SIGMAS), "rho": list(RHOS)},
        "sensitivity_scenarios": sensitivity_scenarios,
        "records": [],
    }
    for record in payload["records"]:
        customers = int(record["customers"])
        seed = int(record["instance_seed"])
        data = make_synthetic_instance(
            customers, int(record["vehicles_available"]), seed, params.shift_length
        )
        distance = plan_from_dict(record["static"]["plan"])
        peak_raw = record["peak_aware_distance"]["plan"]
        peak_aware = None if peak_raw is None else plan_from_dict(peak_raw)
        weighted = plan_from_dict(record["weighted_objective_only"]["plan"])
        fleet_matched = plan_from_dict(record["fleet_matched_distance"]["plan"])
        selected_raw = record["screened"]["selected_plan"]
        if selected_raw is None:
            procedure = weighted
            procedure_source = "slack-aware fallback"
        else:
            procedure = plan_from_dict(selected_raw)
            procedure_source = "screen-selected"
        bank = ScenarioBank(
            int(record["validation_scenarios"]), int(record["validation_seed"]), params
        )
        deterministic_bank = ScenarioBank(1, int(record["validation_seed"]), deterministic_params)
        sensitivity_seed = 300_000 + seed
        configurations = {}
        for name, plan in (
            ("distance", distance),
            ("peak_aware", peak_aware),
            ("slack_aware", weighted),
            ("fleet_matched", fleet_matched),
            ("procedure", procedure),
        ):
            if plan is None:
                configurations[name] = None
                continue
            counts, lateness = scenario_late_counts(
                plan, data, params, profile, bank
            )
            det_counts, det_lateness = scenario_late_counts(
                plan, data, deterministic_params, profile, deterministic_bank
            )
            configurations[name] = {
                "stochastic": summarize_counts(counts, lateness, customers),
                "time_dependent_no_noise": summarize_counts(
                    det_counts, det_lateness, customers
                ),
                "plan_metrics": plan.metrics,
                "beta": plan.beta,
                "parameter_sensitivity": {},
            }
        for sigma in SIGMAS:
            for rho in RHOS:
                sensitivity_params = replace(params, sigma=sigma, rho_log=rho)
                sensitivity_bank = ScenarioBank(
                    sensitivity_scenarios, sensitivity_seed, sensitivity_params
                )
                key = f"sigma={sigma:.2f},rho={rho:.1f}"
                for name, plan in (
                    ("distance", distance),
                    ("peak_aware", peak_aware),
                    ("slack_aware", weighted),
                    ("fleet_matched", fleet_matched),
                    ("procedure", procedure),
                ):
                    if plan is None:
                        continue
                    counts, lateness = scenario_late_counts(
                        plan,
                        data,
                        sensitivity_params,
                        profile,
                        sensitivity_bank,
                    )
                    configurations[name]["parameter_sensitivity"][key] = summarize_counts(
                        counts, lateness, customers
                    )
        output["records"].append(
            {
                "customers": customers,
                "instance_seed": seed,
                "procedure_source": procedure_source,
                "sensitivity_seed": sensitivity_seed,
                "configurations": configurations,
            }
        )
        print(
            f"n={customers} seed={seed} source={procedure_source}",
            flush=True,
        )
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--sensitivity-scenarios", type=int, default=1000)
    args = parser.parse_args()
    result = process(args.input, args.sensitivity_scenarios)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
