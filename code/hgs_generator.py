"""PyVRP/HGS candidate generator with the same planning model as RoutingSolver.

The planning model is identical to the OR-Tools generator in relscreen_v6:
a static travel-time matrix ceil(distance / planning speed) in whole minutes,
service time on leaving a customer, hard (possibly contracted) customer
windows, vehicle capacity, a shift window [0, shift_length] at the depot and
the available fleet. Only the search method differs.

Objectives
  "distance"  minimise total distance.
  "weighted"  the paper's scaled weighted objective restricted to the terms
              PyVRP can express: fuel (distance), driver duration (route
              duration including waiting) and fleet use (fixed vehicle cost),
              with the same coefficients RoutingSolver uses. The slack-deficit
              term has no PyVRP equivalent and is omitted from generation; it
              still enters candidate selection through normalized_score.

Search stops after a fixed number of iterations with a fixed seed, so a solve
is deterministic for given inputs and does not depend on machine speed.

Plans are returned in the pipeline's Plan format. Each vehicle departs at the
latest time that keeps every planned service start within its (contracted)
window and the return within the shift, matching the OR-Tools generator, which
maximises departure times; service starts are then the earliest feasible
starts from that departure.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from pyvrp import Model
from pyvrp.stop import MaxIterations

from relscreen_v6 import InstanceData, ModelParams, Plan

DEFAULT_ITERATIONS = 10_000


def travel_matrix(data: InstanceData, speed_kmh: float) -> List[List[int]]:
    speed = speed_kmh / 60.0
    return [[0 if i == j else int(math.ceil(value / speed)) for j, value in enumerate(row)]
            for i, row in enumerate(data.distance)]


def _coefficients(params: ModelParams, ranges) -> Tuple[int, int, int]:
    lower, upper = ranges
    spans = [max(float(hi) - float(lo), 1.0) for lo, hi in zip(lower, upper)]
    w, scale = params.weights, params.objective_scale
    fuel = max(1, round(scale * w[0] * params.fuel_cost_per_km / spans[0]))
    duration = max(1, round(scale * w[2] / spans[2]))
    fleet = max(1, round(scale * w[3] / spans[3]))
    return fuel, duration, fleet


def schedule(route: Sequence[int], data: InstanceData, params: ModelParams,
             times: List[List[int]]) -> Optional[Tuple[float, Dict[int, float], float]]:
    """Latest feasible departure, earliest service starts from it, and return time."""
    stops = [c for c in route if c != data.depot]
    if not stops:
        return None
    latest_next = float(params.shift_length)           # latest arrival back at the depot
    nxt = data.depot
    latest: Dict[int, float] = {}
    for c in reversed(stops):
        lo, hi = data.offered_windows[c]
        latest[c] = min(float(hi), latest_next - params.service_minutes - times[c][nxt])
        if latest[c] < lo:
            latest[c] = float(lo)                         # waiting absorbs earliness
        latest_next, nxt = latest[c], c
    departure = min(float(params.shift_length), latest[stops[0]] - times[data.depot][stops[0]])
    departure = max(0.0, departure)
    now, prev, starts = departure, data.depot, {}
    for c in stops:
        lo, hi = data.offered_windows[c]
        start = max(now + times[prev][c], float(lo))
        if start > hi + 1e-9:
            return None
        starts[c] = start
        now, prev = start + params.service_minutes, c
    end = now + times[prev][data.depot]
    if end > params.shift_length + 1e-9:
        return None
    return departure, starts, end


class HGSSolver:
    def __init__(self, data: InstanceData, params: ModelParams,
                 reference_ranges=None, planning_speed_kmh: Optional[float] = None,
                 iterations: int = DEFAULT_ITERATIONS, seed: int = 1):
        self.data, self.params = data, params
        self.ranges = reference_ranges
        self.speed = params.nominal_speed_kmh if planning_speed_kmh is None else float(planning_speed_kmh)
        self.times = travel_matrix(data, self.speed)
        self.iterations, self.seed = int(iterations), int(seed)

    def solve(self, objective: str, beta: int = 0,
              data: Optional[InstanceData] = None) -> Optional[Plan]:
        """Solve on `data` (default: this instance contracted by beta)."""
        base = self.data if data is None else data
        d = base.contracted(beta) if data is None else data
        p, times = self.params, self.times
        if objective == "distance":
            unit_dist, unit_dur, fixed = 1, 0, 0
        elif objective == "weighted":
            if self.ranges is None:
                raise ValueError("weighted objective requires reference ranges")
            unit_dist, unit_dur, fixed = _coefficients(p, self.ranges)
        else:
            raise ValueError(f"unknown objective: {objective}")
        n = len(d.demands)
        m = Model()
        locs = [m.add_location(x=float(d.coords[i][0]), y=float(d.coords[i][1])) for i in range(n)]
        depot = m.add_depot(location=locs[0], tw_early=0, tw_late=p.shift_length)
        m.add_vehicle_type(d.num_vehicles, capacity=[p.capacity], start_depot=depot, end_depot=depot,
                           fixed_cost=fixed, tw_early=0, tw_late=p.shift_length,
                           shift_duration=p.shift_length, unit_distance_cost=unit_dist,
                           unit_duration_cost=unit_dur)
        for i in range(1, n):
            lo, hi = d.offered_windows[i]
            m.add_client(location=locs[i], delivery=[int(d.demands[i])],
                         service_duration=p.service_minutes, tw_early=int(lo), tw_late=int(hi))
        for i in range(n):
            for j in range(n):
                if i != j:
                    m.add_edge(locs[i], locs[j], distance=int(d.distance[i][j]), duration=times[i][j])
        result = m.solve(stop=MaxIterations(self.iterations), seed=self.seed, display=False)
        if not result.is_feasible():
            return None
        routes, departures, starts, durations = [], [], {}, []
        for route in result.best.routes():
            # PyVRP 0.14: a route is a sequence of scheduled activities; client
            # activity indices are 0-based, pipeline customers are 1-based.
            visits = [int(a.idx) + 1 for a in route if a.is_client()]
            sched = schedule([0] + visits + [0], d, p, times)
            if sched is None:                       # defensive: HGS feasibility uses the same model
                return None
            dep, st, end = sched
            routes.append([0] + visits + [0]); departures.append(dep)
            starts.update(st); durations.append(end - dep)
        for _ in range(d.num_vehicles - len(routes)):
            routes.append([0, 0]); departures.append(0.0)
        used = [r for r in routes if len(r) > 2]
        distance = float(sum(d.distance[i][j] for r in used for i, j in zip(r[:-1], r[1:])))
        tightness = float(sum(max(0.0, p.target_slack - (d.offered_windows[c][1] - starts[c]))
                              for c in range(1, n)))
        metrics = {"fuel": distance * p.fuel_cost_per_km, "tightness": tightness,
                   "driver_duration": float(sum(durations)), "fleet": float(len(used)),
                   "distance": distance}
        return Plan(routes, departures, starts, metrics, f"hgs-{objective}", beta, int(result.cost()))
