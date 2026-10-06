# V12: corrections on top of v11

V11's two pre-freeze fixes, regression test and documentation corrections are
retained unchanged. The manuscript source and archived experimental evidence
are unchanged.

- **Figure restored.** `paper/matched_sensitivity_v7.pdf` had been re-rendered
  in v10 by a local matplotlib 3.10.8 run, replacing the original rendered with
  the pinned 3.11.2; v11 inherited it. The original file is restored and the
  manuscript PDF rebuilt with it. The underlying data were never affected.
- **Stage-2 size check.** Each stage-2 record's customer size must equal its
  stage-1 record's size. Previously a disagreeing size was accepted. It could
  not change any reported number, because the analysis takes sizes from the
  prescribed design, but the archive should not contain inconsistent records.
  The safeguard checker gains a seventeenth rejection case for it.
- **Help text.** The `--seed-shift` help no longer says that shift 0
  reproduces the archived study. As v11's README already states, wall-clock
  solver limits can produce different routes; exact tables come from the
  archived records.
- **Protocol wording.** The safeguard list now states the global seed-set,
  allocation and stage-2 size checks precisely.

## Verification

- 15 implementation and regression tests passed; integrity check passed.
- Both valid safeguard fixtures passed; all 17 rejection cases were rejected
  with explicit protocol violations.
- Tables regenerated from the archived records in a scratch copy are
  byte-identical to the packaged tables; raw records are byte-identical to the
  original v7 archive.
- No confirmatory instances were generated or solved.

Note for anyone rerunning `code/analyse_v7.py`: it re-renders the figure with
the installed matplotlib. Use the pinned version in `requirements.txt`, or the
figure will differ in rendering from the archived one.
