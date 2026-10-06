"""Exploratory diagnostic: are uncertified no-plan outcomes search limits?

For each screening failure whose first no-plan outcome has no reachability
certificate, re-solve exactly that contracted model (same weighted objective,
same scaling ranges, same planning matrix) with a longer OR-Tools budget.
A plan found with more time proves the original outcome was a search limit.
No plan found still proves nothing about infeasibility.
Uses development instances only; never the confirmatory seeds.
"""
import json, sys, time
from pathlib import Path
from relscreen_v6 import ModelParams, RoutingSolver, make_synthetic_instance

VEHICLES = {20: 6, 50: 14, 100: 26, 200: 40}
budgets = [float(b) for b in sys.argv[1].split(",")] if len(sys.argv) > 1 else [30.0]
only = {int(x) for x in sys.argv[2].split(",")} if len(sys.argv) > 2 else None
out_name = sys.argv[3] if len(sys.argv) > 3 else "search_budget_diagnostic.json"
root = Path(__file__).resolve().parents[1]
stage1 = {}
for n in (20, 50, 100, 200):
    for r in json.loads((root / f"results/study_v6_n{n}.json").read_text())["records"]:
        stage1[r["instance_seed"]] = r
out = []
for f in sorted((root / "results/v7").glob("instance_*.json")):
    r = json.loads(f.read_text()); a = r["old_failure_audit"]
    if a["selected"] or not a["uncertified_no_plan_betas"]:
        continue
    n, seed = r["customers"], r["instance_seed"]
    if only is not None and seed not in only:
        continue
    beta = min(a["uncertified_no_plan_betas"])          # the outcome that stopped the search
    rr = stage1[seed]["reference_ranges"]
    data = make_synthetic_instance(n, VEHICLES[n], seed)
    params = ModelParams()
    found, used = None, None
    for b in budgets:
        t0 = time.perf_counter()
        plan = RoutingSolver(data, params, (rr["lower"], rr["upper"])).solve("weighted", b, beta=beta)
        if plan is not None:
            found, used = b, round(time.perf_counter() - t0, 1); break
    out.append({"customers": n, "seed": seed, "beta": beta, "plan_found_with_budget_s": found})
    print(f"n={n:3d} seed={seed} beta={beta:2d}: "
          + (f"PLAN FOUND with {found:.0f}s budget -> search limit" if found else
             f"no plan within {max(budgets):.0f}s (unresolved)"), flush=True)
(root / "results" / out_name).write_text(json.dumps(
    {"budgets_s": budgets, "results": out}, indent=2))
