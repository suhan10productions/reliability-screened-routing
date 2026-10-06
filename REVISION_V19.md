# V19: responses to the five remaining weaknesses

1. Confirmatory results absent: unchanged by design; the study must run after
   the public freeze. See NEXT_RUNS.md (step 1).
2. Synthetic geometry only: added `code/solomon_benchmark.py` and eight
   100-customer Solomon instances (R101-R103, R112, RC104-RC106, RC108) in
   `data/solomon/`, run through the unchanged pipeline with the paper's
   profile and disturbance model. Mapping verified: HGS finds a 20-route plan
   for mapped R101, matching its best-known vehicle count; OR-Tools finds none
   within 20 s (a generator search limit). Results pending (step 3).
3. AHP weights: the reviewer's option (b) would be inaccurate, because the
   weights generate every candidate plan. Added `code/weight_sensitivity.py`
   (four weight vectors including a rerun of the original weights to measure
   run-to-run variation). Smoke test: the original-weights rerun reproduced the
   archived result on seed 7200 exactly. Results pending (step 2).
4. Unresolved failures: added `code/diagnose_search_budget.py`. Of the 8
   failures that stopped at an uncertified no-plan outcome, 4 were search
   limits (plans found at 30 s or 120 s) and 4 remain unresolved after 120 s.
   Reported in the paper as exploratory, with generated macros; the conclusion's
   n = 20 statement was corrected accordingly.
5. Figure: y-axis now "P − C service probability (percentage points)", exact
   sigma tick labels, faint guide lines at the true sigma values, and a caption
   explaining that offsets are for legibility only. Rendered with the pinned
   matplotlib 3.11.2 (verified to reproduce the original figure pixel for pixel
   before the change).

Unchanged: all tables, existing macros, raw records, and every frozen file.
