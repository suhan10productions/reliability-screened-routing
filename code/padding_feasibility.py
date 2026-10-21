"""Are the missing padded plans infeasible, or failures of the search? (exploratory)

For every development instance and padding level where the padded planner
returned no plan (code/padding_sweep.py), test whether some customer cannot be
served at all at the padded speed: its earliest service start after a direct trip
from the depot, max(l_i, t_0i), is later than u_i, or serving it and driving
straight back exceeds the shift. Such an instance has no feasible plan at that
padding level, whatever the solver. Instances that fail neither test are
unresolved: the search may have failed, or a combination of customers may be
infeasible.

Usage (from the package root):
  PYTHONPATH=code python code/padding_feasibility.py
"""
from __future__ import annotations

import glob
import json
import math
from pathlib import Path

from relscreen_v6 import ModelParams, make_synthetic_instance

ROOT = Path(__file__).resolve().parents[1]
LEVELS = (0, 10, 20, 30, 40, 50)


def main():
    params = ModelParams()
    stage1 = {}
    for f in glob.glob(str(ROOT / "results" / "study_v6_n*.json")):
        for r in json.loads(Path(f).read_text())["records"]:
            stage1[r["instance_seed"]] = r
    seeds = sorted(s for s in stage1 if stage1[s]["reference_ranges"])
    out = {"instances": len(seeds), "levels": {}}
    for lv in LEVELS:
        speed = params.nominal_speed_kmh / (1 + lv / 100) / 60.0
        missing = proven = 0
        for s in seeds:
            p = json.loads((ROOT / "results" / "padding_sweep" / f"pad{lv:02d}_{s}.json").read_text())
            if p["has_plan"]:
                continue
            missing += 1
            d = make_synthetic_instance(stage1[s]["customers"], stage1[s]["vehicles_available"], s)
            for i in range(1, len(d.demands)):
                l, u = d.offered_windows[i]
                start = max(l, math.ceil(d.distance[0][i] / speed))
                if start > u or start + params.service_minutes + math.ceil(d.distance[i][0] / speed) > params.shift_length:
                    proven += 1
                    break
        out["levels"][lv] = {"missing": missing, "proven_infeasible": proven}
    out["missing_total"] = sum(v["missing"] for v in out["levels"].values())
    out["proven_total"] = sum(v["proven_infeasible"] for v in out["levels"].values())
    (ROOT / "results" / "padding_feasibility.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
