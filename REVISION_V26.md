# V26: HGS generator and proposed confirmatory protocol 2

- `code/hgs_generator.py`: PyVRP/HGS candidate generator for the same planning
  model as the OR-Tools generator (static matrix, service on departure, hard
  and contracted windows, capacity, shift, fleet; latest feasible departures).
  Weighted objective: distance, driver duration and fleet terms with the same
  coefficients; the slack-deficit term cannot be expressed in PyVRP and is
  omitted from generation but kept in selection. Fixed 10,000 iterations and
  seed: deterministic for given inputs. Verified at n = 20 (seed 7202) to
  reproduce the OR-Tools distance and conservative plans exactly.
- `code/study_hgs.py`: per-instance HGS nominal, conservative, uncapped and
  capped screened families, each with slack-type and conservative fallbacks;
  same banks, Wilson rule, certificates and selection score as study 1.
- Development run (`results/hgs_dev`, 53 instances, exploratory; cloud
  machine, Python 3.13.16): HGS capped with conservative fallback exceeds HGS
  conservative by 27.0 points [23.0, 30.8] and pools at 94.2%; the OR-Tools
  conservative fallback adds 2.2 [0.4, 4.4] to the capped procedure. The
  HGS beta-0 plan is a weak fallback (it lacks the slack term).
- `CONFIRMATORY_PROTOCOL_2.md` (proposed): G1 generator robustness (primary),
  G2 fallback rule (primary), G3 uncapped fallback (secondary), G4 HGS versus
  OR-Tools (estimate). Seeds + 70000.
- `code/confirm_analysis_hgs.py`, `code/freeze_manifest_hgs.py`,
  `code/check_hgs_safeguards.py` (complete fixture passes; 16 tampering cases
  rejected), `tests/test_hgs_generator.py` (3 tests; 18 in total).
- No study-1 frozen file changed; study-1 safeguards still pass.
