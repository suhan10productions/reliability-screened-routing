# V22: confirmatory results and weight sensitivity written into the paper

- New `code/analyse_v8.py` generates `paper/result_macros_v8.tex`,
  `paper/confirmatory_results.tex`, `paper/weight_results.tex` and
  `paper/confirmatory_appendix.tex` from `results/confirm`,
  `results/weight_sensitivity` and the development records. It computes the
  confirmatory quantities with the frozen analysis function and stops unless
  they equal the saved output of the confirmatory run. Run it with
  `PYTHONPATH=code python code/analyse_v8.py`.
- Manuscript: abstract, introduction (five questions), a design section for the
  confirmatory study and the weight analysis, two results subsections
  (confirmatory study; sensitivity to the objective weights), reproducibility,
  limitations and conclusion rewritten; reference to the Zenodo freeze added.
- Confirmatory outcome: all four prespecified hypotheses confirmed on 53 fresh
  instances (H1 +15.7 [7.5, 23.6]; H2 +11.7 [6.0, 17.9]; H3 46 against 32,
  14 to 0, exact p = 0.00012; H4 +28.3 [19.6, 36.4]).
- Weight sensitivity (exploratory): the advantage over conservative speed holds
  for the original, slack-first and distance-heavy vectors; under equal weights
  it falls to 6.3 [-1.1, 13.7] and 23 instances are admitted against 31.
- Deviations disclosed in the paper: stage 1 ran as four parallel processes
  where the protocol lists a sequential loop; different machine and Python patch
  version from the development runs.
- No frozen file changed (checked byte for byte against the frozen package).
