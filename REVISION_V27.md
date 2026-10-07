# V27: study 2 moved to fresh seeds; freeze guard

- The OR-Tools half of study 2 was run on the seeds of the earlier draft
  (+70000) before protocol 2 was frozen, and its console output (admission
  flags) was seen. Those seeds are abandoned: records kept in
  `results/abandoned_70000/`, never analysed, disclosed in the protocol.
  Study 2 now uses seeds +80000 (87200-89007), with no other change.
- `code/check_freeze_2.py`: refuses to let study 2 start unless
  FROZEN_MANIFEST_2.json matches every listed file, the protocol and manifest
  are committed in HEAD, HEAD is pushed, a `protocol-2*` tag on origin points at
  HEAD, and no results/confirm2 folder exists. Tested in a simulated repository:
  fails when unfrozen, unpushed, untagged, with a run folder present, or after a
  frozen file is edited; passes after a correct freeze.
- Run sheet rewritten: guard is mandatory before any solve; inline `#`
  comments removed from commands (zsh passed them to `wc` as filenames).
