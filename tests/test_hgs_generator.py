import unittest

from relscreen_v6 import ModelParams, make_synthetic_instance
from hgs_generator import HGSSolver, schedule, travel_matrix


class HGSGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.p = ModelParams()
        self.data = make_synthetic_instance(20, 6, 7203)

    def solve(self, beta=0):
        return HGSSolver(self.data, self.p, iterations=500, seed=7203).solve("distance", beta=beta)

    def test_deterministic(self):
        a, b = self.solve(), self.solve()
        self.assertEqual(a.routes, b.routes)
        self.assertEqual(a.departures, b.departures)

    def test_every_customer_once_and_starts_in_windows(self):
        plan = self.solve(beta=20)
        visits = sorted(c for r in plan.routes for c in r if c)
        self.assertEqual(visits, list(range(1, 21)))
        cd = self.data.contracted(20)
        for c, s in plan.service_starts.items():
            lo, hi = cd.offered_windows[c]
            self.assertTrue(lo - 1e-9 <= s <= hi + 1e-9)

    def test_departure_is_latest_feasible(self):
        plan = self.solve()
        times = travel_matrix(self.data, self.p.nominal_speed_kmh)
        for route, dep in zip(plan.routes, plan.departures):
            if len(route) <= 2:
                continue
            got = schedule(route, self.data, self.p, times)
            self.assertIsNotNone(got)
            self.assertEqual(got[0], dep)
            # one minute later must miss a window or the shift end
            stops = [c for c in route if c]
            now, prev, late = dep + 1, 0, False
            for c in stops:
                lo, hi = self.data.offered_windows[c]
                start = max(now + times[prev][c], lo)
                late |= start > hi + 1e-9
                now, prev = start + self.p.service_minutes, c
            late |= now + times[prev][0] > self.p.shift_length + 1e-9
            if dep < self.p.shift_length:
                self.assertTrue(late or dep == 0)


if __name__ == "__main__":
    unittest.main()
