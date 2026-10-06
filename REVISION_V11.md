# V11: final pre-freeze corrections

The manuscript and archived experimental evidence are unchanged.

- Original-procedure status now records `not_attempted` when anchor failure
  prevents candidate generation, matching the capped procedure and protocol.
- Confirmatory validation requires the exact global seed set, supported sizes,
  and the prescribed allocation of seeds to sizes.
- A regression test exercises stage-two dependency handling while preserving
  a successful nominal configuration. It uses stubs, not fresh instances.
- Three additional rejection fixtures cover extra seeds and invalid size
  allocations, extending the safeguard checker to 16 rejection cases.
- README corrects the outdated safeguard count and distinguishes rerunning
  the development design from reproducing exact tables from archived records.

## Before the fresh study

Confirm the author declarations and correspondence details in the manuscript.
Then run `code/freeze_manifest.py` and publicly timestamp the complete package,
protocol and manifest together. The protocol remains proposed until that step.
No confirmatory instances were generated or solved for this revision.

## Verification completed

- 15 implementation and regression tests passed.
- Both valid safeguard fixtures passed; all 16 rejection cases were rejected
  with explicit protocol violations.
- Manuscript files and archived results are byte-identical to v10.

Internal manuscript filenames are retained to preserve existing commands.
