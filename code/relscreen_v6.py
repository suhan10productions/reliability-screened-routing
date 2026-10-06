"""Reliability-screened routing research code, version 6.

The optimizer is a nominal VRPTW candidate generator. Plans are evaluated
separately under a FIFO time-dependent speed profile and correlated lognormal
travel-time disturbances. Screening and validation use separate scenario banks.
Breakdown recourse is excluded because the legacy implementation did not match
the stated policy closely enough to support empirical claims.
"""

from __future__ import annotations

import hashlib
import math
import platform
import sys
import time
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from ortools import __version__ as ortools_version
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

Arc = Tuple[int, int]


@dataclass(frozen=True)
class ModelParams:
    nominal_speed_kmh: float = 40.0
    fuel_cost_per_km: float = 15.0
    capacity: int = 1000
    shift_length: int = 600
    shift_start_minute: int = 360
    service_minutes: int = 10
    target_slack: int = 15
    alpha: float = 0.95
    kappa: float = 0.95
    eta: float = 0.05
    sigma: float = 0.20
    rho_log: float = 0.50
    weights: Tuple[float, float, float, float] = (
        0.5693, 0.2643, 0.1055, 0.0609
    )
    objective_scale: int = 100_000


@dataclass(frozen=True)
class SpeedProfile:
    """Positive piecewise-constant speeds; integration preserves FIFO."""

    periods: Tuple[Tuple[int, int], ...] = (
        (0, 420), (420, 540), (540, 1020), (1020, 1140), (1140, 1440)
    )
    congestion_multiplier: Tuple[float, ...] = (0.9, 1.2, 1.0, 1.3, 0.9)
    free_flow_kmh: float = 40.0

    def speeds_km_per_minute(self) -> Tuple[float, ...]:
        return tuple(
            self.free_flow_kmh / (60.0 * multiplier)
            for multiplier in self.congestion_multiplier
        )


@dataclass(frozen=True)
class InstanceData:
    coords: Tuple[Tuple[int, int], ...]
    demands: Tuple[int, ...]
    offered_windows: Tuple[Tuple[int, int], ...]
    distance: Tuple[Tuple[int, ...], ...]
    num_vehicles: int
    depot: int = 0

    @property
    def num_customers(self) -> int:
        return len(self.demands) - 1

    def contracted(self, beta: int) -> "InstanceData":
        windows = [self.offered_windows[0]]
        for lower, upper in self.offered_windows[1:]:
            windows.append((lower, max(lower, upper - beta)))
        return InstanceData(
            self.coords,
            self.demands,
            tuple(windows),
            self.distance,
            self.num_vehicles,
            self.depot,
        )


@dataclass
class Plan:
    routes: List[List[int]]
    departures: List[float]
    service_starts: Dict[int, float]
    metrics: Dict[str, float]
    objective: str
    beta: int = 0
    solver_objective: Optional[int] = None

    def as_dict(self) -> Dict[str, object]:
        return {
            "routes": self.routes,
            "departures": self.departures,
            "service_starts": {str(k): v for k, v in self.service_starts.items()},
            "metrics": self.metrics,
            "objective": self.objective,
            "beta": self.beta,
            "solver_objective": self.solver_objective,
        }


@dataclass
class ReliabilityReport:
    scenarios: int
    fleet_day_success: float
    fleet_day_lcb: float
    service_level_success: float
    service_level_lcb: float
    mean_on_time_fraction: float
    expected_late_customers: float
    mean_total_lateness: float
    p95_total_lateness: float
    mean_route_success: float

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class CandidateRecord:
    beta: int
    feasible: bool
    plan: Optional[Plan] = None
    screening: Optional[ReliabilityReport] = None
    solve_seconds: Optional[float] = None


def td_travel_minutes(
    distance_km: float, departure_minute: float, profile: SpeedProfile
) -> float:
    """Integrate distance through the speed profile."""

    if distance_km <= 0:
        return 0.0
    speeds = profile.speeds_km_per_minute()
    remaining = float(distance_km)
    current = float(departure_minute)
    final_end = profile.periods[-1][1]
    while remaining > 1e-12:
        period_index = len(profile.periods) - 1
        period_end = math.inf
        for index, (start, end) in enumerate(profile.periods):
            if start <= current < end:
                period_index = index
                period_end = end
                break
        if current >= final_end:
            period_end = math.inf
        speed = speeds[period_index]
        available_distance = (period_end - current) * speed
        if remaining <= available_distance:
            current += remaining / speed
            remaining = 0.0
        else:
            remaining -= available_distance
            current = period_end
    return current - departure_minute


def _stable_seed(master_seed: int, *parts: int) -> int:
    payload = ":".join(str(x) for x in (master_seed,) + parts).encode("ascii")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "little", signed=False)


class ScenarioBank:
    """Order-invariant common random numbers for stochastic evaluation."""

    def __init__(self, scenarios: int, seed: int, params: ModelParams):
        if scenarios <= 0:
            raise ValueError("scenarios must be positive")
        if not 0 <= params.rho_log <= 1:
            raise ValueError("rho_log must lie in [0, 1]")
        self.scenarios = scenarios
        self.seed = int(seed)
        self.params = params
        rng = np.random.default_rng(_stable_seed(self.seed, 0))
        self._global = rng.standard_normal(scenarios)
        self._local: Dict[Arc, np.ndarray] = {}

    def local_errors(self, arc: Arc) -> np.ndarray:
        if arc not in self._local:
            rng = np.random.default_rng(_stable_seed(self.seed, 1, arc[0], arc[1]))
            self._local[arc] = rng.standard_normal(self.scenarios)
        return self._local[arc]

    def multiplier(self, scenario: int, arc: Arc) -> float:
        p = self.params
        epsilon = p.sigma * (
            math.sqrt(p.rho_log) * self._global[scenario]
            + math.sqrt(1.0 - p.rho_log) * self.local_errors(arc)[scenario]
        )
        return math.exp(float(epsilon))


def _evaluate_route(
    route: Sequence[int],
    departure: float,
    data: InstanceData,
    params: ModelParams,
    profile: SpeedProfile,
    bank: Optional[ScenarioBank] = None,
    scenario: Optional[int] = None,
) -> Dict[str, object]:
    time_now = float(departure)
    distance_total = waiting_total = total_lateness = 0.0
    late_customers = on_time = 0
    starts: Dict[int, float] = {}
    for origin, destination in zip(route[:-1], route[1:]):
        distance_km = data.distance[origin][destination]
        distance_total += distance_km
        travel = td_travel_minutes(
            distance_km, params.shift_start_minute + time_now, profile
        )
        if bank is not None:
            if scenario is None:
                raise ValueError("scenario index required with a scenario bank")
            travel *= bank.multiplier(scenario, (origin, destination))
        arrival = time_now + travel
        if destination == data.depot:
            time_now = arrival
            continue
        lower, upper = data.offered_windows[destination]
        start = max(arrival, lower)
        waiting_total += max(0.0, lower - arrival)
        starts[destination] = start
        lateness = max(0.0, start - upper)
        total_lateness += lateness
        late_customers += int(lateness > 1e-9)
        on_time += int(lateness <= 1e-9)
        time_now = start + params.service_minutes
    return {
        "distance": distance_total,
        "duration": time_now - departure,
        "waiting": waiting_total,
        "late_customers": late_customers,
        "on_time_customers": on_time,
        "total_lateness": total_lateness,
        "service_starts": starts,
        "return_time": time_now,
    }


def evaluate_reliability(
    plan: Plan,
    original_data: InstanceData,
    params: ModelParams,
    profile: SpeedProfile,
    bank: ScenarioBank,
) -> ReliabilityReport:
    """Evaluate a selected plan against original, never contracted, windows."""

    fleet_successes = 0
    service_level_successes = 0
    on_time_fractions: List[float] = []
    late_counts: List[float] = []
    lateness_totals: List[float] = []
    route_successes: List[float] = []
    used = [
        (route, plan.departures[index])
        for index, route in enumerate(plan.routes)
        if len(route) > 2
    ]
    if not used:
        raise ValueError("plan contains no used routes")
    for scenario in range(bank.scenarios):
        late = 0
        total_lateness = 0.0
        successful_routes = 0
        for route, departure in used:
            result = _evaluate_route(
                route, departure, original_data, params, profile, bank, scenario
            )
            route_late = int(result["late_customers"])
            late += route_late
            total_lateness += float(result["total_lateness"])
            successful_routes += int(route_late == 0)
        fleet_successes += int(late == 0)
        on_time_fraction = 1.0 - late / original_data.num_customers
        service_level_successes += int(on_time_fraction >= params.kappa)
        late_counts.append(float(late))
        on_time_fractions.append(on_time_fraction)
        lateness_totals.append(total_lateness)
        route_successes.append(successful_routes / len(used))
    p_hat = fleet_successes / bank.scenarios
    service_hat = service_level_successes / bank.scenarios
    return ReliabilityReport(
        scenarios=bank.scenarios,
        fleet_day_success=p_hat,
        fleet_day_lcb=wilson_lower_bound(p_hat, bank.scenarios, params.eta),
        service_level_success=service_hat,
        service_level_lcb=wilson_lower_bound(
            service_hat, bank.scenarios, params.eta
        ),
        mean_on_time_fraction=float(np.mean(on_time_fractions)),
        expected_late_customers=float(np.mean(late_counts)),
        mean_total_lateness=float(np.mean(lateness_totals)),
        p95_total_lateness=float(np.percentile(lateness_totals, 95)),
        mean_route_success=float(np.mean(route_successes)),
    )


def wilson_lower_bound(p_hat: float, sample_size: int, eta: float = 0.05) -> float:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    z_values = {0.10: 1.2815516, 0.05: 1.6448536, 0.025: 1.959964, 0.01: 2.326348}
    if eta not in z_values:
        raise ValueError("unsupported eta")
    z = z_values[eta]
    denominator = 1.0 + z * z / sample_size
    center = p_hat + z * z / (2.0 * sample_size)
    spread = z * math.sqrt(
        p_hat * (1.0 - p_hat) / sample_size
        + z * z / (4.0 * sample_size * sample_size)
    )
    return (center - spread) / denominator


class RoutingSolver:
    """Nominal OR-Tools VRPTW candidate generator."""

    def __init__(
        self,
        data: InstanceData,
        params: ModelParams,
        reference_ranges: Optional[Tuple[Sequence[float], Sequence[float]]] = None,
        planning_speed_kmh: Optional[float] = None,
        exact_fleet: Optional[int] = None,
    ):
        self.data = data
        self.params = params
        self.reference_ranges = reference_ranges
        self.planning_speed_kmh = (
            params.nominal_speed_kmh
            if planning_speed_kmh is None
            else float(planning_speed_kmh)
        )
        if self.planning_speed_kmh <= 0:
            raise ValueError("planning speed must be positive")
        if exact_fleet is not None and not 1 <= exact_fleet <= data.num_vehicles:
            raise ValueError("exact fleet must be between one and the available fleet")
        self.exact_fleet = exact_fleet
        speed = self.planning_speed_kmh / 60.0
        self._nominal_time = tuple(
            tuple(0 if i == j else int(math.ceil(value / speed)) for j, value in enumerate(row))
            for i, row in enumerate(data.distance)
        )

    def solve(
        self,
        objective: str,
        time_limit: float,
        beta: int = 0,
        initial_routes: Optional[Sequence[Sequence[int]]] = None,
    ) -> Optional[Plan]:
        data = self.data.contracted(beta)
        vehicle_count = self.exact_fleet or data.num_vehicles
        manager = pywrapcp.RoutingIndexManager(
            len(data.distance), vehicle_count, data.depot
        )
        routing = pywrapcp.RoutingModel(manager)

        def node(index: int) -> int:
            return manager.IndexToNode(index)

        def time_callback(from_index: int, to_index: int) -> int:
            origin, destination = node(from_index), node(to_index)
            service = 0 if origin == data.depot else self.params.service_minutes
            return self._nominal_time[origin][destination] + service

        time_index = routing.RegisterTransitCallback(time_callback)
        routing.AddDimension(
            time_index,
            self.params.shift_length,
            self.params.shift_length,
            False,
            "Time",
        )
        timedim = routing.GetDimensionOrDie("Time")
        for customer in range(1, len(data.demands)):
            lower, upper = data.offered_windows[customer]
            timedim.CumulVar(manager.NodeToIndex(customer)).SetRange(lower, upper)
        for vehicle in range(vehicle_count):
            start, end = routing.Start(vehicle), routing.End(vehicle)
            timedim.CumulVar(start).SetRange(0, self.params.shift_length)
            timedim.CumulVar(end).SetRange(0, self.params.shift_length)
            routing.AddVariableMaximizedByFinalizer(timedim.CumulVar(start))
            routing.AddVariableMinimizedByFinalizer(timedim.CumulVar(end))

        demand_index = routing.RegisterUnaryTransitCallback(
            lambda index: int(data.demands[node(index)])
        )
        routing.AddDimensionWithVehicleCapacity(
            demand_index, 0, [self.params.capacity] * vehicle_count, True, "Capacity"
        )
        distance_index = routing.RegisterTransitCallback(
            lambda a, b: int(data.distance[node(a)][node(b)])
        )

        if self.exact_fleet is not None:
            for vehicle in range(vehicle_count):
                routing.solver().Add(
                    routing.NextVar(routing.Start(vehicle)) != routing.End(vehicle)
                )

        if objective == "distance":
            routing.SetArcCostEvaluatorOfAllVehicles(distance_index)
        elif objective == "duration":
            routing.SetArcCostEvaluatorOfAllVehicles(distance_index)
            timedim.SetSpanCostCoefficientForAllVehicles(100_000)
        elif objective == "tightness":
            routing.SetArcCostEvaluatorOfAllVehicles(distance_index)
            for customer in range(1, len(data.demands)):
                lower, upper = data.offered_windows[customer]
                target = max(lower, upper - self.params.target_slack)
                timedim.SetCumulVarSoftUpperBound(
                    manager.NodeToIndex(customer), target, 100_000
                )
        elif objective == "fleet":
            routing.SetArcCostEvaluatorOfAllVehicles(distance_index)
            routing.SetFixedCostOfAllVehicles(1_000_000_000)
        elif objective == "weighted":
            if self.reference_ranges is None:
                raise ValueError("weighted objective requires reference ranges")
            lower_ref, upper_ref = self.reference_ranges
            spans = [max(float(hi) - float(lo), 1.0) for lo, hi in zip(lower_ref, upper_ref)]
            weights, scale = self.params.weights, self.params.objective_scale
            fuel_coefficient = max(
                1,
                round(scale * weights[0] * self.params.fuel_cost_per_km / spans[0]),
            )
            weighted_distance = routing.RegisterTransitCallback(
                lambda a, b: int(fuel_coefficient * data.distance[node(a)][node(b)])
            )
            routing.SetArcCostEvaluatorOfAllVehicles(weighted_distance)
            timedim.SetSpanCostCoefficientForAllVehicles(
                max(1, round(scale * weights[2] / spans[2]))
            )
            tightness_coefficient = max(1, round(scale * weights[1] / spans[1]))
            for customer in range(1, len(data.demands)):
                lower, upper = data.offered_windows[customer]
                target = max(lower, upper - self.params.target_slack)
                timedim.SetCumulVarSoftUpperBound(
                    manager.NodeToIndex(customer), target, tightness_coefficient
                )
            routing.SetFixedCostOfAllVehicles(
                max(1, round(scale * weights[3] / spans[3]))
            )
        else:
            raise ValueError(f"unknown objective: {objective}")

        search = pywrapcp.DefaultRoutingSearchParameters()
        search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        search.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        milliseconds = max(1, int(round(time_limit * 1000)))
        search.time_limit.seconds = milliseconds // 1000
        search.time_limit.nanos = (milliseconds % 1000) * 1_000_000
        if initial_routes is None:
            solution = routing.SolveWithParameters(search)
        else:
            seed_routes = []
            for route in initial_routes:
                route = list(route)
                if route and route[0] == data.depot:
                    route = route[1:]
                if route and route[-1] == data.depot:
                    route = route[:-1]
                seed_routes.append(route)
            assignment = routing.ReadAssignmentFromRoutes(seed_routes, True)
            if assignment is None:
                return None
            solution = routing.SolveFromAssignmentWithParameters(assignment, search)
        if solution is None:
            return None

        routes: List[List[int]] = []
        departures: List[float] = []
        starts: Dict[int, float] = {}
        durations: List[float] = []
        for vehicle in range(vehicle_count):
            index = routing.Start(vehicle)
            route: List[int] = []
            departure = float(solution.Value(timedim.CumulVar(index)))
            while not routing.IsEnd(index):
                current = node(index)
                route.append(current)
                if current != data.depot:
                    starts[current] = float(solution.Value(timedim.CumulVar(index)))
                index = solution.Value(routing.NextVar(index))
            route.append(data.depot)
            end = float(solution.Value(timedim.CumulVar(index)))
            routes.append(route)
            departures.append(departure)
            if len(route) > 2:
                durations.append(end - departure)

        used = [route for route in routes if len(route) > 2]
        distance = float(
            sum(data.distance[i][j] for route in used for i, j in zip(route[:-1], route[1:]))
        )
        tightness = float(
            sum(
                max(
                    0.0,
                    self.params.target_slack
                    - (data.offered_windows[c][1] - starts[c]),
                )
                for c in range(1, len(data.demands))
            )
        )
        metrics = {
            "fuel": distance * self.params.fuel_cost_per_km,
            "tightness": tightness,
            "driver_duration": float(sum(durations)),
            "fleet": float(len(used)),
            "distance": distance,
        }
        return Plan(
            routes, departures, starts, metrics, objective, beta,
            int(solution.ObjectiveValue())
        )


def empirical_reference_ranges(
    data: InstanceData, params: ModelParams, time_limit: float, max_attempts: int = 3
) -> Tuple[Tuple[List[float], List[float]], Dict[str, Plan]]:
    """Build heuristic scaling ranges; these are not Pareto bounds."""

    anchors: Dict[str, Plan] = {}
    for objective in ("distance", "tightness", "duration", "fleet"):
        plan = None
        for _ in range(max_attempts):
            plan = RoutingSolver(data, params).solve(objective, time_limit)
            if plan is not None:
                break
        if plan is None:
            raise RuntimeError(f"anchor solve failed for {objective}")
        anchors[objective] = plan
    keys = ("fuel", "tightness", "driver_duration", "fleet")
    values = [[plan.metrics[key] for plan in anchors.values()] for key in keys]
    return ([min(row) for row in values], [max(row) for row in values]), anchors


def normalized_score(
    plan: Plan,
    ranges: Tuple[Sequence[float], Sequence[float]],
    params: ModelParams,
) -> float:
    lower, upper = ranges
    keys = ("fuel", "tightness", "driver_duration", "fleet")
    return sum(
        weight * (plan.metrics[key] - float(lo)) / max(float(hi) - float(lo), 1.0)
        for weight, key, lo, hi in zip(params.weights, keys, lower, upper)
    )


def screen_with_internal_buffers(
    original_data: InstanceData,
    params: ModelParams,
    profile: SpeedProfile,
    ranges: Tuple[Sequence[float], Sequence[float]],
    beta_values: Iterable[int],
    screening_bank: ScenarioBank,
    solve_time: float,
    max_attempts: int = 3,
) -> Tuple[Optional[Plan], List[CandidateRecord]]:
    """Generate on contracted windows; score against original promises."""

    records: List[CandidateRecord] = []
    passing: List[Tuple[float, Plan]] = []
    for beta in beta_values:
        started = time.perf_counter()
        plan = None
        for _ in range(max_attempts):
            plan = RoutingSolver(original_data, params, ranges).solve(
                "weighted", solve_time, beta=beta
            )
            if plan is not None:
                break
        elapsed = time.perf_counter() - started
        if plan is None:
            records.append(CandidateRecord(beta, False, solve_seconds=elapsed))
            continue
        report = evaluate_reliability(plan, original_data, params, profile, screening_bank)
        records.append(CandidateRecord(beta, True, plan, report, elapsed))
        if report.service_level_lcb >= params.alpha:
            passing.append((normalized_score(plan, ranges, params), plan))
    if not passing:
        return None, records
    passing.sort(key=lambda item: item[0])
    return passing[0][1], records


def make_synthetic_instance(
    customers: int, vehicles: int, seed: int, shift_length: int = 600
) -> InstanceData:
    rng = np.random.default_rng(seed)
    coords = [(50, 50)] + [
        (int(rng.integers(0, 100)), int(rng.integers(0, 100)))
        for _ in range(customers)
    ]
    demands = [0] + [int(rng.integers(10, 50)) for _ in range(customers)]
    windows = [(0, shift_length)]
    for _ in range(customers):
        width = int(rng.integers(90, 150))
        start = int(rng.integers(0, shift_length - width - 60))
        windows.append((start, start + width))
    distance = [
        [
            int(round(math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])))
            for j in range(customers + 1)
        ]
        for i in range(customers + 1)
    ]
    return InstanceData(
        tuple(coords), tuple(demands), tuple(windows),
        tuple(tuple(row) for row in distance), vehicles
    )


def environment_metadata() -> Dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "ortools": ortools_version,
        "platform": platform.platform(),
        "processor": platform.processor() or "not reported",
    }
