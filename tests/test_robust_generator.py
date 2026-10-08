import itertools
import random
import unittest

from relscreen_v6 import ModelParams, make_synthetic_instance
from robust_generator import CappedRobustModel, RobustModel, RobustSolver


def robust_ok(m, route, departure=0):
    """Robust feasibility by enumerating every set of at most gamma deviating arcs."""
    if sum(m.dem[c] for c in route) > m.Q:
        return False
    nodes = [0] + list(route) + [0]
    arcs = list(zip(nodes[:-1], nodes[1:]))
    for k in range(min(m.G, len(arcs)) + 1):
        for dev in itertools.combinations(range(len(arcs)), k):
            now = departure
            for idx, (i, j) in enumerate(arcs):
                now += m.S[i] + m.T[i][j] + (m.DEV[i][j] if idx in dev else 0)
                if j:
                    now = max(now, m.L[j])
                    if now > m.U[j]:
                        return False
                elif now > m.H:
                    return False
    return True


SETTINGS = [(0, 0.3), (1, 0.3), (2, 0.5), (3, 0.8), (None, 0.4)]


class RobustModelTests(unittest.TestCase):
    def setUp(self):
        self.p = ModelParams()
        self.data = make_synthetic_instance(20, 6, 7201)
        self.rng = random.Random(3)

    def routes(self, m, count=60):
        for _ in range(count):
            route = self.rng.sample(range(1, 21), self.rng.randint(1, 6))
            route.sort(key=lambda c: m.L[c] + m.U[c])
            yield route

    def test_forward_matches_enumeration(self):
        for g, d in SETTINGS:
            m = RobustModel(self.data, self.p, g, d)
            for route in self.routes(m):
                exact = robust_ok(m, route)
                self.assertEqual(m.feasible(route), exact, (g, d, route))

    def test_join_and_insertion_match_full_check(self):
        for g, d in SETTINGS:
            m = RobustModel(self.data, self.p, g, d)
            for route in self.routes(m):
                if sum(m.dem[c] for c in route) > m.Q:
                    continue
                full = m.forward(route) is not None
                for cut in range(len(route) + 1):
                    pre, suf = route[:cut], route[cut:]
                    a = m.forward(pre)
                    if a is None:
                        continue
                    i, j = (pre[-1] if pre else 0), (suf[0] if suf else 0)
                    self.assertEqual(m.join(a[-1], i, j, m.backward(suf)[1]), full)
                if full:
                    for pos, c in enumerate(route):
                        rest = route[:pos] + route[pos + 1:]
                        a = m.forward(rest)
                        if a is None:
                            continue
                        i = rest[pos - 1] if pos else 0
                        j = rest[pos] if pos < len(rest) else 0
                        self.assertTrue(m.insert_ok(a[pos], i, c, j, m.backward(rest)[pos + 1]))

    def test_latest_departure(self):
        for g, d in SETTINGS:
            m = RobustModel(self.data, self.p, g, d)
            for route in self.routes(m):
                if not m.feasible(route):
                    continue
                dep = m.latest_departure(route)
                self.assertTrue(robust_ok(m, route, dep))
                if dep < m.H:
                    self.assertFalse(robust_ok(m, route, dep + 1))


def capped_ok(cm, route, departure=0):
    """Capped feasibility: robust with relieved deadlines and nominal with original windows."""
    rob, nom = cm.parts
    return robust_ok(rob, route, departure) and robust_ok(nom, route, departure)


class CappedRobustModelTests(unittest.TestCase):
    def setUp(self):
        self.p = ModelParams()
        self.rng = random.Random(11)
        # 50-customer instances where relief is needed at theta = 0.6
        self.cases = [make_synthetic_instance(50, 14, s) for s in (7500, 7501)]

    def test_relief_needed_and_checks_match_enumeration(self):
        relieved_any = False
        for data in self.cases:
            for g, d in [(1, 0.6), (3, 0.6), (None, 0.6), (2, 0.4)]:
                cm = CappedRobustModel(data, self.p, g, d)
                relieved_any |= bool(cm.relieved)
                for _ in range(80):
                    route = self.rng.sample(range(1, 51), self.rng.randint(1, 5))
                    route.sort(key=lambda c: cm.L[c] + cm.parts[1].U[c])
                    if sum(cm.dem[c] for c in route) > cm.Q:
                        continue
                    exact = capped_ok(cm, route)
                    self.assertEqual(cm.feasible(route), exact)
                    if not exact:
                        continue
                    dep = cm.latest_departure(route)
                    self.assertTrue(capped_ok(cm, route, dep))
                    if dep < cm.H:
                        self.assertFalse(capped_ok(cm, route, dep + 1))
                    for pos, c in enumerate(route):
                        rest = route[:pos] + route[pos + 1:]
                        a = cm.forward(rest)
                        if a is None:
                            continue
                        i = rest[pos - 1] if pos else 0
                        j = rest[pos] if pos < len(rest) else 0
                        self.assertTrue(cm.insert_ok(a[pos], i, c, j, cm.backward(rest)[pos + 1]))
                    for cut in range(len(route) + 1):
                        pre, suf = route[:cut], route[cut:]
                        a = cm.forward(pre)
                        if a is None:
                            continue
                        i, j = (pre[-1] if pre else 0), (suf[0] if suf else 0)
                        self.assertTrue(cm.join(a[-1], i, j, cm.backward(suf)[1]))
        self.assertTrue(relieved_any)

    def test_capped_plan_is_feasible(self):
        data = self.cases[1]
        plan = RobustSolver(data, self.p, 2, 0.6, iterations=200, seed=1, capped=True).solve()
        self.assertIsNotNone(plan)
        cm = CappedRobustModel(data, self.p, 2, 0.6)
        visits = sorted(c for r in plan.routes for c in r if c)
        self.assertEqual(visits, list(range(1, 51)))
        for route, dep in zip(plan.routes, plan.departures):
            if len(route) > 2:
                self.assertTrue(capped_ok(cm, route[1:-1], int(dep)))


class RobustSolverTests(unittest.TestCase):
    def setUp(self):
        self.p = ModelParams()
        self.data = make_synthetic_instance(20, 6, 7203)

    def test_plan_is_robust_feasible_and_deterministic(self):
        for g, d in [(2, 0.6), (None, 0.4)]:
            a = RobustSolver(self.data, self.p, g, d, iterations=300, seed=7203).solve()
            b = RobustSolver(self.data, self.p, g, d, iterations=300, seed=7203).solve()
            self.assertEqual(a.routes, b.routes)
            self.assertEqual(a.departures, b.departures)
            visits = sorted(c for r in a.routes for c in r if c)
            self.assertEqual(visits, list(range(1, 21)))
            m = RobustModel(self.data, self.p, g, d)
            for route, dep in zip(a.routes, a.departures):
                if len(route) > 2:
                    self.assertTrue(robust_ok(m, route[1:-1], int(dep)))


if __name__ == "__main__":
    unittest.main()
