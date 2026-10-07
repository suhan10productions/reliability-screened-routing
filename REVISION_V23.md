# V23: Solomon benchmark results written into the paper

- Solomon run (eight R1 and RC1 instances, unchanged pipeline, time-dependent
  overlay): OR-Tools found a nominal plan for five of eight; screening admitted
  three of those (R112, RC104, RC108; 97.7 to 99.4% against 78.0 to 82.0% for
  conservative speed). R103 and RC106 returned the slack-aware fallback (45.1%
  and 42.1%); RC106 fell 22.9 points below conservative speed. Capping changed
  nothing on any instance.
- R101, R102 and RC105 have no OR-Tools plan. `code/solomon_hgs_check.py` shows
  PyVRP/HGS finds feasible plans for all three within 40 s (and for R103 under
  the conservative-speed matrix), so these are search limits of the generator.
  Results are in `results/solomon_hgs_feasibility.json`.
- `code/analyse_v8.py` now also writes `paper/solomon_results.tex` and asserts
  that every missing OR-Tools plan is shown feasible by HGS.
- Paper: design paragraph for the mapping, results subsection and table,
  abstract sentence (247 words), limitations, conclusion, third-party data note
  and a reference for the instance source.
- No frozen file changed.
