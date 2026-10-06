import math
import unittest
from dataclasses import replace

import numpy as np

from relscreen_v6 import (
    ModelParams,
    InstanceData,
    Plan,
    RoutingSolver,
    ScenarioBank,
    SpeedProfile,
    evaluate_reliability,
    empirical_reference_ranges,
    make_synthetic_instance,
    td_travel_minutes,
    wilson_lower_bound,
    _evaluate_route,
)


class ReliabilityScreeningV6Tests(unittest.TestCase):
    def setUp(self):
        self.params = ModelParams()
        self.profile = SpeedProfile()

    def test_fifo_across_speed_boundary(self):
        distance = 30.0
        departures = [419.0, 419.5, 420.0, 420.5]
        arrivals = [
            t + td_travel_minutes(distance, t, self.profile) for t in departures
        ]
        self.assertEqual(arrivals, sorted(arrivals))

    def test_shift_clock_offset_enters_speed_profile(self):
        data = InstanceData(
            coords=((0, 0), (30, 0)),
            demands=(0, 1),
            offered_windows=((0, 600), (0, 600)),
            distance=((0, 30), (30, 0)),
            num_vehicles=1,
        )
        peak = _evaluate_route(
            [0, 1, 0], 60, data, self.params, self.profile
        )["duration"]
        no_offset = _evaluate_route(
            [0, 1, 0], 60, data, replace(self.params, shift_start_minute=0),
            self.profile,
        )["duration"]
        self.assertGreater(peak, no_offset)

    def test_lognormal_parameter_mean_and_median(self):
        bank = ScenarioBank(100_000, 19, self.params)
        values = np.array([bank.multiplier(s, (1, 2)) for s in range(bank.scenarios)])
        self.assertAlmostEqual(float(np.median(values)), 1.0, delta=0.01)
        self.assertAlmostEqual(
            float(np.mean(values)), math.exp(self.params.sigma**2 / 2), delta=0.01
        )

    def test_common_arc_draw_is_order_invariant(self):
        first = ScenarioBank(20, 991, self.params)
        second = ScenarioBank(20, 991, self.params)
        _ = first.multiplier(3, (4, 5))
        value_a = first.multiplier(3, (1, 2))
        value_b = second.multiplier(3, (1, 2))
        self.assertEqual(value_a, value_b)

    def test_wilson_lower_bound(self):
        self.assertAlmostEqual(wilson_lower_bound(0.961, 1000), 0.9495, delta=0.001)
        self.assertLess(wilson_lower_bound(0.95, 1000), 0.95)

    def test_solver_visits_every_customer_once_and_obeys_capacity(self):
        data = make_synthetic_instance(20, 6, 7200)
        plan = RoutingSolver(data, self.params).solve("distance", 0.2)
        self.assertIsNotNone(plan)
        visited = [node for route in plan.routes for node in route if node != 0]
        self.assertEqual(sorted(visited), list(range(1, 21)))
        for route in plan.routes:
            load = sum(data.demands[node] for node in route if node != 0)
            self.assertLessEqual(load, self.params.capacity)

    def test_peak_aware_matrix_uses_slower_planning_times(self):
        data = make_synthetic_instance(20, 6, 7200)
        nominal = RoutingSolver(data, self.params)
        peak_aware = RoutingSolver(
            data,
            self.params,
            planning_speed_kmh=self.params.nominal_speed_kmh / 1.2,
        )
        self.assertGreater(peak_aware._nominal_time[0][1], nominal._nominal_time[0][1])

    def test_exact_fleet_constraint_is_enforced(self):
        data = make_synthetic_instance(20, 6, 7200)
        seed = RoutingSolver(data, self.params).solve("distance", 0.5)
        self.assertIsNotNone(seed)
        used = [route for route in seed.routes if len(route) > 2]
        plan = RoutingSolver(
            data, self.params, exact_fleet=len(used)
        ).solve("distance", 0.5, initial_routes=used)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.metrics["fleet"], len(used))

    def test_contracted_plan_is_evaluated_on_original_windows(self):
        data = make_synthetic_instance(20, 6, 7201)
        ranges, _ = empirical_reference_ranges(data, self.params, 0.15)
        plan = RoutingSolver(data, self.params, ranges).solve("weighted", 0.15, beta=10)
        self.assertIsNotNone(plan)
        report_original = evaluate_reliability(
            plan, data, self.params, self.profile, ScenarioBank(30, 55, self.params)
        )
        report_contracted = evaluate_reliability(
            plan,
            data.contracted(10),
            self.params,
            self.profile,
            ScenarioBank(30, 55, self.params),
        )
        self.assertGreaterEqual(
            report_original.mean_on_time_fraction,
            report_contracted.mean_on_time_fraction,
        )


if __name__ == "__main__":
    unittest.main()
