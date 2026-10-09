# Revision v41: third protocol (robust comparison and fallback rule)

Prespecified (CONFIRMATORY_PROTOCOL_3.md; FROZEN_MANIFEST_3.json; commit
21ffaa8eed4e899778e14014b73533fd4d14d865, tag protocol-3-freeze, Zenodo
10.5281/zenodo.23242687, all public before any run):

- Part B, best-screened fallback on 53 new instances (seeds + 120000), frozen
  OR-Tools and HGS pipelines (`results/confirm3/`), analysis
  `code/confirm_analysis_fallback.py` -> `results/confirm3_fallback_analysis_output.json`:
  F1 +7.3 [2.3, 13.2] confirmed; F2 +4.2 [1.2, 8.0] confirmed; F3 pooled 94.4%
  [90.1, 97.1]; F4 pooled 94.9% [91.0, 97.1]. One instance (127200) had no anchor
  plan, so neither procedure could run (scored 0).
- Part A, robust comparison on the 90 confirmatory instances with up to 100
  customers (`results/confirm/robust_capped`, `results/confirm2/robust_capped`),
  analysis `code/confirm_analysis_robust.py` -> `results/confirm_robust_analysis_output.json`:
  R1 +6.7 [3.0, 11.1], R2 +6.7 [2.2, 12.2], R3 +0.42 vehicles [0.20, 0.67],
  R4 -1.3% distance [-1.7, -0.9]; all confirmed.
- Run record: two-core Linux machine (Intel Xeon 2.1 GHz, Python 3.13.16, pinned
  packages). Part B started 20:40 PKT on 8 October, one minute after the release
  tag; its first stage was interrupted by a machine restart at about 20:55 and
  resumed at 21:50 (the frozen drivers skip completed records). Part B finished
  at 23:52, part A ran 23:52-07:29. Each analysis ran once in confirmatory mode.

Exploratory additions:
- `code/fallback_policy.py` (post hoc fallback comparison, all three studies).
- `code/misspecification_rescreen.py` (stored candidates re-screened under each
  alternative delay model; Appendix C table).
- `code/robust_fleet_matched.py` (robust plans restricted to the comparator's
  fleet; development and part A instances).
- `code/gh_benchmark.py` with `data/gh200` (20 Gehring-Homberger R1/RC1
  instances, HGS pipeline).
- `study_robust.py --reduced-grid` on the 8 development instances with 200
  customers (`results/robust_capped_dev200`).
- `code/weight_bracketing.py` (original and equal weights rerun, fleet and
  duration weights raised; stores every candidate). Equal weights more than
  halved the advantage in both runs (17.5 -> 8.1 here); raising the duration
  weight alone cost 8.9 points, the fleet weight alone 5.6; the run cannot
  separate the two.
- Gehring-Homberger: procedure could run on 18 of 20 instances, admitted 17,
  +15.1 [11.0, 19.1] over conservative speed.
- Robust with 200 customers: screened robust 97.8% with 20.6 vehicles vs HGS
  capped 97.2% with 17.0 (8 instances, descriptive).
- Run logs of protocol 3 are kept in `results/run_logs_protocol3/` (the logs of
  the first stage-1 attempt before the restart were overwritten; `queue.log`
  records both starts).
- `code/analyse_v12.py` writes `paper/fallback_results.tex`,
  `paper/robust_extra.tex`, `paper/gh_results.tex`,
  `paper/weight_bracketing.tex` and `paper/result_macros_v12.tex`.

Manuscript:
- New Section 11 (third protocol design); new Results subsections on the
  Gehring-Homberger check, the robust comparison on the confirmatory instances
  and the fallback rule; the three earlier checks moved to Appendix C with a
  summary in the main text; abstract, introduction, limitations, conclusion,
  reproducibility and availability updated.
- Weights presented as a fixed experimental vector; Appendix A records their
  AHP origin only.
- Introduction leads with the reachability failure shared by all three planners.
- Fig. 2 has 95% intervals for the highlighted configurations.
- Bibliography: protocol-3 freeze and Gehring and Homberger (1999).
- Licence: MIT for code, CC BY 4.0 for records and documents (`LICENSE`, README).

No frozen file changed (all three manifests verified).
