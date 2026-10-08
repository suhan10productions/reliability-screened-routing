"""Budgeted-uncertainty robust VRPTW generator.

Robust model (Bertsimas and Sim 2004; for the VRPTW, Agra et al. 2013): on arc
(i, j) the travel time lies in [t_ij, t_ij + d_ij], where t_ij is the nominal
planning time ceil(distance / planning speed) used by the other generators and
d_ij = ceil(delta * t_ij). A route is robust feasible if every service start
stays within its window, the return stays within the shift, and the load stays
within capacity, whenever at most `gamma` arcs of the route take their upper
value. With waiting allowed, the worst case is attained at integer deviation
patterns and is computed exactly by the dynamic programme of Agra et al.:

    A_k(g) = max(l_k, A_{k-1}(g) + s + t, A_{k-1}(g-1) + s + t + d),

the latest possible service start at the k-th stop when at most g deviations
have occurred. A backward programme B_k(r) gives the latest start at the k-th
stop from which the rest of the route is feasible with at most r further
deviations. A prefix ending at stop i joined to a suffix starting at stop j is
robust feasible if and only if A_j(g) <= B_j(gamma - g) for every g, so every
insertion, removal and exchange is checked exactly in O(gamma) time.
`gamma=None` gives box uncertainty (every arc at its upper value), which is
solved exactly as a nominal model on the padded matrix t_ij + d_ij.

Search: large neighbourhood search (random, worst and related removal chosen
uniformly; greedy or regret-2 insertion) with granular local search (relocate,
exchange, 2-opt*) and simulated-annealing acceptance. The
objective is total distance, the fleet is limited to the available vehicles,
and customers that cannot be inserted carry a large penalty. A solve stops
after a fixed number of iterations with a fixed seed, so it is deterministic
for given inputs and does not depend on machine speed.

Plans are returned in the pipeline's Plan format. Each vehicle departs at the
latest time that keeps its route robust feasible, the analogue of the latest
feasible departure used by the other generators. The reported service starts
and duration are the earliest starts from that departure under the model's
planning times: nominal, or padded for box uncertainty, as for the
conservative-speed baseline.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Sequence, Tuple

from relscreen_v6 import InstanceData, ModelParams, Plan
from hgs_generator import travel_matrix

PENALTY = 10_000          # per unrouted customer; exceeds any distance saving
INFEASIBLE = -10 ** 9     # latest start when no start keeps the rest of the route feasible


class RobustModel:
    """Data and exact robust feasibility checks for one (gamma, delta) setting."""

    def __init__(self, data: InstanceData, params: ModelParams, gamma: Optional[int], delta: float,
                 planning_speed_kmh: Optional[float] = None, upper: Optional[Sequence[int]] = None):
        self.data, self.params = data, params
        self.n = len(data.demands)
        speed = params.nominal_speed_kmh if planning_speed_kmh is None else float(planning_speed_kmh)
        self.T = travel_matrix(data, speed)
        self.delta = float(delta)
        self.DEV = [[0 if i == j else int(math.ceil(self.delta * self.T[i][j] - 1e-9))
                     for j in range(self.n)] for i in range(self.n)]
        if gamma is None:                     # box uncertainty: every arc at its upper value
            self.T = [[t + d for t, d in zip(rt, rd)] for rt, rd in zip(self.T, self.DEV)]
            self.DEV = [[0] * self.n for _ in range(self.n)]
            self.G = 0
        else:
            self.G = int(gamma)
        self.box = gamma is None
        self.L = [int(w[0]) for w in data.offered_windows]
        self.U = [int(w[1]) for w in data.offered_windows] if upper is None else [int(x) for x in upper]
        self.S = [0] + [int(params.service_minutes)] * (self.n - 1)
        self.H = int(params.shift_length)
        self.Q = int(params.capacity)
        self.dem = [int(x) for x in data.demands]
        self.D = [[int(x) for x in row] for row in data.distance]

    # ---- route arrays -------------------------------------------------
    def forward(self, route: Sequence[int]) -> Optional[List[List[int]]]:
        """A[p] for p = 0 (depot departure at time 0) .. m; None if infeasible."""
        G, T, DEV, S, L, U = self.G, self.T, self.DEV, self.S, self.L, self.U
        A = [[0] * (G + 1)]
        prev = 0
        for c in route:
            a, svc, t, dv, lo = A[-1], S[prev], T[prev][c], DEV[prev][c], L[c]
            new = [0] * (G + 1)
            x = a[0] + svc + t
            new[0] = x if x > lo else lo
            for g in range(1, G + 1):
                x = a[g] + svc + t
                y = a[g - 1] + svc + t + dv
                if y > x:
                    x = y
                new[g] = x if x > lo else lo
            if new[G] > U[c]:
                return None
            A.append(new)
            prev = c
        if self.end_time(A[-1], prev) > self.H:
            return None
        return A

    def end_time(self, a: List[int], last: int) -> int:
        G, t, dv, s = self.G, self.T[last][0], self.DEV[last][0], self.S[last]
        end = a[G] + s + t
        if G > 0 and a[G - 1] + s + t + dv > end:
            end = a[G - 1] + s + t + dv
        return end

    def backward(self, route: Sequence[int]) -> List[List[int]]:
        """B[p] for p = 1 .. m+1 (index m+1 is the depot); B[0] unused."""
        G, T, DEV, S, U, H, L = self.G, self.T, self.DEV, self.S, self.U, self.H, self.L
        m = len(route)
        B: List[Optional[List[int]]] = [None] * (m + 2)
        B[m + 1] = [H] * (G + 1)
        nxt = 0
        for p in range(m, 0, -1):
            c = route[p - 1]
            b, s, t, dv, u, lo = B[p + 1], S[c], T[c][nxt], DEV[c][nxt], U[c], L[c]
            new = [0] * (G + 1)
            v = b[0] - s - t
            v = v if v < u else u
            new[0] = v if v >= lo else INFEASIBLE      # waiting cannot help below l_c
            for r in range(1, G + 1):
                v = b[r] - s - t
                w = b[r - 1] - s - t - dv
                if w < v:
                    v = w
                v = v if v < u else u
                new[r] = v if v >= lo else INFEASIBLE
            B[p] = new
            nxt = c
        return B  # type: ignore[return-value]

    def feasible(self, route: Sequence[int]) -> bool:
        return (sum(self.dem[c] for c in route) <= self.Q) and self.forward(route) is not None

    # ---- O(gamma) joint checks -----------------------------------------
    def join(self, a_i: List[int], i: int, j: int, b_j: List[int]) -> bool:
        """Prefix ending at node i (arrays a_i) joined to suffix starting at node j (b_j)."""
        G, lo = self.G, self.L[j]
        base = self.S[i] + self.T[i][j]
        dv = self.DEV[i][j]
        x = a_i[0] + base
        if x < lo:
            x = lo
        if x > b_j[G]:
            return False
        for g in range(1, G + 1):
            x = a_i[g] + base
            y = a_i[g - 1] + base + dv
            if y > x:
                x = y
            if x < lo:
                x = lo
            if x > b_j[G - g]:
                return False
        return True

    def insert_ok(self, a_i: List[int], i: int, c: int, j: int, b_j: List[int]) -> bool:
        """Insert customer c between node i (arrays a_i) and node j (arrays b_j)."""
        G, lo, u = self.G, self.L[c], self.U[c]
        base = self.S[i] + self.T[i][c]
        dv = self.DEV[i][c]
        ac = [0] * (G + 1)
        x = a_i[0] + base
        ac[0] = x if x > lo else lo
        for g in range(1, G + 1):
            x = a_i[g] + base
            y = a_i[g - 1] + base + dv
            if y > x:
                x = y
            ac[g] = x if x > lo else lo
        if ac[G] > u:
            return False
        s, t, dv2 = self.S[c], self.T[c][j], self.DEV[c][j]
        for g in range(G + 1):
            r = G - g
            v = b_j[r] - s - t
            if r > 0:
                w = b_j[r - 1] - s - t - dv2
                if w < v:
                    v = w
            if v > u:
                v = u
            if ac[g] > v:
                return False
        return True

    def latest_departure(self, route: Sequence[int]) -> int:
        B = self.backward(route)
        c = route[0]
        t, dv, G = self.T[0][c], self.DEV[0][c], self.G
        dep = B[1][G] - t
        if G > 0:
            dep = min(dep, B[1][G - 1] - t - dv)
        return max(0, min(self.H, dep))


class CappedRobustModel:
    """Robust model with reachability relief, the analogue of capped contraction.

    A customer that cannot be served on time even by a direct trip whose arc takes
    its upper value would make every plan infeasible. For each customer the robust
    deadline is therefore max(u_i, worst-case direct start); all other deadlines are
    unchanged. The plan must also meet every original window under nominal travel
    times, so no promise is extended. Feasibility is the conjunction of the two
    exact checks: the robust model with relieved deadlines and the nominal model.
    """

    def __init__(self, data: InstanceData, params: ModelParams, gamma: Optional[int], delta: float,
                 planning_speed_kmh: Optional[float] = None):
        probe = RobustModel(data, params, gamma, delta, planning_speed_kmh)
        relief = [probe.U[0]] + [max(probe.U[i], probe.L[i], probe.T[0][i] + probe.DEV[0][i])
                                 for i in range(1, probe.n)]
        self.relieved = [i for i in range(1, probe.n) if relief[i] > probe.U[i]]
        self.parts = (RobustModel(data, params, gamma, delta, planning_speed_kmh, upper=relief),
                      RobustModel(data, params, 0, 0.0, planning_speed_kmh))
        rob = self.parts[0]
        self.data, self.params, self.n = data, params, rob.n
        self.G, self.delta, self.box = rob.G, rob.delta, rob.box
        self.L, self.S, self.H, self.Q, self.dem, self.D = rob.L, rob.S, rob.H, rob.Q, rob.dem, rob.D
        self.T = rob.T                               # planning times of the robust model

    def forward(self, route):
        arrays = [m.forward(route) for m in self.parts]
        if any(a is None for a in arrays):
            return None
        return list(zip(*arrays))

    def backward(self, route):
        arrays = [m.backward(route) for m in self.parts]
        return [None] + list(zip(*(a[1:] for a in arrays)))

    def feasible(self, route) -> bool:
        return all(m.feasible(route) for m in self.parts)

    def join(self, a_i, i, j, b_j) -> bool:
        return all(m.join(a, i, j, b) for m, a, b in zip(self.parts, a_i, b_j))

    def insert_ok(self, a_i, i, c, j, b_j) -> bool:
        return all(m.insert_ok(a, i, c, j, b) for m, a, b in zip(self.parts, a_i, b_j))

    def latest_departure(self, route) -> int:
        return min(m.latest_departure(route) for m in self.parts)


class _Route:
    __slots__ = ("stops", "A", "B", "load", "dist")

    def __init__(self, model: RobustModel, stops: List[int]):
        self.stops = stops
        self.refresh(model)

    def refresh(self, model: RobustModel) -> None:
        s = self.stops
        A = model.forward(s)
        if A is None:
            raise AssertionError("route became robust infeasible")
        self.A, self.B = A, model.backward(s)
        self.load = sum(model.dem[c] for c in s)
        D = model.D
        nodes = [0] + s + [0]
        self.dist = sum(D[a][b] for a, b in zip(nodes[:-1], nodes[1:]))

    def node(self, p: int) -> int:
        """Node at position p in [0] + stops + [0]."""
        return 0 if p == 0 or p == len(self.stops) + 1 else self.stops[p - 1]


class RobustSolver:
    def __init__(self, data: InstanceData, params: ModelParams, gamma: Optional[int], delta: float,
                 iterations: int = 3000, seed: int = 1, neighbours: int = 12,
                 planning_speed_kmh: Optional[float] = None, capped: bool = False):
        model_cls = CappedRobustModel if capped else RobustModel
        self.model = model_cls(data, params, gamma, delta, planning_speed_kmh)
        self.capped = bool(capped)
        self.iterations, self.seed, self.k = int(iterations), int(seed), int(neighbours)
        m = self.model
        self.near = [[] for _ in range(m.n)]
        for c in range(1, m.n):
            order = sorted((x for x in range(1, m.n) if x != c), key=lambda x: (m.D[c][x], x))
            self.near[c] = order[: self.k]

    # ---- solution helpers ------------------------------------------------
    def _cost(self, routes: List[_Route], unrouted: List[int]) -> int:
        return sum(r.dist for r in routes) + PENALTY * len(unrouted)

    def _best_insertion(self, r: _Route, c: int) -> Tuple[int, int]:
        """(distance increase, position) for inserting c into route r; (None, -1) if impossible."""
        m = self.model
        if r.load + m.dem[c] > m.Q:
            return (None, -1)  # type: ignore[return-value]
        D, best, pos = m.D, None, -1
        stops = r.stops
        mlen = len(stops)
        for p in range(mlen + 1):
            i = 0 if p == 0 else stops[p - 1]
            j = 0 if p == mlen else stops[p]
            delta = D[i][c] + D[c][j] - D[i][j]
            if best is not None and delta >= best:
                continue
            if m.insert_ok(r.A[p], i, c, j, r.B[p + 1]):
                best, pos = delta, p
        return (best, pos)  # type: ignore[return-value]

    def _repair(self, routes: List[_Route], unrouted: List[int], rng: random.Random,
                regret: bool, noise: float) -> List[int]:
        m = self.model
        pending = list(unrouted)
        rng.shuffle(pending)
        cache: Dict[Tuple[int, int], Tuple[Optional[int], int]] = {}

        def entry(c: int, ri: int):
            key = (c, ri)
            if key not in cache:
                cache[key] = self._best_insertion(routes[ri], c)
            return cache[key]

        left: List[int] = []
        while pending:
            choice = None
            for c in pending:
                opts = []
                for ri in range(len(routes)):
                    cost, pos = entry(c, ri)
                    if cost is not None:
                        opts.append((cost, ri, pos))
                if not opts:
                    continue
                opts.sort()
                best = opts[0][0] * (1.0 + noise * (2.0 * rng.random() - 1.0)) if noise else opts[0][0]
                if regret:
                    second = opts[1][0] if len(opts) > 1 else 10 ** 6
                    score = (-(second - opts[0][0]), best)
                else:
                    score = (best, 0)
                if choice is None or score < choice[0]:
                    choice = (score, c, opts[0][1], opts[0][2])
            if choice is None:
                left.extend(pending)
                break
            _, c, ri, pos = choice
            r = routes[ri]
            r.stops.insert(pos, c)
            r.refresh(m)
            pending.remove(c)
            for key in [k for k in cache if k[1] == ri]:
                del cache[key]
        return left

    def _remove(self, routes: List[_Route], victims: List[int]) -> None:
        """Remove victims. Under budgeted uncertainty a removal can break robust feasibility
        (one deviation on the new, longer arc can exceed any single deviation on the two arcs
        it replaces); the rest of such a route is then removed too and appended to victims."""
        vs = set(victims)
        for r in routes:
            if vs.intersection(r.stops):
                rest = [c for c in r.stops if c not in vs]
                if rest and self.model.forward(rest) is None:
                    victims.extend(rest)
                    vs.update(rest)
                    rest = []
                r.stops = rest
                r.refresh(self.model)

    def _destroy(self, routes: List[_Route], rng: random.Random, q: int) -> List[int]:
        m = self.model
        routed = [c for r in routes for c in r.stops]
        if not routed:
            return []
        q = min(q, len(routed))
        op = rng.random()
        if op < 1 / 3:                                   # random
            victims = rng.sample(routed, q)
        elif op < 2 / 3:                                 # worst (distance saving), randomised
            saving = {}
            for r in routes:
                nodes = [0] + r.stops + [0]
                for p in range(1, len(nodes) - 1):
                    a, c, b = nodes[p - 1], nodes[p], nodes[p + 1]
                    saving[c] = m.D[a][c] + m.D[c][b] - m.D[a][b]
            order = sorted(routed, key=lambda c: (-saving[c], c))
            victims = []
            while len(victims) < q:
                idx = int(len(order) * rng.random() ** 3)
                victims.append(order.pop(idx))
        else:                                            # related (Shaw): distance and window
            seed_c = rng.choice(routed)
            victims = [seed_c]
            pool = [c for c in routed if c != seed_c]
            while len(victims) < q and pool:
                ref = rng.choice(victims)
                pool.sort(key=lambda c: (m.D[ref][c] + 0.2 * abs(m.L[ref] - m.L[c]), c))
                idx = int(len(pool) * rng.random() ** 4)
                victims.append(pool.pop(idx))
        self._remove(routes, victims)
        return victims

    # ---- local search -----------------------------------------------------
    def _local_search(self, routes: List[_Route]) -> None:
        m = self.model
        improved = True
        while improved:
            improved = False
            where = {}
            for ri, r in enumerate(routes):
                for p, c in enumerate(r.stops, 1):
                    where[c] = (ri, p)
            for c in range(1, m.n):
                if c not in where:
                    continue
                if self._relocate(routes, where, c) or self._two_opt_star(routes, where, c) \
                        or self._exchange(routes, where, c):
                    improved = True
                    where = {}
                    for ri, r in enumerate(routes):
                        for p, x in enumerate(r.stops, 1):
                            where[x] = (ri, p)

    def _relocate(self, routes, where, c) -> bool:
        m, D = self.model, self.model.D
        ri, p = where[c]
        r = routes[ri]
        i, j = r.node(p - 1), r.node(p + 1)
        gain_remove = D[i][c] + D[c][j] - D[i][j]
        if len(r.stops) > 1 and not m.join(r.A[p - 1], i, j, r.B[p + 1]):
            return False
        targets = set()
        for v in self.near[c]:
            if v in where:
                targets.add(where[v][0])
        targets.update(k for k, rr in enumerate(routes) if not rr.stops)
        best = None
        for rk in targets:
            if rk == ri:
                continue
            cost, pos = self._best_insertion(routes[rk], c)
            if cost is not None and cost - gain_remove < 0 and (best is None or cost < best[0]):
                best = (cost, rk, pos)
        if best is None:
            return False
        _, rk, pos = best
        r.stops.pop(p - 1)
        r.refresh(m)
        routes[rk].stops.insert(pos, c)
        routes[rk].refresh(m)
        return True

    def _two_opt_star(self, routes, where, c) -> bool:
        """Connect c directly to a near neighbour v in another route, swapping tails."""
        m, D = self.model, self.model.D
        r1i, p1 = where[c]
        r1 = routes[r1i]
        for v in self.near[c]:
            if v not in where:
                continue
            r2i, p2 = where[v]
            if r2i == r1i:
                continue
            r2 = routes[r2i]
            # new1 = r1[:p1] + r2[p2-1:], new2 = r2[:p2-1] + r1[p1:]
            a1, b1 = c, r1.node(p1 + 1)
            a2, b2 = r2.node(p2 - 1), v
            delta = D[a1][b2] + D[a2][b1] - D[a1][b1] - D[a2][b2]
            if delta >= 0:
                continue
            load1 = sum(m.dem[x] for x in r1.stops[:p1]) + sum(m.dem[x] for x in r2.stops[p2 - 1:])
            load2 = r1.load + r2.load - load1
            if load1 > m.Q or load2 > m.Q:
                continue
            if not m.join(r1.A[p1], a1, b2, r2.B[p2]):
                continue
            if not m.join(r2.A[p2 - 1], a2, b1, r1.B[p1 + 1]):
                continue
            new1 = r1.stops[:p1] + r2.stops[p2 - 1:]
            new2 = r2.stops[:p2 - 1] + r1.stops[p1:]
            r1.stops, r2.stops = new1, new2
            r1.refresh(m)
            r2.refresh(m)
            return True
        return False

    def _exchange(self, routes, where, c) -> bool:
        """Swap c with a near neighbour's route-mate position: c takes v's place and v takes c's."""
        m, D = self.model, self.model.D
        r1i, p1 = where[c]
        r1 = routes[r1i]
        i1, j1 = r1.node(p1 - 1), r1.node(p1 + 1)
        for v in self.near[c]:
            if v not in where:
                continue
            r2i, p2 = where[v]
            if r2i == r1i:
                continue
            r2 = routes[r2i]
            i2, j2 = r2.node(p2 - 1), r2.node(p2 + 1)
            delta = (D[i1][v] + D[v][j1] + D[i2][c] + D[c][j2]
                     - D[i1][c] - D[c][j1] - D[i2][v] - D[v][j2])
            if delta >= 0:
                continue
            if r1.load - m.dem[c] + m.dem[v] > m.Q or r2.load - m.dem[v] + m.dem[c] > m.Q:
                continue
            if not m.insert_ok(r1.A[p1 - 1], i1, v, j1, r1.B[p1 + 1]):
                continue
            if not m.insert_ok(r2.A[p2 - 1], i2, c, j2, r2.B[p2 + 1]):
                continue
            r1.stops[p1 - 1], r2.stops[p2 - 1] = v, c
            r1.refresh(m)
            r2.refresh(m)
            return True
        return False

    # ---- main loop ------------------------------------------------------------
    def _snapshot(self, routes: List[_Route]) -> List[List[int]]:
        return [list(r.stops) for r in routes]

    def _restore(self, snap: List[List[int]]) -> List[_Route]:
        return [_Route(self.model, list(s)) for s in snap]

    def search(self) -> Optional[List[List[int]]]:
        m = self.model
        rng = random.Random(self.seed)
        routes = [_Route(m, []) for _ in range(m.data.num_vehicles)]
        unrouted = self._repair(routes, list(range(1, m.n)), rng, regret=True, noise=0.0)
        self._local_search(routes)
        unrouted = self._repair(routes, unrouted, rng, regret=True, noise=0.0)
        cur_snap, cur_un = self._snapshot(routes), list(unrouted)
        cur_cost = self._cost(routes, unrouted)
        best_snap, best_un, best_cost = cur_snap, cur_un, cur_cost
        n_cust = m.n - 1
        q_lo, q_hi = max(2, int(0.1 * n_cust)), max(3, min(30, int(0.35 * n_cust)))
        base = max(1.0, cur_cost if not cur_un else sum(r.dist for r in routes))
        t0 = 0.05 * base / math.log(2)                 # 5% worse accepted with p = 0.5 at start
        for it in range(self.iterations):
            temp = t0 * (1.0 - it / self.iterations) + 1e-9
            routes = self._restore(cur_snap)
            unrouted = list(cur_un)
            q = rng.randint(q_lo, q_hi)
            removed = self._destroy(routes, rng, q)
            unrouted = self._repair(routes, unrouted + removed, rng,
                                    regret=rng.random() < 0.5, noise=0.1 if rng.random() < 0.5 else 0.0)
            self._local_search(routes)
            if unrouted:
                unrouted = self._repair(routes, unrouted, rng, regret=True, noise=0.0)
            cost = self._cost(routes, unrouted)
            if cost < cur_cost or rng.random() < math.exp(-(cost - cur_cost) / temp):
                cur_snap, cur_un, cur_cost = self._snapshot(routes), list(unrouted), cost
                if cost < best_cost:
                    best_snap, best_un, best_cost = cur_snap, cur_un, cost
        if best_un:
            return None
        for s in best_snap:                          # independent final check
            if s and not m.feasible(s):
                raise AssertionError("final route not robust feasible")
        return [s for s in best_snap]

    def solve(self) -> Optional[Plan]:
        m, p, d = self.model, self.model.params, self.model.data
        sol = self.search()
        if sol is None:
            return None
        routes, departures, starts, durations = [], [], {}, []
        for stops in sol:
            if not stops:
                continue
            dep = m.latest_departure(stops)
            now, prev = float(dep), 0
            for c in stops:
                start = max(now + m.T[prev][c], float(m.L[c]))
                starts[c] = start
                now, prev = start + p.service_minutes, c
            end = now + m.T[prev][0]
            routes.append([0] + stops + [0])
            departures.append(float(dep))
            durations.append(end - dep)
        for _ in range(d.num_vehicles - len(routes)):
            routes.append([0, 0])
            departures.append(0.0)
        used = [r for r in routes if len(r) > 2]
        distance = float(sum(m.D[i][j] for r in used for i, j in zip(r[:-1], r[1:])))
        tightness = float(sum(max(0.0, p.target_slack - (d.offered_windows[c][1] - starts[c]))
                              for c in range(1, m.n)))
        metrics = {"fuel": distance * p.fuel_cost_per_km, "tightness": tightness,
                   "driver_duration": float(sum(durations)), "fleet": float(len(used)),
                   "distance": distance}
        name = f"robust{'-capped' if self.capped else ''}-{'box' if m.box else 'G' + str(m.G)}-d{m.delta:g}"
        return Plan(routes, departures, starts, metrics, name, 0, int(distance))
