# Revision v36: robust optimization comparator (exploratory)

- New: `code/robust_generator.py` (budgeted-uncertainty robust VRPTW, exact
  robust feasibility, ALNS; box uncertainty; reachability-relief variant),
  `code/study_robust.py`, `code/analyse_robust.py`, `code/analyse_v10.py`,
  `tests/test_robust_generator.py`.
- New records: `results/robust_dev` (45 instances, 16 settings each) and
  `results/robust_capped_dev` (45 instances, 15 settings each); summary in
  `results/robust_summary.json`. No software errors.
- Solver quality at Gamma = 0 against PyVRP/HGS on the development instances:
  equal distance on all 20 instances with 20 customers; 0.04% and 0.9% longer on
  average at 50 and 100 customers.
- Manuscript: new Section 10 (robust comparator design), Section 11.11 with
  Tables 14-15 and Fig. 2, appendix Table 18; abstract, introduction, related
  work, limitations (second), reproducibility and conclusion reframed. New
  reference: Bertsimas and Sim (2004).
- No frozen file changed. The archive DOI in the paper (v2.0) does not yet
  contain the robust code and records: publish release v3.0 and update
  `ali2026archive`.
