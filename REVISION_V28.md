# Revision v28: second confirmatory study written into the manuscript

- `code/analyse_v9.py` (new) writes `paper/result_macros_v9.tex`,
  `paper/study2_results.tex` and `paper/study2_appendix.tex` from
  `results/confirm2` and `results/hgs_dev`. It reruns the frozen protocol-2
  validation and analysis and stops unless the result equals
  `results/confirm2/analysis_output.txt`.
- `code/analyse_v8.py`: study-1 headings renamed "First confirmatory study";
  the post hoc fallback paragraph points to the prospective test.
- Manuscript: abstract (249 words, reports the unconfirmed G2 as the protocol
  requires), sixth research question, new Section 9 "Second confirmatory study
  design" (freeze commit 3ba6b71, Zenodo 10.5281/zenodo.23208320, abandoned
  +70000 seeds disclosed), Section 10.10 and Tables 13 and 15, reproducibility,
  limitations (first and seventh), conclusion, data availability.
- Bibliography: `vidal2022`, `ali2026freeze2`; a stray brace removed.
- No file listed in `FROZEN_MANIFEST.json` or `FROZEN_MANIFEST_2.json` changed.

Regenerate: `cd code && python analyse_v8.py && python analyse_v9.py`.
