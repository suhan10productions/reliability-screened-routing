# Revision v37: answers to anticipated reviewer remarks

Text (manuscript):
- Introduction: two explicit contributions (the procedure; matched and
  prespecified evidence), a paragraph on scope (one central question, no new
  routing algorithm, robust comparator illustrative), the reasons for keeping
  generation and validation apart, and screening and relief "survived a change
  of generator" (HGS in the second confirmatory study, robust model exploratory).
- Objective section: the weights shape and rank candidates but are not used by
  the admission test or validation; any scalar objective can replace Z, and the
  results still depend on the objective.
- Screening section: the per-candidate bound is not simultaneous over the grid;
  the 95% target is the admission standard for each plan and applies to
  admitted plans only.
- Hypothesis design: "confirmed" means meeting the protocol's decision
  criterion; H2 and H3 both measure the effect of capping.
- Abstract and conclusion: "met their (protocol-defined) decision criteria";
  admitted plans averaged 97.3-98.0% on fresh scenarios; for fixed plans the
  advantage over padding persisted under four other delay models; OR-Tools is
  named as the generator; the 8.3-21.4 range is across sizes (abstract 249
  words).
- Reproducibility: the new checks, and reproducibility is not validity.
- Limitations third and sixth updated with the new checks.
- `code/analyse_v8.py`: "All four hypotheses were confirmed" replaced by "met
  their protocol-defined decision criteria".

New exploratory analyses (Sections 11.12-11.14, Tables 16-18):
- `code/analyse_family_wise.py` -> `results/family_wise_summary.json`: Bonferroni
  bound over the 13 buffer levels; admitted instances 318 -> 306 (at most 2 per
  study and procedure); admitted plans missing the validation bound 11 -> 1;
  pooled service changed by -1.8 to +0.2 points.
- `code/time_components.py` -> `results/timing_components.json`: screening one
  candidate takes 3-24 ms; one HGS solve 2.2-9.3 s (medians, 20-200 customers).
  Selected-buffer counts come from the stored records.
- `code/misspecification.py` -> `results/misspecification.json`: stored plans on
  5000 new scenarios under heavy tails, incidents, time-of-day noise and a
  stronger morning peak. The advantage over conservative speed held under every
  model (lower limits 11.5 original, 21.9 capped, 23.3 HGS capped). Screened
  robust stayed ahead of HGS capped, but its interval includes zero under
  time-of-day noise and the stronger peak.
- `code/analyse_v11.py` writes `paper/checks_results.tex` and
  `paper/result_macros_v11.tex` from the three JSON files and the records.
- `tests/test_misspecification.py`: the alternative-model evaluator reproduces
  the stored validation under the paper's model for OR-Tools, HGS and robust
  plans of every size.

Display rounding fix:
- The frozen analyses round to two decimals before the paper rounds to one,
  which could round the wrong way (an exact 27.952 was saved as 27.95 and
  printed as 27.9). `code/exact_display.py` reruns the same frozen functions
  with only the display rounding switched off and checks the result against the
  saved output; `analyse_v8.py` and `analyse_v9.py` use it. Three displayed
  values change: G1 mean 27.9 -> 28.0 (abstract and text), pooled HGS capped in
  study 2 91.5 -> 91.6, and the lower limit for H2 6.0 -> 5.9. No decision
  changes.

No frozen file changed (both manifests verified). An independent review of the
new text against the JSON files was run, and its corrections are included.
