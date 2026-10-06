# V15: project renamed from "routeops" to "relscreen"

- Modules renamed: `routeops_v5/v6/v7.py` -> `relscreen_v5/v6/v7.py`; tests
  renamed accordingly; all imports, the freeze-manifest file list, docstrings
  and document titles updated.
- Unchanged by design: the `"schema"` format tags (e.g.
  `"routeops-v7-instance-1"`) in the 70 archived result files and in the code
  that writes them, so archived records stay byte-identical and new runs stay
  format-compatible. The README's naming note explains this.
- The manuscripts never used the name and are unchanged.
- Verified after renaming: every module imports; 15 tests pass; integrity check
  passes; regenerated tables and summaries are byte-identical to the archive;
  safeguard checker passes both valid fixtures and rejects all 17 cases; a full
  two-stage run on a development seed completes with no software errors.
- Renaming does not settle the competing-interests question: if a related
  commercial product exists, disclosure is what addresses it.
