"""Feasibility check for mapped Solomon instances with PyVRP/HGS.

For each requested case, build the mapped instance (see solomon_benchmark.py),
use the stated planning speed for travel times, and ask PyVRP/HGS for a feasible
plan within a short budget. A plan proves the mapped instance is feasible, so a
missing OR-Tools plan on it is a search limit of that generator. Failure to find
a plan within the budget proves nothing.

Usage: PYTHONPATH=code python code/solomon_hgs_check.py [seconds]
"""
import json, math, sys, time
from pathlib import Path
from pyvrp import Model
from pyvrp.stop import MaxRuntime
import solomon_benchmark as sb

CASES = [("R101", 40.0, "nominal"), ("R102", 40.0, "nominal"),
         ("RC105", 40.0, "nominal"), ("R103", 33.3, "conservative-speed")]
seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
out = {}
for name, speed, label in CASES:
    data, ov = sb.load(name)
    n = len(data.demands); m = Model()
    locs = [m.add_location(x=float(data.coords[i][0]), y=float(data.coords[i][1])) for i in range(n)]
    dep = m.add_depot(location=locs[0], tw_early=0, tw_late=ov["shift_length"])
    m.add_vehicle_type(data.num_vehicles, capacity=[ov["capacity"]], start_depot=dep, end_depot=dep,
                       shift_duration=ov["shift_length"], tw_early=0, tw_late=ov["shift_length"])
    for i in range(1, n):
        m.add_client(location=locs[i], delivery=[data.demands[i]], service_duration=ov["service_minutes"],
                     tw_early=data.offered_windows[i][0], tw_late=data.offered_windows[i][1])
    for i in range(n):
        for j in range(n):
            if i != j:
                m.add_edge(locs[i], locs[j], distance=data.distance[i][j],
                           duration=math.ceil(data.distance[i][j] / (speed / 60)))
    t0 = time.perf_counter()
    r = m.solve(stop=MaxRuntime(seconds), seed=1, display=False)
    out[name] = {"matrix": label, "planning_speed_kmh": speed, "budget_s": seconds,
                 "feasible": bool(r.is_feasible()), "routes": r.best.num_routes() if r.is_feasible() else None}
    print(name, label, out[name], flush=True)
Path(__file__).resolve().parents[1].joinpath("results", "solomon_hgs_feasibility.json").write_text(json.dumps(out, indent=2))
